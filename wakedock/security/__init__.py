"""
WakeDock Security Module

Provides comprehensive security features including input validation,
rate limiting, and security utilities.
"""

from .rate_limit import (
    get_rate_limiter,
    init_rate_limiting,
    rate_limit,
    RateLimit,
    RateLimitError,
    RateLimitManager,
    RateLimitMiddleware,
    RateLimitResult,
    RateLimitStrategy,
)
from .validation import (
    ConfigUpdateRequest,
    DockerImage,
    Email,
    EnvironmentVariable,
    FilePath,
    IPAddress,
    NetworkName,
    Password,
    PortMapping,
    sanitize_html,
    sanitize_sql_identifier,
    SecureString,
    SecurityConfig,
    SecurityUtils,
    ServiceCreateRequest,
    ServiceName,
    URL,
    UserCreateRequest,
    Username,
    validate_json_input,
    ValidationError,
    VolumeMount,
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
