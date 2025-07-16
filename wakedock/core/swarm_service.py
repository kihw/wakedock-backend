"""
Service de gestion Docker Swarm pour WakeDock
Implémente l'orchestration de clusters et la gestion de services distribués
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum

import docker
from docker.models.services import Service
from docker.models.nodes import Node
from docker.models.networks import Network
from docker.errors import APIError, NotFound
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.orm import selectinload

from wakedock.models.swarm import (
    SwarmCluster, SwarmNode, SwarmService, SwarmNetwork,
    SwarmServiceReplica, SwarmLoadBalancer, SwarmSecret,
    SwarmConfig, SwarmStack, ServiceHealthCheck
)
from wakedock.core.security_audit_service import SecurityAuditService
from wakedock.core.rbac_service import RBACService
from wakedock.models.audit import AuditAction


logger = logging.getLogger(__name__)


class SwarmMode(str, Enum):
    """Modes du cluster Swarm"""
    MANAGER = "manager"
    WORKER = "worker"
    INACTIVE = "inactive"


class ServiceMode(str, Enum):
    """Modes de service Swarm"""
    REPLICATED = "replicated"
    GLOBAL = "global"


class UpdatePolicy(str, Enum):
    """Politiques de mise à jour des services"""
    ROLLING = "rolling"
    PARALLEL = "parallel"
    STOP_FIRST = "stop_first"


@dataclass
class SwarmClusterInfo:
    """Informations sur le cluster Swarm"""
    cluster_id: str
    nodes_count: int
    managers_count: int
    workers_count: int
    services_count: int
    networks_count: int
    is_healthy: bool
    version: str
    created_at: datetime


@dataclass
class SwarmNodeInfo:
    """Informations sur un nœud Swarm"""
    node_id: str
    hostname: str
    role: SwarmMode
    status: str
    availability: str
    leader: bool
    cpu_cores: int
    memory_bytes: int
    labels: Dict[str, str]
    engine_version: str


@dataclass
class SwarmServiceInfo:
    """Informations sur un service Swarm"""
    service_id: str
    name: str
    image: str
    mode: ServiceMode
    replicas_desired: int
    replicas_running: int
    replicas_ready: int
    ports: List[Dict[str, Any]]
    networks: List[str]
    constraints: List[str]
    labels: Dict[str, str]
    created_at: datetime
    updated_at: datetime


class SwarmService:
    """
    Service de gestion Docker Swarm
    
    Fonctionnalités:
    - Initialisation et gestion de clusters Swarm
    - Déploiement et scaling de services distribués
    - Configuration du load balancing
    - Monitoring de la santé du cluster
    - Gestion des secrets et configs
    - Haute disponibilité
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        security_service: SecurityAuditService,
        rbac_service: RBACService,
        docker_host: str = "unix://var/run/docker.sock"
    ):
        self.db = db_session
        self.security_service = security_service
        self.rbac_service = rbac_service
        self.docker_client = docker.DockerClient(base_url=docker_host)
        self.is_running = False
        
        # Configuration par défaut
        self.default_update_config = {
            "parallelism": 1,
            "delay": 10,
            "failure_action": "pause",
            "monitor": 60,
            "max_failure_ratio": 0.1
        }
        
        self.default_restart_policy = {
            "condition": "on-failure",
            "delay": 5,
            "max_attempts": 3,
            "window": 120
        }
    
    async def start(self) -> None:
        """Démarre le service Swarm"""
        try:
            logger.info("Démarrage du service Swarm...")
            self.is_running = True
            
            # Vérifier si Docker Swarm est initialisé
            await self._check_swarm_status()
            
            # Démarrer le monitoring des clusters
            asyncio.create_task(self._monitor_clusters())
            
            logger.info("Service Swarm démarré avec succès")
            
        except Exception as e:
            logger.error(f"Erreur lors du démarrage du service Swarm: {e}")
            raise
    
    async def stop(self) -> None:
        """Arrête le service Swarm"""
        logger.info("Arrêt du service Swarm...")
        self.is_running = False
        
        try:
            self.docker_client.close()
            logger.info("Service Swarm arrêté")
        except Exception as e:
            logger.error(f"Erreur lors de l'arrêt: {e}")
    
    async def initialize_swarm(
        self,
        user_id: int,
        advertise_addr: Optional[str] = None,
        listen_addr: Optional[str] = None,
        force_new_cluster: bool = False
    ) -> SwarmClusterInfo:
        """
        Initialise un nouveau cluster Swarm
        
        Args:
            user_id: ID de l'utilisateur
            advertise_addr: Adresse d'annonce pour les autres nœuds
            listen_addr: Adresse d'écoute du manager
            force_new_cluster: Forcer la création d'un nouveau cluster
            
        Returns:
            Informations sur le cluster créé
        """
        # Vérifier les permissions
        await self.rbac_service.check_permission(
            user_id, "swarm:cluster:create"
        )
        
        try:
            # Initialiser Swarm
            if force_new_cluster:
                try:
                    self.docker_client.swarm.leave(force=True)
                except:
                    pass
            
            swarm_attrs = {}
            if advertise_addr:
                swarm_attrs["advertise_addr"] = advertise_addr
            if listen_addr:
                swarm_attrs["listen_addr"] = listen_addr
            
            swarm = self.docker_client.swarm.init(**swarm_attrs)
            
            # Créer l'enregistrement en base
            cluster = SwarmCluster(
                cluster_id=swarm.id,
                name=f"swarm-{swarm.id[:8]}",
                status="active",
                manager_token=swarm.attrs.get("JoinTokens", {}).get("Manager", ""),
                worker_token=swarm.attrs.get("JoinTokens", {}).get("Worker", ""),
                advertise_addr=advertise_addr,
                listen_addr=listen_addr,
                created_by=user_id
            )
            
            self.db.add(cluster)
            await self.db.commit()
            
            # Enregistrer les nœuds
            await self._sync_cluster_nodes(cluster.id)
            
            # Audit
            await self.security_service.log_security_event(
                user_id=user_id,
                action=AuditAction.SWARM_CLUSTER_CREATED,
                resource_type="swarm_cluster",
                resource_id=cluster.cluster_id,
                details={
                    "cluster_name": cluster.name,
                    "advertise_addr": advertise_addr,
                    "listen_addr": listen_addr
                }
            )
            
            return await self._get_cluster_info(cluster.cluster_id)
            
        except APIError as e:
            logger.error(f"Erreur Docker lors de l'initialisation Swarm: {e}")
            raise ValueError(f"Impossible d'initialiser le cluster Swarm: {e}")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation Swarm: {e}")
            raise
    
    async def join_swarm(
        self,
        user_id: int,
        manager_addr: str,
        join_token: str,
        advertise_addr: Optional[str] = None,
        listen_addr: Optional[str] = None
    ) -> SwarmNodeInfo:
        """
        Rejoint un cluster Swarm existant
        
        Args:
            user_id: ID de l'utilisateur
            manager_addr: Adresse du manager à rejoindre
            join_token: Token de jonction
            advertise_addr: Adresse d'annonce pour ce nœud
            listen_addr: Adresse d'écoute pour ce nœud
            
        Returns:
            Informations sur le nœud créé
        """
        # Vérifier les permissions
        await self.rbac_service.check_permission(
            user_id, "swarm:node:create"
        )
        
        try:
            # Rejoindre le Swarm
            join_attrs = {
                "remote_addrs": [manager_addr],
                "join_token": join_token
            }
            if advertise_addr:
                join_attrs["advertise_addr"] = advertise_addr
            if listen_addr:
                join_attrs["listen_addr"] = listen_addr
            
            self.docker_client.swarm.join(**join_attrs)
            
            # Obtenir les informations du nœud local
            node_info = self.docker_client.info()
            node_id = node_info.get("Swarm", {}).get("NodeID")
            
            if not node_id:
                raise ValueError("Impossible d'obtenir l'ID du nœud")
            
            # Audit
            await self.security_service.log_security_event(
                user_id=user_id,
                action=AuditAction.SWARM_NODE_JOINED,
                resource_type="swarm_node",
                resource_id=node_id,
                details={
                    "manager_addr": manager_addr,
                    "advertise_addr": advertise_addr,
                    "listen_addr": listen_addr
                }
            )
            
            return await self._get_node_info(node_id)
            
        except APIError as e:
            logger.error(f"Erreur Docker lors de la jonction Swarm: {e}")
            raise ValueError(f"Impossible de rejoindre le cluster Swarm: {e}")
        except Exception as e:
            logger.error(f"Erreur lors de la jonction Swarm: {e}")
            raise
    
    async def leave_swarm(
        self,
        user_id: int,
        force: bool = False
    ) -> bool:
        """
        Quitte le cluster Swarm
        
        Args:
            user_id: ID de l'utilisateur
            force: Forcer la sortie même si c'est un manager
            
        Returns:
            True si la sortie a réussi
        """
        # Vérifier les permissions
        await self.rbac_service.check_permission(
            user_id, "swarm:node:leave"
        )
        
        try:
            # Obtenir l'ID du nœud avant de quitter
            node_info = self.docker_client.info()
            node_id = node_info.get("Swarm", {}).get("NodeID")
            
            # Quitter le Swarm
            self.docker_client.swarm.leave(force=force)
            
            # Audit
            await self.security_service.log_security_event(
                user_id=user_id,
                action=AuditAction.SWARM_NODE_LEFT,
                resource_type="swarm_node",
                resource_id=node_id or "unknown",
                details={"force": force}
            )
            
            return True
            
        except APIError as e:
            logger.error(f"Erreur Docker lors de la sortie Swarm: {e}")
            raise ValueError(f"Impossible de quitter le cluster Swarm: {e}")
        except Exception as e:
            logger.error(f"Erreur lors de la sortie Swarm: {e}")
            raise
    
    async def deploy_service(
        self,
        user_id: int,
        name: str,
        image: str,
        replicas: int = 1,
        mode: ServiceMode = ServiceMode.REPLICATED,
        ports: Optional[List[Dict[str, Any]]] = None,
        networks: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        constraints: Optional[List[str]] = None,
        labels: Optional[Dict[str, str]] = None,
        resources: Optional[Dict[str, Any]] = None,
        restart_policy: Optional[Dict[str, Any]] = None,
        update_config: Optional[Dict[str, Any]] = None,
        health_check: Optional[Dict[str, Any]] = None
    ) -> SwarmServiceInfo:
        """
        Déploie un service sur le cluster Swarm
        
        Args:
            user_id: ID de l'utilisateur
            name: Nom du service
            image: Image Docker à déployer
            replicas: Nombre de répliques (pour mode replicated)
            mode: Mode de service (replicated/global)
            ports: Configuration des ports
            networks: Réseaux à attacher
            env: Variables d'environnement
            constraints: Contraintes de placement
            labels: Labels du service
            resources: Limites de ressources
            restart_policy: Politique de redémarrage
            update_config: Configuration des mises à jour
            health_check: Configuration du health check
            
        Returns:
            Informations sur le service déployé
        """
        # Vérifier les permissions
        await self.rbac_service.check_permission(
            user_id, "swarm:service:create"
        )
        
        try:
            # Préparer la configuration du service
            service_spec = {
                "name": name,
                "task_template": {
                    "container_spec": {
                        "image": image,
                        "env": [f"{k}={v}" for k, v in (env or {}).items()]
                    },
                    "restart_policy": restart_policy or self.default_restart_policy,
                    "placement": {
                        "constraints": constraints or []
                    }
                },
                "labels": labels or {},
                "update_config": update_config or self.default_update_config
            }
            
            # Configuration du mode de service
            if mode == ServiceMode.REPLICATED:
                service_spec["mode"] = {"replicated": {"replicas": replicas}}
            else:
                service_spec["mode"] = {"global": {}}
            
            # Configuration des ressources
            if resources:
                service_spec["task_template"]["resources"] = resources
            
            # Configuration des ports
            if ports:
                service_spec["endpoint_spec"] = {"ports": ports}
            
            # Configuration des réseaux
            if networks:
                service_spec["task_template"]["networks"] = [
                    {"target": net} for net in networks
                ]
            
            # Configuration du health check
            if health_check:
                service_spec["task_template"]["container_spec"]["healthcheck"] = health_check
            
            # Créer le service
            service = self.docker_client.services.create(**service_spec)
            
            # Enregistrer en base
            db_service = SwarmService(
                service_id=service.id,
                name=name,
                image=image,
                mode=mode.value,
                replicas_desired=replicas if mode == ServiceMode.REPLICATED else 0,
                ports=ports or [],
                networks=networks or [],
                constraints=constraints or [],
                labels=labels or {},
                env_vars=env or {},
                resources=resources or {},
                restart_policy=restart_policy or self.default_restart_policy,
                update_config=update_config or self.default_update_config,
                health_check=health_check,
                created_by=user_id
            )
            
            self.db.add(db_service)
            await self.db.commit()
            
            # Créer le health check si configuré
            if health_check:
                health_check_obj = ServiceHealthCheck(
                    service_id=service.id,
                    check_type="http" if health_check.get("test", [""])[0] == "CMD-SHELL" else "tcp",
                    endpoint=health_check.get("test", [""])[1] if len(health_check.get("test", [])) > 1 else "",
                    interval_seconds=health_check.get("interval", 30) // 1000000000,  # Conversion nanoseconds
                    timeout_seconds=health_check.get("timeout", 10) // 1000000000,
                    retries=health_check.get("retries", 3),
                    start_period_seconds=health_check.get("start_period", 60) // 1000000000
                )
                
                self.db.add(health_check_obj)
                await self.db.commit()
            
            # Audit
            await self.security_service.log_security_event(
                user_id=user_id,
                action=AuditAction.SWARM_SERVICE_CREATED,
                resource_type="swarm_service",
                resource_id=service.id,
                details={
                    "service_name": name,
                    "image": image,
                    "mode": mode.value,
                    "replicas": replicas,
                    "networks": networks,
                    "ports": ports
                }
            )
            
            return await self._get_service_info(service.id)
            
        except APIError as e:
            logger.error(f"Erreur Docker lors du déploiement du service: {e}")
            raise ValueError(f"Impossible de déployer le service: {e}")
        except Exception as e:
            logger.error(f"Erreur lors du déploiement du service: {e}")
            raise
    
    async def scale_service(
        self,
        user_id: int,
        service_id: str,
        replicas: int
    ) -> SwarmServiceInfo:
        """
        Scale un service Swarm
        
        Args:
            user_id: ID de l'utilisateur
            service_id: ID du service
            replicas: Nouveau nombre de répliques
            
        Returns:
            Informations mises à jour du service
        """
        # Vérifier les permissions
        await self.rbac_service.check_permission(
            user_id, "swarm:service:scale"
        )
        
        try:
            # Obtenir le service
            service = self.docker_client.services.get(service_id)
            
            # Mettre à jour les répliques
            service_spec = service.attrs["Spec"]
            if "Replicated" in service_spec["Mode"]:
                service_spec["Mode"]["Replicated"]["Replicas"] = replicas
                service.update(**service_spec)
                
                # Mettre à jour en base
                stmt = select(SwarmService).where(SwarmService.service_id == service_id)
                result = await self.db.execute(stmt)
                db_service = result.scalar_one_or_none()
                
                if db_service:
                    db_service.replicas_desired = replicas
                    await self.db.commit()
                
                # Audit
                await self.security_service.log_security_event(
                    user_id=user_id,
                    action=AuditAction.SWARM_SERVICE_SCALED,
                    resource_type="swarm_service",
                    resource_id=service_id,
                    details={
                        "service_name": service.name,
                        "new_replicas": replicas
                    }
                )
                
                return await self._get_service_info(service_id)
            else:
                raise ValueError("Impossible de scaler un service en mode global")
                
        except NotFound:
            raise ValueError(f"Service {service_id} non trouvé")
        except APIError as e:
            logger.error(f"Erreur Docker lors du scaling: {e}")
            raise ValueError(f"Impossible de scaler le service: {e}")
        except Exception as e:
            logger.error(f"Erreur lors du scaling: {e}")
            raise
    
    async def update_service(
        self,
        user_id: int,
        service_id: str,
        image: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        resources: Optional[Dict[str, Any]] = None,
        update_config: Optional[Dict[str, Any]] = None
    ) -> SwarmServiceInfo:
        """
        Met à jour un service Swarm
        
        Args:
            user_id: ID de l'utilisateur
            service_id: ID du service
            image: Nouvelle image (optionnel)
            env: Nouvelles variables d'environnement (optionnel)
            resources: Nouvelles limites de ressources (optionnel)
            update_config: Nouvelle configuration de mise à jour (optionnel)
            
        Returns:
            Informations mises à jour du service
        """
        # Vérifier les permissions
        await self.rbac_service.check_permission(
            user_id, "swarm:service:update"
        )
        
        try:
            # Obtenir le service
            service = self.docker_client.services.get(service_id)
            service_spec = service.attrs["Spec"]
            
            # Mettre à jour l'image
            if image:
                service_spec["TaskTemplate"]["ContainerSpec"]["Image"] = image
            
            # Mettre à jour les variables d'environnement
            if env:
                service_spec["TaskTemplate"]["ContainerSpec"]["Env"] = [
                    f"{k}={v}" for k, v in env.items()
                ]
            
            # Mettre à jour les ressources
            if resources:
                service_spec["TaskTemplate"]["Resources"] = resources
            
            # Mettre à jour la configuration de mise à jour
            if update_config:
                service_spec["UpdateConfig"] = update_config
            
            # Appliquer les mises à jour
            service.update(**service_spec)
            
            # Mettre à jour en base
            stmt = select(SwarmService).where(SwarmService.service_id == service_id)
            result = await self.db.execute(stmt)
            db_service = result.scalar_one_or_none()
            
            if db_service:
                if image:
                    db_service.image = image
                if env:
                    db_service.env_vars = env
                if resources:
                    db_service.resources = resources
                if update_config:
                    db_service.update_config = update_config
                
                await self.db.commit()
            
            # Audit
            await self.security_service.log_security_event(
                user_id=user_id,
                action=AuditAction.SWARM_SERVICE_UPDATED,
                resource_type="swarm_service",
                resource_id=service_id,
                details={
                    "service_name": service.name,
                    "updated_image": image,
                    "updated_env": bool(env),
                    "updated_resources": bool(resources)
                }
            )
            
            return await self._get_service_info(service_id)
            
        except NotFound:
            raise ValueError(f"Service {service_id} non trouvé")
        except APIError as e:
            logger.error(f"Erreur Docker lors de la mise à jour: {e}")
            raise ValueError(f"Impossible de mettre à jour le service: {e}")
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour: {e}")
            raise
    
    async def remove_service(
        self,
        user_id: int,
        service_id: str
    ) -> bool:
        """
        Supprime un service Swarm
        
        Args:
            user_id: ID de l'utilisateur
            service_id: ID du service
            
        Returns:
            True si la suppression a réussi
        """
        # Vérifier les permissions
        await self.rbac_service.check_permission(
            user_id, "swarm:service:delete"
        )
        
        try:
            # Obtenir le service pour l'audit
            service = self.docker_client.services.get(service_id)
            service_name = service.name
            
            # Supprimer le service
            service.remove()
            
            # Supprimer de la base
            stmt = select(SwarmService).where(SwarmService.service_id == service_id)
            result = await self.db.execute(stmt)
            db_service = result.scalar_one_or_none()
            
            if db_service:
                await self.db.delete(db_service)
                await self.db.commit()
            
            # Audit
            await self.security_service.log_security_event(
                user_id=user_id,
                action=AuditAction.SWARM_SERVICE_DELETED,
                resource_type="swarm_service",
                resource_id=service_id,
                details={"service_name": service_name}
            )
            
            return True
            
        except NotFound:
            raise ValueError(f"Service {service_id} non trouvé")
        except APIError as e:
            logger.error(f"Erreur Docker lors de la suppression: {e}")
            raise ValueError(f"Impossible de supprimer le service: {e}")
        except Exception as e:
            logger.error(f"Erreur lors de la suppression: {e}")
            raise
    
    async def get_cluster_info(self, cluster_id: str) -> SwarmClusterInfo:
        """Obtient les informations d'un cluster"""
        return await self._get_cluster_info(cluster_id)
    
    async def get_service_info(self, service_id: str) -> SwarmServiceInfo:
        """Obtient les informations d'un service"""
        return await self._get_service_info(service_id)
    
    async def get_node_info(self, node_id: str) -> SwarmNodeInfo:
        """Obtient les informations d'un nœud"""
        return await self._get_node_info(node_id)
    
    async def list_services(
        self,
        user_id: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SwarmServiceInfo]:
        """
        Liste les services du cluster
        
        Args:
            user_id: ID de l'utilisateur
            filters: Filtres à appliquer
            
        Returns:
            Liste des services
        """
        # Vérifier les permissions
        await self.rbac_service.check_permission(
            user_id, "swarm:service:read"
        )
        
        try:
            services = self.docker_client.services.list(filters=filters)
            service_infos = []
            
            for service in services:
                info = await self._get_service_info(service.id)
                service_infos.append(info)
            
            return service_infos
            
        except APIError as e:
            logger.error(f"Erreur lors de la liste des services: {e}")
            raise ValueError(f"Impossible de lister les services: {e}")
    
    async def _check_swarm_status(self) -> bool:
        """Vérifie le statut du Swarm"""
        try:
            swarm_info = self.docker_client.info().get("Swarm", {})
            return swarm_info.get("LocalNodeState") == "active"
        except Exception:
            return False
    
    async def _get_cluster_info(self, cluster_id: str) -> SwarmClusterInfo:
        """Obtient les informations détaillées d'un cluster"""
        try:
            swarm = self.docker_client.swarm.attrs
            nodes = self.docker_client.nodes.list()
            services = self.docker_client.services.list()
            networks = self.docker_client.networks.list(filters={"scope": "swarm"})
            
            managers_count = len([n for n in nodes if n.attrs["Spec"]["Role"] == "manager"])
            workers_count = len(nodes) - managers_count
            
            # Vérifier la santé du cluster
            is_healthy = all(
                node.attrs["Status"]["State"] == "ready" and
                node.attrs["Spec"]["Availability"] == "active"
                for node in nodes
            )
            
            return SwarmClusterInfo(
                cluster_id=swarm["ID"],
                nodes_count=len(nodes),
                managers_count=managers_count,
                workers_count=workers_count,
                services_count=len(services),
                networks_count=len(networks),
                is_healthy=is_healthy,
                version=swarm["Version"]["Index"],
                created_at=datetime.fromisoformat(swarm["CreatedAt"].replace("Z", "+00:00"))
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des infos cluster: {e}")
            raise
    
    async def _get_node_info(self, node_id: str) -> SwarmNodeInfo:
        """Obtient les informations détaillées d'un nœud"""
        try:
            node = self.docker_client.nodes.get(node_id)
            attrs = node.attrs
            
            return SwarmNodeInfo(
                node_id=node.id,
                hostname=attrs["Description"]["Hostname"],
                role=SwarmMode.MANAGER if attrs["Spec"]["Role"] == "manager" else SwarmMode.WORKER,
                status=attrs["Status"]["State"],
                availability=attrs["Spec"]["Availability"],
                leader=attrs.get("ManagerStatus", {}).get("Leader", False),
                cpu_cores=attrs["Description"]["Resources"]["NanoCPUs"] // 1000000000,
                memory_bytes=attrs["Description"]["Resources"]["MemoryBytes"],
                labels=attrs["Spec"].get("Labels", {}),
                engine_version=attrs["Description"]["Engine"]["EngineVersion"]
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des infos nœud: {e}")
            raise
    
    async def _get_service_info(self, service_id: str) -> SwarmServiceInfo:
        """Obtient les informations détaillées d'un service"""
        try:
            service = self.docker_client.services.get(service_id)
            attrs = service.attrs
            
            # Obtenir les informations sur les répliques
            tasks = self.docker_client.api.tasks(filters={"service": service_id})
            running_tasks = [t for t in tasks if t["Status"]["State"] == "running"]
            ready_tasks = [t for t in running_tasks if t.get("Status", {}).get("State") == "running"]
            
            # Déterminer le mode de service
            mode_info = attrs["Spec"]["Mode"]
            if "Replicated" in mode_info:
                mode = ServiceMode.REPLICATED
                replicas_desired = mode_info["Replicated"]["Replicas"]
            else:
                mode = ServiceMode.GLOBAL
                replicas_desired = len(self.docker_client.nodes.list())
            
            # Obtenir les ports
            endpoint_spec = attrs["Spec"].get("EndpointSpec", {})
            ports = endpoint_spec.get("Ports", [])
            
            # Obtenir les réseaux
            networks = []
            for network in attrs["Spec"]["TaskTemplate"].get("Networks", []):
                networks.append(network["Target"])
            
            # Obtenir les contraintes
            placement = attrs["Spec"]["TaskTemplate"].get("Placement", {})
            constraints = placement.get("Constraints", [])
            
            return SwarmServiceInfo(
                service_id=service.id,
                name=attrs["Spec"]["Name"],
                image=attrs["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"],
                mode=mode,
                replicas_desired=replicas_desired,
                replicas_running=len(running_tasks),
                replicas_ready=len(ready_tasks),
                ports=ports,
                networks=networks,
                constraints=constraints,
                labels=attrs["Spec"].get("Labels", {}),
                created_at=datetime.fromisoformat(attrs["CreatedAt"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(attrs["UpdatedAt"].replace("Z", "+00:00"))
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des infos service: {e}")
            raise
    
    async def _sync_cluster_nodes(self, cluster_id: str) -> None:
        """Synchronise les nœuds du cluster avec la base de données"""
        try:
            nodes = self.docker_client.nodes.list()
            
            for node in nodes:
                attrs = node.attrs
                
                # Vérifier si le nœud existe déjà
                stmt = select(SwarmNode).where(SwarmNode.node_id == node.id)
                result = await self.db.execute(stmt)
                db_node = result.scalar_one_or_none()
                
                if not db_node:
                    db_node = SwarmNode(
                        node_id=node.id,
                        cluster_id=cluster_id,
                        hostname=attrs["Description"]["Hostname"],
                        role=attrs["Spec"]["Role"],
                        status=attrs["Status"]["State"],
                        availability=attrs["Spec"]["Availability"],
                        is_leader=attrs.get("ManagerStatus", {}).get("Leader", False),
                        cpu_cores=attrs["Description"]["Resources"]["NanoCPUs"] // 1000000000,
                        memory_bytes=attrs["Description"]["Resources"]["MemoryBytes"],
                        labels=attrs["Spec"].get("Labels", {}),
                        engine_version=attrs["Description"]["Engine"]["EngineVersion"]
                    )
                    self.db.add(db_node)
                else:
                    # Mettre à jour les informations
                    db_node.status = attrs["Status"]["State"]
                    db_node.availability = attrs["Spec"]["Availability"]
                    db_node.is_leader = attrs.get("ManagerStatus", {}).get("Leader", False)
                    db_node.labels = attrs["Spec"].get("Labels", {})
            
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Erreur lors de la sync des nœuds: {e}")
    
    async def _monitor_clusters(self) -> None:
        """Monitore en continu la santé des clusters"""
        while self.is_running:
            try:
                if await self._check_swarm_status():
                    # Sync des nœuds
                    swarm_info = self.docker_client.swarm.attrs
                    cluster_id = swarm_info["ID"]
                    await self._sync_cluster_nodes(cluster_id)
                    
                    # Monitoring des services
                    await self._monitor_services()
                
                # Attendre avant la prochaine vérification
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Erreur lors du monitoring: {e}")
                await asyncio.sleep(60)
    
    async def _monitor_services(self) -> None:
        """Monitore la santé des services"""
        try:
            services = self.docker_client.services.list()
            
            for service in services:
                # Obtenir les tâches du service
                tasks = self.docker_client.api.tasks(filters={"service": service.id})
                
                # Compter les répliques dans différents états
                running_count = len([t for t in tasks if t["Status"]["State"] == "running"])
                failed_count = len([t for t in tasks if t["Status"]["State"] == "failed"])
                
                # Mettre à jour les métriques en base
                stmt = select(SwarmService).where(SwarmService.service_id == service.id)
                result = await self.db.execute(stmt)
                db_service = result.scalar_one_or_none()
                
                if db_service:
                    db_service.replicas_running = running_count
                    db_service.status = "healthy" if failed_count == 0 else "unhealthy"
                    db_service.last_health_check = datetime.utcnow()
            
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Erreur lors du monitoring des services: {e}")


# Factory function pour les dépendances FastAPI
def get_swarm_service() -> SwarmService:
    """Factory function pour créer le service Swarm"""
    # Cette fonction sera utilisée dans dependencies.py
    pass
