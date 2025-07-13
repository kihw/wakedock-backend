"""Custom exceptions for WakeDock."""

from typing import Optional, Dict, Any


class WakeDockException(Exception):
    """Base exception for WakeDock."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class ServiceException(WakeDockException):
    """Exception related to service operations."""
    pass


class ServiceNotFoundError(ServiceException):
    """Service not found error."""
    
    def __init__(self, service_id: str):
        super().__init__(f"Service not found: {service_id}", {"service_id": service_id})


class ServiceAlreadyExistsError(ServiceException):
    """Service already exists error."""
    
    def __init__(self, service_name: str):
        super().__init__(f"Service already exists: {service_name}", {"service_name": service_name})


class ServiceConfigurationError(ServiceException):
    """Service configuration error."""
    
    def __init__(self, message: str, config_errors: Optional[list] = None):
        details = {"config_errors": config_errors} if config_errors else {}
        super().__init__(f"Service configuration error: {message}", details)


class ServiceStartError(ServiceException):
    """Service start error."""
    
    def __init__(self, service_name: str, reason: str):
        super().__init__(
            f"Failed to start service '{service_name}': {reason}",
            {"service_name": service_name, "reason": reason}
        )


class ServiceStopError(ServiceException):
    """Service stop error."""
    
    def __init__(self, service_name: str, reason: str):
        super().__init__(
            f"Failed to stop service '{service_name}': {reason}",
            {"service_name": service_name, "reason": reason}
        )


class DockerException(WakeDockException):
    """Exception related to Docker operations."""
    pass


class DockerDaemonError(DockerException):
    """Docker daemon not available or responding."""
    
    def __init__(self, reason: str):
        super().__init__(f"Docker daemon error: {reason}", {"reason": reason})


class DockerImageError(DockerException):
    """Docker image related error."""
    
    def __init__(self, image: str, reason: str):
        super().__init__(
            f"Docker image error for '{image}': {reason}",
            {"image": image, "reason": reason}
        )


class DockerContainerError(DockerException):
    """Docker container related error."""
    
    def __init__(self, container_id: str, reason: str):
        super().__init__(
            f"Docker container error for '{container_id}': {reason}",
            {"container_id": container_id, "reason": reason}
        )


class DatabaseException(WakeDockException):
    """Exception related to database operations."""
    pass


class DatabaseConnectionError(DatabaseException):
    """Database connection error."""
    
    def __init__(self, reason: str):
        super().__init__(f"Database connection error: {reason}", {"reason": reason})


class DatabaseMigrationError(DatabaseException):
    """Database migration error."""
    
    def __init__(self, reason: str):
        super().__init__(f"Database migration error: {reason}", {"reason": reason})


class AuthenticationException(WakeDockException):
    """Exception related to authentication."""
    pass


class InvalidCredentialsError(AuthenticationException):
    """Invalid credentials error."""
    
    def __init__(self):
        super().__init__("Invalid username or password")


class TokenExpiredError(AuthenticationException):
    """Token expired error."""
    
    def __init__(self):
        super().__init__("Authentication token has expired")


class InsufficientPermissionsError(AuthenticationException):
    """Insufficient permissions error."""
    
    def __init__(self, required_permission: str):
        super().__init__(
            f"Insufficient permissions. Required: {required_permission}",
            {"required_permission": required_permission}
        )


class ConfigurationException(WakeDockException):
    """Exception related to configuration."""
    pass


class InvalidConfigurationError(ConfigurationException):
    """Invalid configuration error."""
    
    def __init__(self, config_file: str, errors: list):
        super().__init__(
            f"Invalid configuration in {config_file}: {', '.join(errors)}",
            {"config_file": config_file, "errors": errors}
        )


class MissingConfigurationError(ConfigurationException):
    """Missing configuration error."""
    
    def __init__(self, config_key: str):
        super().__init__(
            f"Missing required configuration: {config_key}",
            {"config_key": config_key}
        )


class NetworkException(WakeDockException):
    """Exception related to network operations."""
    pass


class PortUnavailableError(NetworkException):
    """Port unavailable error."""
    
    def __init__(self, port: int):
        super().__init__(f"Port {port} is not available", {"port": port})


class DomainUnavailableError(NetworkException):
    """Domain unavailable error."""
    
    def __init__(self, domain: str):
        super().__init__(f"Domain {domain} is not available", {"domain": domain})


class CaddyException(WakeDockException):
    """Exception related to Caddy operations."""
    pass


class CaddyConfigurationError(CaddyException):
    """Caddy configuration error."""
    
    def __init__(self, reason: str):
        super().__init__(f"Caddy configuration error: {reason}", {"reason": reason})


class CaddyReloadError(CaddyException):
    """Caddy reload error."""
    
    def __init__(self, reason: str):
        super().__init__(f"Failed to reload Caddy: {reason}", {"reason": reason})


class MonitoringException(WakeDockException):
    """Exception related to monitoring operations."""
    pass


class HealthCheckError(MonitoringException):
    """Health check error."""
    
    def __init__(self, check_name: str, reason: str):
        super().__init__(
            f"Health check '{check_name}' failed: {reason}",
            {"check_name": check_name, "reason": reason}
        )


class MetricsCollectionError(MonitoringException):
    """Metrics collection error."""
    
    def __init__(self, reason: str):
        super().__init__(f"Metrics collection error: {reason}", {"reason": reason})


class ValidationException(WakeDockException):
    """Exception related to validation."""
    pass


class InvalidInputError(ValidationException):
    """Invalid input error."""
    
    def __init__(self, field: str, value: str, reason: str):
        super().__init__(
            f"Invalid {field} '{value}': {reason}",
            {"field": field, "value": value, "reason": reason}
        )


class ResourceLimitError(WakeDockException):
    """Resource limit exceeded error."""
    
    def __init__(self, resource: str, limit: str, current: str):
        super().__init__(
            f"Resource limit exceeded for {resource}. Limit: {limit}, Current: {current}",
            {"resource": resource, "limit": limit, "current": current}
        )


# Exception mapping for HTTP status codes
EXCEPTION_STATUS_MAP = {
    ServiceNotFoundError: 404,
    ServiceAlreadyExistsError: 409,
    ServiceConfigurationError: 400,
    ServiceStartError: 500,
    ServiceStopError: 500,
    DockerDaemonError: 503,
    DockerImageError: 400,
    DockerContainerError: 500,
    DatabaseConnectionError: 503,
    DatabaseMigrationError: 500,
    InvalidCredentialsError: 401,
    TokenExpiredError: 401,
    InsufficientPermissionsError: 403,
    InvalidConfigurationError: 400,
    MissingConfigurationError: 400,
    PortUnavailableError: 409,
    DomainUnavailableError: 409,
    CaddyConfigurationError: 500,
    CaddyReloadError: 500,
    HealthCheckError: 503,
    MetricsCollectionError: 500,
    InvalidInputError: 400,
    ResourceLimitError: 429,
}
