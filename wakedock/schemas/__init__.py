"""
WakeDock v0.6.1 - Enhanced API Schemas
Comprehensive Pydantic models for API request/response validation
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, validator

from wakedock.core.validation import CustomValidators

\1aseSchema:
    """
    ase schema with common configuratio

    """

    class Config:
        from_attributes = True
        validate_by_name = True
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: lambda v: str(v)}


\1ontainerStatus:
    """
    Description
    """

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    RESTARTING = "restarting"
    REMOVING = "removing"
    EXITED = "exited"
    DEAD = "dead"


\1estartPolicy:
    """
    Description
    """

    NO = "no"
    ALWAYS = "always"
    UNLESS_STOPPED = "unless-stopped"
    ON_FAILURE = "on-failure"


\1ogLevel:
    """
    Description
    """

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

# Container Schemas


\1ortMapping:
    """
    ort mapping schem

    """

    container_port: int = Field(..., ge=1, le=65535, description="Container port")
    host_port: int = Field(..., ge=1, le=65535, description="Host port")
    protocol: str = Field("tcp", pattern="^(tcp|udp)$", description="Protocol")

    @validator("container_port", "host_port")
    def validate_port(cls, v):
        if not CustomValidators.validate_port_number(v):
            raise ValueError("Invalid port number")
        return v


\1olumeMapping:
    """
    olume mapping schem

    """

    host_path: str = Field(..., description="Host path")
    container_path: str = Field(..., description="Container path")
    mode: str = Field("rw", pattern="^(ro|rw)$", description="Mount mode")

    @validator("container_path")
    def validate_container_path(cls, v):
        if not v.startswith("/"):
            raise ValueError("Container path must be absolute")
        return v


\1nvironmentVariable:
    """
    nvironment variable schem

    """

    name: str = Field(..., description="Variable name")
    value: str = Field(..., description="Variable value")

    @validator("name")
    def validate_name(cls, v):
        if not CustomValidators.validate_environment_variable_name(v):
            raise ValueError("Invalid environment variable name")
        return v


\1ontainerCreateRequest:
    """
    ontainer creation request schem

    """

    name: str = Field(..., min_length=1, max_length=253, description="Container name")
    image: str = Field(..., min_length=1, description="Docker image")
    command: Optional[List[str]] = Field(None, description="Command to run")
    environment: Optional[List[EnvironmentVariable]] = Field(
        [], description="Environment variables"
    )
    ports: Optional[List[PortMapping]] = Field([], description="Port mappings")
    volumes: Optional[List[VolumeMapping]] = Field([], description="Volume mappings")
    restart_policy: RestartPolicy = Field(
        RestartPolicy.NO, description="Restart policy"
    )
    cpu_limit: Optional[float] = Field(None, ge=0.1, le=1000, description="CPU limit")
    memory_limit: Optional[str] = Field(
        None, description="Memory limit (e.g., '512m', '1g')"
    )
    network_mode: Optional[str] = Field("bridge", description="Network mode")
    working_dir: Optional[str] = Field(None, description="Working directory")
    user: Optional[str] = Field(None, description="User to run as")

    @validator("name")
    def validate_container_name(cls, v):
        if not CustomValidators.validate_container_name(v):
            raise ValueError("Invalid container name format")
        return v

    @validator("image")
    def validate_image_name(cls, v):
        if not CustomValidators.validate_docker_image_name(v):
            raise ValueError("Invalid Docker image name format")
        return v

    @validator("memory_limit")
    def validate_memory_limit(cls, v):
        if v and not CustomValidators.validate_memory_limit(v):
            raise ValueError("Invalid memory limit format")
        return v

    @validator("cpu_limit")
    def validate_cpu_limit(cls, v):
        if v and not CustomValidators.validate_cpu_limit(v):
            raise ValueError("Invalid CPU limit value")
        return v


\1ontainerUpdateRequest:
    """
    ontainer update request schem

    """

    restart_policy: Optional[RestartPolicy] = None
    cpu_limit: Optional[float] = Field(None, ge=0.1, le=1000)
    memory_limit: Optional[str] = None

    @validator("memory_limit")
    def validate_memory_limit(cls, v):
        if v and not CustomValidators.validate_memory_limit(v):
            raise ValueError("Invalid memory limit format")
        return v

    @validator("cpu_limit")
    def validate_cpu_limit(cls, v):
        if v and not CustomValidators.validate_cpu_limit(v):
            raise ValueError("Invalid CPU limit value")
        return v


\1ontainerResponse:
    """
    ontainer response schem

    """

    id: str = Field(..., description="Container ID")
    name: str = Field(..., description="Container name")
    image: str = Field(..., description="Docker image")
    status: ContainerStatus = Field(..., description="Container status")
    state: Dict[str, Any] = Field(..., description="Container state")
    created: datetime = Field(..., description="Creation timestamp")
    started: Optional[datetime] = Field(None, description="Start timestamp")
    finished: Optional[datetime] = Field(None, description="Finish timestamp")
    ports: List[PortMapping] = Field([], description="Port mappings")
    volumes: List[VolumeMapping] = Field([], description="Volume mappings")
    environment: List[EnvironmentVariable] = Field(
        [], description="Environment variables"
    )
    restart_policy: RestartPolicy = Field(..., description="Restart policy")
    cpu_limit: Optional[float] = Field(None, description="CPU limit")
    memory_limit: Optional[str] = Field(None, description="Memory limit")
    network_mode: str = Field(..., description="Network mode")


\1ontainerListResponse:
    """
    ontainer list response schem

    """

    containers: List[ContainerResponse] = Field(..., description="List of containers")
    total: int = Field(..., description="Total number of containers")
    page: int = Field(1, description="Current page")
    per_page: int = Field(50, description="Items per page")

# Image Schemas


\1mageResponse:
    """
    ocker image response schem

    """

    id: str = Field(..., description="Image ID")
    repository: str = Field(..., description="Repository name")
    tag: str = Field(..., description="Image tag")
    size: int = Field(..., description="Image size in bytes")
    created: datetime = Field(..., description="Creation timestamp")
    labels: Dict[str, str] = Field({}, description="Image labels")


\1mageListResponse:
    """
    mage list response schem

    """

    images: List[ImageResponse] = Field(..., description="List of images")
    total: int = Field(..., description="Total number of images")

# Network Schemas


\1etworkResponse:
    """
    ocker network response schem

    """

    id: str = Field(..., description="Network ID")
    name: str = Field(..., description="Network name")
    driver: str = Field(..., description="Network driver")
    scope: str = Field(..., description="Network scope")
    created: datetime = Field(..., description="Creation timestamp")
    containers: List[str] = Field([], description="Connected container IDs")


\1etworkCreateRequest:
    """
    etwork creation request schem

    """

    name: str = Field(..., min_length=1, max_length=253, description="Network name")
    driver: str = Field("bridge", description="Network driver")
    options: Optional[Dict[str, str]] = Field({}, description="Driver options")

    @validator("name")
    def validate_network_name(cls, v):
        if not CustomValidators.validate_network_name(v):
            raise ValueError("Invalid network name format")
        return v

# Volume Schemas


\1olumeResponse:
    """
    ocker volume response schem

    """

    name: str = Field(..., description="Volume name")
    driver: str = Field(..., description="Volume driver")
    mountpoint: str = Field(..., description="Mount point")
    created: datetime = Field(..., description="Creation timestamp")
    labels: Dict[str, str] = Field({}, description="Volume labels")


\1olumeCreateRequest:
    """
    olume creation request schem

    """

    name: str = Field(..., min_length=1, max_length=253, description="Volume name")
    driver: str = Field("local", description="Volume driver")
    options: Optional[Dict[str, str]] = Field({}, description="Driver options")
    labels: Optional[Dict[str, str]] = Field({}, description="Volume labels")

    @validator("name")
    def validate_volume_name(cls, v):
        if not CustomValidators.validate_volume_name(v):
            raise ValueError("Invalid volume name format")
        return v

# System Schemas


\1ystemInfoResponse:
    """
    ystem information response schem

    """

    containers: int = Field(..., description="Number of containers")
    containers_running: int = Field(..., description="Number of running containers")
    containers_paused: int = Field(..., description="Number of paused containers")
    containers_stopped: int = Field(..., description="Number of stopped containers")
    images: int = Field(..., description="Number of images")
    docker_version: str = Field(..., description="Docker version")
    api_version: str = Field(..., description="Docker API version")
    os: str = Field(..., description="Operating system")
    architecture: str = Field(..., description="System architecture")
    kernel_version: str = Field(..., description="Kernel version")
    total_memory: int = Field(..., description="Total memory in bytes")
    cpu_count: int = Field(..., description="Number of CPUs")


\1ealthCheckResponse:
    """
    ealth check response schem

    """

    status: str = Field(..., description="Health status")
    timestamp: datetime = Field(..., description="Check timestamp")
    version: str = Field(..., description="Application version")
    uptime: float = Field(..., description="Uptime in seconds")
    checks: Dict[str, Any] = Field({}, description="Individual health checks")

# User and Authentication Schemas


\1serCreateRequest:
    """
    ser creation request schem

    """

    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: str = Field(..., description="Email address")
    password: str = Field(..., min_length=8, description="Password")
    full_name: Optional[str] = Field(None, max_length=200, description="Full name")

    @validator("username")
    def validate_username(cls, v):
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Username can only contain letters, numbers, underscores, and hyphens"
            )
        return v

    @validator("email")
    def validate_email(cls, v):
        # Basic email validation (consider using email-validator for production)
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, v):
            raise ValueError("Invalid email format")
        return v


\1serResponse:
    """
    ser response schem

    """

    id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    full_name: Optional[str] = Field(None, description="Full name")
    is_active: bool = Field(..., description="User active status")
    is_admin: bool = Field(..., description="Admin status")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")


\1oginRequest:
    """
    ogin request schem

    """

    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


\1okenResponse:
    """
    oken response schem

    """

    access_token: str = Field(..., description="Access token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    refresh_token: Optional[str] = Field(None, description="Refresh token")

# Notification Schemas


\1otificationCreateRequest:
    """
    otification creation request schem

    """

    title: str = Field(..., max_length=255, description="Notification title")
    message: str = Field(..., description="Notification message")
    type: str = Field(
        ..., pattern="^(info|success|warning|error)$", description="Notification type"
    )
    user_id: Optional[str] = Field(
        None, description="Target user ID (optional for broadcast)"
    )
    metadata: Optional[Dict[str, Any]] = Field({}, description="Additional metadata")


\1otificationResponse:
    """
    otification response schem

    """

    id: str = Field(..., description="Notification ID")
    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    type: str = Field(..., description="Notification type")
    is_read: bool = Field(..., description="Read status")
    created_at: datetime = Field(..., description="Creation timestamp")
    read_at: Optional[datetime] = Field(None, description="Read timestamp")
    metadata: Dict[str, Any] = Field({}, description="Additional metadata")

# Error Schemas


\1rrorResponse:
    """
    rror response schem

    """

    error: Dict[str, Any] = Field(..., description="Error details")


\1alidationErrorResponse:
    """
    alidation error response schem

    """

    error: Dict[str, Any] = Field(..., description="Validation error details")
    field_errors: Optional[Dict[str, List[str]]] = Field(
        None, description="Field-specific errors"
    )

# Pagination Schemas


\1aginationParams:
    """
    agination parameters schem

    """

    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(50, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(None, description="Sort field")
    sort_order: str = Field("asc", pattern="^(asc|desc)$", description="Sort order")


\1aginatedResponse:
    """
    aginated response schem

    """

    data: List[Any] = Field(..., description="Response data")
    pagination: Dict[str, Any] = Field(..., description="Pagination metadata")

# Metrics and Monitoring Schemas


\1ontainerStatsResponse:
    """
    ontainer statistics response schem

    """

    container_id: str = Field(..., description="Container ID")
    name: str = Field(..., description="Container name")
    cpu_percentage: float = Field(..., description="CPU usage percentage")
    memory_usage: int = Field(..., description="Memory usage in bytes")
    memory_limit: int = Field(..., description="Memory limit in bytes")
    memory_percentage: float = Field(..., description="Memory usage percentage")
    network_rx: int = Field(..., description="Network bytes received")
    network_tx: int = Field(..., description="Network bytes transmitted")
    block_read: int = Field(..., description="Block I/O bytes read")
    block_write: int = Field(..., description="Block I/O bytes written")
    timestamp: datetime = Field(..., description="Statistics timestamp")


\1ystemStatsResponse:
    """
    ystem statistics response schem

    """

    cpu_usage: float = Field(..., description="System CPU usage percentage")
    memory_usage: int = Field(..., description="System memory usage in bytes")
    memory_total: int = Field(..., description="Total system memory in bytes")
    disk_usage: int = Field(..., description="Disk usage in bytes")
    disk_total: int = Field(..., description="Total disk space in bytes")
    load_average: List[float] = Field(..., description="System load average")
    timestamp: datetime = Field(..., description="Statistics timestamp")

# WebSocket Schemas


\1ebSocketMessage:
    """
    ebSocket message schem

    """

    type: str = Field(..., description="Message type")
    data: Any = Field(..., description="Message data")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Message timestamp"
    )


\1ebSocketNotification:
    """
    ebSocket notification schem

    """

    type: str = Field("notification", description="Message type")
    notification: NotificationResponse = Field(..., description="Notification data")


\1ebSocketContainerEvent:
    """
    ebSocket container event schem

    """

    type: str = Field("container_event", description="Message type")
    event: str = Field(..., description="Event type (start, stop, create, destroy)")
    container: ContainerResponse = Field(..., description="Container data")

# Import re for validators
import re
