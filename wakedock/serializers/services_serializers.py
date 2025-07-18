"""
Serializers for Docker services
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator

from wakedock.serializers.base_serializers import (
    BaseSerializer,
    BaseCreateSerializer,
    BaseUpdateSerializer,
    BaseResponseSerializer,
    PaginatedResponseSerializer
)
from wakedock.models.stack import StackStatus, StackType


class ServicePortSerializer(BaseSerializer):
    """Serializer for service ports"""
    
    host: int = Field(..., ge=1, le=65535, description="Host port")
    container: int = Field(..., ge=1, le=65535, description="Container port")
    protocol: str = Field("tcp", description="Protocol (tcp/udp)")
    
    @validator('protocol')
    def validate_protocol(cls, v):
        if v not in ['tcp', 'udp']:
            raise ValueError('Protocol must be either "tcp" or "udp"')
        return v
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "host": 8080,
                "container": 80,
                "protocol": "tcp"
            }
        }


class ServiceVolumeSerializer(BaseSerializer):
    """Serializer for service volumes"""
    
    host: str = Field(..., description="Host path")
    container: str = Field(..., description="Container path")
    mode: str = Field("rw", description="Mount mode (rw/ro)")
    
    @validator('mode')
    def validate_mode(cls, v):
        if v not in ['rw', 'ro']:
            raise ValueError('Mode must be either "rw" or "ro"')
        return v
    
    @validator('container')
    def validate_container_path(cls, v):
        if not v.startswith('/'):
            raise ValueError('Container path must be absolute')
        return v
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "host": "/host/path",
                "container": "/container/path",
                "mode": "rw"
            }
        }


class ServiceHealthCheckSerializer(BaseSerializer):
    """Serializer for service health check"""
    
    test: List[str] = Field(..., description="Health check command")
    interval: int = Field(30, ge=1, description="Health check interval in seconds")
    timeout: int = Field(30, ge=1, description="Health check timeout in seconds")
    retries: int = Field(3, ge=1, description="Number of retries")
    start_period: int = Field(0, ge=0, description="Start period in seconds")
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "test": ["CMD", "curl", "-f", "http://localhost:8080/health"],
                "interval": 30,
                "timeout": 10,
                "retries": 3,
                "start_period": 60
            }
        }


class ServiceResourcesSerializer(BaseSerializer):
    """Serializer for service resources"""
    
    cpu_limit: Optional[str] = Field(None, description="CPU limit")
    memory_limit: Optional[str] = Field(None, description="Memory limit")
    cpu_reservation: Optional[str] = Field(None, description="CPU reservation")
    memory_reservation: Optional[str] = Field(None, description="Memory reservation")
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "cpu_limit": "0.5",
                "memory_limit": "512M",
                "cpu_reservation": "0.25",
                "memory_reservation": "256M"
            }
        }


class ServiceCreateSerializer(BaseCreateSerializer):
    """Serializer for creating services"""
    
    name: str = Field(..., min_length=1, max_length=63, description="Service name")
    type: StackType = Field(..., description="Service type")
    description: Optional[str] = Field(None, max_length=255, description="Service description")
    
    # Docker configuration
    image: Optional[str] = Field(None, description="Docker image")
    command: Optional[List[str]] = Field(None, description="Command to run")
    working_dir: Optional[str] = Field(None, description="Working directory")
    user: Optional[str] = Field(None, description="User to run as")
    
    # Network configuration
    ports: Optional[List[ServicePortSerializer]] = Field(None, description="Port mappings")
    networks: Optional[List[str]] = Field(None, description="Networks to connect to")
    hostname: Optional[str] = Field(None, description="Container hostname")
    
    # Storage configuration
    volumes: Optional[List[ServiceVolumeSerializer]] = Field(None, description="Volume mounts")
    tmpfs: Optional[List[str]] = Field(None, description="Tmpfs mounts")
    
    # Environment configuration
    environment: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    env_file: Optional[List[str]] = Field(None, description="Environment files")
    
    # Labels and metadata
    labels: Optional[Dict[str, str]] = Field(None, description="Service labels")
    tags: Optional[List[str]] = Field(None, description="Service tags")
    
    # Dependencies
    depends_on: Optional[List[str]] = Field(None, description="Service dependencies")
    
    # Health and lifecycle
    health_check: Optional[ServiceHealthCheckSerializer] = Field(None, description="Health check configuration")
    restart_policy: Optional[str] = Field("unless-stopped", description="Restart policy")
    
    # Resources
    resources: Optional[ServiceResourcesSerializer] = Field(None, description="Resource constraints")
    
    # Compose specific
    compose_file: Optional[str] = Field(None, description="Docker Compose file path")
    project_name: Optional[str] = Field(None, description="Docker Compose project name")
    
    @validator('name')
    def validate_name(cls, v):
        import re
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$'
        if not re.match(pattern, v):
            raise ValueError('Name must start and end with alphanumeric characters')
        return v
    
    @validator('restart_policy')
    def validate_restart_policy(cls, v):
        if v not in ['no', 'always', 'on-failure', 'unless-stopped']:
            raise ValueError('Invalid restart policy')
        return v
    
    class Config(BaseCreateSerializer.Config):
        schema_extra = {
            "example": {
                "name": "my-service",
                "type": "compose",
                "description": "My Docker service",
                "image": "nginx:latest",
                "ports": [
                    {
                        "host": 8080,
                        "container": 80,
                        "protocol": "tcp"
                    }
                ],
                "environment": {
                    "NODE_ENV": "production"
                },
                "volumes": [
                    {
                        "host": "/host/data",
                        "container": "/app/data",
                        "mode": "rw"
                    }
                ],
                "labels": {
                    "traefik.enable": "true"
                },
                "restart_policy": "unless-stopped"
            }
        }


class ServiceUpdateSerializer(BaseUpdateSerializer):
    """Serializer for updating services"""
    
    name: Optional[str] = Field(None, min_length=1, max_length=63, description="Service name")
    description: Optional[str] = Field(None, max_length=255, description="Service description")
    
    # Docker configuration
    image: Optional[str] = Field(None, description="Docker image")
    command: Optional[List[str]] = Field(None, description="Command to run")
    working_dir: Optional[str] = Field(None, description="Working directory")
    user: Optional[str] = Field(None, description="User to run as")
    
    # Network configuration
    ports: Optional[List[ServicePortSerializer]] = Field(None, description="Port mappings")
    networks: Optional[List[str]] = Field(None, description="Networks to connect to")
    hostname: Optional[str] = Field(None, description="Container hostname")
    
    # Storage configuration
    volumes: Optional[List[ServiceVolumeSerializer]] = Field(None, description="Volume mounts")
    tmpfs: Optional[List[str]] = Field(None, description="Tmpfs mounts")
    
    # Environment configuration
    environment: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    env_file: Optional[List[str]] = Field(None, description="Environment files")
    
    # Labels and metadata
    labels: Optional[Dict[str, str]] = Field(None, description="Service labels")
    tags: Optional[List[str]] = Field(None, description="Service tags")
    
    # Dependencies
    depends_on: Optional[List[str]] = Field(None, description="Service dependencies")
    
    # Health and lifecycle
    health_check: Optional[ServiceHealthCheckSerializer] = Field(None, description="Health check configuration")
    restart_policy: Optional[str] = Field(None, description="Restart policy")
    
    # Resources
    resources: Optional[ServiceResourcesSerializer] = Field(None, description="Resource constraints")
    
    @validator('name')
    def validate_name(cls, v):
        if v is not None:
            import re
            pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$'
            if not re.match(pattern, v):
                raise ValueError('Name must start and end with alphanumeric characters')
        return v
    
    @validator('restart_policy')
    def validate_restart_policy(cls, v):
        if v is not None and v not in ['no', 'always', 'on-failure', 'unless-stopped']:
            raise ValueError('Invalid restart policy')
        return v


class ServiceResponseSerializer(BaseResponseSerializer):
    """Serializer for service responses"""
    
    name: str = Field(..., description="Service name")
    type: StackType = Field(..., description="Service type")
    status: StackStatus = Field(..., description="Service status")
    description: Optional[str] = Field(None, description="Service description")
    
    # Docker configuration
    image: Optional[str] = Field(None, description="Docker image")
    command: Optional[List[str]] = Field(None, description="Command to run")
    working_dir: Optional[str] = Field(None, description="Working directory")
    user: Optional[str] = Field(None, description="User to run as")
    
    # Network configuration
    ports: Optional[List[ServicePortSerializer]] = Field(None, description="Port mappings")
    networks: Optional[List[str]] = Field(None, description="Networks to connect to")
    hostname: Optional[str] = Field(None, description="Container hostname")
    
    # Storage configuration
    volumes: Optional[List[ServiceVolumeSerializer]] = Field(None, description="Volume mounts")
    tmpfs: Optional[List[str]] = Field(None, description="Tmpfs mounts")
    
    # Environment configuration
    environment: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    env_file: Optional[List[str]] = Field(None, description="Environment files")
    
    # Labels and metadata
    labels: Optional[Dict[str, str]] = Field(None, description="Service labels")
    tags: Optional[List[str]] = Field(None, description="Service tags")
    
    # Dependencies
    depends_on: Optional[List[str]] = Field(None, description="Service dependencies")
    
    # Health and lifecycle
    health_check: Optional[ServiceHealthCheckSerializer] = Field(None, description="Health check configuration")
    restart_policy: Optional[str] = Field(None, description="Restart policy")
    
    # Resources
    resources: Optional[ServiceResourcesSerializer] = Field(None, description="Resource constraints")
    
    # Runtime information
    container_count: Optional[int] = Field(None, description="Number of containers")
    health_status: Optional[str] = Field(None, description="Health status")
    uptime: Optional[str] = Field(None, description="Service uptime")
    
    # Compose specific
    compose_file: Optional[str] = Field(None, description="Docker Compose file path")
    project_name: Optional[str] = Field(None, description="Docker Compose project name")
    
    class Config(BaseResponseSerializer.Config):
        schema_extra = {
            "example": {
                "id": "service-123",
                "name": "my-service",
                "type": "compose",
                "status": "running",
                "description": "My Docker service",
                "image": "nginx:latest",
                "ports": [
                    {
                        "host": 8080,
                        "container": 80,
                        "protocol": "tcp"
                    }
                ],
                "environment": {
                    "NODE_ENV": "production"
                },
                "volumes": [
                    {
                        "host": "/host/data",
                        "container": "/app/data",
                        "mode": "rw"
                    }
                ],
                "labels": {
                    "traefik.enable": "true"
                },
                "restart_policy": "unless-stopped",
                "container_count": 1,
                "health_status": "healthy",
                "uptime": "2h 15m",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z"
            }
        }


class ServiceSummarySerializer(BaseSerializer):
    """Serializer for service summary"""
    
    id: str = Field(..., description="Service ID")
    name: str = Field(..., description="Service name")
    type: StackType = Field(..., description="Service type")
    status: StackStatus = Field(..., description="Service status")
    description: Optional[str] = Field(None, description="Service description")
    container_count: Optional[int] = Field(None, description="Number of containers")
    port_count: Optional[int] = Field(None, description="Number of ports")
    health_status: Optional[str] = Field(None, description="Health status")
    created_at: datetime = Field(..., description="Creation timestamp")
    quick_actions: Optional[List[str]] = Field(None, description="Available quick actions")


class ServiceActionSerializer(BaseSerializer):
    """Serializer for service actions"""
    
    action: str = Field(..., description="Action to perform")
    options: Optional[Dict[str, Any]] = Field(None, description="Action options")
    
    @validator('action')
    def validate_action(cls, v):
        valid_actions = ['start', 'stop', 'restart', 'rebuild', 'delete', 'pause', 'unpause']
        if v not in valid_actions:
            raise ValueError(f'Action must be one of: {valid_actions}')
        return v
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "action": "restart",
                "options": {
                    "timeout": 30
                }
            }
        }


class ServiceBulkActionSerializer(BaseSerializer):
    """Serializer for bulk service actions"""
    
    service_ids: List[str] = Field(..., description="List of service IDs")
    action: str = Field(..., description="Action to perform")
    options: Optional[Dict[str, Any]] = Field(None, description="Action options")
    
    @validator('service_ids')
    def validate_service_ids(cls, v):
        if not v:
            raise ValueError('Service IDs cannot be empty')
        return v
    
    @validator('action')
    def validate_action(cls, v):
        valid_actions = ['start', 'stop', 'restart', 'rebuild', 'delete']
        if v not in valid_actions:
            raise ValueError(f'Action must be one of: {valid_actions}')
        return v
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "service_ids": ["service-1", "service-2"],
                "action": "restart",
                "options": {
                    "timeout": 30
                }
            }
        }


class ServiceFilterSerializer(BaseSerializer):
    """Serializer for service filters"""
    
    search: Optional[str] = Field(None, description="Search query")
    status: Optional[StackStatus] = Field(None, description="Filter by status")
    type: Optional[StackType] = Field(None, description="Filter by type")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "search": "nginx",
                "status": "running",
                "type": "compose",
                "tags": ["web", "production"]
            }
        }


class ServiceStatsSerializer(BaseSerializer):
    """Serializer for service statistics"""
    
    service_name: str = Field(..., description="Service name")
    cpu_usage: float = Field(..., description="CPU usage percentage")
    memory_usage: int = Field(..., description="Memory usage in MB")
    network_rx: int = Field(..., description="Network RX bytes")
    network_tx: int = Field(..., description="Network TX bytes")
    disk_usage: int = Field(..., description="Disk usage in bytes")
    uptime: str = Field(..., description="Service uptime")
    container_count: int = Field(..., description="Number of containers")
    timestamp: datetime = Field(..., description="Statistics timestamp")
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "service_name": "my-service",
                "cpu_usage": 25.5,
                "memory_usage": 512,
                "network_rx": 1024,
                "network_tx": 2048,
                "disk_usage": 1000000,
                "uptime": "2h 15m",
                "container_count": 1,
                "timestamp": "2023-01-01T00:00:00Z"
            }
        }


class ServiceLogsSerializer(BaseSerializer):
    """Serializer for service logs"""
    
    service_name: str = Field(..., description="Service name")
    logs: List[str] = Field(..., description="Log entries")
    log_count: int = Field(..., description="Number of log entries")
    timestamp: datetime = Field(..., description="Logs timestamp")
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "service_name": "my-service",
                "logs": [
                    "2023-01-01T00:00:00Z INFO: Service started",
                    "2023-01-01T00:01:00Z INFO: Processing request"
                ],
                "log_count": 2,
                "timestamp": "2023-01-01T00:00:00Z"
            }
        }
