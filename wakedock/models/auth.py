"""
Authentication models for WakeDock
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Table, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from wakedock.models.base import BaseModel


# Association table for many-to-many relationship between users and roles
user_roles = Table(
    'user_roles',
    BaseModel.metadata,
    Column('user_id', String, ForeignKey('users.id'), primary_key=True),
    Column('role_id', String, ForeignKey('roles.id'), primary_key=True)
)

# Association table for many-to-many relationship between roles and permissions
role_permissions = Table(
    'role_permissions',
    BaseModel.metadata,
    Column('role_id', String, ForeignKey('roles.id'), primary_key=True),
    Column('permission_id', String, ForeignKey('permissions.id'), primary_key=True)
)


class User(BaseModel):
    """User model for authentication"""
    
    __tablename__ = 'users'
    
    # Basic user information
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # Personal information
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    
    # Status and timestamps
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    last_login = Column(DateTime, nullable=True)
    login_count = Column(Integer, default=0, nullable=False)
    last_ip = Column(String(45), nullable=True)  # IPv6 support
    
    # Relationships
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("UserAuditLog", back_populates="user", cascade="all, delete-orphan")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.id:
            self.id = f"user_{uuid.uuid4().hex[:8]}"
    
    def __repr__(self):
        return f"<User(id='{self.id}', username='{self.username}', email='{self.email}')>"
    
    def to_dict(self):
        """Convert user to dictionary"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'login_count': self.login_count,
            'last_ip': self.last_ip,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'roles': [role.name for role in self.roles] if self.roles else []
        }
    
    def get_permissions(self):
        """Get all permissions for this user"""
        permissions = set()
        for role in self.roles:
            for permission in role.permissions:
                permissions.add(permission.name)
        return list(permissions)
    
    def has_permission(self, permission_name):
        """Check if user has a specific permission"""
        return permission_name in self.get_permissions()
    
    def has_role(self, role_name):
        """Check if user has a specific role"""
        return any(role.name == role_name for role in self.roles)


class Role(BaseModel):
    """Role model for authorization"""
    
    __tablename__ = 'roles'
    
    # Role information
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, default=False, nullable=False)  # System roles cannot be deleted
    
    # Relationships
    users = relationship("User", secondary=user_roles, back_populates="roles")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.id:
            self.id = f"role_{uuid.uuid4().hex[:8]}"
    
    def __repr__(self):
        return f"<Role(id='{self.id}', name='{self.name}')>"
    
    def to_dict(self):
        """Convert role to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_system': self.is_system,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'permissions': [permission.name for permission in self.permissions] if self.permissions else []
        }
    
    def add_permission(self, permission):
        """Add permission to role"""
        if permission not in self.permissions:
            self.permissions.append(permission)
    
    def remove_permission(self, permission):
        """Remove permission from role"""
        if permission in self.permissions:
            self.permissions.remove(permission)


class Permission(BaseModel):
    """Permission model for fine-grained authorization"""
    
    __tablename__ = 'permissions'
    
    # Permission information
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    resource = Column(String(50), nullable=False)  # e.g., 'services', 'users', 'containers'
    action = Column(String(50), nullable=False)    # e.g., 'read', 'write', 'delete', 'admin'
    
    # Relationships
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.id:
            self.id = f"perm_{uuid.uuid4().hex[:8]}"
    
    def __repr__(self):
        return f"<Permission(id='{self.id}', name='{self.name}')>"
    
    def to_dict(self):
        """Convert permission to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'resource': self.resource,
            'action': self.action,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class UserSession(BaseModel):
    """User session model for tracking active sessions"""
    
    __tablename__ = 'user_sessions'
    
    # Session information
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    token = Column(String(500), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Session metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    device_info = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.id:
            self.id = f"session_{uuid.uuid4().hex[:8]}"
    
    def __repr__(self):
        return f"<UserSession(id='{self.id}', user_id='{self.user_id}', is_active={self.is_active})>"
    
    def to_dict(self):
        """Convert session to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'token': self.token,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_active': self.is_active,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'device_info': self.device_info,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def is_expired(self):
        """Check if session is expired"""
        return datetime.utcnow() > self.expires_at
    
    def revoke(self):
        """Revoke the session"""
        self.is_active = False
        self.updated_at = datetime.utcnow()


class UserAuditLog(BaseModel):
    """User audit log model for tracking user actions"""
    
    __tablename__ = 'user_audit_logs'
    
    # Audit information
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    action = Column(String(100), nullable=False)
    resource = Column(String(100), nullable=True)
    resource_id = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)  # JSON string
    
    # Request metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    request_id = Column(String(100), nullable=True)
    
    # Result
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.id:
            self.id = f"audit_{uuid.uuid4().hex[:8]}"
    
    def __repr__(self):
        return f"<UserAuditLog(id='{self.id}', user_id='{self.user_id}', action='{self.action}')>"
    
    def to_dict(self):
        """Convert audit log to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'resource': self.resource,
            'resource_id': self.resource_id,
            'details': self.details,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'request_id': self.request_id,
            'success': self.success,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class PasswordResetToken(BaseModel):
    """Password reset token model"""
    
    __tablename__ = 'password_reset_tokens'
    
    # Token information
    user_id = Column(String, ForeignKey('users.id'), nullable=False)
    token = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    
    # Request metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.id:
            self.id = f"reset_{uuid.uuid4().hex[:8]}"
    
    def __repr__(self):
        return f"<PasswordResetToken(id='{self.id}', user_id='{self.user_id}', is_used={self.is_used})>"
    
    def to_dict(self):
        """Convert token to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'token': self.token,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_used': self.is_used,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def is_expired(self):
        """Check if token is expired"""
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self):
        """Check if token is valid (not used and not expired)"""
        return not self.is_used and not self.is_expired()
    
    def use(self):
        """Mark token as used"""
        self.is_used = True
        self.updated_at = datetime.utcnow()


class UserPreferences(BaseModel):
    """User preferences model"""
    
    __tablename__ = 'user_preferences'
    
    # Preference information
    user_id = Column(String, ForeignKey('users.id'), nullable=False, unique=True)
    theme = Column(String(20), default='light', nullable=False)
    language = Column(String(10), default='en', nullable=False)
    timezone = Column(String(50), default='UTC', nullable=False)
    
    # Notification preferences
    email_notifications = Column(Boolean, default=True, nullable=False)
    push_notifications = Column(Boolean, default=True, nullable=False)
    
    # Dashboard preferences
    dashboard_layout = Column(Text, nullable=True)  # JSON string
    default_view = Column(String(50), default='dashboard', nullable=False)
    
    # Relationships
    user = relationship("User")
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.id:
            self.id = f"prefs_{uuid.uuid4().hex[:8]}"
    
    def __repr__(self):
        return f"<UserPreferences(id='{self.id}', user_id='{self.user_id}')>"
    
    def to_dict(self):
        """Convert preferences to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'theme': self.theme,
            'language': self.language,
            'timezone': self.timezone,
            'email_notifications': self.email_notifications,
            'push_notifications': self.push_notifications,
            'dashboard_layout': self.dashboard_layout,
            'default_view': self.default_view,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


# Create default roles and permissions
def create_default_roles_and_permissions():
    """Create default roles and permissions for the system"""
    
    # Default permissions
    permissions = [
        # User management
        Permission(name='users:read', description='View users', resource='users', action='read'),
        Permission(name='users:write', description='Create/update users', resource='users', action='write'),
        Permission(name='users:delete', description='Delete users', resource='users', action='delete'),
        Permission(name='users:admin', description='Full user management', resource='users', action='admin'),
        
        # Service management
        Permission(name='services:read', description='View services', resource='services', action='read'),
        Permission(name='services:write', description='Create/update services', resource='services', action='write'),
        Permission(name='services:delete', description='Delete services', resource='services', action='delete'),
        Permission(name='services:admin', description='Full service management', resource='services', action='admin'),
        
        # Container management
        Permission(name='containers:read', description='View containers', resource='containers', action='read'),
        Permission(name='containers:write', description='Create/update containers', resource='containers', action='write'),
        Permission(name='containers:delete', description='Delete containers', resource='containers', action='delete'),
        Permission(name='containers:admin', description='Full container management', resource='containers', action='admin'),
        
        # System management
        Permission(name='system:read', description='View system info', resource='system', action='read'),
        Permission(name='system:write', description='Update system settings', resource='system', action='write'),
        Permission(name='system:admin', description='Full system management', resource='system', action='admin'),
        
        # Dashboard access
        Permission(name='dashboard:read', description='View dashboard', resource='dashboard', action='read'),
        Permission(name='dashboard:write', description='Configure dashboard', resource='dashboard', action='write'),
    ]
    
    # Default roles
    roles = [
        # Admin role - full access
        Role(
            name='admin',
            description='Administrator with full system access',
            is_system=True
        ),
        
        # Services admin role - full service management
        Role(
            name='services_admin',
            description='Service administrator with full service management access',
            is_system=True
        ),
        
        # User role - basic access
        Role(
            name='user',
            description='Standard user with basic access',
            is_system=True
        ),
        
        # Viewer role - read-only access
        Role(
            name='viewer',
            description='Read-only access to view resources',
            is_system=True
        ),
        
        # Operator role - operational access
        Role(
            name='operator',
            description='Operational access to manage services and containers',
            is_system=True
        ),
    ]
    
    return roles, permissions


def assign_default_permissions():
    """Assign default permissions to roles"""
    
    # This would typically be done in a database migration
    # Here's the mapping for reference:
    
    permission_mapping = {
        'admin': [
            'users:admin', 'services:admin', 'containers:admin', 'system:admin',
            'dashboard:read', 'dashboard:write'
        ],
        'services_admin': [
            'services:admin', 'containers:admin', 'dashboard:read', 'dashboard:write'
        ],
        'operator': [
            'services:read', 'services:write', 'containers:read', 'containers:write',
            'dashboard:read'
        ],
        'user': [
            'services:read', 'containers:read', 'dashboard:read'
        ],
        'viewer': [
            'services:read', 'containers:read', 'dashboard:read'
        ]
    }
    
    return permission_mapping
