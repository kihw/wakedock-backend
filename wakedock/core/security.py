"""
Security module for WakeDock v1.0.0
Handles authentication, authorization, and security utilities
"""

import hashlib
import secrets
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from passlib.context import CryptContext
from passlib.hash import bcrypt
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr


# Password context for hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT configuration
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Security scheme
security = HTTPBearer()


class UserModel(BaseModel):
    """User model for authentication"""
    username: str
    email: EmailStr
    is_active: bool = True
    is_admin: bool = False
    created_at: datetime = None
    last_login: Optional[datetime] = None
    permissions: List[str] = []


class TokenData(BaseModel):
    """Token data model"""
    username: Optional[str] = None
    permissions: List[str] = []


class LoginRequest(BaseModel):
    """Login request model"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Token response model"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserModel


class SecurityConfig:
    """Security configuration"""
    
    def __init__(self):
        self.jwt_secret = SECRET_KEY
        self.jwt_algorithm = ALGORITHM
        self.access_token_expire_minutes = ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = REFRESH_TOKEN_EXPIRE_DAYS
        self.max_login_attempts = 5
        self.lockout_duration_minutes = 30
        self.password_min_length = 8
        self.require_special_chars = True
        self.require_numbers = True
        self.require_uppercase = True
        self.session_timeout_minutes = 480  # 8 hours
        self.csrf_protection = True
        self.cors_origins = ["http://localhost:3000", "https://wakedock.local"]
        self.allowed_hosts = ["localhost", "wakedock.local", "127.0.0.1"]
        self.rate_limit_per_minute = 100
        self.enable_audit_logging = True
        self.encrypt_sensitive_data = True
        self.secure_cookies = True
        self.samesite_cookies = "strict"


# Global security configuration
security_config = SecurityConfig()


class PasswordValidator:
    """Password validation utilities"""
    
    @staticmethod
    def validate_password(password: str) -> bool:
        """Validate password strength"""
        if len(password) < security_config.password_min_length:
            return False
        
        if security_config.require_numbers and not any(c.isdigit() for c in password):
            return False
        
        if security_config.require_uppercase and not any(c.isupper() for c in password):
            return False
        
        if security_config.require_special_chars:
            special_chars = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
            if not any(c in special_chars for c in password):
                return False
        
        return True
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def generate_password() -> str:
        """Generate secure random password"""
        return secrets.token_urlsafe(16)


class TokenManager:
    """JWT token management"""
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=security_config.access_token_expire_minutes)
        
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, security_config.jwt_secret, algorithm=security_config.jwt_algorithm)
    
    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """Create refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=security_config.refresh_token_expire_days)
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, security_config.jwt_secret, algorithm=security_config.jwt_algorithm)
    
    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> dict:
        """Verify and decode token"""
        try:
            payload = jwt.decode(token, security_config.jwt_secret, algorithms=[security_config.jwt_algorithm])
            if payload.get("type") != token_type:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type"
                )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            )


class SessionManager:
    """Session management utilities"""
    
    def __init__(self):
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.login_attempts: Dict[str, Dict[str, Any]] = {}
    
    def create_session(self, user_id: str, user_data: dict) -> str:
        """Create new session"""
        session_id = secrets.token_urlsafe(32)
        self.active_sessions[session_id] = {
            "user_id": user_id,
            "user_data": user_data,
            "created_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "ip_address": None,
            "user_agent": None
        }
        return session_id
    
    def get_session(self, session_id: str) -> Optional[dict]:
        """Get session data"""
        session = self.active_sessions.get(session_id)
        if session:
            # Check if session is expired
            if datetime.utcnow() - session["last_activity"] > timedelta(minutes=security_config.session_timeout_minutes):
                self.destroy_session(session_id)
                return None
            
            # Update last activity
            session["last_activity"] = datetime.utcnow()
            return session
        return None
    
    def destroy_session(self, session_id: str):
        """Destroy session"""
        self.active_sessions.pop(session_id, None)
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions"""
        current_time = datetime.utcnow()
        expired_sessions = [
            session_id for session_id, session in self.active_sessions.items()
            if current_time - session["last_activity"] > timedelta(minutes=security_config.session_timeout_minutes)
        ]
        
        for session_id in expired_sessions:
            self.destroy_session(session_id)
    
    def track_login_attempt(self, username: str, success: bool, ip_address: str = None):
        """Track login attempts for rate limiting"""
        current_time = datetime.utcnow()
        
        if username not in self.login_attempts:
            self.login_attempts[username] = {
                "attempts": 0,
                "last_attempt": current_time,
                "locked_until": None,
                "failed_attempts": []
            }
        
        user_attempts = self.login_attempts[username]
        
        if success:
            # Reset attempts on successful login
            user_attempts["attempts"] = 0
            user_attempts["failed_attempts"] = []
            user_attempts["locked_until"] = None
        else:
            # Increment failed attempts
            user_attempts["attempts"] += 1
            user_attempts["last_attempt"] = current_time
            user_attempts["failed_attempts"].append({
                "timestamp": current_time,
                "ip_address": ip_address
            })
            
            # Lock account if too many attempts
            if user_attempts["attempts"] >= security_config.max_login_attempts:
                user_attempts["locked_until"] = current_time + timedelta(minutes=security_config.lockout_duration_minutes)
    
    def is_account_locked(self, username: str) -> bool:
        """Check if account is locked"""
        if username not in self.login_attempts:
            return False
        
        user_attempts = self.login_attempts[username]
        locked_until = user_attempts.get("locked_until")
        
        if locked_until and datetime.utcnow() < locked_until:
            return True
        
        return False


class PermissionManager:
    """Permission and role management"""
    
    PERMISSIONS = {
        "read_containers": "Can view containers",
        "write_containers": "Can create/modify containers",
        "delete_containers": "Can delete containers",
        "read_services": "Can view services",
        "write_services": "Can create/modify services",
        "delete_services": "Can delete services",
        "read_networks": "Can view networks",
        "write_networks": "Can create/modify networks",
        "delete_networks": "Can delete networks",
        "read_volumes": "Can view volumes",
        "write_volumes": "Can create/modify volumes",
        "delete_volumes": "Can delete volumes",
        "read_images": "Can view images",
        "write_images": "Can create/modify images",
        "delete_images": "Can delete images",
        "read_compose": "Can view compose files",
        "write_compose": "Can create/modify compose files",
        "delete_compose": "Can delete compose files",
        "read_github": "Can view GitHub integrations",
        "write_github": "Can create/modify GitHub integrations",
        "delete_github": "Can delete GitHub integrations",
        "read_metrics": "Can view metrics",
        "read_logs": "Can view logs",
        "read_system": "Can view system information",
        "write_system": "Can modify system settings",
        "admin": "Full administrative access"
    }
    
    ROLES = {
        "viewer": ["read_containers", "read_services", "read_networks", "read_volumes", "read_images", "read_metrics", "read_logs"],
        "developer": ["read_containers", "write_containers", "read_services", "write_services", "read_networks", "read_volumes", "read_images", "read_compose", "write_compose", "read_github", "write_github", "read_metrics", "read_logs"],
        "operator": ["read_containers", "write_containers", "delete_containers", "read_services", "write_services", "delete_services", "read_networks", "write_networks", "read_volumes", "write_volumes", "read_images", "write_images", "read_compose", "write_compose", "delete_compose", "read_github", "write_github", "read_metrics", "read_logs", "read_system"],
        "admin": list(PERMISSIONS.keys())
    }
    
    @staticmethod
    def has_permission(user_permissions: List[str], required_permission: str) -> bool:
        """Check if user has required permission"""
        return required_permission in user_permissions or "admin" in user_permissions
    
    @staticmethod
    def get_role_permissions(role: str) -> List[str]:
        """Get permissions for a role"""
        return PermissionManager.ROLES.get(role, [])
    
    @staticmethod
    def validate_permissions(permissions: List[str]) -> bool:
        """Validate that all permissions exist"""
        return all(perm in PermissionManager.PERMISSIONS for perm in permissions)


class SecurityUtils:
    """Security utility functions"""
    
    @staticmethod
    def generate_csrf_token() -> str:
        """Generate CSRF token"""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def validate_csrf_token(token: str, expected_token: str) -> bool:
        """Validate CSRF token"""
        return secrets.compare_digest(token, expected_token)
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate API key"""
        return f"wk_{secrets.token_urlsafe(32)}"
    
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash API key for storage"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    @staticmethod
    def sanitize_input(input_str: str) -> str:
        """Sanitize user input"""
        # Remove potential XSS characters
        dangerous_chars = ["<", ">", "\"", "'", "&", "javascript:", "data:", "vbscript:"]
        sanitized = input_str
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, "")
        return sanitized.strip()
    
    @staticmethod
    def validate_ip_address(ip: str) -> bool:
        """Validate IP address format"""
        import ipaddress
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def rate_limit_key(ip: str, endpoint: str) -> str:
        """Generate rate limiting key"""
        return f"rate_limit:{ip}:{endpoint}"
    
    @staticmethod
    def encrypt_data(data: str, key: str = None) -> str:
        """Encrypt sensitive data"""
        if not key:
            key = security_config.jwt_secret
        
        # Simple encryption for demo - in production use proper encryption
        encoded = data.encode('utf-8')
        encrypted = hashlib.sha256(encoded + key.encode()).hexdigest()
        return encrypted
    
    @staticmethod
    def audit_log(action: str, user_id: str, details: dict = None):
        """Log security events for audit"""
        if not security_config.enable_audit_logging:
            return
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "user_id": user_id,
            "details": details or {}
        }
        
        # In production, write to secure log file or database
        print(f"AUDIT: {log_entry}")


# Initialize managers
session_manager = SessionManager()
permission_manager = PermissionManager()
password_validator = PasswordValidator()
token_manager = TokenManager()
security_utils = SecurityUtils()


# Dependencies for FastAPI
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserModel:
    """Get current authenticated user"""
    token = credentials.credentials
    payload = token_manager.verify_token(token)
    
    username = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
    
    # In production, fetch from database
    user = UserModel(
        username=username,
        email=f"{username}@wakedock.local",
        permissions=payload.get("permissions", [])
    )
    
    return user


def require_permission(permission: str):
    """Decorator to require specific permission"""
    def permission_dependency(current_user: UserModel = Depends(get_current_user)):
        if not permission_manager.has_permission(current_user.permissions, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission}"
            )
        return current_user
    return permission_dependency


def require_admin(current_user: UserModel = Depends(get_current_user)):
    """Require admin privileges"""
    if not permission_manager.has_permission(current_user.permissions, "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user


# Export main components
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
