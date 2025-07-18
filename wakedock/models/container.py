"""
Container models for database operations - MVC Architecture
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Float, ForeignKey, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref

from wakedock.core.database import Base

import logging
logger = logging.getLogger(__name__)


class Container(Base):
    """Container model for database operations"""
    
    __tablename__ = 'containers'
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Container identification
    container_id = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(128), index=True, nullable=False)
    
    # Container configuration
    image = Column(String(255), nullable=False)
    command = Column(Text, nullable=True)
    status = Column(String(32), index=True, nullable=False, default='created')
    
    # Container data
    environment = Column(JSON, nullable=True, default=dict)
    ports = Column(JSON, nullable=True, default=dict)
    volumes = Column(JSON, nullable=True, default=dict)
    labels = Column(JSON, nullable=True, default=dict)
    restart_policy = Column(JSON, nullable=True, default=dict)
    
    # Resource limits
    cpu_limit = Column(Float, nullable=True)
    memory_limit = Column(Integer, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    logs = relationship("ContainerLog", back_populates="container", cascade="all, delete-orphan")
    metrics = relationship("ContainerMetrics", back_populates="container", cascade="all, delete-orphan")
    networks = relationship("ContainerNetwork", back_populates="container", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_container_status_created', 'status', 'created_at'),
        Index('idx_container_image_status', 'image', 'status'),
        Index('idx_container_name_status', 'name', 'status'),
    )
    
    def __repr__(self):
        return f"<Container(id={self.id}, name='{self.name}', status='{self.status}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert container to dictionary"""
        return {
            'id': self.id,
            'container_id': self.container_id,
            'name': self.name,
            'image': self.image,
            'command': self.command,
            'status': self.status,
            'environment': self.environment or {},
            'ports': self.ports or {},
            'volumes': self.volumes or {},
            'labels': self.labels or {},
            'restart_policy': self.restart_policy or {},
            'cpu_limit': self.cpu_limit,
            'memory_limit': self.memory_limit,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def is_running(self) -> bool:
        """Check if container is running"""
        return self.status == 'running'
    
    def is_stopped(self) -> bool:
        """Check if container is stopped"""
        return self.status in ['stopped', 'exited']
    
    def get_uptime(self) -> Optional[str]:
        """Get container uptime"""
        if not self.created_at:
            return None
        
        uptime = datetime.utcnow() - self.created_at
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def get_port_mappings(self) -> List[str]:
        """Get formatted port mappings"""
        if not self.ports:
            return []
        
        mappings = []
        for container_port, host_port in self.ports.items():
            if host_port:
                mappings.append(f"{host_port}:{container_port}")
            else:
                mappings.append(f"{container_port}")
        
        return mappings
    
    def get_volume_mappings(self) -> List[str]:
        """Get formatted volume mappings"""
        if not self.volumes:
            return []
        
        mappings = []
        for host_path, container_path in self.volumes.items():
            mappings.append(f"{host_path}:{container_path}")
        
        return mappings
    
    def get_environment_list(self) -> List[str]:
        """Get environment variables as list"""
        if not self.environment:
            return []
        
        return [f"{key}={value}" for key, value in self.environment.items()]
    
    def has_label(self, key: str, value: Optional[str] = None) -> bool:
        """Check if container has specific label"""
        if not self.labels:
            return False
        
        if key not in self.labels:
            return False
        
        if value is not None:
            return self.labels[key] == value
        
        return True
    
    def get_restart_policy_name(self) -> str:
        """Get restart policy name"""
        if not self.restart_policy:
            return 'no'
        
        return self.restart_policy.get('Name', 'no')


class ContainerLog(Base):
    """Container log model for database operations"""
    
    __tablename__ = 'container_logs'
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to container
    container_id = Column(Integer, ForeignKey('containers.id'), nullable=False, index=True)
    
    # Log data
    log_level = Column(String(16), nullable=False, default='INFO')
    message = Column(Text, nullable=False)
    source = Column(String(100), nullable=False, default='container')
    
    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    container = relationship("Container", back_populates="logs")
    
    # Indexes
    __table_args__ = (
        Index('idx_container_logs_container_timestamp', 'container_id', 'timestamp'),
        Index('idx_container_logs_level_timestamp', 'log_level', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<ContainerLog(id={self.id}, container_id={self.container_id}, level='{self.log_level}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert log to dictionary"""
        return {
            'id': self.id,
            'container_id': self.container_id,
            'log_level': self.log_level,
            'message': self.message,
            'source': self.source,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
    
    def is_error(self) -> bool:
        """Check if log is an error"""
        return self.log_level in ['ERROR', 'FATAL']
    
    def is_warning(self) -> bool:
        """Check if log is a warning"""
        return self.log_level == 'WARN'
    
    def get_formatted_message(self) -> str:
        """Get formatted log message with timestamp"""
        timestamp_str = self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else 'Unknown'
        return f"[{timestamp_str}] [{self.log_level}] {self.message}"


class ContainerMetrics(Base):
    """Container metrics model for database operations"""
    
    __tablename__ = 'container_metrics'
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to container
    container_id = Column(Integer, ForeignKey('containers.id'), nullable=False, index=True)
    
    # CPU metrics
    cpu_usage = Column(Float, nullable=False, default=0.0)
    
    # Memory metrics
    memory_usage = Column(Integer, nullable=False, default=0)
    memory_limit = Column(Integer, nullable=False, default=0)
    
    # Network metrics
    network_rx = Column(Integer, nullable=False, default=0)
    network_tx = Column(Integer, nullable=False, default=0)
    
    # Disk metrics
    disk_read = Column(Integer, nullable=False, default=0)
    disk_write = Column(Integer, nullable=False, default=0)
    
    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    container = relationship("Container", back_populates="metrics")
    
    # Indexes
    __table_args__ = (
        Index('idx_container_metrics_container_timestamp', 'container_id', 'timestamp'),
        Index('idx_container_metrics_timestamp', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<ContainerMetrics(id={self.id}, container_id={self.container_id}, cpu={self.cpu_usage}%)>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            'id': self.id,
            'container_id': self.container_id,
            'cpu_usage': self.cpu_usage,
            'memory_usage': self.memory_usage,
            'memory_limit': self.memory_limit,
            'memory_percentage': self.get_memory_percentage(),
            'network_rx': self.network_rx,
            'network_tx': self.network_tx,
            'disk_read': self.disk_read,
            'disk_write': self.disk_write,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
    
    def get_memory_percentage(self) -> float:
        """Get memory usage as percentage"""
        if self.memory_limit == 0:
            return 0.0
        
        return round((self.memory_usage / self.memory_limit) * 100, 2)
    
    def get_formatted_memory(self) -> str:
        """Get formatted memory usage"""
        def format_bytes(bytes_value):
            for unit in ['B', 'KB', 'MB', 'GB']:
                if bytes_value < 1024:
                    return f"{bytes_value:.1f} {unit}"
                bytes_value /= 1024
            return f"{bytes_value:.1f} TB"
        
        usage = format_bytes(self.memory_usage)
        limit = format_bytes(self.memory_limit)
        percentage = self.get_memory_percentage()
        
        return f"{usage} / {limit} ({percentage}%)"
    
    def get_formatted_network(self) -> str:
        """Get formatted network usage"""
        def format_bytes(bytes_value):
            for unit in ['B', 'KB', 'MB', 'GB']:
                if bytes_value < 1024:
                    return f"{bytes_value:.1f} {unit}"
                bytes_value /= 1024
            return f"{bytes_value:.1f} TB"
        
        rx = format_bytes(self.network_rx)
        tx = format_bytes(self.network_tx)
        
        return f"RX: {rx} / TX: {tx}"
    
    def get_formatted_disk(self) -> str:
        """Get formatted disk usage"""
        def format_bytes(bytes_value):
            for unit in ['B', 'KB', 'MB', 'GB']:
                if bytes_value < 1024:
                    return f"{bytes_value:.1f} {unit}"
                bytes_value /= 1024
            return f"{bytes_value:.1f} TB"
        
        read = format_bytes(self.disk_read)
        write = format_bytes(self.disk_write)
        
        return f"Read: {read} / Write: {write}"
    
    def is_high_cpu(self, threshold: float = 80.0) -> bool:
        """Check if CPU usage is high"""
        return self.cpu_usage > threshold
    
    def is_high_memory(self, threshold: float = 80.0) -> bool:
        """Check if memory usage is high"""
        return self.get_memory_percentage() > threshold


class ContainerNetwork(Base):
    """Container network model for database operations"""
    
    __tablename__ = 'container_networks'
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to container
    container_id = Column(Integer, ForeignKey('containers.id'), nullable=False, index=True)
    
    # Network configuration
    network_name = Column(String(128), nullable=False)
    network_id = Column(String(64), nullable=False)
    ip_address = Column(String(45), nullable=True)  # Supports IPv4 and IPv6
    mac_address = Column(String(17), nullable=True)
    gateway = Column(String(45), nullable=True)
    subnet = Column(String(45), nullable=True)
    
    # Network settings
    network_mode = Column(String(32), nullable=False, default='bridge')
    aliases = Column(JSON, nullable=True, default=list)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    container = relationship("Container", back_populates="networks")
    
    # Indexes
    __table_args__ = (
        Index('idx_container_networks_container_network', 'container_id', 'network_name'),
        Index('idx_container_networks_network_id', 'network_id'),
        Index('idx_container_networks_ip_address', 'ip_address'),
    )
    
    def __repr__(self):
        return f"<ContainerNetwork(id={self.id}, container_id={self.container_id}, network='{self.network_name}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert network to dictionary"""
        return {
            'id': self.id,
            'container_id': self.container_id,
            'network_name': self.network_name,
            'network_id': self.network_id,
            'ip_address': self.ip_address,
            'mac_address': self.mac_address,
            'gateway': self.gateway,
            'subnet': self.subnet,
            'network_mode': self.network_mode,
            'aliases': self.aliases or [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def is_bridge_network(self) -> bool:
        """Check if network is bridge mode"""
        return self.network_mode == 'bridge'
    
    def is_host_network(self) -> bool:
        """Check if network is host mode"""
        return self.network_mode == 'host'
    
    def get_network_info(self) -> str:
        """Get formatted network information"""
        info_parts = [f"Network: {self.network_name}"]
        
        if self.ip_address:
            info_parts.append(f"IP: {self.ip_address}")
        
        if self.gateway:
            info_parts.append(f"Gateway: {self.gateway}")
        
        if self.subnet:
            info_parts.append(f"Subnet: {self.subnet}")
        
        return " | ".join(info_parts)


# Create all indexes
def create_container_indexes(engine):
    """Create additional indexes for container tables"""
    from sqlalchemy import text
    
    with engine.connect() as conn:
        # Additional indexes for performance
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_containers_status_updated 
            ON containers(status, updated_at DESC);
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_containers_image_created 
            ON containers(image, created_at DESC);
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_container_logs_container_level_timestamp 
            ON container_logs(container_id, log_level, timestamp DESC);
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_container_metrics_container_cpu_timestamp 
            ON container_metrics(container_id, cpu_usage DESC, timestamp DESC);
        """))
        
        conn.commit()
        logger.info("Created additional container indexes")
