"""
API Routes pour la gestion Docker Swarm
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from wakedock.core.auth_middleware import require_authenticated_user
from wakedock.core.dependencies import get_swarm_service
from wakedock.core.swarm_service import SwarmService
from wakedock.database.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/swarm", tags=["swarm"])


# Modèles Pydantic pour les requêtes et réponses
class SwarmInitRequest(BaseModel):
    """Modèle pour l'initialisation d'un cluster Swarm"""
    advertise_addr: Optional[str] = Field(None, description="Adresse d'annonce pour les autres nœuds")
    listen_addr: Optional[str] = Field(None, description="Adresse d'écoute du manager")
    force_new_cluster: bool = Field(False, description="Forcer la création d'un nouveau cluster")


class SwarmJoinRequest(BaseModel):
    """Modèle pour rejoindre un cluster Swarm"""
    manager_addr: str = Field(..., description="Adresse du manager à rejoindre")
    join_token: str = Field(..., description="Token de jonction")
    advertise_addr: Optional[str] = Field(None, description="Adresse d'annonce pour ce nœud")
    listen_addr: Optional[str] = Field(None, description="Adresse d'écoute pour ce nœud")


class SwarmLeaveRequest(BaseModel):
    """Modèle pour quitter un cluster Swarm"""
    force: bool = Field(False, description="Forcer la sortie même si c'est un manager")


class ServiceCreateRequest(BaseModel):
    """Modèle pour créer un service Swarm"""
    name: str = Field(..., description="Nom du service")
    image: str = Field(..., description="Image Docker à déployer")
    replicas: int = Field(1, ge=0, description="Nombre de répliques")
    mode: str = Field("replicated", regex="^(replicated|global)$", description="Mode de service")
    ports: Optional[List[Dict[str, Any]]] = Field(None, description="Configuration des ports")
    networks: Optional[List[str]] = Field(None, description="Réseaux à attacher")
    env: Optional[Dict[str, str]] = Field(None, description="Variables d'environnement")
    constraints: Optional[List[str]] = Field(None, description="Contraintes de placement")
    labels: Optional[Dict[str, str]] = Field(None, description="Labels du service")
    resources: Optional[Dict[str, Any]] = Field(None, description="Limites de ressources")
    restart_policy: Optional[Dict[str, Any]] = Field(None, description="Politique de redémarrage")
    update_config: Optional[Dict[str, Any]] = Field(None, description="Configuration des mises à jour")
    health_check: Optional[Dict[str, Any]] = Field(None, description="Configuration du health check")


class ServiceUpdateRequest(BaseModel):
    """Modèle pour mettre à jour un service Swarm"""
    image: Optional[str] = Field(None, description="Nouvelle image")
    env: Optional[Dict[str, str]] = Field(None, description="Nouvelles variables d'environnement")
    resources: Optional[Dict[str, Any]] = Field(None, description="Nouvelles limites de ressources")
    update_config: Optional[Dict[str, Any]] = Field(None, description="Nouvelle configuration de mise à jour")


class ServiceScaleRequest(BaseModel):
    """Modèle pour scaler un service Swarm"""
    replicas: int = Field(..., ge=0, description="Nouveau nombre de répliques")


class SwarmClusterResponse(BaseModel):
    """Modèle de réponse pour les informations de cluster"""
    cluster_id: str
    nodes_count: int
    managers_count: int
    workers_count: int
    services_count: int
    networks_count: int
    is_healthy: bool
    version: str
    created_at: datetime


class SwarmNodeResponse(BaseModel):
    """Modèle de réponse pour les informations de nœud"""
    node_id: str
    hostname: str
    role: str
    status: str
    availability: str
    leader: bool
    cpu_cores: int
    memory_bytes: int
    labels: Dict[str, str]
    engine_version: str


class SwarmServiceResponse(BaseModel):
    """Modèle de réponse pour les informations de service"""
    service_id: str
    name: str
    image: str
    mode: str
    replicas_desired: int
    replicas_running: int
    replicas_ready: int
    ports: List[Dict[str, Any]]
    networks: List[str]
    constraints: List[str]
    labels: Dict[str, str]
    created_at: datetime
    updated_at: datetime


# Routes pour la gestion des clusters
@router.post("/cluster/init", response_model=SwarmClusterResponse)
async def initialize_swarm_cluster(
    request: SwarmInitRequest,
    swarm_service: SwarmService = Depends(get_swarm_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Initialise un nouveau cluster Docker Swarm
    
    Permissions requises: swarm:cluster:create
    """
    try:
        cluster_info = await swarm_service.initialize_swarm(
            user_id=current_user.id,
            advertise_addr=request.advertise_addr,
            listen_addr=request.listen_addr,
            force_new_cluster=request.force_new_cluster
        )
        
        return SwarmClusterResponse(
            cluster_id=cluster_info.cluster_id,
            nodes_count=cluster_info.nodes_count,
            managers_count=cluster_info.managers_count,
            workers_count=cluster_info.workers_count,
            services_count=cluster_info.services_count,
            networks_count=cluster_info.networks_count,
            is_healthy=cluster_info.is_healthy,
            version=cluster_info.version,
            created_at=cluster_info.created_at
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation du cluster: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.post("/cluster/join", response_model=SwarmNodeResponse)
async def join_swarm_cluster(
    request: SwarmJoinRequest,
    swarm_service: SwarmService = Depends(get_swarm_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Rejoint un cluster Docker Swarm existant
    
    Permissions requises: swarm:node:create
    """
    try:
        node_info = await swarm_service.join_swarm(
            user_id=current_user.id,
            manager_addr=request.manager_addr,
            join_token=request.join_token,
            advertise_addr=request.advertise_addr,
            listen_addr=request.listen_addr
        )
        
        return SwarmNodeResponse(
            node_id=node_info.node_id,
            hostname=node_info.hostname,
            role=node_info.role.value,
            status=node_info.status,
            availability=node_info.availability,
            leader=node_info.leader,
            cpu_cores=node_info.cpu_cores,
            memory_bytes=node_info.memory_bytes,
            labels=node_info.labels,
            engine_version=node_info.engine_version
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur lors de la jonction au cluster: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.post("/cluster/leave")
async def leave_swarm_cluster(
    request: SwarmLeaveRequest,
    swarm_service: SwarmService = Depends(get_swarm_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Quitte le cluster Docker Swarm
    
    Permissions requises: swarm:node:leave
    """
    try:
        success = await swarm_service.leave_swarm(
            user_id=current_user.id,
            force=request.force
        )
        
        return {"success": success, "message": "Nœud retiré du cluster avec succès"}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur lors de la sortie du cluster: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.get("/cluster/info", response_model=SwarmClusterResponse)
async def get_cluster_info(
    swarm_service: SwarmService = Depends(get_swarm_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Obtient les informations du cluster Swarm
    
    Permissions requises: swarm:cluster:read
    """
    try:
        # Obtenir l'ID du cluster depuis Docker
        import docker
        client = docker.from_env()
        swarm_info = client.swarm.attrs
        cluster_id = swarm_info["ID"]
        
        cluster_info = await swarm_service.get_cluster_info(cluster_id)
        
        return SwarmClusterResponse(
            cluster_id=cluster_info.cluster_id,
            nodes_count=cluster_info.nodes_count,
            managers_count=cluster_info.managers_count,
            workers_count=cluster_info.workers_count,
            services_count=cluster_info.services_count,
            networks_count=cluster_info.networks_count,
            is_healthy=cluster_info.is_healthy,
            version=cluster_info.version,
            created_at=cluster_info.created_at
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des infos cluster: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des informations du cluster"
        )


# Routes pour la gestion des services
@router.post("/services", response_model=SwarmServiceResponse)
async def create_swarm_service(
    request: ServiceCreateRequest,
    swarm_service: SwarmService = Depends(get_swarm_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Crée un nouveau service sur le cluster Swarm
    
    Permissions requises: swarm:service:create
    """
    try:
        from wakedock.core.swarm_service import ServiceMode
        
        mode = ServiceMode.REPLICATED if request.mode == "replicated" else ServiceMode.GLOBAL
        
        service_info = await swarm_service.deploy_service(
            user_id=current_user.id,
            name=request.name,
            image=request.image,
            replicas=request.replicas,
            mode=mode,
            ports=request.ports,
            networks=request.networks,
            env=request.env,
            constraints=request.constraints,
            labels=request.labels,
            resources=request.resources,
            restart_policy=request.restart_policy,
            update_config=request.update_config,
            health_check=request.health_check
        )
        
        return SwarmServiceResponse(
            service_id=service_info.service_id,
            name=service_info.name,
            image=service_info.image,
            mode=service_info.mode.value,
            replicas_desired=service_info.replicas_desired,
            replicas_running=service_info.replicas_running,
            replicas_ready=service_info.replicas_ready,
            ports=service_info.ports,
            networks=service_info.networks,
            constraints=service_info.constraints,
            labels=service_info.labels,
            created_at=service_info.created_at,
            updated_at=service_info.updated_at
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur lors de la création du service: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.get("/services", response_model=List[SwarmServiceResponse])
async def list_swarm_services(
    swarm_service: SwarmService = Depends(get_swarm_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Liste tous les services du cluster Swarm
    
    Permissions requises: swarm:service:read
    """
    try:
        services = await swarm_service.list_services(current_user.id)
        
        return [
            SwarmServiceResponse(
                service_id=service.service_id,
                name=service.name,
                image=service.image,
                mode=service.mode.value,
                replicas_desired=service.replicas_desired,
                replicas_running=service.replicas_running,
                replicas_ready=service.replicas_ready,
                ports=service.ports,
                networks=service.networks,
                constraints=service.constraints,
                labels=service.labels,
                created_at=service.created_at,
                updated_at=service.updated_at
            )
            for service in services
        ]
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur lors de la liste des services: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.get("/services/{service_id}", response_model=SwarmServiceResponse)
async def get_swarm_service(
    service_id: str,
    swarm_service: SwarmService = Depends(get_swarm_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Obtient les informations d'un service spécifique
    
    Permissions requises: swarm:service:read
    """
    try:
        service_info = await swarm_service.get_service_info(service_id)
        
        return SwarmServiceResponse(
            service_id=service_info.service_id,
            name=service_info.name,
            image=service_info.image,
            mode=service_info.mode.value,
            replicas_desired=service_info.replicas_desired,
            replicas_running=service_info.replicas_running,
            replicas_ready=service_info.replicas_ready,
            ports=service_info.ports,
            networks=service_info.networks,
            constraints=service_info.constraints,
            labels=service_info.labels,
            created_at=service_info.created_at,
            updated_at=service_info.updated_at
        )
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service {service_id} non trouvé"
        )
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du service: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.put("/services/{service_id}/scale", response_model=SwarmServiceResponse)
async def scale_swarm_service(
    service_id: str,
    request: ServiceScaleRequest,
    swarm_service: SwarmService = Depends(get_swarm_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Scale un service Swarm
    
    Permissions requises: swarm:service:scale
    """
    try:
        service_info = await swarm_service.scale_service(
            user_id=current_user.id,
            service_id=service_id,
            replicas=request.replicas
        )
        
        return SwarmServiceResponse(
            service_id=service_info.service_id,
            name=service_info.name,
            image=service_info.image,
            mode=service_info.mode.value,
            replicas_desired=service_info.replicas_desired,
            replicas_running=service_info.replicas_running,
            replicas_ready=service_info.replicas_ready,
            ports=service_info.ports,
            networks=service_info.networks,
            constraints=service_info.constraints,
            labels=service_info.labels,
            created_at=service_info.created_at,
            updated_at=service_info.updated_at
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur lors du scaling du service: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.put("/services/{service_id}", response_model=SwarmServiceResponse)
async def update_swarm_service(
    service_id: str,
    request: ServiceUpdateRequest,
    swarm_service: SwarmService = Depends(get_swarm_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Met à jour un service Swarm
    
    Permissions requises: swarm:service:update
    """
    try:
        service_info = await swarm_service.update_service(
            user_id=current_user.id,
            service_id=service_id,
            image=request.image,
            env=request.env,
            resources=request.resources,
            update_config=request.update_config
        )
        
        return SwarmServiceResponse(
            service_id=service_info.service_id,
            name=service_info.name,
            image=service_info.image,
            mode=service_info.mode.value,
            replicas_desired=service_info.replicas_desired,
            replicas_running=service_info.replicas_running,
            replicas_ready=service_info.replicas_ready,
            ports=service_info.ports,
            networks=service_info.networks,
            constraints=service_info.constraints,
            labels=service_info.labels,
            created_at=service_info.created_at,
            updated_at=service_info.updated_at
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du service: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.delete("/services/{service_id}")
async def delete_swarm_service(
    service_id: str,
    swarm_service: SwarmService = Depends(get_swarm_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Supprime un service Swarm
    
    Permissions requises: swarm:service:delete
    """
    try:
        success = await swarm_service.remove_service(
            user_id=current_user.id,
            service_id=service_id
        )
        
        return {"success": success, "message": "Service supprimé avec succès"}
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du service: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


# Routes pour le monitoring et les métriques
@router.get("/cluster/health")
async def get_cluster_health(
    swarm_service: SwarmService = Depends(get_swarm_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Obtient l'état de santé du cluster Swarm
    
    Permissions requises: swarm:cluster:read
    """
    try:
        import docker
        client = docker.from_env()
        
        # Vérifier si Swarm est actif
        info = client.info()
        swarm_info = info.get("Swarm", {})
        
        if swarm_info.get("LocalNodeState") != "active":
            return {
                "status": "inactive",
                "message": "Docker Swarm n'est pas initialisé",
                "cluster_id": None,
                "nodes": [],
                "services": []
            }
        
        # Obtenir les informations du cluster
        cluster_id = swarm_info["Cluster"]["ID"]
        cluster_info = await swarm_service.get_cluster_info(cluster_id)
        
        # Obtenir les nœuds
        nodes = client.nodes.list()
        nodes_status = []
        for node in nodes:
            attrs = node.attrs
            nodes_status.append({
                "node_id": node.id,
                "hostname": attrs["Description"]["Hostname"],
                "role": attrs["Spec"]["Role"],
                "status": attrs["Status"]["State"],
                "availability": attrs["Spec"]["Availability"],
                "leader": attrs.get("ManagerStatus", {}).get("Leader", False)
            })
        
        # Obtenir les services
        services = client.services.list()
        services_status = []
        for service in services:
            attrs = service.attrs
            services_status.append({
                "service_id": service.id,
                "name": attrs["Spec"]["Name"],
                "image": attrs["Spec"]["TaskTemplate"]["ContainerSpec"]["Image"],
                "replicas": attrs["Spec"].get("Mode", {}).get("Replicated", {}).get("Replicas", 0)
            })
        
        return {
            "status": "healthy" if cluster_info.is_healthy else "unhealthy",
            "cluster_id": cluster_id,
            "nodes_count": cluster_info.nodes_count,
            "services_count": cluster_info.services_count,
            "managers_count": cluster_info.managers_count,
            "workers_count": cluster_info.workers_count,
            "nodes": nodes_status,
            "services": services_status
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la santé du cluster: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération de l'état de santé"
        )
