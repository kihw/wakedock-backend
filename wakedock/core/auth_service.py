"""
Service d'authentification JWT pour WakeDock
Gestion complète des tokens JWT avec refresh automatique
"""

import os
import secrets
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, List, Optional

import jwt
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from wakedock.logging import get_logger
from wakedock.models.user import User

logger = get_logger(__name__)


class AuthService:
    """
    Service d'authentification centralisé avec JWT
    """
    
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.security = HTTPBearer()
        
        # Configuration JWT
        self.secret_key = os.getenv("JWT_SECRET_KEY", self._generate_secret_key())
        self.algorithm = "HS256"
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
        self.refresh_token_expire_days = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))
        
        # Sessions actives (en mémoire pour l'instant, à migrer vers Redis)
        self._active_sessions: Dict[str, Dict[str, Any]] = {}
        
        logger.info(f"AuthService initialisé - Access Token: {self.access_token_expire_minutes}min, Refresh Token: {self.refresh_token_expire_days}j")
    
    def _generate_secret_key(self) -> str:
        """Génère une clé secrète sécurisée"""
        return secrets.token_urlsafe(32)
    
    def hash_password(self, password: str) -> str:
        """Hache un mot de passe"""
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Vérifie un mot de passe"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(self, user_id: int, username: str, permissions: List[str] = None) -> str:
        """
        Crée un token d'accès JWT
        """
        if permissions is None:
            permissions = []
            
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        payload = {
            "sub": str(user_id),
            "username": username,
            "permissions": permissions,
            "type": "access",
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": secrets.token_urlsafe(16)  # JWT ID unique
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        logger.debug(f"Token d'accès créé pour l'utilisateur {username} (expire: {expire})")
        return token
    
    def create_refresh_token(self, user_id: int, username: str, session_id: str = None) -> str:
        """
        Crée un refresh token JWT
        """
        if session_id is None:
            session_id = secrets.token_urlsafe(16)
            
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        
        payload = {
            "sub": str(user_id),
            "username": username,
            "type": "refresh",
            "session_id": session_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": secrets.token_urlsafe(16)
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        # Enregistrer la session
        self._active_sessions[session_id] = {
            "user_id": user_id,
            "username": username,
            "created_at": datetime.utcnow(),
            "expires_at": expire,
            "last_activity": datetime.utcnow(),
            "refresh_token_jti": payload["jti"]
        }
        
        logger.debug(f"Refresh token créé pour l'utilisateur {username} (session: {session_id}, expire: {expire})")
        return token
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Vérifie et décode un token JWT
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Vérifier que le token n'a pas expiré
            exp = payload.get("exp")
            if exp and datetime.utcnow() > datetime.fromtimestamp(exp):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token expiré"
                )
            
            # Pour les refresh tokens, vérifier que la session est active
            if payload.get("type") == "refresh":
                session_id = payload.get("session_id")
                if session_id not in self._active_sessions:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Session invalide"
                    )
                
                # Mettre à jour l'activité de la session
                self._active_sessions[session_id]["last_activity"] = datetime.utcnow()
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expiré"
            )
        except jwt.JWTError as e:
            logger.warning(f"Erreur de validation JWT: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide"
            )
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, str]:
        """
        Renouvelle un token d'accès à partir d'un refresh token
        """
        payload = self.verify_token(refresh_token)
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de type incorrect"
            )
        
        user_id = int(payload["sub"])
        username = payload["username"]
        payload["session_id"]
        
        # Récupérer les permissions de l'utilisateur depuis la DB
        # TODO: Implémenter la récupération des permissions
        permissions = []
        
        # Créer un nouveau token d'accès
        new_access_token = self.create_access_token(user_id, username, permissions)
        
        logger.info(f"Token d'accès renouvelé pour l'utilisateur {username}")
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": self.access_token_expire_minutes * 60
        }
    
    def authenticate_user(self, username: str, password: str, db: Session) -> Optional[User]:
        """
        Authentifie un utilisateur avec nom d'utilisateur et mot de passe
        """
        try:
            # Rechercher l'utilisateur
            user = db.query(User).filter(User.username == username).first()
            
            if not user:
                logger.warning(f"Tentative de connexion avec un nom d'utilisateur inexistant: {username}")
                return None
            
            if not user.is_active:
                logger.warning(f"Tentative de connexion avec un compte désactivé: {username}")
                return None
            
            # Vérifier le mot de passe
            if not self.verify_password(password, user.hashed_password):
                logger.warning(f"Tentative de connexion avec un mot de passe incorrect: {username}")
                return None
            
            logger.info(f"Authentification réussie pour l'utilisateur: {username}")
            return user
            
        except Exception as e:
            logger.error(f"Erreur lors de l'authentification: {e}")
            return None
    
    def login(self, username: str, password: str, db: Session) -> Dict[str, Any]:
        """
        Connecte un utilisateur et retourne les tokens
        """
        user = self.authenticate_user(username, password, db)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Nom d'utilisateur ou mot de passe incorrect"
            )
        
        # Créer une nouvelle session
        session_id = secrets.token_urlsafe(16)
        
        # Récupérer les permissions
        # TODO: Implémenter la récupération des permissions depuis les rôles
        permissions = []
        
        # Créer les tokens
        access_token = self.create_access_token(user.id, user.username, permissions)
        refresh_token = self.create_refresh_token(user.id, user.username, session_id)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.access_token_expire_minutes * 60,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "permissions": permissions
            }
        }
    
    def logout(self, refresh_token: str) -> bool:
        """
        Déconnecte un utilisateur en invalidant sa session
        """
        try:
            payload = self.verify_token(refresh_token)
            session_id = payload.get("session_id")
            
            if session_id and session_id in self._active_sessions:
                del self._active_sessions[session_id]
                logger.info(f"Session {session_id} supprimée pour l'utilisateur {payload.get('username')}")
                return True
                
        except Exception as e:
            logger.warning(f"Erreur lors de la déconnexion: {e}")
        
        return False
    
    def logout_all_sessions(self, user_id: int) -> int:
        """
        Déconnecte toutes les sessions d'un utilisateur
        """
        sessions_removed = 0
        sessions_to_remove = []
        
        for session_id, session_data in self._active_sessions.items():
            if session_data["user_id"] == user_id:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self._active_sessions[session_id]
            sessions_removed += 1
        
        logger.info(f"{sessions_removed} sessions supprimées pour l'utilisateur {user_id}")
        return sessions_removed
    
    def get_user_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Récupère toutes les sessions actives d'un utilisateur
        """
        sessions = []
        
        for session_id, session_data in self._active_sessions.items():
            if session_data["user_id"] == user_id:
                sessions.append({
                    "session_id": session_id,
                    "created_at": session_data["created_at"],
                    "last_activity": session_data["last_activity"],
                    "expires_at": session_data["expires_at"]
                })
        
        return sessions
    
    def cleanup_expired_sessions(self) -> int:
        """
        Nettoie les sessions expirées
        """
        now = datetime.utcnow()
        expired_sessions = []
        
        for session_id, session_data in self._active_sessions.items():
            if session_data["expires_at"] < now:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self._active_sessions[session_id]
        
        if expired_sessions:
            logger.info(f"{len(expired_sessions)} sessions expirées nettoyées")
        
        return len(expired_sessions)


# Instance globale du service d'authentification
_auth_service: AuthService = None

@lru_cache()
def get_auth_service() -> AuthService:
    """
    Dépendance FastAPI pour obtenir le service d'authentification
    """
    global _auth_service
    
    if _auth_service is None:
        _auth_service = AuthService()
    
    return _auth_service
