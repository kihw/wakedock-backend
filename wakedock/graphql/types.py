"""
GraphQL types for WakeDock
"""

import strawberry
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


@strawberry.enum
class ContainerStatus(Enum):
    """Container status enumeration"""
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    RESTARTING = "restarting"
    DEAD = "dead"


@strawberry.enum
class ServiceStatus(Enum):
    """Service status enumeration"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"
    UNKNOWN = "unknown"


@strawberry.enum
class NetworkDriver(Enum):
    """Network driver enumeration"""
    BRIDGE = "bridge"
    HOST = "host"
    OVERLAY = "overlay"
    MACVLAN = "macvlan"
    NONE = "none"


@strawberry.type
class Port:
    """Container port mapping"""
    container_port: int
    host_port: Optional[int]
    protocol: str
    host_ip: Optional[str]


@strawberry.type
class Mount:
    """Container mount point"""
    source: str
    destination: str
    type: str
    read_only: bool


@strawberry.type
class Container:
    """Container GraphQL type"""
    id: str
    name: str
    image: str
    status: ContainerStatus
    state: str
    created: datetime
    started: Optional[datetime]
    finished: Optional[datetime]
    ports: List[Port]
    mounts: List[Mount]
    labels: Dict[str, str]
    env_vars: Dict[str, str]
    networks: List[str]
    restart_policy: str
    cpu_percent: Optional[float]
    memory_usage: Optional[int]
    memory_limit: Optional[int]
    
    @strawberry.field
    def uptime(self) -> Optional[str]:
        """Calculate container uptime"""
        if self.started and self.status == ContainerStatus.RUNNING:
            delta = datetime.now() - self.started
            return str(delta)
        return None


@strawberry.type
class Service:
    """Service GraphQL type"""
    id: str
    name: str
    image: str
    replicas: int
    status: ServiceStatus
    created: datetime
    updated: datetime
    ports: List[Port]
    networks: List[str]
    labels: Dict[str, str]
    env_vars: Dict[str, str]
    constraints: List[str]
    mode: str
    endpoint_mode: str
    
    @strawberry.field
    def running_replicas(self) -> int:
        """Get number of running replicas"""
        # This would be resolved by the resolver
        return 0


@strawberry.type
class IPAMConfig:
    """IPAM configuration"""
    subnet: str
    gateway: Optional[str]
    ip_range: Optional[str]


@strawberry.type
class Network:
    """Network GraphQL type"""
    id: str
    name: str
    driver: NetworkDriver
    scope: str
    internal: bool
    attachable: bool
    ingress: bool
    ipam_config: List[IPAMConfig]
    containers: List[str]
    services: List[str]
    created: datetime
    labels: Dict[str, str]
    
    @strawberry.field
    def connected_count(self) -> int:
        """Get number of connected containers"""
        return len(self.containers)


@strawberry.type
class Volume:
    """Volume GraphQL type"""
    name: str
    driver: str
    mountpoint: str
    created: datetime
    labels: Dict[str, str]
    scope: str
    size: Optional[int]
    usage: Optional[int]
    
    @strawberry.field
    def used_by_count(self) -> int:
        """Get number of containers using this volume"""
        # This would be resolved by the resolver
        return 0


@strawberry.type
class SystemInfo:
    """System information GraphQL type"""
    version: str
    api_version: str
    docker_version: str
    platform: str
    architecture: str
    cpu_count: int
    memory_total: int
    memory_available: int
    disk_total: int
    disk_available: int
    uptime: str
    containers_running: int
    containers_stopped: int
    containers_paused: int
    images_count: int
    volumes_count: int
    networks_count: int
    
    @strawberry.field
    def memory_usage_percent(self) -> float:
        """Calculate memory usage percentage"""
        if self.memory_total > 0:
            used = self.memory_total - self.memory_available
            return (used / self.memory_total) * 100
        return 0.0
    
    @strawberry.field
    def disk_usage_percent(self) -> float:
        """Calculate disk usage percentage"""
        if self.disk_total > 0:
            used = self.disk_total - self.disk_available
            return (used / self.disk_total) * 100
        return 0.0


@strawberry.type
class HealthCheck:
    """Health check result"""
    status: str
    timestamp: datetime
    duration: float
    services: List[str]
    errors: List[str]
    
    @strawberry.field
    def is_healthy(self) -> bool:
        """Check if system is healthy"""
        return self.status == "healthy" and len(self.errors) == 0


@strawberry.type
class ContainerStats:
    """Container statistics"""
    container_id: str
    cpu_percent: float
    memory_usage: int
    memory_limit: int
    memory_percent: float
    network_rx_bytes: int
    network_tx_bytes: int
    block_read_bytes: int
    block_write_bytes: int
    timestamp: datetime
    
    @strawberry.field
    def memory_usage_mb(self) -> float:
        """Memory usage in MB"""
        return self.memory_usage / 1024 / 1024
    
    @strawberry.field
    def memory_limit_mb(self) -> float:
        """Memory limit in MB"""
        return self.memory_limit / 1024 / 1024


@strawberry.type
class ServiceStats:
    """Service statistics"""
    service_id: str
    replicas_running: int
    replicas_desired: int
    tasks_running: int
    tasks_desired: int
    cpu_usage: float
    memory_usage: int
    network_ingress: int
    network_egress: int
    timestamp: datetime
    
    @strawberry.field
    def replica_health_percent(self) -> float:
        """Replica health percentage"""
        if self.replicas_desired > 0:
            return (self.replicas_running / self.replicas_desired) * 100
        return 0.0


@strawberry.type
class NetworkStats:
    """Network statistics"""
    network_id: str
    containers_connected: int
    services_connected: int
    total_rx_bytes: int
    total_tx_bytes: int
    packets_rx: int
    packets_tx: int
    timestamp: datetime


@strawberry.type
class VolumeStats:
    """Volume statistics"""
    volume_name: str
    size_bytes: int
    used_bytes: int
    available_bytes: int
    used_by_containers: int
    timestamp: datetime
    
    @strawberry.field
    def usage_percent(self) -> float:
        """Volume usage percentage"""
        if self.size_bytes > 0:
            return (self.used_bytes / self.size_bytes) * 100
        return 0.0
    
    @strawberry.field
    def size_mb(self) -> float:
        """Volume size in MB"""
        return self.size_bytes / 1024 / 1024


# Input types for mutations
@strawberry.input
class ContainerInput:
    """Container creation input"""
    name: str
    image: str
    ports: Optional[List[str]] = None
    env_vars: Optional[Dict[str, str]] = None
    volumes: Optional[List[str]] = None
    networks: Optional[List[str]] = None
    labels: Optional[Dict[str, str]] = None
    restart_policy: Optional[str] = None


@strawberry.input
class ServiceInput:
    """Service creation input"""
    name: str
    image: str
    replicas: Optional[int] = 1
    ports: Optional[List[str]] = None
    env_vars: Optional[Dict[str, str]] = None
    networks: Optional[List[str]] = None
    labels: Optional[Dict[str, str]] = None
    constraints: Optional[List[str]] = None
    mode: Optional[str] = "replicated"


@strawberry.input
class NetworkInput:
    """Network creation input"""
    name: str
    driver: Optional[str] = "bridge"
    internal: Optional[bool] = False
    attachable: Optional[bool] = True
    labels: Optional[Dict[str, str]] = None
    ipam_config: Optional[List[str]] = None


@strawberry.input
class VolumeInput:
    """Volume creation input"""
    name: str
    driver: Optional[str] = "local"
    labels: Optional[Dict[str, str]] = None
    driver_opts: Optional[Dict[str, str]] = None


@strawberry.input
class PaginationInput:
    """Pagination input"""
    limit: Optional[int] = 20
    offset: Optional[int] = 0


@strawberry.input
class FilterInput:
    """Filter input"""
    status: Optional[List[str]] = None
    labels: Optional[Dict[str, str]] = None
    created_since: Optional[datetime] = None
    created_before: Optional[datetime] = None


@strawberry.input
class SortInput:
    """Sort input"""
    field: str
    direction: Optional[str] = "asc"