"""
Authentication routes for FastAPI - MVC Architecture
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from wakedock.controllers.auth_controller import AuthController
from wakedock.repositories.auth_repository import AuthRepository
from wakedock.validators.auth_validator import AuthValidator
from wakedock.services.auth_service import AuthService
from wakedock.views.auth_view import AuthView
from wakedock.serializers.auth_serializers import (
    LoginSerializer,
    RegisterSerializer,
    ProfileUpdateSerializer,
    PasswordChangeSerializer,
    PasswordResetRequestSerializer,
    PasswordResetSerializer,
    TokenRefreshSerializer,
    UserSearchSerializer,
    RoleAssignmentSerializer,
    BulkUserActionSerializer
)
from wakedock.core.database import get_db_session
from wakedock.database.models import User

import logging
logger = logging.getLogger(__name__)

# FastAPI router
router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Security scheme
security = HTTPBearer()

# Dependencies
async def get_auth_dependencies(db: AsyncSession = Depends(get_db_session)):
    """Get authentication dependencies"""
    auth_repository = AuthRepository(db)
    auth_validator = AuthValidator()
    auth_service = AuthService()
    auth_controller = AuthController(auth_repository, auth_validator, auth_service)
    auth_view = AuthView()
    
    return auth_controller, auth_view

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db_session)
):
    """Get current authenticated user"""
    try:
        auth_repository = AuthRepository(db)
        payload = await auth_repository.verify_token(credentials.credentials)
        
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        
        user = await auth_repository.get_by_id(payload['user_id'])
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


@router.post("/login", summary="User login", description="Authenticate user and return JWT token")
async def login(
    request: Request,
    login_data: LoginSerializer,
    deps = Depends(get_auth_dependencies)
):
    """User login endpoint"""
    try:
        auth_controller, auth_view = deps
        
        # Authenticate user
        result = await auth_controller.authenticate(
            username=login_data.username,
            password=login_data.password
        )
        
        # Format response
        response = await auth_view.login_response(
            user=result['user'],
            token=result['token'],
            expires_at=result['expires_at']
        )
        
        # Log successful login
        logger.info(f"User '{login_data.username}' logged in successfully")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/register", summary="User registration", description="Register new user account")
async def register(
    request: Request,
    register_data: RegisterSerializer,
    deps = Depends(get_auth_dependencies)
):
    """User registration endpoint"""
    try:
        auth_controller, auth_view = deps
        
        # Register user
        result = await auth_controller.register(
            username=register_data.username,
            email=register_data.email,
            password=register_data.password,
            first_name=register_data.first_name,
            last_name=register_data.last_name,
            roles=register_data.roles
        )
        
        # Format response
        response = await auth_view.register_response(result['user'])
        
        # Log successful registration
        logger.info(f"User '{register_data.username}' registered successfully")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/logout", summary="User logout", description="Logout user and revoke token")
async def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    deps = Depends(get_auth_dependencies)
):
    """User logout endpoint"""
    try:
        auth_controller, auth_view = deps
        
        # Logout user
        await auth_controller.logout(credentials.credentials)
        
        # Format response
        response = await auth_view.logout_response()
        
        logger.info("User logged out successfully")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.post("/refresh", summary="Refresh token", description="Refresh JWT authentication token")
async def refresh_token(
    request: Request,
    refresh_data: TokenRefreshSerializer,
    deps = Depends(get_auth_dependencies)
):
    """Token refresh endpoint"""
    try:
        auth_controller, auth_view = deps
        
        # Refresh token
        result = await auth_controller.refresh_token(refresh_data.token)
        
        # Format response
        response = await auth_view.token_refresh_response(
            token=result['token'],
            expires_at=result['expires_at']
        )
        
        logger.info("Token refreshed successfully")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.get("/me", summary="Get current user", description="Get current user profile information")
async def get_current_user_profile(
    request: Request,
    current_user = Depends(get_current_user),
    deps = Depends(get_auth_dependencies)
):
    """Get current user profile endpoint"""
    try:
        auth_controller, auth_view = deps
        
        # Get current user info
        user_info = await auth_controller.get_current_user(
            request.headers.get('Authorization', '').replace('Bearer ', '')
        )
        
        # Format response
        response = await auth_view.user_profile_response(current_user)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get current user error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user profile"
        )


@router.put("/me", summary="Update profile", description="Update current user profile")
async def update_profile(
    request: Request,
    profile_data: ProfileUpdateSerializer,
    current_user = Depends(get_current_user),
    deps = Depends(get_auth_dependencies)
):
    """Update user profile endpoint"""
    try:
        auth_controller, auth_view = deps
        
        # Update profile
        result = await auth_controller.update_profile(
            user_id=current_user.id,
            first_name=profile_data.first_name,
            last_name=profile_data.last_name,
            email=profile_data.email
        )
        
        # Format response
        response = await auth_view.profile_update_response(result['user'])
        
        logger.info(f"Profile updated for user '{current_user.username}'")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile update error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile update failed"
        )


@router.post("/change-password", summary="Change password", description="Change user password")
async def change_password(
    request: Request,
    password_data: PasswordChangeSerializer,
    current_user = Depends(get_current_user),
    deps = Depends(get_auth_dependencies)
):
    """Change password endpoint"""
    try:
        auth_controller, auth_view = deps
        
        # Change password
        result = await auth_controller.change_password(
            user_id=current_user.id,
            current_password=password_data.current_password,
            new_password=password_data.new_password
        )
        
        # Format response
        response = await auth_view.password_change_response()
        
        logger.info(f"Password changed for user '{current_user.username}'")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )


@router.get("/users", summary="Get users", description="Get users list (admin only)")
async def get_users(
    request: Request,
    search: UserSearchSerializer = Depends(),
    current_user = Depends(get_current_user),
    deps = Depends(get_auth_dependencies)
):
    """Get users endpoint (admin only)"""
    try:
        # Check admin permission
        if not current_user.has_permission('users:read'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        auth_controller, auth_view = deps
        
        # Get users
        result = await auth_controller.get_users(
            limit=search.limit,
            offset=search.offset
        )
        
        # Format response
        response = await auth_view.users_list_response(
            users=result['users'],
            total_count=result['total_count'],
            limit=result['limit'],
            offset=result['offset']
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get users error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get users"
        )


@router.get("/stats", summary="Get auth stats", description="Get authentication statistics (admin only)")
async def get_auth_stats(
    request: Request,
    current_user = Depends(get_current_user),
    deps = Depends(get_auth_dependencies)
):
    """Get authentication statistics endpoint (admin only)"""
    try:
        # Check admin permission
        if not current_user.has_permission('users:read'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        auth_controller, auth_view = deps
        
        # Get stats
        stats = await auth_controller.get_auth_stats()
        
        # Format response
        response = await auth_view.auth_stats_response(stats)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get auth stats error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get authentication statistics"
        )


# Health check endpoint
@router.get("/health", summary="Auth health check", description="Check authentication service health")
async def health_check(request: Request):
    """Authentication service health check"""
    try:
        return {
            "status": "healthy",
            "service": "authentication",
            "timestamp": "2023-01-01T00:00:00Z"
        }
        
    except Exception as e:
        logger.error(f"Auth health check error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service unhealthy"
        )


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
