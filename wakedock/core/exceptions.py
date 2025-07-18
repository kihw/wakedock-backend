"""
Core exceptions for WakeDock
"""


class WakeDockError(Exception):
    """Base exception for WakeDock"""
    pass


class WakeDockException(WakeDockError):
    """General WakeDock exception (alias for WakeDockError)"""
    pass


class DatabaseError(WakeDockError):
    """Exception for database-related errors"""
    pass


class AnalyticsError(WakeDockError):
    """Exception for analytics-related errors"""
    pass


class ServiceError(WakeDockError):
    """Exception for service-related errors"""
    pass


class ConfigurationError(WakeDockError):
    """Exception for configuration errors"""
    pass


class ValidationError(WakeDockError):
    """Exception for validation errors"""
    pass


class NotFoundError(WakeDockError):
    """Exception for resource not found errors"""
    pass


class AuthenticationError(WakeDockError):
    """Exception for authentication errors"""
    pass


class AuthorizationError(WakeDockError):
    """Exception for authorization errors"""
    pass


class BusinessLogicError(WakeDockError):
    """Exception for business logic errors"""
    pass


class ContainerNotFoundError(WakeDockError):
    """Exception for container not found errors"""
    pass


class ContainerOperationError(WakeDockError):
    """Exception for container operation errors"""
    pass


class DockerError(WakeDockError):
    """Exception for Docker-related errors"""
    pass


class ImageNotFoundError(WakeDockError):
    """Exception for image not found errors"""
    pass


class NetworkError(WakeDockError):
    """Exception for network-related errors"""
    pass


class MetricNotFoundError(WakeDockError):
    """Exception for metric not found errors"""
    pass


class AlertError(WakeDockError):
    """Exception for alert-related errors"""
    pass


class AggregationError(WakeDockError):
    """Exception for data aggregation errors"""
    pass
