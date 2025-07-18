"""
Simple authentication service for WakeDock
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:

    """
    Get the current authenticated user.
    For now, this is a simple implementation that just returns the token as user ID.
    In a real implementation, this would validate the JWT token.

    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # For demo purposes, use the token as user ID
    # In production, you would validate the JWT token here
    return credentials.credentials


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
) -> Optional[str]:

    """
    Get the current authenticated user, but make it optional.

    """
    if not credentials:
        return None
    return credentials.credentials
