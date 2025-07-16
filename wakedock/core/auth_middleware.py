"""
Middleware d'authentification pour WakeDock
Protection automatique des routes sensibles
"""

from typing import Optional, List
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from wakedock.core.auth_service import get_auth_service
from wakedock.core.database import get_db
from wakedock.models.user import User
from wakedock.core.logging import logger


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware pour l'authentification automatique des routes protégées
    """
    
    def __init__(self, app, excluded_paths: List[str] = None):
        super().__init__(app)
        self.excluded_paths = excluded_paths or [
            "/docs",
            "/redoc", 
            "/openapi.json",
            "/api/v1/health",
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
            "/favicon.ico"
        ]
        self.security = HTTPBearer(auto_error=False)
        
    async def dispatch(self, request: Request, call_next):
        # Vérifier si la route est exclue de l'authentification
        if self._is_excluded_path(request.url.path):
            return await call_next(request)
        
        # Tenter d'authentifier la requête
        try:
            user = await self._authenticate_request(request)
            
            # Ajouter l'utilisateur au state de la requête
            if user:
                request.state.current_user = user
                request.state.is_authenticated = True
            else:
                request.state.current_user = None
                request.state.is_authenticated = False
                
        except HTTPException as e:
            # Pour les routes API protégées, retourner une erreur
            if request.url.path.startswith("/api/v1/") and not request.url.path.startswith("/api/v1/auth/"):
                return Response(
                    content=f'{{"detail":"{e.detail}"}}',
                    status_code=e.status_code,
                    media_type="application/json"
                )
            else:
                # Pour les autres routes, laisser passer (gestion par les dépendances)
                request.state.current_user = None
                request.state.is_authenticated = False
        
        return await call_next(request)
    
    def _is_excluded_path(self, path: str) -> bool:
        """Vérifie si le chemin est exclu de l'authentification"""
        for excluded in self.excluded_paths:
            if path.startswith(excluded):
                return True
        return False
    
    async def _authenticate_request(self, request: Request) -> Optional[User]:
        """Authentifie une requête et retourne l'utilisateur"""
        # Extraire le token depuis l'en-tête Authorization
        authorization = request.headers.get("Authorization")
        
        if not authorization:
            return None
            
        if not authorization.startswith("Bearer "):
            return None
            
        token = authorization.replace("Bearer ", "")
        
        try:
            auth_service = get_auth_service()
            payload = auth_service.verify_token(token)
            
            if payload.get("type") != "access":
                return None
            
            user_id = int(payload["sub"])
            
            # Récupérer l'utilisateur depuis la DB
            db = next(get_db())
            try:
                user = db.query(User).filter(User.id == user_id).first()
                
                if not user or not user.is_active:
                    return None
                
                return user
                
            finally:
                db.close()
                
        except Exception as e:
            logger.debug(f"Erreur d'authentification middleware: {e}")
            return None


def require_permissions(*required_permissions: str):
    """
    Décorateur pour exiger des permissions spécifiques
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Récupérer l'utilisateur depuis le state de la requête
            request = kwargs.get('request') or (args[0] if args else None)
            
            if not hasattr(request, 'state') or not request.state.is_authenticated:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentification requise"
                )
            
            user = request.state.current_user
            user_permissions = user.get_permissions()
            
            # Vérifier les permissions
            missing_permissions = []
            for perm in required_permissions:
                if perm not in user_permissions:
                    missing_permissions.append(perm)
            
            if missing_permissions:
                logger.warning(f"Accès refusé pour {user.username}: permissions manquantes {missing_permissions}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permissions insuffisantes. Requis: {', '.join(missing_permissions)}"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_admin(func):
    """
    Décorateur pour exiger les droits administrateur
    """
    async def wrapper(*args, **kwargs):
        request = kwargs.get('request') or (args[0] if args else None)
        
        if not hasattr(request, 'state') or not request.state.is_authenticated:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentification requise"
            )
        
        user = request.state.current_user
        
        if not user.is_superuser:
            logger.warning(f"Accès admin refusé pour {user.username}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Droits administrateur requis"
            )
        
        return await func(*args, **kwargs)
    
    return wrapper


# Dépendance FastAPI pour récupérer l'utilisateur authentifié
async def get_current_user_dependency(request: Request) -> User:
    """
    Dépendance FastAPI pour récupérer l'utilisateur actuel
    Compatible avec le middleware d'authentification
    """
    if not hasattr(request, 'state') or not request.state.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise"
        )
    
    return request.state.current_user


# Dépendance optionnelle (ne lève pas d'erreur si non authentifié)
async def get_current_user_optional(request: Request) -> Optional[User]:
    """
    Dépendance FastAPI optionnelle pour l'utilisateur actuel
    """
    if hasattr(request, 'state') and request.state.is_authenticated:
        return request.state.current_user
    return None
