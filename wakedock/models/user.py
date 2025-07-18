"""
Modèle de données pour les utilisateurs
"""

from datetime import datetime, timedelta
from typing import List

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from wakedock.core.database import Base


class User(Base):
    """
    Modèle utilisateur avec authentification
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    
    # Statut et permissions
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Préférences utilisateur
    theme_preference = Column(String(20), default="light")  # light, dark, auto
    language_preference = Column(String(10), default="fr")
    timezone = Column(String(50), default="UTC")
    
    # Métadonnées de sécurité
    failed_login_attempts = Column(Integer, default=0)
    account_locked_until = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relations
    roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")
    theme_preferences = relationship("UserThemePreferences", back_populates="user", uselist=False, cascade="all, delete-orphan")
    
    # Relations Swarm
    swarm_clusters = relationship("SwarmCluster", back_populates="creator")
    swarm_services = relationship("SwarmService", back_populates="creator")
    swarm_networks = relationship("SwarmNetwork", back_populates="creator")
    swarm_secrets = relationship("SwarmSecret", back_populates="creator")
    swarm_configs = relationship("SwarmConfig", back_populates="creator")
    swarm_stacks = relationship("SwarmStack", back_populates="creator")
    swarm_load_balancers = relationship("SwarmLoadBalancer", back_populates="creator")
    
    # Relations Environment
    environments = relationship("Environment", back_populates="creator")
    environment_variables = relationship("EnvironmentVariable", back_populates="creator")
    environment_configs = relationship("EnvironmentConfig", back_populates="creator")
    environment_templates = relationship("EnvironmentTemplate", back_populates="creator")
    build_promotions_created = relationship("BuildPromotion", foreign_keys="BuildPromotion.created_by", back_populates="creator")
    build_promotions_approved = relationship("BuildPromotion", foreign_keys="BuildPromotion.approved_by", back_populates="approver")
    promotion_approvals = relationship("PromotionApproval", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"

    @property
    def is_locked(self) -> bool:
        """Vérifie si le compte est verrouillé"""
        if self.account_locked_until is None:
            return False
        return datetime.utcnow() < self.account_locked_until

    def lock_account(self, duration_minutes: int = 30):
        """Verrouille le compte pour une durée donnée"""
        self.account_locked_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
        self.failed_login_attempts += 1

    def unlock_account(self):
        """Déverrouille le compte"""
        self.account_locked_until = None
        self.failed_login_attempts = 0

    def get_permissions(self) -> List[str]:
        """Récupère toutes les permissions de l'utilisateur via ses rôles"""
        permissions = set()
        
        for user_role in self.roles:
            if user_role.role.is_active:
                for role_permission in user_role.role.permissions:
                    if role_permission.permission.is_active:
                        permissions.add(role_permission.permission.name)
        
        return list(permissions)


class Role(Base):
    """
    Modèle de rôle pour RBAC
    """
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # Statut
    is_active = Column(Boolean, default=True)
    is_system_role = Column(Boolean, default=False)  # Rôles système non modifiables
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    users = relationship("UserRole", back_populates="role")
    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Role(id={self.id}, name='{self.name}')>"


class Permission(Base):
    """
    Modèle de permission pour RBAC
    """
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # Catégorie et module
    category = Column(String(50), nullable=False)  # containers, monitoring, system, etc.
    module = Column(String(50), nullable=True)
    
    # Statut
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relations
    roles = relationship("RolePermission", back_populates="permission")

    def __repr__(self):
        return f"<Permission(id={self.id}, name='{self.name}', category='{self.category}')>"


class UserRole(Base):
    """
    Table d'association pour les utilisateurs et rôles
    """
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    
    # Métadonnées
    assigned_at = Column(DateTime, default=datetime.utcnow)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    expires_at = Column(DateTime, nullable=True)  # Rôle temporaire
    
    # Relations
    user = relationship("User", back_populates="roles", foreign_keys=[user_id])
    role = relationship("Role", back_populates="users")
    assigned_by_user = relationship("User", foreign_keys=[assigned_by])

    def __repr__(self):
        return f"<UserRole(user_id={self.user_id}, role_id={self.role_id})>"


class RolePermission(Base):
    """
    Table d'association pour les rôles et permissions
    """
    __tablename__ = "role_permissions"

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=False)
    
    # Métadonnées
    assigned_at = Column(DateTime, default=datetime.utcnow)
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relations
    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="roles")
    assigned_by_user = relationship("User", foreign_keys=[assigned_by])

    def __repr__(self):
        return f"<RolePermission(role_id={self.role_id}, permission_id={self.permission_id})>"


class AuditLog(Base):
    """
    Logs d'audit pour traçabilité sécurisée
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Action et contexte
    action = Column(String(100), nullable=False)  # login, logout, create_container, etc.
    resource_type = Column(String(50), nullable=True)  # container, image, service, etc.
    resource_id = Column(String(255), nullable=True)
    
    # Détails
    details = Column(Text, nullable=True)  # JSON avec détails de l'action
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Statut
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relations
    user = relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', user_id={self.user_id})>"


class UserThemePreferences(Base):
    """
    Préférences de thème utilisateur
    """
    __tablename__ = "user_theme_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    
    # Paramètres de thème
    theme_mode = Column(String(20), default="auto", nullable=False)  # light, dark, auto
    custom_colors = Column(JSON, default=dict, nullable=False)  # Couleurs personnalisées
    animations_enabled = Column(Boolean, default=True, nullable=False)
    transitions_enabled = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relations
    user = relationship("User", back_populates="theme_preferences")

    def __repr__(self):
        return f"<UserThemePreferences(id={self.id}, user_id={self.user_id}, theme_mode='{self.theme_mode}')>"
