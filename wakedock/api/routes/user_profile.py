"""
Routes API pour la gestion des profils utilisateur et préférences
Extension des routes d'authentification pour la version 0.3.2
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, validator

from wakedock.core.user_profile_service import get_user_profile_service, UserProfileService
from wakedock.database.database import get_db
from wakedock.models.user import User
from wakedock.api.routes.auth import get_current_user, log_audit_action
from wakedock.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/profile", tags=["user-profile"])


# Modèles Pydantic pour les requêtes/réponses
class UserPreferences(BaseModel):
    theme: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    
    @validator('theme')
    def validate_theme(cls, v):
        if v is not None and v not in ["light", "dark", "auto", "high-contrast"]:
            raise ValueError("Thème non supporté")
        return v
    
    @validator('language')
    def validate_language(cls, v):
        if v is not None and v not in ["fr", "en", "es", "de", "it"]:
            raise ValueError("Langue non supportée")
        return v


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    preferences: Optional[UserPreferences] = None


class UserProfileResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    is_superuser: bool
    is_verified: bool
    created_at: str
    updated_at: str
    last_login: Optional[str]
    password_changed_at: Optional[str]
    preferences: dict
    security: dict
    permissions: List[str]
    roles: List[dict]
    activity: dict


class UserActivityResponse(BaseModel):
    id: int
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    success: bool
    error_message: Optional[str]
    created_at: str


class SecurityInfoResponse(BaseModel):
    password_age_days: Optional[int]
    failed_login_attempts: int
    is_account_locked: bool
    account_locked_until: Optional[str]
    is_verified: bool
    recent_activities_count: int
    failed_logins_week: int
    last_login: Optional[str]
    created_at: str


class AvailablePreferencesResponse(BaseModel):
    themes: List[str]
    languages: List[str]
    timezones: List[str]


@router.get("/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    profile_service: UserProfileService = Depends(get_user_profile_service),
    db: Session = Depends(get_db)
):
    """
    Récupère le profil complet de l'utilisateur connecté
    """
    profile = profile_service.get_user_profile(current_user.id, db)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil utilisateur non trouvé"
        )
    
    return UserProfileResponse(**profile)


@router.put("/me")
async def update_my_profile(
    profile_data: UpdateProfileRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    profile_service: UserProfileService = Depends(get_user_profile_service),
    db: Session = Depends(get_db)
):
    """
    Met à jour le profil de l'utilisateur connecté
    """
    # Convertir en dictionnaire pour le service
    update_data = profile_data.dict(exclude_unset=True)
    
    # Valider les données
    validation_errors = profile_service.validate_profile_data(update_data)
    if validation_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"validation_errors": validation_errors}
        )
    
    # Mettre à jour le profil
    success = profile_service.update_user_profile(current_user.id, update_data, db)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Erreur lors de la mise à jour du profil"
        )
    
    # Log d'audit
    log_audit_action(
        db, current_user, "profile_updated", True, request,
        details=f"Profil mis à jour: {list(update_data.keys())}"
    )
    
    return {"message": "Profil mis à jour avec succès"}


@router.patch("/me/preferences")
async def update_my_preferences(
    preferences: UserPreferences,
    request: Request,
    current_user: User = Depends(get_current_user),
    profile_service: UserProfileService = Depends(get_user_profile_service),
    db: Session = Depends(get_db)
):
    """
    Met à jour uniquement les préférences de l'utilisateur
    """
    prefs_data = preferences.dict(exclude_unset=True)
    
    if not prefs_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune préférence à mettre à jour"
        )
    
    success = profile_service.update_user_preferences(current_user.id, prefs_data, db)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Erreur lors de la mise à jour des préférences"
        )
    
    # Log d'audit
    log_audit_action(
        db, current_user, "preferences_updated", True, request,
        details=f"Préférences mises à jour: {list(prefs_data.keys())}"
    )
    
    return {"message": "Préférences mises à jour avec succès"}


@router.get("/me/activity", response_model=List[UserActivityResponse])
async def get_my_activity_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    profile_service: UserProfileService = Depends(get_user_profile_service),
    db: Session = Depends(get_db)
):
    """
    Récupère l'historique d'activité de l'utilisateur connecté
    """
    activities = profile_service.get_user_activity_history(current_user.id, db, limit, offset)
    
    return [UserActivityResponse(**activity) for activity in activities]


@router.get("/me/security", response_model=SecurityInfoResponse)
async def get_my_security_info(
    current_user: User = Depends(get_current_user),
    profile_service: UserProfileService = Depends(get_user_profile_service),
    db: Session = Depends(get_db)
):
    """
    Récupère les informations de sécurité de l'utilisateur connecté
    """
    security_info = profile_service.get_user_security_info(current_user.id, db)
    
    if not security_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Informations de sécurité non trouvées"
        )
    
    return SecurityInfoResponse(**security_info)


@router.get("/preferences/available", response_model=AvailablePreferencesResponse)
async def get_available_preferences(
    profile_service: UserProfileService = Depends(get_user_profile_service)
):
    """
    Récupère les options disponibles pour les préférences utilisateur
    """
    preferences = profile_service.get_available_preferences()
    return AvailablePreferencesResponse(**preferences)


# Routes pour les administrateurs (gestion d'autres utilisateurs)
@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_user_profile(
    user_id: int,
    current_user: User = Depends(get_current_user),
    profile_service: UserProfileService = Depends(get_user_profile_service),
    db: Session = Depends(get_db)
):
    """
    Récupère le profil d'un utilisateur spécifique (admin uniquement)
    """
    # Vérifier les permissions
    if not current_user.is_superuser and current_user.id != user_id:
        # Vérifier si l'utilisateur a la permission de voir les profils
        user_permissions = current_user.get_permissions()
        if "users:read" not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes pour voir ce profil"
            )
    
    profile = profile_service.get_user_profile(user_id, db)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profil utilisateur non trouvé"
        )
    
    return UserProfileResponse(**profile)


@router.put("/{user_id}")
async def update_user_profile(
    user_id: int,
    profile_data: UpdateProfileRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    profile_service: UserProfileService = Depends(get_user_profile_service),
    db: Session = Depends(get_db)
):
    """
    Met à jour le profil d'un utilisateur spécifique (admin uniquement)
    """
    # Vérifier les permissions
    if not current_user.is_superuser:
        user_permissions = current_user.get_permissions()
        if "users:update" not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes pour modifier ce profil"
            )
    
    # Convertir en dictionnaire
    update_data = profile_data.dict(exclude_unset=True)
    
    # Valider les données
    validation_errors = profile_service.validate_profile_data(update_data)
    if validation_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"validation_errors": validation_errors}
        )
    
    # Mettre à jour le profil
    success = profile_service.update_user_profile(user_id, update_data, db)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Erreur lors de la mise à jour du profil"
        )
    
    # Log d'audit
    target_user = db.query(User).filter(User.id == user_id).first()
    log_audit_action(
        db, current_user, "user_profile_updated", True, request,
        details=f"Profil de {target_user.username if target_user else user_id} mis à jour par admin: {list(update_data.keys())}"
    )
    
    return {"message": "Profil utilisateur mis à jour avec succès"}


@router.get("/{user_id}/activity", response_model=List[UserActivityResponse])
async def get_user_activity_history(
    user_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    profile_service: UserProfileService = Depends(get_user_profile_service),
    db: Session = Depends(get_db)
):
    """
    Récupère l'historique d'activité d'un utilisateur spécifique (admin uniquement)
    """
    # Vérifier les permissions
    if not current_user.is_superuser and current_user.id != user_id:
        user_permissions = current_user.get_permissions()
        if "audit:read" not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes pour voir l'historique d'activité"
            )
    
    activities = profile_service.get_user_activity_history(user_id, db, limit, offset)
    
    return [UserActivityResponse(**activity) for activity in activities]


@router.get("/{user_id}/security", response_model=SecurityInfoResponse)
async def get_user_security_info(
    user_id: int,
    current_user: User = Depends(get_current_user),
    profile_service: UserProfileService = Depends(get_user_profile_service),
    db: Session = Depends(get_db)
):
    """
    Récupère les informations de sécurité d'un utilisateur spécifique (admin uniquement)
    """
    # Vérifier les permissions
    if not current_user.is_superuser and current_user.id != user_id:
        user_permissions = current_user.get_permissions()
        if "users:read" not in user_permissions and "audit:read" not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes pour voir les informations de sécurité"
            )
    
    security_info = profile_service.get_user_security_info(user_id, db)
    
    if not security_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Informations de sécurité non trouvées"
        )
    
    return SecurityInfoResponse(**security_info)
