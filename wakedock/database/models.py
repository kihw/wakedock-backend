"""SQLAlchemy models for WakeDock."""

from datetime import datetime
from typing import Optional, List
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, 
    ForeignKey, Enum, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class ServiceStatus(PyEnum):
    """Enumeration for service status."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"
    UNKNOWN = "unknown"


class UserRole(PyEnum):
    """Enumeration for user roles."""
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class User(Base):
    """User model for authentication and authorization."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    
    # Relationships
    services = relationship("Service", back_populates="owner")
    
    def __repr__(self) -> str:
        return f"<User(username='{self.username}', role='{self.role.value}')>"


class Service(Base):
    """Service model representing Docker services managed by WakeDock."""
    
    __tablename__ = "services"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text)
    
    # Docker configuration
    image = Column(String(255), nullable=False)
    tag = Column(String(50), default="latest")
    ports = Column(JSON)  # Port mapping configuration
    volumes = Column(JSON)  # Volume mapping configuration
    environment = Column(JSON)  # Environment variables
    labels = Column(JSON)  # Docker labels
    networks = Column(JSON)  # Network configuration
    
    # Service configuration
    domain = Column(String(255))  # Domain for Caddy routing
    subdomain = Column(String(100))  # Subdomain for automatic routing
    enable_ssl = Column(Boolean, default=True)
    enable_auth = Column(Boolean, default=False)
    
    # Status and monitoring
    status = Column(Enum(ServiceStatus), default=ServiceStatus.STOPPED, nullable=False)
    container_id = Column(String(64))  # Docker container ID
    
    # Resource limits
    memory_limit = Column(String(20))  # e.g., "512m", "1g"
    cpu_limit = Column(String(10))  # e.g., "0.5", "1.0"
    
    # Wake configuration
    wake_enabled = Column(Boolean, default=True, nullable=False)
    sleep_timeout = Column(Integer, default=300)  # seconds
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_wake = Column(DateTime(timezone=True))
    last_sleep = Column(DateTime(timezone=True))
    
    # Foreign keys
    owner_id = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    owner = relationship("User", back_populates="services")
    
    def __repr__(self) -> str:
        return f"<Service(name='{self.name}', status='{self.status.value}')>"


class Configuration(Base):
    """System configuration model."""
    
    __tablename__ = "configurations"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(Text)
    description = Column(Text)
    category = Column(String(50), default="general")
    is_secret = Column(Boolean, default=False)  # For sensitive configuration
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self) -> str:
        return f"<Configuration(key='{self.key}', category='{self.category}')>"


class ServiceLog(Base):
    """Service log entries for monitoring and debugging."""
    
    __tablename__ = "service_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    level = Column(String(10), nullable=False)  # INFO, WARN, ERROR, DEBUG
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Additional context
    container_id = Column(String(64))
    source = Column(String(50))  # e.g., "docker", "wakedock", "caddy"
    
    # Index for performance
    __table_args__ = (
        UniqueConstraint('id'),
    )
    
    def __repr__(self) -> str:
        return f"<ServiceLog(service_id={self.service_id}, level='{self.level}')>"


class ServiceMetric(Base):
    """Service metrics for monitoring and analytics."""
    
    __tablename__ = "service_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    
    # Resource metrics
    cpu_usage = Column(String(10))  # Percentage
    memory_usage = Column(String(20))  # e.g., "256MB"
    memory_limit = Column(String(20))
    network_rx = Column(String(20))  # Bytes received
    network_tx = Column(String(20))  # Bytes transmitted
    
    # Timestamps
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Index for performance on queries
    __table_args__ = (
        UniqueConstraint('id'),
    )
    
    def __repr__(self) -> str:
        return f"<ServiceMetric(service_id={self.service_id}, timestamp={self.timestamp})>"
