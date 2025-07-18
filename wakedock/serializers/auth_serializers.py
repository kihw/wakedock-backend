"""
Serializers for authentication operations
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator, EmailStr

from wakedock.serializers.base_serializers import (
    BaseSerializer,
    BaseCreateSerializer,
    BaseUpdateSerializer,
    BaseResponseSerializer,
    PaginatedResponseSerializer
)


class UserRoleSerializer(BaseSerializer):
    """Serializer for user roles"""
    
    id: str = Field(..., description="Role ID")
    name: str = Field(..., description="Role name")
    description: Optional[str] = Field(None, description="Role description")
    permissions: List[str] = Field([], description="Role permissions")
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "id": "role-123",
                "name": "admin",
                "description": "Administrator role",
                "permissions": ["users:read", "users:write", "services:admin"]
            }
        }


class UserPermissionSerializer(BaseSerializer):
    """Serializer for user permissions"""
    
    id: str = Field(..., description="Permission ID")
    name: str = Field(..., description="Permission name")
    description: Optional[str] = Field(None, description="Permission description")
    resource: str = Field(..., description="Resource type")
    action: str = Field(..., description="Action type")
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "id": "perm-123",
                "name": "services:read",
                "description": "Read services",
                "resource": "services",
                "action": "read"
            }
        }


class UserSessionSerializer(BaseSerializer):
    """Serializer for user sessions"""
    
    id: str = Field(..., description="Session ID")
    created_at: datetime = Field(..., description="Session creation time")
    expires_at: datetime = Field(..., description="Session expiration time")
    is_active: bool = Field(..., description="Session active status")
    last_activity: Optional[datetime] = Field(None, description="Last activity time")
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "id": "session-123",
                "created_at": "2023-01-01T00:00:00Z",
                "expires_at": "2023-01-02T00:00:00Z",
                "is_active": True,
                "last_activity": "2023-01-01T12:00:00Z"
            }
        }


class LoginSerializer(BaseSerializer):
    """Serializer for login request"""
    
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=8, description="Password")
    remember_me: bool = Field(False, description="Remember me option")
    
    @validator('username')
    def validate_username(cls, v):
        import re
        pattern = r'^[a-zA-Z0-9_.-]+$'
        if not re.match(pattern, v):
            raise ValueError('Username can only contain letters, numbers, dots, hyphens, and underscores')
        return v
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "username": "john_doe",
                "password": "SecurePassword123!",
                "remember_me": False
            }
        }


class RegisterSerializer(BaseCreateSerializer):
    """Serializer for user registration"""
    
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=8, description="Password")
    confirm_password: str = Field(..., min_length=8, description="Confirm password")
    first_name: Optional[str] = Field(None, max_length=100, description="First name")
    last_name: Optional[str] = Field(None, max_length=100, description="Last name")
    roles: Optional[List[str]] = Field(None, description="User roles")
    
    @validator('username')
    def validate_username(cls, v):
        import re
        pattern = r'^[a-zA-Z0-9_.-]+$'
        if not re.match(pattern, v):
            raise ValueError('Username can only contain letters, numbers, dots, hyphens, and underscores')
        
        forbidden = ['admin', 'root', 'system', 'null', 'undefined']
        if v.lower() in forbidden:
            raise ValueError('This username is not allowed')
        
        return v
    
    @validator('password')
    def validate_password(cls, v):
        import re
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v
    
    @validator('confirm_password')
    def validate_confirm_password(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v
    
    @validator('first_name', 'last_name')
    def validate_name(cls, v):
        if v is not None:
            import re
            pattern = r'^[a-zA-Z\s\'-]+$'
            if not re.match(pattern, v):
                raise ValueError('Name can only contain letters, spaces, hyphens, and apostrophes')
        return v
    
    @validator('roles')
    def validate_roles(cls, v):
        if v is not None:
            valid_roles = ['admin', 'user', 'services_admin', 'viewer', 'operator']
            for role in v:
                if role not in valid_roles:
                    raise ValueError(f'Invalid role: {role}')
        return v
    
    class Config(BaseCreateSerializer.Config):
        schema_extra = {
            "example": {
                "username": "john_doe",
                "email": "john@example.com",
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
                "first_name": "John",
                "last_name": "Doe",
                "roles": ["user"]
            }
        }


class ProfileUpdateSerializer(BaseUpdateSerializer):
    """Serializer for profile update"""
    
    first_name: Optional[str] = Field(None, max_length=100, description="First name")
    last_name: Optional[str] = Field(None, max_length=100, description="Last name")
    email: Optional[EmailStr] = Field(None, description="Email address")
    
    @validator('first_name', 'last_name')
    def validate_name(cls, v):
        if v is not None:
            import re
            pattern = r'^[a-zA-Z\s\'-]+$'
            if not re.match(pattern, v):
                raise ValueError('Name can only contain letters, spaces, hyphens, and apostrophes')
        return v
    
    class Config(BaseUpdateSerializer.Config):
        schema_extra = {
            "example": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com"
            }
        }


class PasswordChangeSerializer(BaseSerializer):
    """Serializer for password change"""
    
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")
    confirm_new_password: str = Field(..., min_length=8, description="Confirm new password")
    
    @validator('new_password')
    def validate_new_password(cls, v):
        import re
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v
    
    @validator('confirm_new_password')
    def validate_confirm_new_password(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v
    
    @validator('new_password')
    def validate_password_different(cls, v, values):
        if 'current_password' in values and v == values['current_password']:
            raise ValueError('New password must be different from current password')
        return v
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "current_password": "OldPassword123!",
                "new_password": "NewPassword123!",
                "confirm_new_password": "NewPassword123!"
            }
        }


class PasswordResetRequestSerializer(BaseSerializer):
    """Serializer for password reset request"""
    
    email: EmailStr = Field(..., description="Email address")
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "email": "john@example.com"
            }
        }


class PasswordResetSerializer(BaseSerializer):
    """Serializer for password reset"""
    
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password")
    confirm_new_password: str = Field(..., min_length=8, description="Confirm new password")
    
    @validator('new_password')
    def validate_new_password(cls, v):
        import re
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
            raise ValueError('Password must contain at least one special character')
        return v
    
    @validator('confirm_new_password')
    def validate_confirm_new_password(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "token": "reset-token-123",
                "new_password": "NewPassword123!",
                "confirm_new_password": "NewPassword123!"
            }
        }


class TokenRefreshSerializer(BaseSerializer):
    """Serializer for token refresh"""
    
    token: str = Field(..., description="Current authentication token")
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
            }
        }


class UserResponseSerializer(BaseResponseSerializer):
    """Serializer for user response"""
    
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    is_active: bool = Field(..., description="User active status")
    roles: List[UserRoleSerializer] = Field([], description="User roles")
    permissions: List[str] = Field([], description="User permissions")
    last_login: Optional[datetime] = Field(None, description="Last login time")
    
    class Config(BaseResponseSerializer.Config):
        schema_extra = {
            "example": {
                "id": "user-123",
                "username": "john_doe",
                "email": "john@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "is_active": True,
                "roles": [
                    {
                        "id": "role-123",
                        "name": "user",
                        "description": "Standard user role",
                        "permissions": ["services:read"]
                    }
                ],
                "permissions": ["services:read"],
                "last_login": "2023-01-01T00:00:00Z",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z"
            }
        }


class UserSummarySerializer(BaseSerializer):
    """Serializer for user summary"""
    
    id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    is_active: bool = Field(..., description="User active status")
    roles: List[str] = Field([], description="User role names")
    last_login: Optional[datetime] = Field(None, description="Last login time")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "id": "user-123",
                "username": "john_doe",
                "email": "john@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "is_active": True,
                "roles": ["user"],
                "last_login": "2023-01-01T00:00:00Z",
                "created_at": "2023-01-01T00:00:00Z"
            }
        }


class UserDetailSerializer(BaseResponseSerializer):
    """Serializer for detailed user information"""
    
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    is_active: bool = Field(..., description="User active status")
    roles: List[UserRoleSerializer] = Field([], description="User roles")
    permissions: List[str] = Field([], description="User permissions")
    sessions: List[UserSessionSerializer] = Field([], description="Active sessions")
    last_login: Optional[datetime] = Field(None, description="Last login time")
    login_count: int = Field(0, description="Total login count")
    last_ip: Optional[str] = Field(None, description="Last IP address")
    
    class Config(BaseResponseSerializer.Config):
        schema_extra = {
            "example": {
                "id": "user-123",
                "username": "john_doe",
                "email": "john@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "is_active": True,
                "roles": [
                    {
                        "id": "role-123",
                        "name": "user",
                        "description": "Standard user role",
                        "permissions": ["services:read"]
                    }
                ],
                "permissions": ["services:read"],
                "sessions": [
                    {
                        "id": "session-123",
                        "created_at": "2023-01-01T00:00:00Z",
                        "expires_at": "2023-01-02T00:00:00Z",
                        "is_active": True,
                        "last_activity": "2023-01-01T12:00:00Z"
                    }
                ],
                "last_login": "2023-01-01T00:00:00Z",
                "login_count": 42,
                "last_ip": "192.168.1.100",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z"
            }
        }


class LoginResponseSerializer(BaseSerializer):
    """Serializer for login response"""
    
    user: UserResponseSerializer = Field(..., description="User information")
    token: str = Field(..., description="Authentication token")
    expires_at: datetime = Field(..., description="Token expiration time")
    permissions: List[str] = Field([], description="User permissions")
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "user": {
                    "id": "user-123",
                    "username": "john_doe",
                    "email": "john@example.com",
                    "first_name": "John",
                    "last_name": "Doe",
                    "is_active": True,
                    "roles": [
                        {
                            "id": "role-123",
                            "name": "user",
                            "description": "Standard user role",
                            "permissions": ["services:read"]
                        }
                    ],
                    "permissions": ["services:read"],
                    "last_login": "2023-01-01T00:00:00Z",
                    "created_at": "2023-01-01T00:00:00Z",
                    "updated_at": "2023-01-01T00:00:00Z"
                },
                "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                "expires_at": "2023-01-02T00:00:00Z",
                "permissions": ["services:read"]
            }
        }


class RoleAssignmentSerializer(BaseSerializer):
    """Serializer for role assignment"""
    
    user_ids: List[str] = Field(..., description="List of user IDs")
    roles: List[str] = Field(..., description="List of roles to assign")
    
    @validator('user_ids')
    def validate_user_ids(cls, v):
        if not v:
            raise ValueError('User IDs cannot be empty')
        if len(v) > 100:
            raise ValueError('Cannot assign roles to more than 100 users at once')
        return v
    
    @validator('roles')
    def validate_roles(cls, v):
        if not v:
            raise ValueError('Roles cannot be empty')
        valid_roles = ['admin', 'user', 'services_admin', 'viewer', 'operator']
        for role in v:
            if role not in valid_roles:
                raise ValueError(f'Invalid role: {role}')
        return v
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "user_ids": ["user-123", "user-456"],
                "roles": ["user", "viewer"]
            }
        }


class BulkUserActionSerializer(BaseSerializer):
    """Serializer for bulk user actions"""
    
    user_ids: List[str] = Field(..., description="List of user IDs")
    action: str = Field(..., description="Action to perform")
    options: Optional[Dict[str, Any]] = Field(None, description="Action options")
    
    @validator('user_ids')
    def validate_user_ids(cls, v):
        if not v:
            raise ValueError('User IDs cannot be empty')
        if len(v) > 100:
            raise ValueError('Cannot perform bulk action on more than 100 users at once')
        return v
    
    @validator('action')
    def validate_action(cls, v):
        valid_actions = ['activate', 'deactivate', 'delete', 'assign_role', 'remove_role']
        if v not in valid_actions:
            raise ValueError(f'Invalid action: {v}')
        return v
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "user_ids": ["user-123", "user-456"],
                "action": "activate",
                "options": {}
            }
        }


class UserSearchSerializer(BaseSerializer):
    """Serializer for user search"""
    
    query: Optional[str] = Field(None, max_length=255, description="Search query")
    role: Optional[str] = Field(None, description="Filter by role")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    limit: Optional[int] = Field(100, ge=1, le=1000, description="Limit results")
    offset: Optional[int] = Field(0, ge=0, description="Offset results")
    
    @validator('role')
    def validate_role(cls, v):
        if v is not None:
            valid_roles = ['admin', 'user', 'services_admin', 'viewer', 'operator']
            if v not in valid_roles:
                raise ValueError(f'Invalid role: {v}')
        return v
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "query": "john",
                "role": "user",
                "is_active": True,
                "limit": 50,
                "offset": 0
            }
        }


class AuthStatsSerializer(BaseSerializer):
    """Serializer for authentication statistics"""
    
    total_users: int = Field(..., description="Total number of users")
    active_users: int = Field(..., description="Number of active users")
    inactive_users: int = Field(..., description="Number of inactive users")
    active_sessions: int = Field(..., description="Number of active sessions")
    recent_logins: int = Field(..., description="Recent logins (last 24h)")
    timestamp: datetime = Field(..., description="Statistics timestamp")
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "total_users": 150,
                "active_users": 120,
                "inactive_users": 30,
                "active_sessions": 45,
                "recent_logins": 25,
                "timestamp": "2023-01-01T00:00:00Z"
            }
        }


class SecurityMetricsSerializer(BaseSerializer):
    """Serializer for security metrics"""
    
    active_lockouts: int = Field(..., description="Number of active lockouts")
    recent_login_attempts: int = Field(..., description="Recent login attempts")
    active_password_reset_tokens: int = Field(..., description="Active password reset tokens")
    total_login_attempts: int = Field(..., description="Total login attempts tracked")
    max_login_attempts: int = Field(..., description="Maximum login attempts allowed")
    lockout_duration: int = Field(..., description="Lockout duration in seconds")
    timestamp: datetime = Field(..., description="Metrics timestamp")
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "active_lockouts": 5,
                "recent_login_attempts": 150,
                "active_password_reset_tokens": 3,
                "total_login_attempts": 1200,
                "max_login_attempts": 5,
                "lockout_duration": 300,
                "timestamp": "2023-01-01T00:00:00Z"
            }
        }
