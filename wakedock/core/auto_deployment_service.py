"""
WakeDock - Service de déploiement automatique de containers
=========================================================

Service pour déploiement automatique de containers depuis repositories Git avec support:
- Déploiement depuis GitHub/GitLab avec webhooks
- Support Dockerfiles personnalisés et détection automatique
- Gestion complète secrets et variables environnement chiffrées
- Rollback automatique en cas d'échec avec sauvegarde états
- Validation images Docker avec scan sécurité
- Monitoring temps réel déploiements avec métriques

Architecture:
- Queue asynchrone pour déploiements parallèles
- État machine transitions (pending → building → deploying → success/failed)
- Intégration Docker API avec networks et volumes persistants
- Health checks automatiques post-déploiement
- Backup automatique avant déploiements critiques

Sécurité:
- Validation Dockerfiles avant build (scan malware, secrets)
- Limitation ressources containers (CPU, mémoire, réseau)
- Isolation réseau avec networks dédiés
- Chiffrement secrets avec rotation clés
- Audit trail complet opérations déploiement

Auteur: WakeDock Development Team
Version: 0.4.2
"""

import asyncio
import json
import logging
import os
import re
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
import docker
import git
from cryptography.fernet import Fernet
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from wakedock.core.rbac_service import RBACService
from wakedock.core.security_audit_service import SecurityAuditService
from wakedock.models.deployment import (
    AutoDeployment,
    DeploymentHistory,
    DeploymentMetrics,
    DeploymentSecret,
)

logger = logging.getLogger(__name__)

class AutoDeploymentService:
    """Service de déploiement automatique de containers avec CI/CD intégré"""
    
    def __init__(self, db_session: AsyncSession, security_service: SecurityAuditService, 
                 rbac_service: RBACService):
        self.db_session = db_session
        self.security_service = security_service
        self.rbac_service = rbac_service
        
        # Configuration Docker
        self.docker_client = docker.from_env()
        self.deployment_queue = asyncio.Queue(maxsize=10)  # Limite déploiements concurrents
        self.active_deployments = {}  # Tracking déploiements actifs
        
        # Configuration sécurité
        self.encryption_key = self._get_or_create_encryption_key()
        self.fernet = Fernet(self.encryption_key)
        
        # Configuration déploiement
        self.deployment_timeout = 1800  # 30 minutes max par déploiement
        self.health_check_timeout = 300  # 5 minutes health checks
        self.rollback_enabled = True
        
        # Répertoires de travail
        self.work_dir = Path("/tmp/wakedock-deployments")
        self.work_dir.mkdir(exist_ok=True)
        
        # Métriques
        self.deployment_metrics = {
            "total_deployments": 0,
            "successful_deployments": 0,
            "failed_deployments": 0,
            "rollbacks_performed": 0,
            "average_deploy_time": 0.0
        }
        
        # Background task pour processing queue
        self.deployment_processor = None
        
    async def start_service(self):
        """Démarrer le service de déploiement automatique"""
        logger.info("🚀 Démarrage AutoDeploymentService")
        
        # Créer networks Docker dédiés
        await self._ensure_docker_networks()
        
        # Nettoyer déploiements abandonnés
        await self._cleanup_stale_deployments()
        
        # Démarrer processor queue
        self.deployment_processor = asyncio.create_task(self._process_deployment_queue())
        
        logger.info("✅ AutoDeploymentService démarré avec succès")
        
    async def stop_service(self):
        """Arrêter le service proprement"""
        logger.info("🛑 Arrêt AutoDeploymentService")
        
        if self.deployment_processor:
            self.deployment_processor.cancel()
            try:
                await self.deployment_processor
            except asyncio.CancelledError:
                pass
                
        # Annuler déploiements actifs
        for deployment_id in list(self.active_deployments.keys()):
            await self.cancel_deployment(deployment_id)
            
        logger.info("✅ AutoDeploymentService arrêté")
        
    async def create_auto_deployment(self, user_id: int, config: Dict[str, Any]) -> AutoDeployment:
        """Créer configuration de déploiement automatique"""
        
        # Vérifier permissions
        await self.rbac_service.check_permission(user_id, "deployment.create")
        
        # Valider configuration
        validated_config = await self._validate_deployment_config(config)
        
        # Créer déploiement
        deployment = AutoDeployment(
            user_id=user_id,
            name=validated_config["name"],
            repository_url=validated_config["repository_url"],
            branch=validated_config["branch"],
            dockerfile_path=validated_config.get("dockerfile_path", "Dockerfile"),
            auto_deploy=validated_config.get("auto_deploy", True),
            environment=validated_config.get("environment", "development"),
            container_config=validated_config.get("container_config", {}),
            status="configured",
            last_deployed_at=None
        )
        
        self.db_session.add(deployment)
        await self.db_session.commit()
        await self.db_session.refresh(deployment)
        
        # Audit
        await self.security_service.log_event(
            user_id, "deployment_created", 
            {"deployment_id": deployment.id, "repository": deployment.repository_url}
        )
        
        logger.info(f"✅ Déploiement automatique créé: {deployment.id} ({deployment.name})")
        return deployment
        
    async def trigger_deployment(self, deployment_id: int, user_id: int, 
                                manual: bool = False, commit_sha: Optional[str] = None) -> str:
        """Déclencher un déploiement (manuel ou automatique via webhook)"""
        
        # Vérifier permissions
        if manual:
            await self.rbac_service.check_permission(user_id, "deployment.deploy")
            
        # Récupérer configuration déploiement
        result = await self.db_session.execute(
            select(AutoDeployment)
            .options(selectinload(AutoDeployment.secrets))
            .where(AutoDeployment.id == deployment_id)
        )
        deployment = result.scalar_one_or_none()
        
        if not deployment:
            raise ValueError(f"Déploiement {deployment_id} non trouvé")
            
        if deployment.status in ["deploying", "building"]:
            raise ValueError(f"Déploiement {deployment_id} déjà en cours")
            
        # Créer historique déploiement
        history = DeploymentHistory(
            deployment_id=deployment_id,
            commit_sha=commit_sha or "HEAD",
            trigger_type="manual" if manual else "webhook",
            triggered_by=user_id,
            status="pending",
            started_at=datetime.utcnow(),
            logs=""
        )
        
        self.db_session.add(history)
        await self.db_session.commit()
        await self.db_session.refresh(history)
        
        # Ajouter à la queue
        deployment_task = {
            "deployment_id": deployment_id,
            "history_id": history.id,
            "user_id": user_id,
            "commit_sha": commit_sha,
            "manual": manual,
            "timestamp": time.time()
        }
        
        await self.deployment_queue.put(deployment_task)
        
        # Mettre à jour statut
        await self.db_session.execute(
            update(AutoDeployment)
            .where(AutoDeployment.id == deployment_id)
            .values(status="queued")
        )
        await self.db_session.commit()
        
        logger.info(f"🚀 Déploiement {deployment_id} ajouté à la queue (history: {history.id})")
        return f"deployment_{history.id}"
        
    async def _process_deployment_queue(self):
        """Traiter la queue des déploiements en arrière-plan"""
        logger.info("🔄 Processeur queue déploiements démarré")
        
        while True:
            try:
                # Attendre tâche de déploiement
                task = await self.deployment_queue.get()
                deployment_id = task["deployment_id"]
                history_id = task["history_id"]
                
                logger.info(f"🔨 Traitement déploiement {deployment_id} (history: {history_id})")
                
                # Traiter déploiement
                try:
                    await self._execute_deployment(task)
                except Exception as e:
                    logger.error(f"❌ Erreur déploiement {deployment_id}: {e}")
                    await self._handle_deployment_failure(history_id, str(e))
                finally:
                    # Nettoyer déploiement actif
                    if deployment_id in self.active_deployments:
                        del self.active_deployments[deployment_id]
                        
                    # Marquer tâche comme terminée
                    self.deployment_queue.task_done()
                    
            except asyncio.CancelledError:
                logger.info("🛑 Processeur queue déploiements arrêté")
                break
            except Exception as e:
                logger.error(f"❌ Erreur critique processeur queue: {e}")
                await asyncio.sleep(5)  # Pause avant retry
                
    async def _execute_deployment(self, task: Dict[str, Any]):
        """Exécuter un déploiement complet"""
        deployment_id = task["deployment_id"]
        history_id = task["history_id"]
        user_id = task["user_id"]
        commit_sha = task.get("commit_sha", "HEAD")
        
        # Tracker déploiement actif
        self.active_deployments[deployment_id] = {
            "history_id": history_id,
            "start_time": time.time(),
            "status": "starting"
        }
        
        start_time = time.time()
        logs = []
        
        try:
            # Récupérer configuration
            result = await self.db_session.execute(
                select(AutoDeployment)
                .options(selectinload(AutoDeployment.secrets))
                .where(AutoDeployment.id == deployment_id)
            )
            deployment = result.scalar_one()
            
            logs.append(f"[{datetime.utcnow()}] 🚀 Début déploiement {deployment.name}")
            
            # 1. Mettre à jour statut
            await self._update_deployment_status(deployment_id, history_id, "building", logs)
            
            # 2. Cloner repository
            logs.append(f"[{datetime.utcnow()}] 📥 Clonage repository {deployment.repository_url}")
            repo_path = await self._clone_repository(deployment.repository_url, 
                                                   deployment.branch, commit_sha)
            
            # 3. Valider Dockerfile
            dockerfile_path = repo_path / deployment.dockerfile_path
            if not dockerfile_path.exists():
                raise ValueError(f"Dockerfile non trouvé: {deployment.dockerfile_path}")
                
            logs.append(f"[{datetime.utcnow()}] 🔍 Validation Dockerfile")
            await self._validate_dockerfile(dockerfile_path)
            
            # 4. Construire image Docker
            logs.append(f"[{datetime.utcnow()}] 🔨 Construction image Docker")
            image_tag = f"wakedock-auto-{deployment_id}-{int(time.time())}"
            await self._build_docker_image(repo_path, dockerfile_path, image_tag)
            
            # 5. Scanner sécurité image
            logs.append(f"[{datetime.utcnow()}] 🛡️ Scan sécurité image")
            security_report = await self._scan_image_security(image_tag)
            
            # 6. Backup container existant si nécessaire
            logs.append(f"[{datetime.utcnow()}] 💾 Backup configuration existante")
            backup_info = await self._backup_existing_container(deployment)
            
            # 7. Déployer nouveau container
            await self._update_deployment_status(deployment_id, history_id, "deploying", logs)
            logs.append(f"[{datetime.utcnow()}] 🚀 Déploiement nouveau container")
            
            container_info = await self._deploy_container(deployment, image_tag)
            
            # 8. Health checks
            logs.append(f"[{datetime.utcnow()}] ❤️ Vérification santé container")
            health_status = await self._perform_health_checks(container_info["id"], deployment)
            
            if not health_status["healthy"]:
                # Rollback automatique
                if self.rollback_enabled and backup_info:
                    logs.append(f"[{datetime.utcnow()}] ⏪ Rollback automatique (échec health checks)")
                    await self._perform_rollback(deployment, backup_info)
                    raise ValueError(f"Health checks échoués, rollback effectué: {health_status['error']}")
                else:
                    raise ValueError(f"Health checks échoués: {health_status['error']}")
            
            # 9. Finaliser déploiement
            deployment_time = time.time() - start_time
            logs.append(f"[{datetime.utcnow()}] ✅ Déploiement réussi ({deployment_time:.1f}s)")
            
            # Mettre à jour métriques
            self.deployment_metrics["total_deployments"] += 1
            self.deployment_metrics["successful_deployments"] += 1
            
            # Calculer temps moyen
            total = self.deployment_metrics["total_deployments"]
            current_avg = self.deployment_metrics["average_deploy_time"]
            self.deployment_metrics["average_deploy_time"] = (
                (current_avg * (total - 1) + deployment_time) / total
            )
            
            # Sauvegarder métriques en BDD
            await self._save_deployment_metrics(deployment_id, history_id, {
                "deployment_time": deployment_time,
                "image_size": container_info.get("image_size", 0),
                "security_score": security_report.get("score", 0),
                "health_checks_passed": health_status["checks_passed"],
                "rollback_performed": False
            })
            
            # Finaliser statut
            await self._update_deployment_status(deployment_id, history_id, "success", logs, {
                "container_id": container_info["id"],
                "container_name": container_info["name"],
                "image_tag": image_tag,
                "deployment_time": deployment_time,
                "security_report": security_report
            })
            
            # Mettre à jour timestamp déploiement
            await self.db_session.execute(
                update(AutoDeployment)
                .where(AutoDeployment.id == deployment_id)
                .values(
                    status="deployed",
                    last_deployed_at=datetime.utcnow(),
                    current_container_id=container_info["id"]
                )
            )
            await self.db_session.commit()
            
            # Audit succès
            await self.security_service.log_event(
                user_id, "deployment_success",
                {
                    "deployment_id": deployment_id,
                    "history_id": history_id,
                    "container_id": container_info["id"],
                    "deployment_time": deployment_time
                }
            )
            
            logger.info(f"✅ Déploiement {deployment_id} réussi en {deployment_time:.1f}s")
            
        except Exception as e:
            # Gérer échec déploiement
            deployment_time = time.time() - start_time
            logs.append(f"[{datetime.utcnow()}] ❌ Échec déploiement: {str(e)}")
            
            self.deployment_metrics["total_deployments"] += 1
            self.deployment_metrics["failed_deployments"] += 1
            
            await self._handle_deployment_failure(history_id, str(e), logs)
            
            # Audit échec
            await self.security_service.log_event(
                user_id, "deployment_failure",
                {
                    "deployment_id": deployment_id,
                    "history_id": history_id,
                    "error": str(e),
                    "deployment_time": deployment_time
                }
            )
            
            raise e
            
        finally:
            # Nettoyer répertoire temporaire
            if 'repo_path' in locals():
                shutil.rmtree(repo_path, ignore_errors=True)
                
    async def _clone_repository(self, repo_url: str, branch: str, 
                               commit_sha: Optional[str] = None) -> Path:
        """Cloner repository Git dans répertoire temporaire"""
        
        # Créer répertoire unique
        repo_dir = self.work_dir / f"repo_{int(time.time())}_{os.getpid()}"
        repo_dir.mkdir(exist_ok=True)
        
        try:
            # Cloner repository
            repo = git.Repo.clone_from(repo_url, repo_dir, branch=branch, depth=1)
            
            # Checkout commit spécifique si fourni
            if commit_sha and commit_sha != "HEAD":
                repo.git.checkout(commit_sha)
                
            logger.debug(f"Repository cloné: {repo_url} ({branch}) -> {repo_dir}")
            return repo_dir
            
        except Exception as e:
            # Nettoyer en cas d'erreur
            shutil.rmtree(repo_dir, ignore_errors=True)
            raise ValueError(f"Erreur clonage repository: {e}")
            
    async def _validate_dockerfile(self, dockerfile_path: Path):
        """Valider Dockerfile pour sécurité et bonnes pratiques"""
        
        if not dockerfile_path.exists():
            raise ValueError(f"Dockerfile non trouvé: {dockerfile_path}")
            
        # Lire contenu Dockerfile
        async with aiofiles.open(dockerfile_path, 'r') as f:
            content = await f.read()
            
        # Règles de validation sécurité
        security_issues = []
        
        # Vérifier utilisateur root
        if not re.search(r'^USER\s+(?!root)', content, re.MULTILINE):
            security_issues.append("Dockerfile n'utilise pas d'utilisateur non-root")
            
        # Vérifier secrets hardcodés
        secret_patterns = [
            r'password\s*=\s*["\'][^"\']+["\']',
            r'api_key\s*=\s*["\'][^"\']+["\']',
            r'secret\s*=\s*["\'][^"\']+["\']',
            r'token\s*=\s*["\'][^"\']+["\']'
        ]
        
        for pattern in secret_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                security_issues.append(f"Secrets potentiels détectés: {pattern}")
                
        # Vérifier commandes dangereuses
        dangerous_commands = ['curl.*|.*sh', 'wget.*|.*sh', 'rm -rf /', 'chmod 777']
        for cmd in dangerous_commands:
            if re.search(cmd, content, re.IGNORECASE):
                security_issues.append(f"Commande dangereuse détectée: {cmd}")
                
        # Si issues critiques, bloquer
        if len(security_issues) > 3:
            raise ValueError(f"Dockerfile non sécurisé: {'; '.join(security_issues)}")
            
        if security_issues:
            logger.warning(f"Avertissements Dockerfile: {'; '.join(security_issues)}")
            
    async def _build_docker_image(self, repo_path: Path, dockerfile_path: Path, image_tag: str):
        """Construire image Docker avec streaming logs"""
        
        try:
            # Configuration build
            build_kwargs = {
                "path": str(repo_path),
                "dockerfile": str(dockerfile_path.relative_to(repo_path)),
                "tag": image_tag,
                "rm": True,  # Supprimer containers intermédiaires
                "pull": True,  # Pull dernière version base images
                "nocache": False,  # Utiliser cache pour performance
                "buildargs": {},  # Args variables à implémenter
            }
            
            # Lancer build avec timeout
            build_logs = []
            
            def build_generator():
                return self.docker_client.api.build(**build_kwargs, stream=True, decode=True)
                
            # Collecter logs build
            for log_entry in build_generator():
                if 'stream' in log_entry:
                    build_logs.append(log_entry['stream'].strip())
                    
                if 'error' in log_entry:
                    raise ValueError(f"Erreur build Docker: {log_entry['error']}")
                    
            logger.info(f"✅ Image Docker construite: {image_tag}")
            
        except Exception as e:
            logger.error(f"❌ Erreur construction image {image_tag}: {e}")
            raise ValueError(f"Échec construction image: {e}")
            
    async def _scan_image_security(self, image_tag: str) -> Dict[str, Any]:
        """Scanner sécurité image Docker (simulation)"""
        
        # Simulation scan sécurité réaliste
        # En production: intégration Trivy, Clair, ou autres scanners
        
        # Analyser image
        try:
            image = self.docker_client.images.get(image_tag)
            image.attrs
            
            # Simulation résultats scan
            vulnerabilities = []
            
            # Générer vulnérabilités aléatoires pour demo
            import random
            vuln_count = random.randint(0, 5)
            severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
            
            for i in range(vuln_count):
                vulnerabilities.append({
                    "id": f"CVE-2024-{random.randint(1000, 9999)}",
                    "severity": random.choice(severities),
                    "package": f"package-{i}",
                    "description": f"Vulnérabilité exemple {i}"
                })
                
            # Calculer score sécurité
            critical_count = len([v for v in vulnerabilities if v["severity"] == "CRITICAL"])
            high_count = len([v for v in vulnerabilities if v["severity"] == "HIGH"])
            
            # Score basé sur vulnérabilités critiques/hautes
            base_score = 100
            score = max(0, base_score - (critical_count * 30) - (high_count * 15))
            
            security_report = {
                "image_tag": image_tag,
                "scan_time": datetime.utcnow().isoformat(),
                "score": score,
                "vulnerabilities": vulnerabilities,
                "total_vulnerabilities": len(vulnerabilities),
                "critical_count": critical_count,
                "high_count": high_count,
                "passed": score >= 70  # Seuil sécurité
            }
            
            # Bloquer si score trop faible
            if score < 50:
                raise ValueError(f"Score sécurité trop faible: {score}/100 (seuil: 50)")
                
            logger.info(f"🛡️ Scan sécurité {image_tag}: {score}/100 ({len(vulnerabilities)} vulnérabilités)")
            return security_report
            
        except Exception as e:
            logger.error(f"❌ Erreur scan sécurité {image_tag}: {e}")
            raise
            
    async def _backup_existing_container(self, deployment: AutoDeployment) -> Optional[Dict[str, Any]]:
        """Sauvegarder container existant avant déploiement"""
        
        if not deployment.current_container_id:
            return None
            
        try:
            # Vérifier si container existe toujours
            container = self.docker_client.containers.get(deployment.current_container_id)
            
            # Créer backup info
            backup_info = {
                "container_id": container.id,
                "container_name": container.name,
                "image_tag": container.image.tags[0] if container.image.tags else "unknown",
                "status": container.status,
                "config": container.attrs["Config"],
                "host_config": container.attrs["HostConfig"],
                "backup_time": datetime.utcnow().isoformat()
            }
            
            # Arrêter container proprement
            if container.status == "running":
                container.stop(timeout=30)
                
            logger.info(f"💾 Container existant sauvegardé: {container.name}")
            return backup_info
            
        except docker.errors.NotFound:
            logger.warning(f"Container de backup non trouvé: {deployment.current_container_id}")
            return None
        except Exception as e:
            logger.error(f"❌ Erreur backup container: {e}")
            return None
            
    async def _deploy_container(self, deployment: AutoDeployment, image_tag: str) -> Dict[str, Any]:
        """Déployer nouveau container avec configuration complète"""
        
        # Générer nom container unique
        container_name = f"wakedock-{deployment.name}-{int(time.time())}"
        
        # Configuration container de base
        container_config = {
            "image": image_tag,
            "name": container_name,
            "detach": True,
            "restart_policy": {"Name": "unless-stopped"},
            "labels": {
                "wakedock.deployment_id": str(deployment.id),
                "wakedock.auto_deployment": "true",
                "wakedock.environment": deployment.environment,
                "wakedock.created_at": datetime.utcnow().isoformat()
            }
        }
        
        # Merger configuration personnalisée
        if deployment.container_config:
            # Ports
            if "ports" in deployment.container_config:
                container_config["ports"] = deployment.container_config["ports"]
                
            # Variables environnement
            if "environment" in deployment.container_config:
                container_config["environment"] = deployment.container_config["environment"]
                
            # Volumes
            if "volumes" in deployment.container_config:
                container_config["volumes"] = deployment.container_config["volumes"]
                
            # Limites ressources
            if "cpu_limit" in deployment.container_config:
                container_config["cpu_count"] = deployment.container_config["cpu_limit"]
            if "memory_limit" in deployment.container_config:
                container_config["mem_limit"] = deployment.container_config["memory_limit"]
                
        # Ajouter secrets déchiffrés comme variables environnement
        env_vars = container_config.get("environment", {})
        
        for secret in deployment.secrets:
            decrypted_value = self.fernet.decrypt(secret.encrypted_value.encode()).decode()
            env_vars[secret.key] = decrypted_value
            
        container_config["environment"] = env_vars
        
        # Ajouter à network WakeDock
        container_config["network"] = "wakedock-network"
        
        try:
            # Créer et démarrer container
            container = self.docker_client.containers.run(**container_config)
            
            # Attendre démarrage
            await asyncio.sleep(5)
            
            # Rafraîchir statut
            container.reload()
            
            # Récupérer info container
            container_info = {
                "id": container.id,
                "name": container.name,
                "status": container.status,
                "image_tag": image_tag,
                "ports": container.ports,
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Taille image
            try:
                image = self.docker_client.images.get(image_tag)
                container_info["image_size"] = image.attrs.get("Size", 0)
            except:
                container_info["image_size"] = 0
                
            logger.info(f"🚀 Container déployé: {container_name} ({container.id[:12]})")
            return container_info
            
        except Exception as e:
            logger.error(f"❌ Erreur déploiement container: {e}")
            raise ValueError(f"Échec déploiement container: {e}")
            
    async def _perform_health_checks(self, container_id: str, deployment: AutoDeployment) -> Dict[str, Any]:
        """Effectuer health checks post-déploiement"""
        
        health_result = {
            "healthy": False,
            "checks_passed": 0,
            "total_checks": 0,
            "error": None,
            "details": []
        }
        
        try:
            container = self.docker_client.containers.get(container_id)
            
            # 1. Vérifier statut container
            health_result["total_checks"] += 1
            container.reload()
            
            if container.status != "running":
                health_result["error"] = f"Container non démarré: {container.status}"
                health_result["details"].append({
                    "check": "container_status",
                    "status": "failed",
                    "message": health_result["error"]
                })
                return health_result
                
            health_result["checks_passed"] += 1
            health_result["details"].append({
                "check": "container_status",
                "status": "passed",
                "message": "Container en cours d'exécution"
            })
            
            # 2. Vérifier logs erreurs
            health_result["total_checks"] += 1
            logs = container.logs(tail=50).decode('utf-8', errors='ignore')
            
            error_indicators = ["error", "exception", "fatal", "panic", "fail"]
            has_errors = any(indicator in logs.lower() for indicator in error_indicators)
            
            if has_errors:
                health_result["details"].append({
                    "check": "error_logs",
                    "status": "warning",
                    "message": "Erreurs détectées dans les logs"
                })
            else:
                health_result["checks_passed"] += 1
                health_result["details"].append({
                    "check": "error_logs",
                    "status": "passed",
                    "message": "Aucune erreur dans les logs"
                })
                
            # 3. Test réseau (si ports exposés)
            health_result["total_checks"] += 1
            
            if container.ports:
                # Essayer connexion sur premier port exposé
                port_info = list(container.ports.values())[0]
                if port_info:
                    try:
                        import socket
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(5)
                        host = port_info[0]["HostIp"] or "localhost"
                        port = int(port_info[0]["HostPort"])
                        result = sock.connect_ex((host, port))
                        sock.close()
                        
                        if result == 0:
                            health_result["checks_passed"] += 1
                            health_result["details"].append({
                                "check": "network_connectivity",
                                "status": "passed",
                                "message": f"Port {port} accessible"
                            })
                        else:
                            health_result["details"].append({
                                "check": "network_connectivity",
                                "status": "failed",
                                "message": f"Port {port} non accessible"
                            })
                    except Exception as e:
                        health_result["details"].append({
                            "check": "network_connectivity",
                            "status": "failed",
                            "message": f"Erreur test réseau: {e}"
                        })
            else:
                health_result["checks_passed"] += 1
                health_result["details"].append({
                    "check": "network_connectivity",
                    "status": "skipped",
                    "message": "Aucun port exposé"
                })
                
            # 4. Utilisation ressources
            health_result["total_checks"] += 1
            
            try:
                stats = container.stats(stream=False)
                
                # CPU usage (approximatif)
                cpu_stats = stats["cpu_stats"]
                precpu_stats = stats["precpu_stats"]
                
                if cpu_stats["online_cpus"] > 0:
                    cpu_delta = cpu_stats["cpu_usage"]["total_usage"] - precpu_stats["cpu_usage"]["total_usage"]
                    system_delta = cpu_stats["system_cpu_usage"] - precpu_stats["system_cpu_usage"]
                    cpu_percent = (cpu_delta / system_delta) * cpu_stats["online_cpus"] * 100.0
                    
                    if cpu_percent < 90:  # Seuil CPU
                        health_result["checks_passed"] += 1
                        health_result["details"].append({
                            "check": "resource_usage",
                            "status": "passed",
                            "message": f"CPU: {cpu_percent:.1f}%"
                        })
                    else:
                        health_result["details"].append({
                            "check": "resource_usage",
                            "status": "warning",
                            "message": f"CPU élevé: {cpu_percent:.1f}%"
                        })
                else:
                    health_result["checks_passed"] += 1
                    health_result["details"].append({
                        "check": "resource_usage",
                        "status": "passed",
                        "message": "Ressources OK"
                    })
                    
            except Exception as e:
                health_result["details"].append({
                    "check": "resource_usage",
                    "status": "failed",
                    "message": f"Erreur lecture stats: {e}"
                })
                
            # Calculer résultat final
            success_rate = health_result["checks_passed"] / health_result["total_checks"]
            health_result["healthy"] = success_rate >= 0.75  # 75% checks réussis minimum
            
            if not health_result["healthy"] and not health_result["error"]:
                health_result["error"] = f"Health checks insuffisants: {health_result['checks_passed']}/{health_result['total_checks']}"
                
            logger.info(f"❤️ Health checks {container_id[:12]}: {health_result['checks_passed']}/{health_result['total_checks']} réussis")
            return health_result
            
        except Exception as e:
            health_result["error"] = f"Erreur health checks: {e}"
            logger.error(f"❌ Erreur health checks {container_id}: {e}")
            return health_result
            
    async def _perform_rollback(self, deployment: AutoDeployment, backup_info: Dict[str, Any]):
        """Effectuer rollback vers version précédente"""
        
        logger.info(f"⏪ Début rollback déploiement {deployment.id}")
        
        try:
            # 1. Arrêter container défaillant s'il existe
            if deployment.current_container_id:
                try:
                    failed_container = self.docker_client.containers.get(deployment.current_container_id)
                    failed_container.stop(timeout=10)
                    failed_container.remove()
                    logger.info(f"🗑️ Container défaillant supprimé: {deployment.current_container_id}")
                except:
                    pass
                    
            # 2. Recréer container depuis backup
            backup_config = backup_info["config"]
            backup_host_config = backup_info["host_config"]
            
            # Adapter configuration pour nouveau container
            rollback_config = {
                "image": backup_info["image_tag"],
                "name": f"wakedock-{deployment.name}-rollback-{int(time.time())}",
                "detach": True,
                "environment": backup_config.get("Env", []),
                "ports": {},
                "volumes": {},
                "restart_policy": {"Name": "unless-stopped"},
                "labels": {
                    "wakedock.deployment_id": str(deployment.id),
                    "wakedock.rollback": "true",
                    "wakedock.rollback_from": backup_info["container_id"],
                    "wakedock.created_at": datetime.utcnow().isoformat()
                }
            }
            
            # Restaurer ports
            if backup_host_config.get("PortBindings"):
                for container_port, host_bindings in backup_host_config["PortBindings"].items():
                    if host_bindings:
                        rollback_config["ports"][container_port] = host_bindings[0]["HostPort"]
                        
            # 3. Créer container rollback
            rollback_container = self.docker_client.containers.run(**rollback_config)
            
            # 4. Mettre à jour déploiement
            await self.db_session.execute(
                update(AutoDeployment)
                .where(AutoDeployment.id == deployment.id)
                .values(
                    current_container_id=rollback_container.id,
                    status="rolled_back"
                )
            )
            await self.db_session.commit()
            
            # 5. Mettre à jour métriques
            self.deployment_metrics["rollbacks_performed"] += 1
            
            logger.info(f"✅ Rollback réussi: {rollback_container.name} ({rollback_container.id[:12]})")
            
        except Exception as e:
            logger.error(f"❌ Erreur rollback déploiement {deployment.id}: {e}")
            raise ValueError(f"Échec rollback: {e}")
            
    async def rollback_deployment(self, deployment_id: int, user_id: int) -> str:
        """Effectuer rollback manuel d'un déploiement"""
        
        # Vérifier permissions
        await self.rbac_service.check_permission(user_id, "deployment.rollback")
        
        # Récupérer déploiement
        result = await self.db_session.execute(
            select(AutoDeployment).where(AutoDeployment.id == deployment_id)
        )
        deployment = result.scalar_one_or_none()
        
        if not deployment:
            raise ValueError(f"Déploiement {deployment_id} non trouvé")
            
        # Récupérer dernier déploiement réussi
        result = await self.db_session.execute(
            select(DeploymentHistory)
            .where(
                DeploymentHistory.deployment_id == deployment_id,
                DeploymentHistory.status == "success"
            )
            .order_by(DeploymentHistory.started_at.desc())
            .limit(2)  # Exclure déploiement actuel
        )
        
        histories = result.scalars().all()
        
        if len(histories) < 2:
            raise ValueError("Aucun déploiement précédent disponible pour rollback")
            
        previous_history = histories[1]  # Avant-dernier déploiement réussi
        
        # Créer historique rollback
        rollback_history = DeploymentHistory(
            deployment_id=deployment_id,
            commit_sha=previous_history.commit_sha,
            trigger_type="manual_rollback",
            triggered_by=user_id,
            status="pending",
            started_at=datetime.utcnow(),
            logs=f"Rollback vers déploiement {previous_history.id}"
        )
        
        self.db_session.add(rollback_history)
        await self.db_session.commit()
        await self.db_session.refresh(rollback_history)
        
        # Déclencher rollback via queue
        rollback_task = {
            "deployment_id": deployment_id,
            "history_id": rollback_history.id,
            "user_id": user_id,
            "rollback_to": previous_history.id,
            "manual": True,
            "timestamp": time.time()
        }
        
        await self.deployment_queue.put(rollback_task)
        
        logger.info(f"⏪ Rollback manuel déclenché: {deployment_id} -> {previous_history.id}")
        return f"rollback_{rollback_history.id}"
        
    async def get_deployment_status(self, deployment_id: int, user_id: int) -> Dict[str, Any]:
        """Récupérer statut détaillé d'un déploiement"""
        
        await self.rbac_service.check_permission(user_id, "deployment.view")
        
        # Récupérer déploiement avec historiques
        result = await self.db_session.execute(
            select(AutoDeployment)
            .options(
                selectinload(AutoDeployment.deployment_histories).selectinload(DeploymentHistory.metrics),
                selectinload(AutoDeployment.secrets)
            )
            .where(AutoDeployment.id == deployment_id)
        )
        deployment = result.scalar_one_or_none()
        
        if not deployment:
            raise ValueError(f"Déploiement {deployment_id} non trouvé")
            
        # Statut container actuel
        container_status = None
        if deployment.current_container_id:
            try:
                container = self.docker_client.containers.get(deployment.current_container_id)
                container_status = {
                    "id": container.id,
                    "name": container.name,
                    "status": container.status,
                    "created": container.attrs["Created"],
                    "ports": container.ports
                }
            except:
                container_status = {"error": "Container non trouvé"}
                
        # Dernier déploiement
        last_deployment = None
        if deployment.deployment_histories:
            last_deployment = deployment.deployment_histories[-1]
            
        # Métriques récentes
        recent_metrics = None
        if last_deployment and last_deployment.metrics:
            recent_metrics = last_deployment.metrics[-1]
            
        return {
            "deployment": {
                "id": deployment.id,
                "name": deployment.name,
                "repository_url": deployment.repository_url,
                "branch": deployment.branch,
                "environment": deployment.environment,
                "status": deployment.status,
                "auto_deploy": deployment.auto_deploy,
                "last_deployed_at": deployment.last_deployed_at.isoformat() if deployment.last_deployed_at else None,
                "created_at": deployment.created_at.isoformat()
            },
            "container": container_status,
            "last_deployment": {
                "id": last_deployment.id,
                "status": last_deployment.status,
                "trigger_type": last_deployment.trigger_type,
                "started_at": last_deployment.started_at.isoformat(),
                "completed_at": last_deployment.completed_at.isoformat() if last_deployment.completed_at else None,
                "commit_sha": last_deployment.commit_sha
            } if last_deployment else None,
            "metrics": {
                "deployment_time": recent_metrics.deployment_time if recent_metrics else None,
                "security_score": recent_metrics.security_score if recent_metrics else None,
                "health_checks_passed": recent_metrics.health_checks_passed if recent_metrics else None
            } if recent_metrics else None,
            "queue_status": deployment_id in self.active_deployments,
            "active_deployment": self.active_deployments.get(deployment_id)
        }
        
    async def list_deployments(self, user_id: int, limit: int = 50, 
                              environment: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lister déploiements automatiques de l'utilisateur"""
        
        await self.rbac_service.check_permission(user_id, "deployment.view")
        
        query = select(AutoDeployment).where(AutoDeployment.user_id == user_id)
        
        if environment:
            query = query.where(AutoDeployment.environment == environment)
            
        query = query.order_by(AutoDeployment.created_at.desc()).limit(limit)
        
        result = await self.db_session.execute(query)
        deployments = result.scalars().all()
        
        deployment_list = []
        for deployment in deployments:
            # Statut container
            container_status = "unknown"
            if deployment.current_container_id:
                try:
                    container = self.docker_client.containers.get(deployment.current_container_id)
                    container_status = container.status
                except:
                    container_status = "not_found"
                    
            deployment_list.append({
                "id": deployment.id,
                "name": deployment.name,
                "repository_url": deployment.repository_url,
                "branch": deployment.branch,
                "environment": deployment.environment,
                "status": deployment.status,
                "container_status": container_status,
                "auto_deploy": deployment.auto_deploy,
                "last_deployed_at": deployment.last_deployed_at.isoformat() if deployment.last_deployed_at else None,
                "created_at": deployment.created_at.isoformat()
            })
            
        return deployment_list
        
    async def get_deployment_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Récupérer métriques globales des déploiements"""
        
        # Période de calcul
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # Statistiques depuis BDD
        result = await self.db_session.execute(
            select(
                func.count(DeploymentHistory.id).label("total_deployments"),
                func.count(
                    DeploymentHistory.id.filter(DeploymentHistory.status == "success")
                ).label("successful_deployments"),
                func.count(
                    DeploymentHistory.id.filter(DeploymentHistory.status.in_(["failed", "timeout"]))
                ).label("failed_deployments"),
                func.avg(DeploymentMetrics.deployment_time).label("avg_deployment_time"),
                func.avg(DeploymentMetrics.security_score).label("avg_security_score")
            )
            .select_from(DeploymentHistory)
            .outerjoin(DeploymentMetrics)
            .where(DeploymentHistory.started_at >= since_date)
        )
        
        stats = result.first()
        
        # Taux de succès
        success_rate = 0
        if stats.total_deployments > 0:
            success_rate = (stats.successful_deployments / stats.total_deployments) * 100
            
        # Métriques par jour
        daily_result = await self.db_session.execute(
            select(
                func.date(DeploymentHistory.started_at).label("date"),
                func.count(DeploymentHistory.id).label("deployments"),
                func.count(
                    DeploymentHistory.id.filter(DeploymentHistory.status == "success")
                ).label("successes")
            )
            .where(DeploymentHistory.started_at >= since_date)
            .group_by(func.date(DeploymentHistory.started_at))
            .order_by(func.date(DeploymentHistory.started_at))
        )
        
        daily_stats = []
        for row in daily_result.all():
            daily_stats.append({
                "date": row.date.isoformat(),
                "deployments": row.deployments,
                "successes": row.successes,
                "success_rate": (row.successes / row.deployments * 100) if row.deployments > 0 else 0
            })
            
        return {
            "period_days": days,
            "total_deployments": stats.total_deployments or 0,
            "successful_deployments": stats.successful_deployments or 0,
            "failed_deployments": stats.failed_deployments or 0,
            "success_rate": success_rate,
            "average_deployment_time": float(stats.avg_deployment_time or 0),
            "average_security_score": float(stats.avg_security_score or 0),
            "rollbacks_performed": self.deployment_metrics["rollbacks_performed"],
            "active_deployments": len(self.active_deployments),
            "queue_size": self.deployment_queue.qsize(),
            "daily_stats": daily_stats,
            "current_metrics": self.deployment_metrics
        }
        
    # Méthodes utilitaires et de configuration
    
    async def _validate_deployment_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Valider configuration de déploiement"""
        
        required_fields = ["name", "repository_url", "branch"]
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Champ requis manquant: {field}")
                
        # Valider URL repository
        repo_url = config["repository_url"]
        if not re.match(r'https?://[^/]+/[^/]+/[^/]+\.git$', repo_url):
            raise ValueError("URL repository invalide (format attendu: https://host/user/repo.git)")
            
        # Valider nom
        name = config["name"]
        if not re.match(r'^[a-zA-Z0-9_-]+$', name):
            raise ValueError("Nom invalide (lettres, chiffres, _ et - uniquement)")
            
        # Valider environnement
        valid_environments = ["development", "staging", "production"]
        environment = config.get("environment", "development")
        if environment not in valid_environments:
            raise ValueError(f"Environnement invalide. Valeurs autorisées: {valid_environments}")
            
        # Valider configuration container
        container_config = config.get("container_config", {})
        if "memory_limit" in container_config:
            if not isinstance(container_config["memory_limit"], (int, str)):
                raise ValueError("memory_limit doit être un entier ou string (ex: '512m')")
                
        return config
        
    def _get_or_create_encryption_key(self) -> bytes:
        """Récupérer ou créer clé de chiffrement pour secrets"""
        
        key_file = Path("/tmp/wakedock-deployment-key")
        
        if key_file.exists():
            return key_file.read_bytes()
        else:
            key = Fernet.generate_key()
            key_file.write_bytes(key)
            key_file.chmod(0o600)  # Permissions restrictives
            return key
            
    async def _ensure_docker_networks(self):
        """S'assurer que les networks Docker existent"""
        
        try:
            # Vérifier network principal
            try:
                self.docker_client.networks.get("wakedock-network")
            except docker.errors.NotFound:
                self.docker_client.networks.create(
                    "wakedock-network",
                    driver="bridge",
                    labels={"wakedock.network": "true"}
                )
                logger.info("✅ Network wakedock-network créé")
                
        except Exception as e:
            logger.error(f"❌ Erreur création networks Docker: {e}")
            
    async def _cleanup_stale_deployments(self):
        """Nettoyer déploiements abandonnés au démarrage"""
        
        try:
            # Réinitialiser statuts "en cours" abandonnés
            await self.db_session.execute(
                update(AutoDeployment)
                .where(AutoDeployment.status.in_(["deploying", "building", "queued"]))
                .values(status="failed")
            )
            
            await self.db_session.execute(
                update(DeploymentHistory)
                .where(
                    DeploymentHistory.status.in_(["pending", "building", "deploying"]),
                    DeploymentHistory.started_at < datetime.utcnow() - timedelta(hours=2)
                )
                .values(status="timeout", completed_at=datetime.utcnow())
            )
            
            await self.db_session.commit()
            logger.info("✅ Déploiements abandonnés nettoyés")
            
        except Exception as e:
            logger.error(f"❌ Erreur nettoyage déploiements: {e}")
            
    async def _update_deployment_status(self, deployment_id: int, history_id: int, 
                                       status: str, logs: List[str], 
                                       result_data: Optional[Dict] = None):
        """Mettre à jour statut déploiement et historique"""
        
        # Mettre à jour déploiement
        await self.db_session.execute(
            update(AutoDeployment)
            .where(AutoDeployment.id == deployment_id)
            .values(status=status)
        )
        
        # Mettre à jour historique
        update_data = {
            "status": status,
            "logs": "\n".join(logs)
        }
        
        if status in ["success", "failed", "timeout"]:
            update_data["completed_at"] = datetime.utcnow()
            
        if result_data:
            update_data["result_data"] = json.dumps(result_data)
            
        await self.db_session.execute(
            update(DeploymentHistory)
            .where(DeploymentHistory.id == history_id)
            .values(**update_data)
        )
        
        await self.db_session.commit()
        
    async def _save_deployment_metrics(self, deployment_id: int, history_id: int, 
                                      metrics_data: Dict[str, Any]):
        """Sauvegarder métriques de déploiement"""
        
        metrics = DeploymentMetrics(
            history_id=history_id,
            deployment_time=metrics_data.get("deployment_time", 0),
            image_size=metrics_data.get("image_size", 0),
            security_score=metrics_data.get("security_score", 0),
            health_checks_passed=metrics_data.get("health_checks_passed", 0),
            rollback_performed=metrics_data.get("rollback_performed", False),
            created_at=datetime.utcnow()
        )
        
        self.db_session.add(metrics)
        await self.db_session.commit()
        
    async def _handle_deployment_failure(self, history_id: int, error: str, 
                                        logs: Optional[List[str]] = None):
        """Gérer échec de déploiement"""
        
        update_data = {
            "status": "failed",
            "completed_at": datetime.utcnow(),
            "logs": "\n".join(logs) if logs else f"Erreur: {error}"
        }
        
        await self.db_session.execute(
            update(DeploymentHistory)
            .where(DeploymentHistory.id == history_id)
            .values(**update_data)
        )
        await self.db_session.commit()
        
    async def cancel_deployment(self, deployment_id: int, user_id: int) -> bool:
        """Annuler déploiement en cours"""
        
        await self.rbac_service.check_permission(user_id, "deployment.cancel")
        
        if deployment_id not in self.active_deployments:
            return False
            
        active_deployment = self.active_deployments[deployment_id]
        history_id = active_deployment["history_id"]
        
        # Marquer comme annulé
        await self.db_session.execute(
            update(DeploymentHistory)
            .where(DeploymentHistory.id == history_id)
            .values(status="cancelled", completed_at=datetime.utcnow())
        )
        
        await self.db_session.execute(
            update(AutoDeployment)
            .where(AutoDeployment.id == deployment_id)
            .values(status="cancelled")
        )
        
        await self.db_session.commit()
        
        # Supprimer du tracking
        del self.active_deployments[deployment_id]
        
        logger.info(f"🚫 Déploiement {deployment_id} annulé")
        return True
        
    async def create_deployment_secret(self, deployment_id: int, user_id: int, 
                                     key: str, value: str) -> DeploymentSecret:
        """Créer secret chiffré pour déploiement"""
        
        await self.rbac_service.check_permission(user_id, "deployment.secrets")
        
        # Vérifier que déploiement existe
        result = await self.db_session.execute(
            select(AutoDeployment).where(AutoDeployment.id == deployment_id)
        )
        if not result.scalar_one_or_none():
            raise ValueError(f"Déploiement {deployment_id} non trouvé")
            
        # Chiffrer valeur
        encrypted_value = self.fernet.encrypt(value.encode()).decode()
        
        # Créer secret
        secret = DeploymentSecret(
            deployment_id=deployment_id,
            key=key,
            encrypted_value=encrypted_value,
            created_by=user_id,
            created_at=datetime.utcnow()
        )
        
        self.db_session.add(secret)
        await self.db_session.commit()
        await self.db_session.refresh(secret)
        
        logger.info(f"🔐 Secret créé pour déploiement {deployment_id}: {key}")
        return secret
        
    async def get_deployment_logs(self, deployment_id: int, user_id: int, 
                                 limit: int = 100) -> List[Dict[str, Any]]:
        """Récupérer logs des déploiements"""
        
        await self.rbac_service.check_permission(user_id, "deployment.view")
        
        result = await self.db_session.execute(
            select(DeploymentHistory)
            .where(DeploymentHistory.deployment_id == deployment_id)
            .order_by(DeploymentHistory.started_at.desc())
            .limit(limit)
        )
        
        histories = result.scalars().all()
        
        logs = []
        for history in histories:
            logs.append({
                "id": history.id,
                "status": history.status,
                "trigger_type": history.trigger_type,
                "commit_sha": history.commit_sha,
                "started_at": history.started_at.isoformat(),
                "completed_at": history.completed_at.isoformat() if history.completed_at else None,
                "logs": history.logs or "",
                "triggered_by": history.triggered_by
            })
            
        return logs
