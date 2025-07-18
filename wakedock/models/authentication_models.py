"""
Models for authentication and user management
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from wakedock.models.base import BaseModel, AuditableModel

# Association table for user-role many-to-many relationship
user_roles = Table(
    'user_roles',
    BaseModel.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('role_id', Integer, ForeignKey('roles.id'), primary_key=True)
)

class User(AuditableModel):
    """Model for users"""
    
    __tablename__ = "users"
    
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    avatar_url = Column(String(500), nullable=True)
    timezone = Column(String(50), default="UTC")
    language = Column(String(10), default="en")
    last_login = Column(DateTime(timezone=True), nullable=True)
    login_count = Column(Integer, default=0)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime(timezone=True), nullable=True)
    email_verification_token = Column(String(255), nullable=True)
    preferences = Column(JSON, nullable=True)
    
    # Relations
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    sessions = relationship("UserSession", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.id}: {self.username}>"


class Role(AuditableModel):
    """Model for roles"""
    
    __tablename__ = "roles"
    
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    permissions = Column(JSON, nullable=True)  # List of permissions
    is_system = Column(Boolean, default=False)  # System roles cannot be deleted
    
    # Relations
    users = relationship("User", secondary=user_roles, back_populates="roles")
    
    def __repr__(self):
        return f"<Role {self.id}: {self.name}>"


class UserSession(BaseModel):
    """Model for user sessions"""
    
    __tablename__ = "user_sessions"
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token = Column(String(255), unique=True, nullable=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    last_activity = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relations
    user = relationship("User", back_populates="sessions")
    
    def __repr__(self):
        return f"<UserSession {self.id}: {self.user_id}>"


class Permission(BaseModel):
    """Model for permissions"""
    
    __tablename__ = "permissions"
    
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    resource = Column(String(255), nullable=False)  # containers, alerts, analytics, etc.
    action = Column(String(100), nullable=False)  # read, write, delete, execute
    
    def __repr__(self):
        return f"<Permission {self.id}: {self.name}>"


class UserActivity(BaseModel):
    """Model for user activity logs"""
    
    __tablename__ = "user_activity"
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(255), nullable=False)
    resource = Column(String(255), nullable=True)
    resource_id = Column(String(255), nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    details = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<UserActivity {self.id}: {self.action}>"


class APIKey(AuditableModel):
    """Model for API keys"""
    
    __tablename__ = "api_keys"
    
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True, index=True)
    permissions = Column(JSON, nullable=True)  # List of permissions
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<APIKey {self.id}: {self.name}>"
