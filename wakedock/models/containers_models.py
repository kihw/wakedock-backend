"""
Models for containers management
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from wakedock.models.base import BaseModel, AuditableModel

class Container(AuditableModel):
    """Model for containers"""
    
    __tablename__ = "containers"
    
    name = Column(String(255), nullable=False)
    image = Column(String(255), nullable=False)
    tag = Column(String(100), default="latest")
    container_id = Column(String(255), nullable=True)  # Docker container ID
    status = Column(String(50), default="created")  # created, running, stopped, paused, etc.
    ports = Column(JSON, nullable=True)  # Port mappings
    volumes = Column(JSON, nullable=True)  # Volume mappings
    environment = Column(JSON, nullable=True)  # Environment variables
    labels = Column(JSON, nullable=True)  # Container labels
    networks = Column(JSON, nullable=True)  # Network configurations
    restart_policy = Column(String(50), default="no")  # no, always, unless-stopped, on-failure
    cpu_limit = Column(String(50), nullable=True)
    memory_limit = Column(String(50), nullable=True)
    stack_id = Column(Integer, ForeignKey("container_stacks.id"), nullable=True)
    
    # Relations
    stack = relationship("ContainerStack", back_populates="containers")
    
    def __repr__(self):
        return f"<Container {self.id}: {self.name}>"


class ContainerStack(AuditableModel):
    """Model for container stacks"""
    
    __tablename__ = "container_stacks"
    
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    compose_file = Column(Text, nullable=True)  # Docker Compose YAML content
    compose_version = Column(String(50), default="3.8")
    status = Column(String(50), default="created")  # created, running, stopped, error
    environment = Column(String(100), default="development")  # development, staging, production
    networks = Column(JSON, nullable=True)  # Network configurations
    volumes = Column(JSON, nullable=True)  # Volume configurations
    secrets = Column(JSON, nullable=True)  # Secrets configurations
    configs = Column(JSON, nullable=True)  # Configs
    
    # Relations
    containers = relationship("Container", back_populates="stack")
    
    def __repr__(self):
        return f"<ContainerStack {self.id}: {self.name}>"


class ContainerLog(BaseModel):
    """Model for container logs"""
    
    __tablename__ = "container_logs"
    
    container_id = Column(Integer, ForeignKey("containers.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    level = Column(String(20), default="info")  # debug, info, warning, error
    message = Column(Text, nullable=False)
    source = Column(String(100), nullable=True)  # stdout, stderr
    
    def __repr__(self):
        return f"<ContainerLog {self.id}: {self.level}>"


class ContainerMetrics(BaseModel):
    """Model for container metrics"""
    
    __tablename__ = "container_metrics"
    
    container_id = Column(Integer, ForeignKey("containers.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    cpu_usage = Column(String(50), nullable=True)  # CPU usage percentage
    memory_usage = Column(String(50), nullable=True)  # Memory usage
    memory_limit = Column(String(50), nullable=True)  # Memory limit
    network_rx = Column(String(50), nullable=True)  # Network received bytes
    network_tx = Column(String(50), nullable=True)  # Network transmitted bytes
    disk_usage = Column(String(50), nullable=True)  # Disk usage
    
    def __repr__(self):
        return f"<ContainerMetrics {self.id}: {self.timestamp}>"


class ContainerEvent(BaseModel):
    """Model for container events"""
    
    __tablename__ = "container_events"
    
    container_id = Column(Integer, ForeignKey("containers.id"), nullable=False)
    event_type = Column(String(50), nullable=False)  # start, stop, restart, destroy, etc.
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(String(255), nullable=True)
    details = Column(JSON, nullable=True)
    
    def __repr__(self):
        return f"<ContainerEvent {self.id}: {self.event_type}>"
