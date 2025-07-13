"""Authentication and authorization module for WakeDock."""

from .jwt import JWTManager, create_access_token, verify_token
from .dependencies import get_current_user, get_current_active_user, require_role
from .models import UserCreate, UserUpdate, UserResponse, Token, TokenData
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
