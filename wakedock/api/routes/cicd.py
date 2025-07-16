"""
Routes API pour l'intégration CI/CD avec GitHub Actions
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, Query
from pydantic import BaseModel, Field
from wakedock.core.cicd_service import (
    get_cicd_service,
    CICDService,
    GitHubActionConfig,
    BuildStatus,
    DeploymentEnvironment,
    BuildResult
)
from wakedock.core.auth_middleware import PermissionRequired
from wakedock.core.dependencies import get_current_user
from wakedock.models.user import User
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cicd", tags=["ci-cd"])

# Modèles Pydantic pour les requêtes/réponses

class GitHubIntegrationRequest(BaseModel):
    """Modèle pour créer une intégration GitHub"""
    name: str = Field(..., min_length=1, max_length=255)
    repository: str = Field(..., regex=r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$')
    workflow_file: str = Field(..., min_length=1)
    branch: str = Field(default="main", min_length=1)
    environment: DeploymentEnvironment = DeploymentEnvironment.DEVELOPMENT
    auto_deploy: bool = False
    security_checks: bool = True
    required_approvals: int = Field(default=0, ge=0, le=10)
    timeout_minutes: int = Field(default=30, ge=5, le=180)
    secrets: Dict[str, str] = {}
    variables: Dict[str, str] = {}

class GitHubIntegrationResponse(BaseModel):
    """Modèle de réponse pour une intégration GitHub"""
    id: int
    name: str
    repository: str
    workflow_file: str
    branch: str
    environment: str
    auto_deploy: bool
    security_checks: bool
    is_active: bool
    webhook_url: Optional[str]
    created_at: str
    created_by: int

class BuildRequest(BaseModel):
    """Modèle pour déclencher un build"""
    branch: Optional[str] = None
    environment_variables: Dict[str, str] = {}

class BuildResponse(BaseModel):
    """Modèle de réponse pour un build"""
    build_id: str
    integration_id: int
    branch: str
    commit_sha: str
    status: str
    triggered_by: Optional[int]
    is_manual: bool
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    duration_seconds: Optional[int]
    logs_url: Optional[str]
    error_message: Optional[str]

class DeploymentRequest(BaseModel):
    """Modèle pour déclencher un déploiement"""
    build_id: str
    environment: DeploymentEnvironment
    description: Optional[str] = ""
    health_check_url: Optional[str] = None

class PipelineMetricsResponse(BaseModel):
    """Modèle de réponse pour les métriques pipeline"""
    period_days: int
    total_builds: int
    builds_by_status: Dict[str, int]
    success_rate_percent: float
    average_duration_seconds: float
    builds_by_integration: Dict[str, int]
    generated_at: str

# Routes pour les intégrations GitHub

@router.post("/integrations", response_model=Dict[str, Any])
@PermissionRequired("cicd.create")
async def create_github_integration(
    integration_request: GitHubIntegrationRequest,
    current_user: User = Depends(get_current_user),
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Crée une nouvelle intégration GitHub Actions
    """
    try:
        config = GitHubActionConfig(**integration_request.dict())
        result = await cicd_service.register_github_integration(config, current_user.id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur création intégration GitHub: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la création de l'intégration")

@router.get("/integrations", response_model=List[GitHubIntegrationResponse])
@PermissionRequired("cicd.view")
async def list_github_integrations(
    current_user: User = Depends(get_current_user),
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Liste toutes les intégrations GitHub Actions
    """
    try:
        # Cette fonction devrait être implémentée dans le service
        # Pour l'instant, retourner une liste vide
        return []
    except Exception as e:
        logger.error(f"Erreur récupération intégrations: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération des intégrations")

@router.get("/integrations/{integration_id}", response_model=GitHubIntegrationResponse)
@PermissionRequired("cicd.view")
async def get_github_integration(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Récupère une intégration GitHub Actions spécifique
    """
    try:
        # À implémenter dans le service
        raise HTTPException(status_code=501, detail="Non implémenté")
    except Exception as e:
        logger.error(f"Erreur récupération intégration {integration_id}: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération de l'intégration")

@router.put("/integrations/{integration_id}")
@PermissionRequired("cicd.update")
async def update_github_integration(
    integration_id: int,
    integration_request: GitHubIntegrationRequest,
    current_user: User = Depends(get_current_user),
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Met à jour une intégration GitHub Actions
    """
    try:
        # À implémenter dans le service
        raise HTTPException(status_code=501, detail="Non implémenté")
    except Exception as e:
        logger.error(f"Erreur mise à jour intégration {integration_id}: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la mise à jour de l'intégration")

@router.delete("/integrations/{integration_id}")
@PermissionRequired("cicd.delete")
async def delete_github_integration(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Supprime une intégration GitHub Actions
    """
    try:
        # À implémenter dans le service
        raise HTTPException(status_code=501, detail="Non implémenté")
    except Exception as e:
        logger.error(f"Erreur suppression intégration {integration_id}: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la suppression de l'intégration")

# Routes pour les builds

@router.post("/integrations/{integration_id}/builds", response_model=Dict[str, str])
@PermissionRequired("cicd.build")
async def trigger_build(
    integration_id: int,
    build_request: BuildRequest,
    current_user: User = Depends(get_current_user),
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Déclenche un build manuellement
    """
    try:
        build_id = await cicd_service.trigger_build(
            integration_id=integration_id,
            branch=build_request.branch,
            user_id=current_user.id,
            manual=True
        )
        
        return {
            "build_id": build_id,
            "status": "triggered",
            "message": "Build déclenché avec succès"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur déclenchement build: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors du déclenchement du build")

@router.get("/builds", response_model=List[BuildResponse])
@PermissionRequired("cicd.view")
async def list_builds(
    integration_id: Optional[int] = Query(None, description="Filtrer par intégration"),
    status: Optional[BuildStatus] = Query(None, description="Filtrer par statut"),
    limit: int = Query(50, ge=1, le=500, description="Nombre maximum de builds"),
    current_user: User = Depends(get_current_user),
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Liste l'historique des builds avec filtres
    """
    try:
        builds = await cicd_service.get_builds_history(
            integration_id=integration_id,
            status=status,
            limit=limit
        )
        
        return [BuildResponse(**build) for build in builds]
    except Exception as e:
        logger.error(f"Erreur récupération builds: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération des builds")

@router.get("/builds/{build_id}", response_model=BuildResult)
@PermissionRequired("cicd.view")
async def get_build_status(
    build_id: str,
    current_user: User = Depends(get_current_user),
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Récupère le statut détaillé d'un build
    """
    try:
        build_result = await cicd_service.get_build_status(build_id)
        if not build_result:
            raise HTTPException(status_code=404, detail="Build introuvable")
        
        return build_result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur récupération statut build {build_id}: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération du statut du build")

@router.post("/builds/{build_id}/cancel")
@PermissionRequired("cicd.build")
async def cancel_build(
    build_id: str,
    current_user: User = Depends(get_current_user),
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Annule un build en cours
    """
    try:
        success = await cicd_service.cancel_build(build_id, current_user.id)
        if not success:
            raise HTTPException(status_code=400, detail="Impossible d'annuler ce build")
        
        return {
            "build_id": build_id,
            "status": "cancelled",
            "cancelled_by": current_user.id,
            "cancelled_at": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur annulation build {build_id}: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de l'annulation du build")

@router.get("/builds/{build_id}/logs")
@PermissionRequired("cicd.view")
async def get_build_logs(
    build_id: str,
    current_user: User = Depends(get_current_user),
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Récupère les logs d'un build
    """
    try:
        build_result = await cicd_service.get_build_status(build_id)
        if not build_result:
            raise HTTPException(status_code=404, detail="Build introuvable")
        
        if build_result.logs_url:
            return {"logs_url": build_result.logs_url}
        else:
            return {"message": "Logs non disponibles pour ce build"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur récupération logs build {build_id}: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération des logs")

# Routes pour les webhooks

@router.post("/webhooks/{integration_id}")
async def handle_github_webhook(
    integration_id: int,
    request: Request,
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Endpoint pour recevoir les webhooks GitHub
    """
    try:
        # Récupérer le payload et les headers
        payload = await request.body()
        headers = dict(request.headers)
        client_ip = request.client.host if request.client else "unknown"
        
        # Traiter le webhook
        result = await cicd_service.handle_webhook(
            integration_id=integration_id,
            headers=headers,
            payload=payload,
            user_ip=client_ip
        )
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur traitement webhook {integration_id}: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors du traitement du webhook")

# Routes pour les métriques et dashboard

@router.get("/metrics", response_model=PipelineMetricsResponse)
@PermissionRequired("cicd.view")
async def get_pipeline_metrics(
    days: int = Query(30, ge=1, le=365, description="Nombre de jours pour les métriques"),
    current_user: User = Depends(get_current_user),
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Récupère les métriques des pipelines CI/CD
    """
    try:
        metrics = await cicd_service.get_pipeline_metrics(days=days)
        return PipelineMetricsResponse(**metrics)
    except Exception as e:
        logger.error(f"Erreur calcul métriques pipeline: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors du calcul des métriques")

@router.get("/dashboard/summary")
@PermissionRequired("cicd.view")
async def get_cicd_dashboard_summary(
    current_user: User = Depends(get_current_user),
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Récupère un résumé pour le dashboard CI/CD
    """
    try:
        # Métriques récentes
        recent_metrics = await cicd_service.get_pipeline_metrics(days=7)
        
        # Builds récents
        recent_builds = await cicd_service.get_builds_history(limit=10)
        
        # Builds actifs
        active_builds = [
            build for build in recent_builds 
            if build.get('status') in ['pending', 'in_progress']
        ]
        
        # Calculer le statut global
        total_recent = recent_metrics.get('total_builds', 0)
        success_rate = recent_metrics.get('success_rate_percent', 0)
        
        if success_rate >= 90:
            ci_status = "excellent"
        elif success_rate >= 75:
            ci_status = "good"
        elif success_rate >= 50:
            ci_status = "warning"
        else:
            ci_status = "critical"
        
        return {
            "summary": {
                "total_builds_7d": total_recent,
                "success_rate_7d": success_rate,
                "active_builds": len(active_builds),
                "average_duration": recent_metrics.get('average_duration_seconds', 0)
            },
            "recent_builds": recent_builds[:5],
            "active_builds": active_builds,
            "ci_status": ci_status,
            "last_updated": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Erreur génération résumé dashboard: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la génération du résumé")

# Routes pour la gestion des secrets

@router.post("/secrets")
@PermissionRequired("cicd.admin")
async def create_secret(
    name: str,
    value: str,
    description: Optional[str] = "",
    scope: str = "global",
    scope_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Crée un nouveau secret chiffré
    """
    try:
        # À implémenter dans le service
        raise HTTPException(status_code=501, detail="Non implémenté")
    except Exception as e:
        logger.error(f"Erreur création secret: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la création du secret")

@router.get("/secrets")
@PermissionRequired("cicd.admin")
async def list_secrets(
    scope: Optional[str] = Query(None, description="Filtrer par portée"),
    current_user: User = Depends(get_current_user),
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Liste les secrets (sans les valeurs)
    """
    try:
        # À implémenter dans le service
        raise HTTPException(status_code=501, detail="Non implémenté")
    except Exception as e:
        logger.error(f"Erreur récupération secrets: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération des secrets")

@router.delete("/secrets/{secret_id}")
@PermissionRequired("cicd.admin")
async def delete_secret(
    secret_id: int,
    current_user: User = Depends(get_current_user),
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Supprime un secret
    """
    try:
        # À implémenter dans le service
        raise HTTPException(status_code=501, detail="Non implémenté")
    except Exception as e:
        logger.error(f"Erreur suppression secret {secret_id}: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la suppression du secret")

# Routes pour les déploiements

@router.post("/deployments")
@PermissionRequired("cicd.deploy")
async def trigger_deployment(
    deployment_request: DeploymentRequest,
    current_user: User = Depends(get_current_user),
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Déclenche un déploiement
    """
    try:
        # À implémenter dans le service
        raise HTTPException(status_code=501, detail="Non implémenté")
    except Exception as e:
        logger.error(f"Erreur déclenchement déploiement: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors du déclenchement du déploiement")

@router.get("/deployments")
@PermissionRequired("cicd.view")
async def list_deployments(
    environment: Optional[DeploymentEnvironment] = Query(None, description="Filtrer par environnement"),
    limit: int = Query(50, ge=1, le=500, description="Nombre maximum de déploiements"),
    current_user: User = Depends(get_current_user),
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Liste l'historique des déploiements
    """
    try:
        # À implémenter dans le service
        raise HTTPException(status_code=501, detail="Non implémenté")
    except Exception as e:
        logger.error(f"Erreur récupération déploiements: {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la récupération des déploiements")

# Routes pour la configuration et santé

@router.get("/health")
@PermissionRequired("cicd.view")
async def get_cicd_health(
    current_user: User = Depends(get_current_user),
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Vérifie l'état de santé du système CI/CD
    """
    try:
        queue_size = cicd_service.build_queue.qsize()
        active_builds_count = len(cicd_service.active_builds)
        github_connected = cicd_service.github_token is not None
        
        return {
            "status": "healthy",
            "queue_size": queue_size,
            "active_builds": active_builds_count,
            "max_concurrent_builds": cicd_service.max_concurrent_builds,
            "github_connected": github_connected,
            "webhook_secret_configured": cicd_service.github_webhook_secret is not None,
            "last_check": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "last_check": datetime.utcnow().isoformat()
        }

@router.get("/configuration")
@PermissionRequired("cicd.admin")
async def get_cicd_configuration(
    current_user: User = Depends(get_current_user),
    cicd_service: CICDService = Depends(get_cicd_service)
):
    """
    Récupère la configuration actuelle du système CI/CD
    """
    return {
        "max_concurrent_builds": cicd_service.max_concurrent_builds,
        "build_timeout_minutes": cicd_service.build_timeout_minutes,
        "github_api_url": cicd_service.github_api_url,
        "storage_path": str(cicd_service.storage_path),
        "github_token_configured": cicd_service.github_token is not None,
        "webhook_secret_configured": cicd_service.github_webhook_secret is not None
    }
