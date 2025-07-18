"""
Container serializers for data validation and serialization - MVC Architecture
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator

from wakedock.serializers.base_serializer import BaseSerializer

import logging
logger = logging.getLogger(__name__)


class ContainerCreateSerializer(BaseSerializer):
    """Serializer for container creation"""
    
    name: str = Field(..., min_length=1, max_length=128, description="Container name")
    image: str = Field(..., min_length=1, max_length=255, description="Docker image name")
    command: Optional[str] = Field(None, max_length=1000, description="Container command")
    environment: Optional[Dict[str, str]] = Field(default_factory=dict, description="Environment variables")
    ports: Optional[Dict[str, int]] = Field(default_factory=dict, description="Port mappings")
    volumes: Optional[Dict[str, str]] = Field(default_factory=dict, description="Volume mappings")
    labels: Optional[Dict[str, str]] = Field(default_factory=dict, description="Container labels")
    restart_policy: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Restart policy")
    resources: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Resource limits")
    
    @validator('name')
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Container name cannot be empty')
        return v.strip()
    
    @validator('image')
    def validate_image(cls, v):
        if not v or not v.strip():
            raise ValueError('Image name cannot be empty')
        return v.strip()
    
    @validator('ports')
    def validate_ports(cls, v):
        if v:
            for container_port, host_port in v.items():
                if not container_port.isdigit():
                    raise ValueError(f'Container port must be numeric: {container_port}')
                if not (1 <= int(container_port) <= 65535):
                    raise ValueError(f'Container port must be between 1 and 65535: {container_port}')
                if host_port and not (1 <= int(host_port) <= 65535):
                    raise ValueError(f'Host port must be between 1 and 65535: {host_port}')
        return v or {}
    
    @validator('volumes')
    def validate_volumes(cls, v):
        if v:
            for host_path, container_path in v.items():
                if not host_path.startswith('/'):
                    raise ValueError(f'Host path must be absolute: {host_path}')
                if not container_path.startswith('/'):
                    raise ValueError(f'Container path must be absolute: {container_path}')
        return v or {}


class ContainerUpdateSerializer(BaseSerializer):
    """Serializer for container updates"""
    
    name: Optional[str] = Field(None, min_length=1, max_length=128, description="Container name")
    labels: Optional[Dict[str, str]] = Field(None, description="Container labels")
    restart_policy: Optional[Dict[str, Any]] = Field(None, description="Restart policy")
    resources: Optional[Dict[str, Any]] = Field(None, description="Resource limits")
    
    @validator('name')
    def validate_name(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('Container name cannot be empty')
        return v.strip() if v else v


class ContainerSearchSerializer(BaseSerializer):
    """Serializer for container search"""
    
    query: str = Field(..., min_length=2, max_length=100, description="Search query")
    status: Optional[str] = Field(None, description="Container status filter")
    image: Optional[str] = Field(None, description="Image name filter")
    limit: int = Field(50, ge=1, le=100, description="Number of results to return")
    offset: int = Field(0, ge=0, description="Number of results to skip")
    
    @validator('query')
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError('Search query cannot be empty')
        return v.strip()
    
    @validator('status')
    def validate_status(cls, v):
        if v is not None:
            valid_statuses = ['created', 'running', 'paused', 'restarting', 'removing', 'exited', 'dead', 'stopped']
            if v not in valid_statuses:
                raise ValueError(f'Invalid status. Must be one of: {", ".join(valid_statuses)}')
        return v


class ContainerLogsSerializer(BaseSerializer):
    """Serializer for container logs request"""
    
    container_id: str = Field(..., min_length=12, max_length=64, description="Container ID")
    limit: int = Field(100, ge=1, le=1000, description="Number of log lines to return")
    follow: bool = Field(False, description="Follow log output")
    level: Optional[str] = Field(None, description="Log level filter")
    
    @validator('container_id')
    def validate_container_id(cls, v):
        if not v or not v.strip():
            raise ValueError('Container ID cannot be empty')
        return v.strip()
    
    @validator('level')
    def validate_level(cls, v):
        if v is not None:
            valid_levels = ['DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL']
            if v.upper() not in valid_levels:
                raise ValueError(f'Invalid log level. Must be one of: {", ".join(valid_levels)}')
        return v.upper() if v else v


class ContainerStatsSerializer(BaseSerializer):
    """Serializer for container statistics request"""
    
    container_id: str = Field(..., min_length=12, max_length=64, description="Container ID")
    
    @validator('container_id')
    def validate_container_id(cls, v):
        if not v or not v.strip():
            raise ValueError('Container ID cannot be empty')
        return v.strip()


class ContainerCommandSerializer(BaseSerializer):
    """Serializer for container command execution"""
    
    container_id: str = Field(..., min_length=12, max_length=64, description="Container ID")
    command: str = Field(..., min_length=1, max_length=1000, description="Command to execute")
    workdir: Optional[str] = Field(None, max_length=500, description="Working directory")
    
    @validator('container_id')
    def validate_container_id(cls, v):
        if not v or not v.strip():
            raise ValueError('Container ID cannot be empty')
        return v.strip()
    
    @validator('command')
    def validate_command(cls, v):
        if not v or not v.strip():
            raise ValueError('Command cannot be empty')
        return v.strip()


class ContainerMetricsSerializer(BaseSerializer):
    """Serializer for container metrics"""
    
    container_id: str = Field(..., description="Container ID")
    cpu_usage: float = Field(..., ge=0, le=100, description="CPU usage percentage")
    memory_usage: int = Field(..., ge=0, description="Memory usage in bytes")
    memory_limit: int = Field(..., ge=0, description="Memory limit in bytes")
    network_rx: int = Field(0, ge=0, description="Network bytes received")
    network_tx: int = Field(0, ge=0, description="Network bytes transmitted")
    disk_read: int = Field(0, ge=0, description="Disk bytes read")
    disk_write: int = Field(0, ge=0, description="Disk bytes written")
    
    @validator('container_id')
    def validate_container_id(cls, v):
        if not v or not v.strip():
            raise ValueError('Container ID cannot be empty')
        return v.strip()


class ContainerLogSerializer(BaseSerializer):
    """Serializer for container log entry"""
    
    container_id: str = Field(..., description="Container ID")
    level: str = Field(..., description="Log level")
    message: str = Field(..., min_length=1, max_length=10000, description="Log message")
    source: str = Field("container", max_length=100, description="Log source")
    
    @validator('container_id')
    def validate_container_id(cls, v):
        if not v or not v.strip():
            raise ValueError('Container ID cannot be empty')
        return v.strip()
    
    @validator('level')
    def validate_level(cls, v):
        if not v or not v.strip():
            raise ValueError('Log level cannot be empty')
        
        valid_levels = ['DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL']
        if v.upper() not in valid_levels:
            raise ValueError(f'Invalid log level. Must be one of: {", ".join(valid_levels)}')
        
        return v.upper()
    
    @validator('message')
    def validate_message(cls, v):
        if not v or not v.strip():
            raise ValueError('Log message cannot be empty')
        return v.strip()


class ContainerImageSerializer(BaseSerializer):
    """Serializer for Docker image operations"""
    
    image_name: str = Field(..., min_length=1, max_length=255, description="Docker image name")
    tag: Optional[str] = Field("latest", max_length=128, description="Image tag")
    
    @validator('image_name')
    def validate_image_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Image name cannot be empty')
        return v.strip()
    
    @validator('tag')
    def validate_tag(cls, v):
        if v is not None and not v.strip():
            raise ValueError('Tag cannot be empty')
        return v.strip() if v else "latest"


class ContainerFilterSerializer(BaseSerializer):
    """Serializer for container filtering"""
    
    status: Optional[str] = Field(None, description="Container status filter")
    image: Optional[str] = Field(None, description="Image name filter")
    label: Optional[Dict[str, str]] = Field(None, description="Label filters")
    name: Optional[str] = Field(None, description="Container name filter")
    limit: int = Field(50, ge=1, le=100, description="Number of results to return")
    offset: int = Field(0, ge=0, description="Number of results to skip")
    
    @validator('status')
    def validate_status(cls, v):
        if v is not None:
            valid_statuses = ['created', 'running', 'paused', 'restarting', 'removing', 'exited', 'dead', 'stopped']
            if v not in valid_statuses:
                raise ValueError(f'Invalid status. Must be one of: {", ".join(valid_statuses)}')
        return v


class ContainerResponseSerializer(BaseSerializer):
    """Serializer for container response data"""
    
    id: int = Field(..., description="Database ID")
    container_id: str = Field(..., description="Docker container ID")
    name: str = Field(..., description="Container name")
    image: str = Field(..., description="Docker image")
    command: Optional[str] = Field(None, description="Container command")
    status: str = Field(..., description="Container status")
    environment: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    ports: Dict[str, int] = Field(default_factory=dict, description="Port mappings")
    volumes: Dict[str, str] = Field(default_factory=dict, description="Volume mappings")
    labels: Dict[str, str] = Field(default_factory=dict, description="Container labels")
    restart_policy: Dict[str, Any] = Field(default_factory=dict, description="Restart policy")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    uptime: Optional[str] = Field(None, description="Container uptime")


class ContainerListResponseSerializer(BaseSerializer):
    """Serializer for container list response"""
    
    containers: List[ContainerResponseSerializer] = Field(..., description="List of containers")
    total_count: int = Field(..., description="Total number of containers")
    limit: int = Field(..., description="Results limit")
    offset: int = Field(..., description="Results offset")
    has_more: bool = Field(..., description="Whether there are more results")


class ContainerStatsResponseSerializer(BaseSerializer):
    """Serializer for container statistics response"""
    
    container: ContainerResponseSerializer = Field(..., description="Container info")
    current_stats: Dict[str, Any] = Field(..., description="Current container statistics")
    metrics_history: List[Dict[str, Any]] = Field(..., description="Historical metrics")
    uptime: Optional[str] = Field(None, description="Container uptime")


class ContainerLogsResponseSerializer(BaseSerializer):
    """Serializer for container logs response"""
    
    container: ContainerResponseSerializer = Field(..., description="Container info")
    docker_logs: List[str] = Field(..., description="Docker logs")
    db_logs: List[Dict[str, Any]] = Field(..., description="Database logs")
    total_logs: int = Field(..., description="Total number of logs")


class ContainerOperationResponseSerializer(BaseSerializer):
    """Serializer for container operation response"""
    
    container: ContainerResponseSerializer = Field(..., description="Container info")
    operation: str = Field(..., description="Operation performed")
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Operation message")
    timestamp: datetime = Field(..., description="Operation timestamp")


class ContainerSyncResponseSerializer(BaseSerializer):
    """Serializer for container sync response"""
    
    synced_count: int = Field(..., description="Number of containers synced")
    created_count: int = Field(..., description="Number of containers created")
    updated_count: int = Field(..., description="Number of containers updated")
    timestamp: datetime = Field(..., description="Sync timestamp")


class ContainerStatisticsResponseSerializer(BaseSerializer):
    """Serializer for container statistics response"""
    
    database_stats: Dict[str, Any] = Field(..., description="Database statistics")
    docker_stats: Dict[str, Any] = Field(..., description="Docker statistics")
    summary: Dict[str, Any] = Field(..., description="Summary statistics")
    timestamp: datetime = Field(..., description="Statistics timestamp")


class ContainerHealthResponseSerializer(BaseSerializer):
    """Serializer for container health check response"""
    
    container: ContainerResponseSerializer = Field(..., description="Container info")
    health_status: str = Field(..., description="Health status")
    health_check: Dict[str, Any] = Field(..., description="Health check details")
    timestamp: datetime = Field(..., description="Health check timestamp")


class ImageListResponseSerializer(BaseSerializer):
    """Serializer for Docker images list response"""
    
    images: List[Dict[str, Any]] = Field(..., description="List of Docker images")
    total_count: int = Field(..., description="Total number of images")
    timestamp: datetime = Field(..., description="List timestamp")


class ImagePullResponseSerializer(BaseSerializer):
    """Serializer for Docker image pull response"""
    
    image: Dict[str, Any] = Field(..., description="Pulled image info")
    success: bool = Field(..., description="Pull success status")
    message: str = Field(..., description="Pull message")
    timestamp: datetime = Field(..., description="Pull timestamp")
