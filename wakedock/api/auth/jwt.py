"""JWT token management for WakeDock authentication."""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import jwt
from jwt.exceptions import InvalidTokenError
from passlib.context import CryptContext

from wakedock.config import get_settings
from wakedock.database.models import UserRole
from .models import TokenData


class JWTManager:
    """JWT token management."""
    
    def __init__(self):
        """Initialize JWT manager with settings."""
        self.settings = get_settings()
        self.secret_key = self._get_secret_key()
        self.algorithm = "HS256"
        self.access_token_expires = timedelta(hours=24)
        self.refresh_token_expires = timedelta(days=7)
    
    def _get_secret_key(self) -> str:
        """Get JWT secret key from environment or generate one."""
        secret = os.getenv("JWT_SECRET_KEY")
        if not secret:
            # In production, this should be a proper secret
            import secrets
            secret = secrets.token_urlsafe(32)
            print(f"⚠️  Generated JWT secret: {secret}")
            print("⚠️  Please set JWT_SECRET_KEY environment variable in production!")
        return secret
    
    def create_access_token(
        self, 
        user_id: int, 
        username: str, 
        role: UserRole,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token."""
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + self.access_token_expires
        
        to_encode = {
            "sub": str(user_id),
            "username": username,
            "role": role.value,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "access"
        }
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(self, user_id: int) -> str:
        """Create a JWT refresh token."""
        expire = datetime.now(timezone.utc) + self.refresh_token_expires
        
        to_encode = {
            "sub": str(user_id),
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "refresh"
        }
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Optional[TokenData]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            user_id: Optional[str] = payload.get("sub")
            username: Optional[str] = payload.get("username")
            role_str: Optional[str] = payload.get("role")
            exp: Optional[int] = payload.get("exp")
            
            if user_id is None:
                return None
            
            # Convert role string back to enum
            role = None
            if role_str:
                try:
                    role = UserRole(role_str)
                except ValueError:
                    return None
            
            return TokenData(
                user_id=int(user_id),
                username=username,
                role=role,
                exp=exp
            )
            
        except InvalidTokenError:
            return None
        except ValueError:
            return None
    
    def is_token_expired(self, token_data: TokenData) -> bool:
        """Check if a token is expired."""
        if token_data.exp is None:
            return True
        
        current_time = datetime.now(timezone.utc).timestamp()
        return current_time > token_data.exp
    
    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Create a new access token from a refresh token."""
        try:
            payload = jwt.decode(refresh_token, self.secret_key, algorithms=[self.algorithm])
            
            # Check if it's a refresh token
            if payload.get("type") != "refresh":
                return None
            
            user_id = payload.get("sub")
            if user_id is None:
                return None
            
            # Here you would typically fetch user from database to get current role
            # For now, we'll create a token with basic user role
            # This should be improved to fetch actual user data
            return self.create_access_token(
                user_id=int(user_id),
                username="",  # Would be fetched from DB
                role=UserRole.USER  # Would be fetched from DB
            )
            
        except InvalidTokenError:
            return None


# Global JWT manager instance
jwt_manager = JWTManager()


def create_access_token(
    user_id: int, 
    username: str, 
    role: UserRole,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create an access token."""
    return jwt_manager.create_access_token(user_id, username, role, expires_delta)


def verify_token(token: str) -> Optional[TokenData]:
    """Verify a JWT token."""
    return jwt_manager.verify_token(token)
