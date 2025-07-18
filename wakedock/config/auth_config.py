"""
Authentication configuration for FastAPI application
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import FastAPI
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from wakedock.api.routes.auth import router as auth_router
from wakedock.middleware.auth_middleware import (
    setup_all_auth_middleware,
    AuthenticationMiddleware,
    RoleBasedAccessMiddleware,
    SecurityHeadersMiddleware,
    RateLimitMiddleware
)

# Authentication configuration
AUTH_CONFIG = {
    "JWT_SECRET_KEY": "your-secret-key-here",  # Should be from environment
    "JWT_ALGORITHM": "HS256",
    "JWT_EXPIRY_HOURS": 24,
    "REFRESH_TOKEN_EXPIRY_DAYS": 7,
    "PASSWORD_RESET_EXPIRY_HOURS": 1,
    "MAX_LOGIN_ATTEMPTS": 5,
    "LOCKOUT_DURATION_MINUTES": 30,
    "PASSWORD_MIN_LENGTH": 8,
    "PASSWORD_REQUIRE_UPPERCASE": True,
    "PASSWORD_REQUIRE_LOWERCASE": True,
    "PASSWORD_REQUIRE_DIGITS": True,
    "PASSWORD_REQUIRE_SPECIAL": True,
    "SESSION_TIMEOUT_MINUTES": 60,
    "REMEMBER_ME_DAYS": 30
}

# Middleware configuration
MIDDLEWARE_CONFIG = {
    "exclude_paths": [
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/refresh",
        "/api/auth/reset-password",
        "/api/auth/reset-password/confirm",
        "/api/auth/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
        "/health",
        "/api/health"
    ],
    "role_permissions": {
        "/api/admin/": ["admin"],
        "/api/users/": ["admin", "manager"],
        "/api/auth/users": ["admin"],
        "/api/auth/stats": ["admin"],
        "/api/auth/roles/": ["admin"],
        "/api/auth/bulk-action": ["admin"],
        "/api/containers/": ["admin", "manager", "user"],
        "/api/alerts/": ["admin", "manager"],
        "/api/analytics/": ["admin", "manager"],
        "/api/dashboard/": ["admin", "manager", "user"]
    },
    "rate_limit_per_minute": 60
}

# Security headers configuration
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()"
}

# Default user roles and permissions
DEFAULT_ROLES = {
    "admin": {
        "name": "Administrator",
        "description": "Full system access",
        "permissions": [
            "users:create", "users:read", "users:update", "users:delete", "users:manage",
            "roles:create", "roles:read", "roles:update", "roles:delete", "roles:manage",
            "containers:create", "containers:read", "containers:update", "containers:delete", "containers:manage",
            "alerts:create", "alerts:read", "alerts:update", "alerts:delete", "alerts:manage",
            "analytics:read", "analytics:manage",
            "dashboard:read", "dashboard:manage",
            "system:read", "system:manage"
        ]
    },
    "manager": {
        "name": "Manager",
        "description": "Management access",
        "permissions": [
            "users:read", "users:update",
            "containers:create", "containers:read", "containers:update", "containers:delete",
            "alerts:read", "alerts:update", "alerts:manage",
            "analytics:read",
            "dashboard:read", "dashboard:manage"
        ]
    },
    "user": {
        "name": "User",
        "description": "Basic user access",
        "permissions": [
            "containers:read", "containers:update",
            "alerts:read",
            "dashboard:read"
        ]
    }
}

# Authentication utility functions
def get_auth_config() -> Dict[str, Any]:
    """Get authentication configuration"""
    return AUTH_CONFIG.copy()

def get_middleware_config() -> Dict[str, Any]:
    """Get middleware configuration"""
    return MIDDLEWARE_CONFIG.copy()

def get_security_headers() -> Dict[str, str]:
    """Get security headers configuration"""
    return SECURITY_HEADERS.copy()

def get_default_roles() -> Dict[str, Dict[str, Any]]:
    """Get default roles configuration"""
    return DEFAULT_ROLES.copy()

def setup_authentication(app: FastAPI) -> None:
    """Setup complete authentication system for FastAPI app"""
    
    # Add authentication routes
    app.include_router(auth_router)
    
    # Setup middleware
    setup_all_auth_middleware(
        app,
        exclude_paths=MIDDLEWARE_CONFIG["exclude_paths"],
        role_permissions=MIDDLEWARE_CONFIG["role_permissions"],
        requests_per_minute=MIDDLEWARE_CONFIG["rate_limit_per_minute"]
    )
    
    # Add startup event for authentication initialization
    @app.on_event("startup")
    async def init_authentication():
        """Initialize authentication system on startup"""
        from wakedock.core.database import get_db_session
        from wakedock.repositories.auth_repository import AuthRepository
        
        try:
            async with get_db_session() as db:
                auth_repository = AuthRepository(db)
                
                # Initialize default roles if they don't exist
                for role_name, role_data in DEFAULT_ROLES.items():
                    existing_role = await auth_repository.get_role_by_name(role_name)
                    if not existing_role:
                        await auth_repository.create_role(
                            name=role_name,
                            description=role_data["description"],
                            permissions=role_data["permissions"]
                        )
                
                # Create default admin user if it doesn't exist
                admin_user = await auth_repository.get_by_username("admin")
                if not admin_user:
                    await auth_repository.create_user(
                        username="admin",
                        email="admin@wakedock.com",
                        password="Admin123!",  # Should be changed on first login
                        first_name="System",
                        last_name="Administrator",
                        roles=["admin"]
                    )
                
                print("Authentication system initialized successfully")
                
        except Exception as e:
            print(f"Authentication initialization error: {str(e)}")

# JWT token configuration
def get_jwt_config() -> Dict[str, Any]:
    """Get JWT configuration"""
    return {
        "secret_key": AUTH_CONFIG["JWT_SECRET_KEY"],
        "algorithm": AUTH_CONFIG["JWT_ALGORITHM"],
        "access_token_expire_minutes": AUTH_CONFIG["JWT_EXPIRY_HOURS"] * 60,
        "refresh_token_expire_days": AUTH_CONFIG["REFRESH_TOKEN_EXPIRY_DAYS"]
    }

# Password validation configuration
def get_password_config() -> Dict[str, Any]:
    """Get password validation configuration"""
    return {
        "min_length": AUTH_CONFIG["PASSWORD_MIN_LENGTH"],
        "require_uppercase": AUTH_CONFIG["PASSWORD_REQUIRE_UPPERCASE"],
        "require_lowercase": AUTH_CONFIG["PASSWORD_REQUIRE_LOWERCASE"],
        "require_digits": AUTH_CONFIG["PASSWORD_REQUIRE_DIGITS"],
        "require_special": AUTH_CONFIG["PASSWORD_REQUIRE_SPECIAL"]
    }

# Session configuration
def get_session_config() -> Dict[str, Any]:
    """Get session configuration"""
    return {
        "timeout_minutes": AUTH_CONFIG["SESSION_TIMEOUT_MINUTES"],
        "remember_me_days": AUTH_CONFIG["REMEMBER_ME_DAYS"]
    }

# Security configuration
def get_security_config() -> Dict[str, Any]:
    """Get security configuration"""
    return {
        "max_login_attempts": AUTH_CONFIG["MAX_LOGIN_ATTEMPTS"],
        "lockout_duration_minutes": AUTH_CONFIG["LOCKOUT_DURATION_MINUTES"],
        "password_reset_expiry_hours": AUTH_CONFIG["PASSWORD_RESET_EXPIRY_HOURS"]
    }

# Example usage in main FastAPI app
"""
from fastapi import FastAPI
from wakedock.config.auth_config import setup_authentication

app = FastAPI(title="WakeDock API", version="1.0.0")

# Setup authentication system
setup_authentication(app)

# Your other routes and middleware...
"""
