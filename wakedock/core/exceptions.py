"""
Core exceptions for WakeDock
"""


class WakeDockError(Exception):
    """Base exception for WakeDock"""
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
