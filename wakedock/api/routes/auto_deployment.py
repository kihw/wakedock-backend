"""
WakeDock - API Routes pour déploiement automatique de containers
==============================================================

Routes FastAPI pour gestion complète déploiements automatiques:
- Configuration déploiements depuis repositories Git
- Déclenchement manuel et automatique via webhooks
- Gestion secrets chiffrés pour containers
- Monitoring santé et métriques déploiements
- Rollback automatique et manuel
- Logs et historique complets

Sécurité:
- Authentification utilisateur requise
- Permissions RBAC granulaires
- Validation données d'entrée
- Audit trail complet
- Rate limiting sur déclenchements

API Design:
- REST standard avec codes HTTP appropriés
- Réponses JSON structurées
- Pagination pour listes
- Filtres et tri avancés
- Streaming logs temps réel

Auteur: WakeDock Development Team
Version: 0.4.2
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from wakedock.core.auto_deployment_service import AutoDeploymentService
from wakedock.core.dependencies import (
    get_auto_deployment_service,
    get_current_user,
    get_db,
)
from wakedock.core.rbac_service import get_rbac_service, RBACService
from wakedock.models.deployment import (
    AutoDeployment,
    DeploymentHistory,
    DeploymentSecret,
)
from wakedock.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auto-deploy", tags=["Auto Deployment"])

# ================================
# Modèles Pydantic pour validation
# ================================

class AutoDeploymentCreate(BaseModel):
    """Modèle création déploiement automatique"""
    name: str = Field(..., min_length=1, max_length=100, description="Nom unique du déploiement")
    repository_url: str = Field(..., description="URL du repository Git")
    branch: str = Field(default="main", description="Branche Git à déployer")
    dockerfile_path: str = Field(default="Dockerfile", description="Chemin relatif vers Dockerfile")
    auto_deploy: bool = Field(default=True, description="Déploiement automatique sur push")
    environment: str = Field(default="development", description="Environnement de déploiement")
    container_config: Optional[Dict[str, Any]] = Field(default={}, description="Configuration container JSON")
    
    @validator('repository_url')
    def validate_repository_url(cls, v):
        if not v.startswith(('https://', 'git@')):
            raise ValueError('URL repository doit commencer par https:// ou git@')
        return v
    
    @validator('environment')
    def validate_environment(cls, v):
        if v not in ['development', 'staging', 'production']:
            raise ValueError('Environnement doit être: development, staging, ou production')
        return v
    
    @validator('name')
    def validate_name(cls, v):
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Nom doit contenir uniquement lettres, chiffres, _ et -')
        return v

class AutoDeploymentUpdate(BaseModel):
    """Modèle mise à jour déploiement automatique"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    branch: Optional[str] = None
    dockerfile_path: Optional[str] = None
    auto_deploy: Optional[bool] = None
    environment: Optional[str] = None
    container_config: Optional[Dict[str, Any]] = None
    
    @validator('environment')
    def validate_environment(cls, v):
        if v is not None and v not in ['development', 'staging', 'production']:
            raise ValueError('Environnement doit être: development, staging, ou production')
        return v

class DeploymentTrigger(BaseModel):
    """Modèle déclenchement déploiement"""
    commit_sha: Optional[str] = Field(None, description="SHA commit spécifique")
    force: bool = Field(default=False, description="Forcer même si déploiement en cours")
    environment_override: Optional[str] = Field(None, description="Surcharger environnement")

class SecretCreate(BaseModel):
    """Modèle création secret"""
    key: str = Field(..., min_length=1, max_length=100, description="Nom variable environnement")
    value: str = Field(..., min_length=1, description="Valeur du secret")
    description: Optional[str] = Field(None, max_length=200, description="Description optionnelle")
    
    @validator('key')
    def validate_key(cls, v):
        import re
        if not re.match(r'^[A-Z][A-Z0-9_]*$', v):
            raise ValueError('Clé doit être en MAJUSCULES avec underscores uniquement')
        return v

class WebhookPayload(BaseModel):
    """Modèle payload webhook Git"""
    repository: Dict[str, Any]
    ref: str
    commits: List[Dict[str, Any]]
    head_commit: Optional[Dict[str, Any]] = None

class DeploymentResponse(BaseModel):
    """Modèle réponse déploiement"""
    id: int
    name: str
    status: str
    repository_url: str
    branch: str
    environment: str
    auto_deploy: bool
    current_container_id: Optional[str]
    last_deployed_at: Optional[datetime]
    created_at: datetime

class DeploymentHistoryResponse(BaseModel):
    """Modèle réponse historique déploiement"""
    id: int
    deployment_id: int
    commit_sha: str
    trigger_type: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    triggered_by: int

class MetricsResponse(BaseModel):
    """Modèle réponse métriques"""
    total_deployments: int
    successful_deployments: int
    failed_deployments: int
    success_rate: float
    average_deployment_time: float
    rollbacks_performed: int
    active_deployments: int

# =====================================
# Routes CRUD Déploiements Automatiques
# =====================================

@router.post("/deployments", response_model=DeploymentResponse, status_code=201)
async def create_auto_deployment(
    deployment_data: AutoDeploymentCreate,
    current_user: User = Depends(get_current_user),
    deployment_service: AutoDeploymentService = Depends(get_auto_deployment_service),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Créer nouvelle configuration de déploiement automatique
    
    Permissions requises: deployment.create
    """
    try:
        # Vérifier permissions
        await rbac_service.check_permission(current_user.id, "deployment.create")
        
        # Créer déploiement
        deployment = await deployment_service.create_auto_deployment(
            user_id=current_user.id,
            config=deployment_data.dict()
        )
        
        logger.info(f"✅ Déploiement automatique créé: {deployment.id} par utilisateur {current_user.id}")
        
        return DeploymentResponse(
            id=deployment.id,
            name=deployment.name,
            status=deployment.status,
            repository_url=deployment.repository_url,
            branch=deployment.branch,
            environment=deployment.environment,
            auto_deploy=deployment.auto_deploy,
            current_container_id=deployment.current_container_id,
            last_deployed_at=deployment.last_deployed_at,
            created_at=deployment.created_at
        )
        
    except Exception as e:
        logger.error(f"❌ Erreur création déploiement automatique: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/deployments", response_model=List[DeploymentResponse])
async def list_auto_deployments(
    environment: Optional[str] = Query(None, description="Filtrer par environnement"),
    status: Optional[str] = Query(None, description="Filtrer par statut"),
    limit: int = Query(50, ge=1, le=100, description="Nombre maximum de résultats"),
    offset: int = Query(0, ge=0, description="Offset pour pagination"),
    current_user: User = Depends(get_current_user),
    deployment_service: AutoDeploymentService = Depends(get_auto_deployment_service),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Lister déploiements automatiques de l'utilisateur
    
    Permissions requises: deployment.view
    """
    try:
        await rbac_service.check_permission(current_user.id, "deployment.view")
        
        deployments = await deployment_service.list_deployments(
            user_id=current_user.id,
            limit=limit,
            environment=environment
        )
        
        # Filtrer par statut si spécifié
        if status:
            deployments = [d for d in deployments if d["status"] == status]
            
        # Pagination manuelle
        paginated = deployments[offset:offset + limit]
        
        return [
            DeploymentResponse(
                id=d["id"],
                name=d["name"],
                status=d["status"],
                repository_url=d["repository_url"],
                branch=d["branch"],
                environment=d["environment"],
                auto_deploy=d["auto_deploy"],
                current_container_id=d.get("current_container_id"),
                last_deployed_at=datetime.fromisoformat(d["last_deployed_at"]) if d["last_deployed_at"] else None,
                created_at=datetime.fromisoformat(d["created_at"])
            )
            for d in paginated
        ]
        
    except Exception as e:
        logger.error(f"❌ Erreur liste déploiements: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/deployments/{deployment_id}", response_model=Dict[str, Any])
async def get_auto_deployment(
    deployment_id: int,
    current_user: User = Depends(get_current_user),
    deployment_service: AutoDeploymentService = Depends(get_auto_deployment_service),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Récupérer détails complets d'un déploiement automatique
    
    Permissions requises: deployment.view
    """
    try:
        await rbac_service.check_permission(current_user.id, "deployment.view")
        
        deployment_status = await deployment_service.get_deployment_status(
            deployment_id=deployment_id,
            user_id=current_user.id
        )
        
        return deployment_status
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Erreur récupération déploiement {deployment_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/deployments/{deployment_id}", response_model=DeploymentResponse)
async def update_auto_deployment(
    deployment_id: int,
    update_data: AutoDeploymentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Mettre à jour configuration déploiement automatique
    
    Permissions requises: deployment.update
    """
    try:
        await rbac_service.check_permission(current_user.id, "deployment.update")
        
        # Récupérer déploiement
        result = await db.execute(
            select(AutoDeployment).where(
                AutoDeployment.id == deployment_id,
                AutoDeployment.user_id == current_user.id
            )
        )
        deployment = result.scalar_one_or_none()
        
        if not deployment:
            raise HTTPException(status_code=404, detail="Déploiement non trouvé")
            
        # Mettre à jour champs
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(deployment, field, value)
            
        deployment.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(deployment)
        
        logger.info(f"✅ Déploiement {deployment_id} mis à jour par utilisateur {current_user.id}")
        
        return DeploymentResponse(
            id=deployment.id,
            name=deployment.name,
            status=deployment.status,
            repository_url=deployment.repository_url,
            branch=deployment.branch,
            environment=deployment.environment,
            auto_deploy=deployment.auto_deploy,
            current_container_id=deployment.current_container_id,
            last_deployed_at=deployment.last_deployed_at,
            created_at=deployment.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur mise à jour déploiement {deployment_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/deployments/{deployment_id}", status_code=204)
async def delete_auto_deployment(
    deployment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Supprimer déploiement automatique
    
    Permissions requises: deployment.delete
    """
    try:
        await rbac_service.check_permission(current_user.id, "deployment.delete")
        
        # Récupérer déploiement
        result = await db.execute(
            select(AutoDeployment).where(
                AutoDeployment.id == deployment_id,
                AutoDeployment.user_id == current_user.id
            )
        )
        deployment = result.scalar_one_or_none()
        
        if not deployment:
            raise HTTPException(status_code=404, detail="Déploiement non trouvé")
            
        # Supprimer container s'il existe
        if deployment.current_container_id:
            try:
                import docker
                docker_client = docker.from_env()
                container = docker_client.containers.get(deployment.current_container_id)
                container.stop(timeout=10)
                container.remove()
                logger.info(f"🗑️ Container supprimé: {deployment.current_container_id}")
            except:
                pass  # Container peut déjà être supprimé
                
        # Supprimer déploiement
        await db.delete(deployment)
        await db.commit()
        
        logger.info(f"✅ Déploiement {deployment_id} supprimé par utilisateur {current_user.id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur suppression déploiement {deployment_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# ========================================
# Routes Déclenchement et Contrôle
# ========================================

@router.post("/deployments/{deployment_id}/deploy", status_code=202)
async def trigger_deployment(
    deployment_id: int,
    trigger_data: DeploymentTrigger,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    deployment_service: AutoDeploymentService = Depends(get_auto_deployment_service),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Déclencher déploiement manuel
    
    Permissions requises: deployment.deploy
    """
    try:
        await rbac_service.check_permission(current_user.id, "deployment.deploy")
        
        # Déclencher déploiement
        deployment_task_id = await deployment_service.trigger_deployment(
            deployment_id=deployment_id,
            user_id=current_user.id,
            manual=True,
            commit_sha=trigger_data.commit_sha
        )
        
        logger.info(f"🚀 Déploiement {deployment_id} déclenché manuellement par utilisateur {current_user.id}")
        
        return {
            "message": "Déploiement déclenché avec succès",
            "deployment_id": deployment_id,
            "task_id": deployment_task_id,
            "status": "queued"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Erreur déclenchement déploiement {deployment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/deployments/{deployment_id}/rollback", status_code=202)
async def rollback_deployment(
    deployment_id: int,
    current_user: User = Depends(get_current_user),
    deployment_service: AutoDeploymentService = Depends(get_auto_deployment_service),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Déclencher rollback manuel vers version précédente
    
    Permissions requises: deployment.rollback
    """
    try:
        await rbac_service.check_permission(current_user.id, "deployment.rollback")
        
        # Déclencher rollback
        rollback_task_id = await deployment_service.rollback_deployment(
            deployment_id=deployment_id,
            user_id=current_user.id
        )
        
        logger.info(f"⏪ Rollback {deployment_id} déclenché par utilisateur {current_user.id}")
        
        return {
            "message": "Rollback déclenché avec succès",
            "deployment_id": deployment_id,
            "task_id": rollback_task_id,
            "status": "queued"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Erreur rollback déploiement {deployment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/deployments/{deployment_id}/cancel", status_code=200)
async def cancel_deployment(
    deployment_id: int,
    current_user: User = Depends(get_current_user),
    deployment_service: AutoDeploymentService = Depends(get_auto_deployment_service),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Annuler déploiement en cours
    
    Permissions requises: deployment.cancel
    """
    try:
        await rbac_service.check_permission(current_user.id, "deployment.cancel")
        
        # Annuler déploiement
        cancelled = await deployment_service.cancel_deployment(
            deployment_id=deployment_id,
            user_id=current_user.id
        )
        
        if cancelled:
            logger.info(f"🚫 Déploiement {deployment_id} annulé par utilisateur {current_user.id}")
            return {"message": "Déploiement annulé avec succès", "cancelled": True}
        else:
            return {"message": "Aucun déploiement actif à annuler", "cancelled": False}
            
    except Exception as e:
        logger.error(f"❌ Erreur annulation déploiement {deployment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================
# Routes Webhooks Git
# ============================

@router.post("/webhooks/{deployment_id}", status_code=200)
async def handle_git_webhook(
    deployment_id: int,
    payload: WebhookPayload,
    background_tasks: BackgroundTasks,
    deployment_service: AutoDeploymentService = Depends(get_auto_deployment_service),
    db: AsyncSession = Depends(get_db)
):
    """
    Gérer webhooks Git pour déploiement automatique
    
    Note: Endpoint public pour webhooks Git (pas d'auth utilisateur)
    """
    try:
        # Récupérer configuration déploiement
        result = await db.execute(
            select(AutoDeployment).where(AutoDeployment.id == deployment_id)
        )
        deployment = result.scalar_one_or_none()
        
        if not deployment:
            raise HTTPException(status_code=404, detail="Déploiement non trouvé")
            
        if not deployment.auto_deploy:
            return {"message": "Déploiement automatique désactivé", "triggered": False}
            
        # Vérifier branche
        ref_branch = payload.ref.replace('refs/heads/', '')
        if ref_branch != deployment.branch:
            return {"message": f"Branche ignorée: {ref_branch} (attendue: {deployment.branch})", "triggered": False}
            
        # Récupérer commit SHA
        commit_sha = None
        if payload.head_commit:
            commit_sha = payload.head_commit.get("id")
        elif payload.commits:
            commit_sha = payload.commits[-1].get("id")
            
        # Déclencher déploiement automatique
        deployment_task_id = await deployment_service.trigger_deployment(
            deployment_id=deployment_id,
            user_id=deployment.user_id,  # Utiliser propriétaire déploiement
            manual=False,
            commit_sha=commit_sha
        )
        
        logger.info(f"🔗 Webhook déploiement {deployment_id} déclenché: {commit_sha}")
        
        return {
            "message": "Déploiement déclenché par webhook",
            "deployment_id": deployment_id,
            "task_id": deployment_task_id,
            "commit_sha": commit_sha,
            "branch": ref_branch,
            "triggered": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur webhook déploiement {deployment_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ===============================
# Routes Historique et Logs
# ===============================

@router.get("/deployments/{deployment_id}/history", response_model=List[DeploymentHistoryResponse])
async def get_deployment_history(
    deployment_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="Filtrer par statut"),
    current_user: User = Depends(get_current_user),
    deployment_service: AutoDeploymentService = Depends(get_auto_deployment_service),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Récupérer historique des déploiements
    
    Permissions requises: deployment.view
    """
    try:
        await rbac_service.check_permission(current_user.id, "deployment.view")
        
        logs = await deployment_service.get_deployment_logs(
            deployment_id=deployment_id,
            user_id=current_user.id,
            limit=limit
        )
        
        # Filtrer par statut si spécifié
        if status:
            logs = [log for log in logs if log["status"] == status]
            
        # Pagination
        paginated_logs = logs[offset:offset + limit]
        
        return [
            DeploymentHistoryResponse(
                id=log["id"],
                deployment_id=deployment_id,
                commit_sha=log["commit_sha"],
                trigger_type=log["trigger_type"],
                status=log["status"],
                started_at=datetime.fromisoformat(log["started_at"]),
                completed_at=datetime.fromisoformat(log["completed_at"]) if log["completed_at"] else None,
                duration_seconds=log.get("duration_seconds"),
                triggered_by=log["triggered_by"]
            )
            for log in paginated_logs
        ]
        
    except Exception as e:
        logger.error(f"❌ Erreur historique déploiement {deployment_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/deployments/{deployment_id}/logs/{history_id}")
async def get_deployment_logs_detail(
    deployment_id: int,
    history_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Récupérer logs détaillés d'un déploiement spécifique
    
    Permissions requises: deployment.view
    """
    try:
        await rbac_service.check_permission(current_user.id, "deployment.view")
        
        # Vérifier autorisation
        result = await db.execute(
            select(DeploymentHistory)
            .join(AutoDeployment)
            .where(
                DeploymentHistory.id == history_id,
                DeploymentHistory.deployment_id == deployment_id,
                AutoDeployment.user_id == current_user.id
            )
        )
        history = result.scalar_one_or_none()
        
        if not history:
            raise HTTPException(status_code=404, detail="Historique de déploiement non trouvé")
            
        return {
            "id": history.id,
            "deployment_id": history.deployment_id,
            "commit_sha": history.commit_sha,
            "trigger_type": history.trigger_type,
            "status": history.status,
            "started_at": history.started_at.isoformat(),
            "completed_at": history.completed_at.isoformat() if history.completed_at else None,
            "logs": history.logs or "",
            "result_data": json.loads(history.result_data) if history.result_data else {},
            "error_message": history.error_message
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur logs déploiement {deployment_id}/{history_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# ==============================
# Routes Gestion Secrets
# ==============================

@router.post("/deployments/{deployment_id}/secrets", status_code=201)
async def create_deployment_secret(
    deployment_id: int,
    secret_data: SecretCreate,
    current_user: User = Depends(get_current_user),
    deployment_service: AutoDeploymentService = Depends(get_auto_deployment_service),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Créer secret chiffré pour déploiement
    
    Permissions requises: deployment.secrets
    """
    try:
        await rbac_service.check_permission(current_user.id, "deployment.secrets")
        
        # Créer secret
        secret = await deployment_service.create_deployment_secret(
            deployment_id=deployment_id,
            user_id=current_user.id,
            key=secret_data.key,
            value=secret_data.value
        )
        
        logger.info(f"🔐 Secret créé pour déploiement {deployment_id}: {secret_data.key}")
        
        return {
            "id": secret.id,
            "deployment_id": secret.deployment_id,
            "key": secret.key,
            "description": secret.description,
            "created_at": secret.created_at.isoformat()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Erreur création secret: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/deployments/{deployment_id}/secrets")
async def list_deployment_secrets(
    deployment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Lister secrets d'un déploiement (sans valeurs)
    
    Permissions requises: deployment.view
    """
    try:
        await rbac_service.check_permission(current_user.id, "deployment.view")
        
        # Vérifier autorisation
        result = await db.execute(
            select(AutoDeployment).where(
                AutoDeployment.id == deployment_id,
                AutoDeployment.user_id == current_user.id
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Déploiement non trouvé")
            
        # Récupérer secrets
        result = await db.execute(
            select(DeploymentSecret).where(DeploymentSecret.deployment_id == deployment_id)
        )
        secrets = result.scalars().all()
        
        return [
            {
                "id": secret.id,
                "key": secret.key,
                "description": secret.description,
                "created_at": secret.created_at.isoformat(),
                "last_used_at": secret.last_used_at.isoformat() if secret.last_used_at else None
            }
            for secret in secrets
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur liste secrets: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/deployments/{deployment_id}/secrets/{secret_id}", status_code=204)
async def delete_deployment_secret(
    deployment_id: int,
    secret_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Supprimer secret de déploiement
    
    Permissions requises: deployment.secrets
    """
    try:
        await rbac_service.check_permission(current_user.id, "deployment.secrets")
        
        # Vérifier autorisation
        result = await db.execute(
            select(DeploymentSecret)
            .join(AutoDeployment)
            .where(
                DeploymentSecret.id == secret_id,
                DeploymentSecret.deployment_id == deployment_id,
                AutoDeployment.user_id == current_user.id
            )
        )
        secret = result.scalar_one_or_none()
        
        if not secret:
            raise HTTPException(status_code=404, detail="Secret non trouvé")
            
        await db.delete(secret)
        await db.commit()
        
        logger.info(f"🗑️ Secret supprimé: {secret.key} (déploiement {deployment_id})")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur suppression secret: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# ===============================
# Routes Métriques et Monitoring
# ===============================

@router.get("/metrics", response_model=MetricsResponse)
async def get_deployment_metrics(
    days: int = Query(7, ge=1, le=90, description="Période en jours"),
    current_user: User = Depends(get_current_user),
    deployment_service: AutoDeploymentService = Depends(get_auto_deployment_service),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Récupérer métriques globales des déploiements
    
    Permissions requises: deployment.view
    """
    try:
        await rbac_service.check_permission(current_user.id, "deployment.view")
        
        metrics = await deployment_service.get_deployment_metrics(days=days)
        
        return MetricsResponse(
            total_deployments=metrics["total_deployments"],
            successful_deployments=metrics["successful_deployments"],
            failed_deployments=metrics["failed_deployments"],
            success_rate=metrics["success_rate"],
            average_deployment_time=metrics["average_deployment_time"],
            rollbacks_performed=metrics["rollbacks_performed"],
            active_deployments=metrics["active_deployments"]
        )
        
    except Exception as e:
        logger.error(f"❌ Erreur métriques déploiements: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/deployments/{deployment_id}/health")
async def get_container_health(
    deployment_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Récupérer état santé container actuel
    
    Permissions requises: deployment.view
    """
    try:
        await rbac_service.check_permission(current_user.id, "deployment.view")
        
        # Vérifier autorisation
        result = await db.execute(
            select(AutoDeployment).where(
                AutoDeployment.id == deployment_id,
                AutoDeployment.user_id == current_user.id
            )
        )
        deployment = result.scalar_one_or_none()
        
        if not deployment:
            raise HTTPException(status_code=404, detail="Déploiement non trouvé")
            
        if not deployment.current_container_id:
            return {"status": "no_container", "message": "Aucun container déployé"}
            
        # Vérifier statut container Docker
        try:
            import docker
            docker_client = docker.from_env()
            container = docker_client.containers.get(deployment.current_container_id)
            
            # Récupérer stats en temps réel
            stats = container.stats(stream=False)
            
            # Calculer utilisation CPU
            cpu_percent = 0
            if "cpu_stats" in stats and "precpu_stats" in stats:
                cpu_stats = stats["cpu_stats"]
                precpu_stats = stats["precpu_stats"]
                
                if cpu_stats.get("online_cpus", 0) > 0:
                    cpu_delta = cpu_stats["cpu_usage"]["total_usage"] - precpu_stats["cpu_usage"]["total_usage"]
                    system_delta = cpu_stats["system_cpu_usage"] - precpu_stats["system_cpu_usage"]
                    if system_delta > 0:
                        cpu_percent = (cpu_delta / system_delta) * cpu_stats["online_cpus"] * 100.0
                        
            # Calculer utilisation mémoire
            memory_usage = 0
            memory_limit = 0
            if "memory_stats" in stats:
                memory_usage = stats["memory_stats"].get("usage", 0)
                memory_limit = stats["memory_stats"].get("limit", 0)
                
            memory_percent = (memory_usage / memory_limit * 100) if memory_limit > 0 else 0
            
            return {
                "status": "healthy" if container.status == "running" else "unhealthy",
                "container_status": container.status,
                "container_id": container.id,
                "container_name": container.name,
                "created": container.attrs["Created"],
                "cpu_usage": round(cpu_percent, 2),
                "memory_usage": memory_usage,
                "memory_limit": memory_limit,
                "memory_percent": round(memory_percent, 2),
                "ports": container.ports,
                "networks": list(container.attrs["NetworkSettings"]["Networks"].keys())
            }
            
        except docker.errors.NotFound:
            return {"status": "container_not_found", "message": "Container non trouvé"}
        except Exception as e:
            return {"status": "error", "message": f"Erreur récupération état: {e}"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur santé container {deployment_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/dashboard")
async def get_deployment_dashboard(
    current_user: User = Depends(get_current_user),
    deployment_service: AutoDeploymentService = Depends(get_auto_deployment_service),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Récupérer données dashboard déploiements
    
    Permissions requises: deployment.view
    """
    try:
        await rbac_service.check_permission(current_user.id, "deployment.view")
        
        # Métriques globales
        metrics = await deployment_service.get_deployment_metrics(days=30)
        
        # Déploiements récents
        recent_deployments = await deployment_service.list_deployments(
            user_id=current_user.id,
            limit=10
        )
        
        # Statut par environnement
        env_stats = {}
        for deployment in recent_deployments:
            env = deployment["environment"]
            if env not in env_stats:
                env_stats[env] = {"total": 0, "active": 0, "failed": 0}
            env_stats[env]["total"] += 1
            if deployment["status"] == "deployed":
                env_stats[env]["active"] += 1
            elif deployment["status"] == "failed":
                env_stats[env]["failed"] += 1
                
        return {
            "metrics": metrics,
            "recent_deployments": recent_deployments[:5],  # 5 plus récents
            "environment_stats": env_stats,
            "active_deployments": metrics["active_deployments"],
            "queue_size": metrics["queue_size"],
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur dashboard déploiements: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Fonction utilitaire pour streaming logs en temps réel
async def stream_deployment_logs(deployment_id: int, history_id: int, db: AsyncSession):
    """Streamer logs de déploiement en temps réel"""
    
    last_position = 0
    
    while True:
        try:
            # Récupérer logs depuis dernière position
            result = await db.execute(
                select(DeploymentHistory.logs, DeploymentHistory.status)
                .where(DeploymentHistory.id == history_id)
            )
            row = result.first()
            
            if not row:
                break
                
            logs, status = row
            
            # Nouveau contenu depuis dernière lecture
            if logs and len(logs) > last_position:
                new_content = logs[last_position:]
                yield f"data: {json.dumps({'logs': new_content, 'status': status})}\n\n"
                last_position = len(logs)
                
            # Arrêter si déploiement terminé
            if status in ["success", "failed", "cancelled", "timeout"]:
                yield f"data: {json.dumps({'status': status, 'completed': True})}\n\n"
                break
                
            await asyncio.sleep(2)  # Polling toutes les 2 secondes
            
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            break

@router.get("/deployments/{deployment_id}/logs/{history_id}/stream")
async def stream_deployment_logs_endpoint(
    deployment_id: int,
    history_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    rbac_service: RBACService = Depends(get_rbac_service)
):
    """
    Streamer logs de déploiement en temps réel (Server-Sent Events)
    
    Permissions requises: deployment.view
    """
    try:
        await rbac_service.check_permission(current_user.id, "deployment.view")
        
        # Vérifier autorisation
        result = await db.execute(
            select(DeploymentHistory)
            .join(AutoDeployment)
            .where(
                DeploymentHistory.id == history_id,
                DeploymentHistory.deployment_id == deployment_id,
                AutoDeployment.user_id == current_user.id
            )
        )
        
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Historique de déploiement non trouvé")
            
        return StreamingResponse(
            stream_deployment_logs(deployment_id, history_id, db),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur streaming logs: {e}")
        raise HTTPException(status_code=400, detail=str(e))
