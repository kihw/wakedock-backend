"""
API Routes pour la gestion des environnements
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from wakedock.core.auth_middleware import require_authenticated_user
from wakedock.core.dependencies import get_environment_service
from wakedock.core.environment_service import (
    EnvironmentService,
    EnvironmentStatus,
    EnvironmentType,
    PromotionType,
)
from wakedock.database.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/environments", tags=["environments"])


# Modèles Pydantic pour les requêtes et réponses
class EnvironmentCreateRequest(BaseModel):
    """Modèle pour créer un environnement"""
    name: str = Field(..., description="Nom de l'environnement")
    type: EnvironmentType = Field(..., description="Type d'environnement")
    description: Optional[str] = Field(None, description="Description")
    config: Optional[Dict[str, Any]] = Field(None, description="Configuration spécifique")
    variables: Optional[Dict[str, str]] = Field(None, description="Variables d'environnement")


class EnvironmentUpdateRequest(BaseModel):
    """Modèle pour mettre à jour un environnement"""
    description: Optional[str] = Field(None, description="Nouvelle description")
    config: Optional[Dict[str, Any]] = Field(None, description="Nouvelle configuration")
    status: Optional[EnvironmentStatus] = Field(None, description="Nouveau statut")


class EnvironmentVariablesRequest(BaseModel):
    """Modèle pour définir les variables d'environnement"""
    variables: Dict[str, str] = Field(..., description="Variables à définir")
    overwrite: bool = Field(False, description="Remplacer les variables existantes")


class BuildPromotionRequest(BaseModel):
    """Modèle pour promouvoir un build"""
    build_id: str = Field(..., description="ID du build à promouvoir")
    source_environment: str = Field(..., description="Environnement source")
    target_environment: str = Field(..., description="Environnement cible")
    promotion_type: PromotionType = Field(PromotionType.MANUAL, description="Type de promotion")
    auto_approve: bool = Field(False, description="Approuver automatiquement")


class PromotionApprovalRequest(BaseModel):
    """Modèle pour approuver une promotion"""
    approved: bool = Field(..., description="Approuvé ou rejeté")
    comment: Optional[str] = Field("", description="Commentaire d'approbation")


class EnvironmentResponse(BaseModel):
    """Modèle de réponse pour les environnements"""
    id: int
    name: str
    type: str
    status: str
    description: str
    config: Dict[str, Any]
    variables: Dict[str, str]
    health_score: float
    last_deployment: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class PromotionResponse(BaseModel):
    """Modèle de réponse pour les promotions"""
    id: int
    build_id: str
    source_env: str
    target_env: str
    promotion_type: str
    status: str
    approvals_required: int
    approvals_received: int
    started_at: datetime
    completed_at: Optional[datetime]
    promoted_by: str


class EnvironmentHealthResponse(BaseModel):
    """Modèle de réponse pour la santé d'environnement"""
    environment_id: int
    environment_name: str
    health_score: float
    status: str
    last_check: Optional[datetime]
    metrics: Dict[str, Any]
    trend: str
    average_score: float
    history: List[Dict[str, Any]]


# Routes pour la gestion des environnements
@router.post("/", response_model=EnvironmentResponse)
async def create_environment(
    request: EnvironmentCreateRequest,
    environment_service: EnvironmentService = Depends(get_environment_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Crée un nouvel environnement
    
    Permissions requises: environment:create
    """
    try:
        env_info = await environment_service.create_environment(
            user_id=current_user.id,
            name=request.name,
            env_type=request.type,
            description=request.description or "",
            config=request.config,
            variables=request.variables
        )
        
        return EnvironmentResponse(
            id=env_info.id,
            name=env_info.name,
            type=env_info.type.value,
            status=env_info.status.value,
            description=env_info.description,
            config=env_info.config,
            variables=env_info.variables,
            health_score=env_info.health_score,
            last_deployment=env_info.last_deployment,
            created_at=env_info.created_at,
            updated_at=env_info.updated_at
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
        logger.error(f"Erreur lors de la création de l'environnement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.get("/", response_model=List[EnvironmentResponse])
async def list_environments(
    env_type: Optional[EnvironmentType] = None,
    status: Optional[EnvironmentStatus] = None,
    environment_service: EnvironmentService = Depends(get_environment_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Liste tous les environnements
    
    Permissions requises: environment:read
    """
    try:
        environments = await environment_service.list_environments(
            user_id=current_user.id,
            env_type=env_type,
            status=status
        )
        
        return [
            EnvironmentResponse(
                id=env.id,
                name=env.name,
                type=env.type.value,
                status=env.status.value,
                description=env.description,
                config=env.config,
                variables=env.variables,
                health_score=env.health_score,
                last_deployment=env.last_deployment,
                created_at=env.created_at,
                updated_at=env.updated_at
            )
            for env in environments
        ]
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur lors de la liste des environnements: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.get("/{environment_id}", response_model=EnvironmentResponse)
async def get_environment(
    environment_id: int,
    environment_service: EnvironmentService = Depends(get_environment_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Obtient les détails d'un environnement
    
    Permissions requises: environment:read
    """
    try:
        # Vérifier les permissions via la liste (qui fait déjà la vérification)
        environments = await environment_service.list_environments(current_user.id)
        env_info = next((env for env in environments if env.id == environment_id), None)
        
        if not env_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Environnement {environment_id} non trouvé"
            )
        
        return EnvironmentResponse(
            id=env_info.id,
            name=env_info.name,
            type=env_info.type.value,
            status=env_info.status.value,
            description=env_info.description,
            config=env_info.config,
            variables=env_info.variables,
            health_score=env_info.health_score,
            last_deployment=env_info.last_deployment,
            created_at=env_info.created_at,
            updated_at=env_info.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'environnement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.put("/{environment_id}", response_model=EnvironmentResponse)
async def update_environment(
    environment_id: int,
    request: EnvironmentUpdateRequest,
    environment_service: EnvironmentService = Depends(get_environment_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Met à jour un environnement
    
    Permissions requises: environment:update
    """
    try:
        env_info = await environment_service.update_environment(
            user_id=current_user.id,
            environment_id=environment_id,
            description=request.description,
            config=request.config,
            status=request.status
        )
        
        return EnvironmentResponse(
            id=env_info.id,
            name=env_info.name,
            type=env_info.type.value,
            status=env_info.status.value,
            description=env_info.description,
            config=env_info.config,
            variables=env_info.variables,
            health_score=env_info.health_score,
            last_deployment=env_info.last_deployment,
            created_at=env_info.created_at,
            updated_at=env_info.updated_at
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
        logger.error(f"Erreur lors de la mise à jour de l'environnement: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.put("/{environment_id}/variables")
async def set_environment_variables(
    environment_id: int,
    request: EnvironmentVariablesRequest,
    environment_service: EnvironmentService = Depends(get_environment_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Définit les variables d'environnement
    
    Permissions requises: environment:variables:update
    """
    try:
        variables = await environment_service.set_environment_variables(
            user_id=current_user.id,
            environment_id=environment_id,
            variables=request.variables,
            overwrite=request.overwrite
        )
        
        return {
            "environment_id": environment_id,
            "variables": variables,
            "count": len(variables),
            "overwrite": request.overwrite
        }
        
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
        logger.error(f"Erreur lors de la mise à jour des variables: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.get("/{environment_id}/health", response_model=EnvironmentHealthResponse)
async def get_environment_health(
    environment_id: int,
    environment_service: EnvironmentService = Depends(get_environment_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Obtient la santé d'un environnement
    
    Permissions requises: environment:health:read
    """
    try:
        health = await environment_service.get_environment_health(
            user_id=current_user.id,
            environment_id=environment_id
        )
        
        return EnvironmentHealthResponse(**health)
        
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
        logger.error(f"Erreur lors de la récupération de la santé: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


# Routes pour la promotion de builds
@router.post("/promotions", response_model=PromotionResponse)
async def create_build_promotion(
    request: BuildPromotionRequest,
    environment_service: EnvironmentService = Depends(get_environment_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Démarre une promotion de build
    
    Permissions requises: environment:promote:{target_environment}
    """
    try:
        promotion_info = await environment_service.promote_build(
            user_id=current_user.id,
            build_id=request.build_id,
            source_environment=request.source_environment,
            target_environment=request.target_environment,
            promotion_type=request.promotion_type,
            auto_approve=request.auto_approve
        )
        
        return PromotionResponse(
            id=promotion_info.id,
            build_id=promotion_info.build_id,
            source_env=promotion_info.source_env,
            target_env=promotion_info.target_env,
            promotion_type=promotion_info.promotion_type.value,
            status=promotion_info.status.value,
            approvals_required=promotion_info.approvals_required,
            approvals_received=promotion_info.approvals_received,
            started_at=promotion_info.started_at,
            completed_at=promotion_info.completed_at,
            promoted_by=promotion_info.promoted_by
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
        logger.error(f"Erreur lors de la promotion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.put("/promotions/{promotion_id}/approve", response_model=PromotionResponse)
async def approve_promotion(
    promotion_id: int,
    request: PromotionApprovalRequest,
    environment_service: EnvironmentService = Depends(get_environment_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Approuve ou rejette une promotion
    
    Permissions requises: environment:promotion:approve
    """
    try:
        promotion_info = await environment_service.approve_promotion(
            user_id=current_user.id,
            promotion_id=promotion_id,
            approved=request.approved,
            comment=request.comment
        )
        
        return PromotionResponse(
            id=promotion_info.id,
            build_id=promotion_info.build_id,
            source_env=promotion_info.source_env,
            target_env=promotion_info.target_env,
            promotion_type=promotion_info.promotion_type.value,
            status=promotion_info.status.value,
            approvals_required=promotion_info.approvals_required,
            approvals_received=promotion_info.approvals_received,
            started_at=promotion_info.started_at,
            completed_at=promotion_info.completed_at,
            promoted_by=promotion_info.promoted_by
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
        logger.error(f"Erreur lors de l'approbation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


# Routes utilitaires
@router.get("/types")
async def get_environment_types():
    """
    Retourne les types d'environnements disponibles
    """
    return {
        "types": [
            {
                "value": env_type.value,
                "label": env_type.value.title(),
                "description": f"Environnement {env_type.value}"
            }
            for env_type in EnvironmentType
        ]
    }


@router.get("/statuses")
async def get_environment_statuses():
    """
    Retourne les statuts d'environnements disponibles
    """
    return {
        "statuses": [
            {
                "value": status.value,
                "label": status.value.title(),
                "description": f"Statut {status.value}"
            }
            for status in EnvironmentStatus
        ]
    }


@router.get("/overview")
async def get_environments_overview(
    environment_service: EnvironmentService = Depends(get_environment_service),
    current_user: User = Depends(require_authenticated_user)
):
    """
    Vue d'ensemble des environnements
    
    Permissions requises: environment:read
    """
    try:
        environments = await environment_service.list_environments(current_user.id)
        
        # Statistiques par type
        by_type = {}
        by_status = {}
        total_health = 0
        
        for env in environments:
            # Par type
            env_type = env.type.value
            if env_type not in by_type:
                by_type[env_type] = {"count": 0, "healthy": 0, "total_health": 0}
            by_type[env_type]["count"] += 1
            by_type[env_type]["total_health"] += env.health_score
            if env.health_score >= 0.8:
                by_type[env_type]["healthy"] += 1
            
            # Par statut
            env_status = env.status.value
            by_status[env_status] = by_status.get(env_status, 0) + 1
            
            total_health += env.health_score
        
        # Calculer les moyennes
        for env_type in by_type:
            count = by_type[env_type]["count"]
            by_type[env_type]["avg_health"] = by_type[env_type]["total_health"] / count if count > 0 else 0
            by_type[env_type]["health_percentage"] = (by_type[env_type]["healthy"] / count * 100) if count > 0 else 0
        
        return {
            "total_environments": len(environments),
            "average_health": total_health / len(environments) if environments else 0,
            "by_type": by_type,
            "by_status": by_status,
            "healthy_environments": sum(1 for env in environments if env.health_score >= 0.8),
            "last_updated": datetime.utcnow()
        }
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Erreur lors de la vue d'ensemble: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )
