"""
WakeDock Core Module v1.0.0
Core functionality for WakeDock container orchestration platform
"""

from .security import (
    SecurityConfig,
    UserModel,
    TokenData,
    LoginRequest,
    TokenResponse,
    PasswordValidator,
    TokenManager,
    SessionManager,
    PermissionManager,
    SecurityUtils,
    security_config,
    session_manager,
    permission_manager,
    password_validator,
    token_manager,
    security_utils,
    get_current_user,
    require_permission,
    require_admin
)

__version__ = "1.0.0"
__author__ = "WakeDock Team"
__description__ = "Core functionality for WakeDock container orchestration platform"

__all__ = [
    "SecurityConfig",
    "UserModel",
    "TokenData",
    "LoginRequest",
    "TokenResponse",
    "PasswordValidator",
    "TokenManager",
    "SessionManager",
    "PermissionManager",
    "SecurityUtils",
    "security_config",
    "session_manager",
    "permission_manager",
    "password_validator",
    "token_manager",
    "security_utils",
    "get_current_user",
    "require_permission",
    "require_admin"
]
