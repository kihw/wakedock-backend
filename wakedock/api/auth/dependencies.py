"""FastAPI dependencies for authentication and authorization."""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from wakedock.database.database import get_db_session
from wakedock.database.models import User, UserRole
from .jwt import verify_token
from .models import TokenData

# HTTP Bearer token scheme
security = HTTPBearer()


def get_token_data(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> TokenData:
    """Extract and validate JWT token data."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_data = verify_token(credentials.credentials)
    if token_data is None:
        raise credentials_exception
    
    return token_data


def get_current_user(
    token_data: TokenData = Depends(get_token_data),
    db: Session = Depends(get_db_session)
) -> User:
    """Get the current authenticated user."""
    if token_data.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token data"
        )
    
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get the current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return current_user


def get_current_verified_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get the current verified user."""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not verified"
        )
    
    return current_user


def require_role(required_role: UserRole):
    """Dependency factory for role-based access control."""
    def role_dependency(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        """Check if user has required role."""
        # Admin can access everything
        if current_user.role == UserRole.ADMIN:
            return current_user
        
        # Check specific role requirement
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires {required_role.value} role"
            )
        
        return current_user
    
    return role_dependency


def require_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Require admin role."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return current_user


def require_owner_or_admin(service_owner_id: int):
    """Dependency factory to require service ownership or admin role."""
    def ownership_dependency(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        """Check if user owns the service or is admin."""
        if current_user.role == UserRole.ADMIN:
            return current_user
        
        if current_user.id != service_owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only manage your own services"
            )
        
        return current_user
    
    return ownership_dependency


# Optional authentication (doesn't raise error if no token)
def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db_session)
) -> Optional[User]:
    """Get current user if authenticated, None otherwise."""
    if credentials is None:
        return None
    
    try:
        token_data = verify_token(credentials.credentials)
        if token_data is None or token_data.user_id is None:
            return None
        
        user = db.query(User).filter(User.id == token_data.user_id).first()
        if user is None or not user.is_active:
            return None
        
        return user
    except Exception:
        return None
