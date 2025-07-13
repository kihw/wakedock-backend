"""
WakeDock Security Module

Provides comprehensive security features including input validation,
rate limiting, and security utilities.
"""

from .validation import (
    ValidationError,
    SecurityConfig,
    SecureString,
    ServiceName,
    DockerImage,
    PortMapping,
    FilePath,
    VolumeMount,
    EnvironmentVariable,
    NetworkName,
    IPAddress,
    URL,
    Password,
    Username,
    Email,
    ServiceCreateRequest,
    UserCreateRequest,
    ConfigUpdateRequest,
    SecurityUtils,
    sanitize_html,
    sanitize_sql_identifier,
    validate_json_input
)

from .rate_limit import (
    RateLimit,
    RateLimitResult,
    RateLimitError,
    RateLimitStrategy,
    RateLimitManager,
    RateLimitMiddleware,
    rate_limit,
    get_rate_limiter,
    init_rate_limiting
)


__all__ = [
    # Validation
    'ValidationError',
    'SecurityConfig',
    'SecureString',
    'ServiceName',
    'DockerImage',
    'PortMapping',
    'FilePath',
    'VolumeMount',
    'EnvironmentVariable',
    'NetworkName',
    'IPAddress',
    'URL',
    'Password',
    'Username',
    'Email',
    'ServiceCreateRequest',
    'UserCreateRequest',
    'ConfigUpdateRequest',
    'SecurityUtils',
    'sanitize_html',
    'sanitize_sql_identifier',
    'validate_json_input',
    
    # Rate Limiting
    'RateLimit',
    'RateLimitResult',
    'RateLimitError',
    'RateLimitStrategy',
    'RateLimitManager',
    'RateLimitMiddleware',
    'rate_limit',
    'get_rate_limiter',
    'init_rate_limiting'
]
