"""
Authentication service for WakeDock.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import select

from wakedock.models.auth_models import User, RefreshToken, AuditLog
from wakedock.core.auth.jwt_service import JWTService
from wakedock.logging import get_logger

logger = get_logger(__name__)


class AuthService:
    """Service for authentication operations."""
    
    def __init__(self, db: Session):
        self.db = db
        self.jwt_service = JWTService()
    
    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate a user with username and password."""
        # Query user by username
        result = self.db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        # Verify password
        if not self.jwt_service.verify_password(password, user.hashed_password):
            return None
        
        # Update last login
        user.last_login = datetime.utcnow()
        self.db.commit()
        
        # Log authentication
        self._log_audit(user.id, "user.login", "User logged in")
        
        return user
    
    async def create_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        role: str = "user"
    ) -> User:
        """Create a new user."""
        # Hash password
        hashed_password = self.jwt_service.get_password_hash(password)
        
        # Create user
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        # Log user creation
        self._log_audit(user.id, "user.create", f"User {username} created")
        
        return user
    
    async def create_tokens(self, user: User) -> dict:
        """Create access and refresh tokens for a user."""
        # Token payload
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "role": user.role.value
        }
        
        # Create tokens
        access_token = self.jwt_service.create_access_token(token_data)
        refresh_token, expires_at = self.jwt_service.create_refresh_token(token_data)
        
        # Store refresh token
        db_refresh_token = RefreshToken(
            token=refresh_token,
            user_id=user.id,
            expires_at=expires_at
        )
        self.db.add(db_refresh_token)
        self.db.commit()
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    
    async def refresh_access_token(self, refresh_token: str) -> Optional[dict]:
        """Refresh an access token using a refresh token."""
        try:
            # Decode refresh token
            payload = self.jwt_service.decode_token(refresh_token)
            
            if payload.get("type") != "refresh":
                return None
            
            # Check if token exists and is valid
            result = self.db.execute(
                select(RefreshToken).where(RefreshToken.token == refresh_token)
            )
            db_token = result.scalar_one_or_none()
            
            if not db_token or not db_token.is_valid():
                return None
            
            # Get user
            result = self.db.execute(
                select(User).where(User.id == db_token.user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user or not user.is_active:
                return None
            
            # Create new access token
            token_data = {
                "sub": str(user.id),
                "username": user.username,
                "role": user.role.value
            }
            access_token = self.jwt_service.create_access_token(token_data)
            
            return {
                "access_token": access_token,
                "token_type": "bearer"
            }
            
        except ValueError:
            return None
    
    async def revoke_refresh_token(self, refresh_token: str) -> bool:
        """Revoke a refresh token."""
        result = self.db.execute(
            select(RefreshToken).where(RefreshToken.token == refresh_token)
        )
        db_token = result.scalar_one_or_none()
        
        if db_token:
            db_token.is_revoked = True
            self.db.commit()
            return True
        
        return False
    
    async def get_current_user(self, token: str) -> Optional[User]:
        """Get current user from access token."""
        try:
            # Decode token
            payload = self.jwt_service.decode_token(token)
            
            if payload.get("type") != "access":
                return None
            
            # Get user
            user_id = int(payload.get("sub"))
            result = self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if user and user.is_active:
                return user
            
            return None
            
        except (ValueError, TypeError):
            return None
    
    def _log_audit(self, user_id: int, action: str, details: str = None):
        """Log an audit entry."""
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            details=details
        )
        self.db.add(audit_log)
        # Don't commit here, let the caller handle transaction