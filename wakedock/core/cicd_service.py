"""
Service d'intégration CI/CD avec GitHub Actions pour WakeDock
Gestion des webhooks, builds automatisés et notifications de déploiement
"""
import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
from pydantic import BaseModel
from sqlalchemy import and_, desc, func, select

from wakedock.core.config import get_settings
from wakedock.core.database import get_async_session
from wakedock.core.security_audit_service import (
    get_security_audit_service,
    SecurityEventData,
    SecurityEventType,
)
from wakedock.models.cicd import CIBuild, GitHubIntegration

logger = logging.getLogger(__name__)

class BuildStatus(str, Enum):
    """États des builds CI/CD"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

class DeploymentEnvironment(str, Enum):
    """Environnements de déploiement"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"

class WebhookEvent(str, Enum):
    """Types d'événements webhook GitHub"""
    PUSH = "push"
    PULL_REQUEST = "pull_request"
    RELEASE = "release"
    WORKFLOW_RUN = "workflow_run"
    DEPLOYMENT = "deployment"
    DEPLOYMENT_STATUS = "deployment_status"

class GitHubActionConfig(BaseModel):
    """Configuration pour une action GitHub"""
    name: str
    repository: str
    workflow_file: str
    branch: str = "main"
    environment: DeploymentEnvironment = DeploymentEnvironment.DEVELOPMENT
    auto_deploy: bool = False
    security_checks: bool = True
    required_approvals: int = 0
    timeout_minutes: int = 30
    secrets: Dict[str, str] = {}
    variables: Dict[str, str] = {}

class WebhookPayload(BaseModel):
    """Payload des webhooks GitHub"""
    event_type: WebhookEvent
    repository: str
    branch: str
    commit_sha: str
    author: str
    message: str
    timestamp: datetime
    workflow_run_id: Optional[int] = None
    deployment_id: Optional[int] = None
    raw_payload: Dict[str, Any] = {}

class BuildResult(BaseModel):
    """Résultat d'un build"""
    build_id: str
    status: BuildStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    logs_url: Optional[str] = None
    artifacts_url: Optional[str] = None
    security_report: Optional[Dict[str, Any]] = None
    test_results: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

class CICDService:
    """Service d'intégration CI/CD avec GitHub Actions"""
    
    def __init__(self, storage_path: str = "/var/log/wakedock/cicd"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Configuration GitHub
        settings = get_settings()
        self.github_token = getattr(settings, 'GITHUB_TOKEN', None)
        self.github_webhook_secret = getattr(settings, 'GITHUB_WEBHOOK_SECRET', None)
        self.github_api_url = "https://api.github.com"
        
        # Configuration des builds
        self.max_concurrent_builds = getattr(settings, 'MAX_CONCURRENT_BUILDS', 5)
        self.build_timeout_minutes = getattr(settings, 'BUILD_TIMEOUT_MINUTES', 60)
        
        # Suivi des builds actifs
        self.active_builds: Dict[str, asyncio.Task] = {}
        self.build_queue: asyncio.Queue = asyncio.Queue()
        
        # Cache des configurations
        self.github_configs: Dict[str, GitHubActionConfig] = {}
        
        # Service de sécurité pour l'audit
        self.security_service = get_security_audit_service()
        
        logger.info(f"Service CI/CD initialisé - Stockage: {self.storage_path}")

    async def start(self):
        """Démarre le service CI/CD"""
        # Démarrer le processeur de builds
        asyncio.create_task(self._process_build_queue())
        
        # Charger les configurations existantes
        await self._load_github_configurations()
        
        # Vérifier la connectivité GitHub
        if self.github_token:
            await self._verify_github_connection()
        
        logger.info("Service CI/CD démarré")

    async def stop(self):
        """Arrête le service CI/CD"""
        # Annuler tous les builds actifs
        for build_id, task in self.active_builds.items():
            if not task.done():
                task.cancel()
                logger.info(f"Build {build_id} annulé lors de l'arrêt")
        
        # Attendre la fin des tâches
        if self.active_builds:
            await asyncio.gather(*self.active_builds.values(), return_exceptions=True)
        
        logger.info("Service CI/CD arrêté")

    async def register_github_integration(
        self,
        config: GitHubActionConfig,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Enregistre une nouvelle intégration GitHub Actions
        """
        try:
            async with get_async_session() as session:
                # Vérifier si l'intégration existe déjà
                existing = await session.execute(
                    select(GitHubIntegration).where(
                        and_(
                            GitHubIntegration.repository == config.repository,
                            GitHubIntegration.workflow_file == config.workflow_file
                        )
                    )
                )
                
                if existing.scalar_one_or_none():
                    raise ValueError(f"Intégration déjà existante pour {config.repository}/{config.workflow_file}")
                
                # Créer l'intégration
                integration = GitHubIntegration(
                    name=config.name,
                    repository=config.repository,
                    workflow_file=config.workflow_file,
                    branch=config.branch,
                    environment=config.environment.value,
                    auto_deploy=config.auto_deploy,
                    security_checks=config.security_checks,
                    required_approvals=config.required_approvals,
                    timeout_minutes=config.timeout_minutes,
                    configuration=config.dict(),
                    created_by=user_id,
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                
                session.add(integration)
                await session.commit()
                
                # Mettre en cache
                integration_key = f"{config.repository}/{config.workflow_file}"
                self.github_configs[integration_key] = config
                
                # Audit log
                await self.security_service.log_security_event(
                    SecurityEventData(
                        event_type=SecurityEventType.SYSTEM_ACCESS,
                        user_id=user_id,
                        ip_address="127.0.0.1",  # À adapter selon le contexte
                        action="github_integration_created",
                        resource=config.repository,
                        success=True,
                        details={
                            "integration_name": config.name,
                            "repository": config.repository,
                            "workflow_file": config.workflow_file,
                            "environment": config.environment.value
                        }
                    )
                )
                
                return {
                    "integration_id": integration.id,
                    "webhook_url": f"/api/v1/cicd/webhooks/{integration.id}",
                    "status": "created",
                    "message": "Intégration GitHub Actions créée avec succès"
                }
                
        except Exception as e:
            logger.error(f"Erreur création intégration GitHub: {e}")
            raise

    async def handle_webhook(
        self,
        integration_id: int,
        headers: Dict[str, str],
        payload: bytes,
        user_ip: str = "unknown"
    ) -> Dict[str, Any]:
        """
        Traite un webhook GitHub
        """
        try:
            # Vérifier la signature du webhook
            if not await self._verify_webhook_signature(headers, payload):
                raise ValueError("Signature webhook invalide")
            
            # Parser le payload
            payload_data = json.loads(payload.decode('utf-8'))
            event_type = headers.get('X-GitHub-Event', 'unknown')
            
            # Récupérer la configuration de l'intégration
            async with get_async_session() as session:
                integration = await session.get(GitHubIntegration, integration_id)
                if not integration or not integration.is_active:
                    raise ValueError("Intégration introuvable ou inactive")
            
            # Créer l'objet webhook
            webhook_event = await self._parse_webhook_payload(event_type, payload_data)
            
            # Audit log
            await self.security_service.log_security_event(
                SecurityEventData(
                    event_type=SecurityEventType.SYSTEM_ACCESS,
                    user_id=None,
                    ip_address=user_ip,
                    action="webhook_received",
                    resource=webhook_event.repository,
                    success=True,
                    details={
                        "event_type": event_type,
                        "repository": webhook_event.repository,
                        "branch": webhook_event.branch,
                        "commit_sha": webhook_event.commit_sha
                    }
                )
            )
            
            # Traiter l'événement selon le type
            result = await self._process_webhook_event(integration, webhook_event)
            
            return {
                "status": "processed",
                "event_type": event_type,
                "result": result
            }
            
        except Exception as e:
            logger.error(f"Erreur traitement webhook {integration_id}: {e}")
            
            # Audit log de l'erreur
            await self.security_service.log_security_event(
                SecurityEventData(
                    event_type=SecurityEventType.SUSPICIOUS_ACTIVITY,
                    user_id=None,
                    ip_address=user_ip,
                    action="webhook_error",
                    resource=f"integration_{integration_id}",
                    success=False,
                    details={"error": str(e)}
                )
            )
            
            raise

    async def trigger_build(
        self,
        integration_id: int,
        branch: str = None,
        user_id: int = None,
        manual: bool = True
    ) -> str:
        """
        Déclenche un build manuellement
        """
        try:
            async with get_async_session() as session:
                integration = await session.get(GitHubIntegration, integration_id)
                if not integration:
                    raise ValueError("Intégration introuvable")
                
                # Générer l'ID du build
                build_id = f"build_{integration_id}_{int(datetime.utcnow().timestamp())}"
                
                # Créer l'enregistrement de build
                build = CIBuild(
                    build_id=build_id,
                    integration_id=integration_id,
                    branch=branch or integration.branch,
                    commit_sha="manual",
                    triggered_by=user_id,
                    status=BuildStatus.PENDING.value,
                    is_manual=manual,
                    created_at=datetime.utcnow()
                )
                
                session.add(build)
                await session.commit()
                
                # Ajouter à la queue
                await self.build_queue.put({
                    "build_id": build_id,
                    "integration": integration,
                    "branch": branch or integration.branch,
                    "manual": manual
                })
                
                # Audit log
                await self.security_service.log_security_event(
                    SecurityEventData(
                        event_type=SecurityEventType.SYSTEM_ACCESS,
                        user_id=user_id,
                        ip_address="127.0.0.1",
                        action="build_triggered",
                        resource=integration.repository,
                        success=True,
                        details={
                            "build_id": build_id,
                            "repository": integration.repository,
                            "branch": branch or integration.branch,
                            "manual": manual
                        }
                    )
                )
                
                return build_id
                
        except Exception as e:
            logger.error(f"Erreur déclenchement build: {e}")
            raise

    async def get_build_status(self, build_id: str) -> Optional[BuildResult]:
        """
        Récupère le statut d'un build
        """
        try:
            async with get_async_session() as session:
                build = await session.execute(
                    select(CIBuild).where(CIBuild.build_id == build_id)
                )
                build_record = build.scalar_one_or_none()
                
                if not build_record:
                    return None
                
                duration = None
                if build_record.started_at and build_record.completed_at:
                    duration = int((build_record.completed_at - build_record.started_at).total_seconds())
                
                return BuildResult(
                    build_id=build_record.build_id,
                    status=BuildStatus(build_record.status),
                    started_at=build_record.started_at or build_record.created_at,
                    completed_at=build_record.completed_at,
                    duration_seconds=duration,
                    logs_url=build_record.logs_url,
                    artifacts_url=build_record.artifacts_url,
                    security_report=build_record.security_report,
                    test_results=build_record.test_results,
                    error_message=build_record.error_message
                )
                
        except Exception as e:
            logger.error(f"Erreur récupération statut build {build_id}: {e}")
            return None

    async def get_builds_history(
        self,
        integration_id: Optional[int] = None,
        status: Optional[BuildStatus] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Récupère l'historique des builds
        """
        try:
            async with get_async_session() as session:
                query = select(CIBuild).order_by(desc(CIBuild.created_at))
                
                conditions = []
                if integration_id:
                    conditions.append(CIBuild.integration_id == integration_id)
                if status:
                    conditions.append(CIBuild.status == status.value)
                
                if conditions:
                    query = query.where(and_(*conditions))
                
                query = query.limit(limit)
                result = await session.execute(query)
                builds = result.scalars().all()
                
                return [
                    {
                        "build_id": build.build_id,
                        "integration_id": build.integration_id,
                        "branch": build.branch,
                        "commit_sha": build.commit_sha,
                        "status": build.status,
                        "triggered_by": build.triggered_by,
                        "is_manual": build.is_manual,
                        "created_at": build.created_at.isoformat(),
                        "started_at": build.started_at.isoformat() if build.started_at else None,
                        "completed_at": build.completed_at.isoformat() if build.completed_at else None,
                        "duration_seconds": int((build.completed_at - build.started_at).total_seconds()) if build.started_at and build.completed_at else None,
                        "logs_url": build.logs_url,
                        "error_message": build.error_message
                    }
                    for build in builds
                ]
                
        except Exception as e:
            logger.error(f"Erreur récupération historique builds: {e}")
            return []

    async def cancel_build(self, build_id: str, user_id: int) -> bool:
        """
        Annule un build en cours
        """
        try:
            # Annuler la tâche si elle est active
            if build_id in self.active_builds:
                task = self.active_builds[build_id]
                if not task.done():
                    task.cancel()
                    del self.active_builds[build_id]
            
            # Mettre à jour le statut en base
            async with get_async_session() as session:
                build = await session.execute(
                    select(CIBuild).where(CIBuild.build_id == build_id)
                )
                build_record = build.scalar_one_or_none()
                
                if build_record and build_record.status in [BuildStatus.PENDING.value, BuildStatus.IN_PROGRESS.value]:
                    build_record.status = BuildStatus.CANCELLED.value
                    build_record.completed_at = datetime.utcnow()
                    build_record.error_message = f"Build annulé par l'utilisateur {user_id}"
                    
                    await session.commit()
                    
                    # Audit log
                    await self.security_service.log_security_event(
                        SecurityEventData(
                            event_type=SecurityEventType.SYSTEM_ACCESS,
                            user_id=user_id,
                            ip_address="127.0.0.1",
                            action="build_cancelled",
                            resource=build_id,
                            success=True,
                            details={"build_id": build_id}
                        )
                    )
                    
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur annulation build {build_id}: {e}")
            return False

    async def get_pipeline_metrics(self, days: int = 30) -> Dict[str, Any]:
        """
        Calcule les métriques des pipelines CI/CD
        """
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            async with get_async_session() as session:
                # Total des builds
                total_builds_query = select(func.count(CIBuild.id)).where(
                    CIBuild.created_at >= start_date
                )
                total_builds = await session.scalar(total_builds_query)
                
                # Builds par statut
                builds_by_status_query = select(
                    CIBuild.status,
                    func.count(CIBuild.id).label('count')
                ).where(
                    CIBuild.created_at >= start_date
                ).group_by(CIBuild.status)
                
                builds_by_status_result = await session.execute(builds_by_status_query)
                builds_by_status = {row[0]: row[1] for row in builds_by_status_result}
                
                # Temps de build moyen
                avg_duration_query = select(
                    func.avg(
                        func.extract('epoch', CIBuild.completed_at - CIBuild.started_at)
                    )
                ).where(
                    and_(
                        CIBuild.created_at >= start_date,
                        CIBuild.started_at.isnot(None),
                        CIBuild.completed_at.isnot(None),
                        CIBuild.status == BuildStatus.SUCCESS.value
                    )
                )
                avg_duration = await session.scalar(avg_duration_query) or 0
                
                # Taux de succès
                success_rate = 0
                if total_builds > 0:
                    successful_builds = builds_by_status.get(BuildStatus.SUCCESS.value, 0)
                    success_rate = (successful_builds / total_builds) * 100
                
                # Builds par intégration
                builds_by_integration_query = select(
                    GitHubIntegration.name,
                    func.count(CIBuild.id).label('count')
                ).join(
                    CIBuild, GitHubIntegration.id == CIBuild.integration_id
                ).where(
                    CIBuild.created_at >= start_date
                ).group_by(GitHubIntegration.name)
                
                builds_by_integration_result = await session.execute(builds_by_integration_query)
                builds_by_integration = {row[0]: row[1] for row in builds_by_integration_result}
                
                return {
                    "period_days": days,
                    "total_builds": total_builds,
                    "builds_by_status": builds_by_status,
                    "success_rate_percent": round(success_rate, 2),
                    "average_duration_seconds": round(avg_duration, 2),
                    "builds_by_integration": builds_by_integration,
                    "generated_at": end_date.isoformat()
                }
                
        except Exception as e:
            logger.error(f"Erreur calcul métriques pipeline: {e}")
            return {}

    # Méthodes privées

    async def _process_build_queue(self):
        """Traite la queue des builds"""
        while True:
            try:
                # Limiter le nombre de builds concurrents
                if len(self.active_builds) >= self.max_concurrent_builds:
                    await asyncio.sleep(5)
                    continue
                
                # Récupérer le prochain build
                build_data = await self.build_queue.get()
                
                # Créer et lancer la tâche de build
                task = asyncio.create_task(
                    self._execute_build(build_data)
                )
                self.active_builds[build_data["build_id"]] = task
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur traitement queue builds: {e}")

    async def _execute_build(self, build_data: Dict[str, Any]):
        """Exécute un build"""
        build_id = build_data["build_id"]
        integration = build_data["integration"]
        
        try:
            # Mettre à jour le statut
            await self._update_build_status(build_id, BuildStatus.IN_PROGRESS)
            
            # Simuler l'exécution du build (à remplacer par l'appel réel à GitHub Actions)
            await self._simulate_github_actions_build(build_id, integration, build_data)
            
        except asyncio.CancelledError:
            await self._update_build_status(build_id, BuildStatus.CANCELLED)
        except Exception as e:
            logger.error(f"Erreur exécution build {build_id}: {e}")
            await self._update_build_status(
                build_id, 
                BuildStatus.FAILURE, 
                error_message=str(e)
            )
        finally:
            # Nettoyer
            if build_id in self.active_builds:
                del self.active_builds[build_id]

    async def _simulate_github_actions_build(
        self, 
        build_id: str, 
        integration: GitHubIntegration, 
        build_data: Dict[str, Any]
    ):
        """
        Simule l'exécution d'un build GitHub Actions
        (À remplacer par l'intégration réelle avec l'API GitHub)
        """
        # Simuler différentes étapes du build
        steps = [
            ("Checkout", 5),
            ("Setup Environment", 10),
            ("Install Dependencies", 15),
            ("Run Tests", 20),
            ("Security Scan", 10),
            ("Build Artifacts", 15),
            ("Deploy", 10)
        ]
        
        sum(step[1] for step in steps)
        
        for step_name, duration in steps:
            await asyncio.sleep(duration / 10)  # Accélérer pour la démo
            logger.info(f"Build {build_id}: {step_name} terminé")
        
        # Simuler les résultats
        security_report = {
            "vulnerabilities_found": 0,
            "security_score": 95,
            "scan_duration": 10
        }
        
        test_results = {
            "total_tests": 150,
            "passed": 148,
            "failed": 2,
            "coverage_percent": 87.5
        }
        
        # Déterminer le statut final (95% de succès)
        import random
        success = random.random() < 0.95
        
        if success:
            await self._update_build_status(
                build_id,
                BuildStatus.SUCCESS,
                security_report=security_report,
                test_results=test_results,
                logs_url=f"https://github.com/{integration.repository}/actions/runs/{build_id}",
                artifacts_url=f"https://github.com/{integration.repository}/actions/runs/{build_id}/artifacts"
            )
        else:
            await self._update_build_status(
                build_id,
                BuildStatus.FAILURE,
                error_message="Tests unitaires échoués",
                test_results=test_results
            )

    async def _update_build_status(
        self,
        build_id: str,
        status: BuildStatus,
        error_message: str = None,
        security_report: Dict[str, Any] = None,
        test_results: Dict[str, Any] = None,
        logs_url: str = None,
        artifacts_url: str = None
    ):
        """Met à jour le statut d'un build"""
        try:
            async with get_async_session() as session:
                build = await session.execute(
                    select(CIBuild).where(CIBuild.build_id == build_id)
                )
                build_record = build.scalar_one_or_none()
                
                if build_record:
                    build_record.status = status.value
                    
                    if status == BuildStatus.IN_PROGRESS and not build_record.started_at:
                        build_record.started_at = datetime.utcnow()
                    
                    if status in [BuildStatus.SUCCESS, BuildStatus.FAILURE, BuildStatus.CANCELLED, BuildStatus.TIMEOUT]:
                        build_record.completed_at = datetime.utcnow()
                    
                    if error_message:
                        build_record.error_message = error_message
                    
                    if security_report:
                        build_record.security_report = security_report
                    
                    if test_results:
                        build_record.test_results = test_results
                    
                    if logs_url:
                        build_record.logs_url = logs_url
                    
                    if artifacts_url:
                        build_record.artifacts_url = artifacts_url
                    
                    await session.commit()
                    
        except Exception as e:
            logger.error(f"Erreur mise à jour statut build {build_id}: {e}")

    async def _verify_webhook_signature(self, headers: Dict[str, str], payload: bytes) -> bool:
        """Vérifie la signature d'un webhook GitHub"""
        if not self.github_webhook_secret:
            logger.warning("Secret webhook non configuré - signature non vérifiée")
            return True  # En mode développement
        
        signature_header = headers.get('X-Hub-Signature-256', '')
        if not signature_header.startswith('sha256='):
            return False
        
        expected_signature = signature_header[7:]  # Enlever 'sha256='
        
        computed_signature = hmac.new(
            self.github_webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, computed_signature)

    async def _parse_webhook_payload(self, event_type: str, payload: Dict[str, Any]) -> WebhookPayload:
        """Parse un payload webhook GitHub"""
        repository = payload.get('repository', {}).get('full_name', 'unknown')
        
        if event_type == 'push':
            return WebhookPayload(
                event_type=WebhookEvent.PUSH,
                repository=repository,
                branch=payload.get('ref', '').replace('refs/heads/', ''),
                commit_sha=payload.get('head_commit', {}).get('id', ''),
                author=payload.get('head_commit', {}).get('author', {}).get('name', ''),
                message=payload.get('head_commit', {}).get('message', ''),
                timestamp=datetime.utcnow(),
                raw_payload=payload
            )
        
        elif event_type == 'workflow_run':
            return WebhookPayload(
                event_type=WebhookEvent.WORKFLOW_RUN,
                repository=repository,
                branch=payload.get('workflow_run', {}).get('head_branch', ''),
                commit_sha=payload.get('workflow_run', {}).get('head_sha', ''),
                author=payload.get('workflow_run', {}).get('actor', {}).get('login', ''),
                message=f"Workflow: {payload.get('workflow_run', {}).get('name', '')}",
                timestamp=datetime.utcnow(),
                workflow_run_id=payload.get('workflow_run', {}).get('id'),
                raw_payload=payload
            )
        
        # Autres types d'événements...
        return WebhookPayload(
            event_type=WebhookEvent(event_type) if event_type in [e.value for e in WebhookEvent] else WebhookEvent.PUSH,
            repository=repository,
            branch='unknown',
            commit_sha='unknown',
            author='unknown',
            message=f'Événement {event_type}',
            timestamp=datetime.utcnow(),
            raw_payload=payload
        )

    async def _process_webhook_event(
        self, 
        integration: GitHubIntegration, 
        webhook_event: WebhookPayload
    ) -> Dict[str, Any]:
        """Traite un événement webhook"""
        try:
            if webhook_event.event_type == WebhookEvent.PUSH:
                # Déclencher un build si auto-deploy activé
                if integration.auto_deploy and webhook_event.branch == integration.branch:
                    build_id = await self.trigger_build(
                        integration.id,
                        webhook_event.branch,
                        manual=False
                    )
                    return {"action": "build_triggered", "build_id": build_id}
            
            elif webhook_event.event_type == WebhookEvent.WORKFLOW_RUN:
                # Traiter le résultat d'un workflow
                return {"action": "workflow_status_updated"}
            
            return {"action": "event_processed"}
            
        except Exception as e:
            logger.error(f"Erreur traitement événement webhook: {e}")
            return {"action": "error", "message": str(e)}

    async def _load_github_configurations(self):
        """Charge les configurations GitHub depuis la base de données"""
        try:
            async with get_async_session() as session:
                integrations = await session.execute(
                    select(GitHubIntegration).where(GitHubIntegration.is_active == True)
                )
                
                for integration in integrations.scalars():
                    config = GitHubActionConfig(**integration.configuration)
                    key = f"{integration.repository}/{integration.workflow_file}"
                    self.github_configs[key] = config
                    
                logger.info(f"Chargé {len(self.github_configs)} configurations GitHub")
                
        except Exception as e:
            logger.error(f"Erreur chargement configurations GitHub: {e}")

    async def _verify_github_connection(self):
        """Vérifie la connectivité avec GitHub"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'token {self.github_token}',
                    'Accept': 'application/vnd.github.v3+json'
                }
                
                async with session.get(f"{self.github_api_url}/user", headers=headers) as response:
                    if response.status == 200:
                        user_data = await response.json()
                        logger.info(f"Connecté à GitHub en tant que: {user_data.get('login')}")
                    else:
                        logger.warning(f"Problème de connexion GitHub: {response.status}")
                        
        except Exception as e:
            logger.error(f"Erreur vérification connexion GitHub: {e}")

# Instance globale du service
_cicd_service: Optional[CICDService] = None

def get_cicd_service() -> CICDService:
    """Factory pour obtenir l'instance du service CI/CD"""
    global _cicd_service
    
    if _cicd_service is None:
        _cicd_service = CICDService()
    
    return _cicd_service
