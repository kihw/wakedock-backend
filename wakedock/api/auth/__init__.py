"""Authentication and authorization module for WakeDock."""

from .dependencies import get_current_active_user, get_current_user, require_role
from .jwt import create_access_token, JWTManager, verify_token
from .models import Token, TokenData, UserCreate, UserResponse, UserUpdate
from .password import PasswordManager

__all__ = [
    "JWTManager",
    "create_access_token", 
    "verify_token",
    "get_current_user",
    "get_current_active_user",
    "require_role",
    "UserCreate",
    "UserUpdate", 
    "UserResponse",
    "Token",
    "TokenData",
    "PasswordManager"
]
