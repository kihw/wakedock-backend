"""
Routes d'authentification pour WakeDock
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from wakedock.core.auth_service import AuthService, get_auth_service
from wakedock.database.database import get_db
from wakedock.logging import get_logger
from wakedock.models.user import AuditLog, User

logger = get_logger(__name__)


router = APIRouter(prefix="/auth", tags=["authentication"])


# Modèles Pydantic pour les requêtes/réponses
class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: bool = False


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: dict


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class LogoutRequest(BaseModel):
    refresh_token: str


class UserProfileResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    theme_preference: str
    language_preference: str
    timezone: str
    created_at: datetime
    last_login: Optional[datetime]
    permissions: list


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# Middleware de protection des routes
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPAuthorizationCredentials),
    auth_service: AuthService = Depends(get_auth_service),
    db: Session = Depends(get_db)
) -> User:
    """
    Middleware pour vérifier l'authentification et récupérer l'utilisateur actuel
    """
    try:
        # Extraire le token
        token = credentials.credentials
        
        # Vérifier le token
        payload = auth_service.verify_token(token)
        
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Type de token incorrect"
            )
        
        user_id = int(payload["sub"])
        
        # Récupérer l'utilisateur depuis la DB
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Utilisateur non trouvé"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Compte utilisateur désactivé"
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de l'utilisateur: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide"
        )


def log_audit_action(
    db: Session,
    user: Optional[User],
    action: str,
    success: bool,
    request: Request,
    details: str = None,
    error_message: str = None
):
    """
    Enregistre une action dans les logs d'audit
    """
    try:
        audit_log = AuditLog(
            user_id=user.id if user else None,
            action=action,
            details=details,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            success=success,
            error_message=error_message
        )
        
        db.add(audit_log)
        db.commit()
        
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement des logs d'audit: {e}")


@router.post("/login", response_model=LoginResponse)
async def login(
    login_request: LoginRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    db: Session = Depends(get_db)
):
    """
    Connexion utilisateur avec JWT
    """
    try:
        # Authentifier l'utilisateur
        result = auth_service.login(login_request.username, login_request.password, db)
        
        # Mettre à jour la date de dernière connexion
        user = db.query(User).filter(User.username == login_request.username).first()
        if user:
            user.last_login = datetime.utcnow()
            user.failed_login_attempts = 0  # Reset des tentatives échouées
            user.unlock_account()  # Déverrouiller si verrouillé
            db.commit()
        
        # Log d'audit
        log_audit_action(
            db, user, "login", True, request,
            details=f"Connexion réussie pour {login_request.username}"
        )
        
        logger.info(f"Connexion réussie pour l'utilisateur: {login_request.username}")
        
        return LoginResponse(**result)
        
    except HTTPException as e:
        # Gérer les tentatives de connexion échouées
        user = db.query(User).filter(User.username == login_request.username).first()
        if user:
            user.failed_login_attempts += 1
            
            # Verrouiller le compte après 5 tentatives échouées
            if user.failed_login_attempts >= 5:
                user.lock_account(30)  # Verrouiller 30 minutes
                error_detail = f"Compte verrouillé après {user.failed_login_attempts} tentatives"
            else:
                error_detail = f"Tentative {user.failed_login_attempts}/5"
            
            db.commit()
        else:
            error_detail = "Utilisateur inexistant"
        
        # Log d'audit
        log_audit_action(
            db, user, "login_failed", False, request,
            details=f"Échec de connexion pour {login_request.username}",
            error_message=str(e.detail)
        )
        
        logger.warning(f"Échec de connexion pour: {login_request.username} - {error_detail}")
        raise e


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    refresh_request: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Renouvellement du token d'accès
    """
    try:
        result = auth_service.refresh_access_token(refresh_request.refresh_token)
        logger.debug("Token d'accès renouvelé avec succès")
        return RefreshTokenResponse(**result)
        
    except HTTPException as e:
        logger.warning(f"Échec du renouvellement de token: {e.detail}")
        raise e


@router.post("/logout")
async def logout(
    logout_request: LogoutRequest,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    db: Session = Depends(get_db)
):
    """
    Déconnexion utilisateur
    """
    try:
        # Récupérer l'utilisateur depuis le refresh token
        payload = auth_service.verify_token(logout_request.refresh_token)
        username = payload.get("username")
        
        # Invalider la session
        success = auth_service.logout(logout_request.refresh_token)
        
        if success:
            # Log d'audit
            user = db.query(User).filter(User.username == username).first()
            log_audit_action(
                db, user, "logout", True, request,
                details=f"Déconnexion pour {username}"
            )
            
            logger.info(f"Déconnexion réussie pour l'utilisateur: {username}")
            return {"message": "Déconnexion réussie"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Échec de la déconnexion"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la déconnexion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.post("/logout-all")
async def logout_all_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    db: Session = Depends(get_db)
):
    """
    Déconnexion de toutes les sessions d'un utilisateur
    """
    sessions_removed = auth_service.logout_all_sessions(current_user.id)
    
    # Log d'audit
    log_audit_action(
        db, current_user, "logout_all", True, request,
        details=f"Déconnexion de toutes les sessions ({sessions_removed} sessions)"
    )
    
    logger.info(f"Toutes les sessions supprimées pour l'utilisateur: {current_user.username} ({sessions_removed} sessions)")
    
    return {
        "message": f"Toutes les sessions ont été fermées",
        "sessions_removed": sessions_removed
    }


@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Récupération du profil utilisateur
    """
    permissions = current_user.get_permissions()
    
    return UserProfileResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        theme_preference=current_user.theme_preference,
        language_preference=current_user.language_preference,
        timezone=current_user.timezone,
        created_at=current_user.created_at,
        last_login=current_user.last_login,
        permissions=permissions
    )


@router.get("/sessions")
async def get_active_sessions(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Récupération des sessions actives de l'utilisateur
    """
    sessions = auth_service.get_user_sessions(current_user.id)
    return {"sessions": sessions}


@router.post("/change-password")
async def change_password(
    password_request: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    db: Session = Depends(get_db)
):
    """
    Changement de mot de passe
    """
    # Vérifier l'ancien mot de passe
    if not auth_service.verify_password(password_request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mot de passe actuel incorrect"
        )
    
    # Mettre à jour le mot de passe
    current_user.hashed_password = auth_service.hash_password(password_request.new_password)
    current_user.password_changed_at = datetime.utcnow()
    db.commit()
    
    # Invalider toutes les sessions (force reconnexion)
    sessions_removed = auth_service.logout_all_sessions(current_user.id)
    
    # Log d'audit
    log_audit_action(
        db, current_user, "password_changed", True, request,
        details=f"Changement de mot de passe, {sessions_removed} sessions fermées"
    )
    
    logger.info(f"Mot de passe changé pour l'utilisateur: {current_user.username}")
    
    return {
        "message": "Mot de passe changé avec succès",
        "sessions_invalidated": sessions_removed
    }


@router.get("/verify-token")
async def verify_token(
    current_user: User = Depends(get_current_user)
):
    """
    Vérification de la validité du token (pour le frontend)
    """
    return {
        "valid": True,
        "user_id": current_user.id,
        "username": current_user.username
    }
