"""
Core authentication middleware functions
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from wakedock.core.database import get_db_session
from wakedock.models.auth import User

security = HTTPBearer()


def require_authenticated_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db_session)
) -> User:
    """Require authenticated user - FastAPI dependency"""
    try:
        # For now, return a mock user
        # In production, this would validate the JWT token and return the user
        user = User(
            id="user_123",
            email="admin@wakedock.com",
            username="admin",
            is_active=True,
            is_admin=True
        )
        
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db_session)
) -> Optional[User]:
    """Get current user (optional) - FastAPI dependency"""
    if not credentials:
        return None
    
    try:
        return User(
            id="user_123",
            email="admin@wakedock.com",
            username="admin",
            is_active=True,
            is_admin=True
        )
    except Exception:
        return None