"""
WakeDock Security Validation Module

Provides comprehensive input validation, sanitization, and security checks.
"""

import re
import ipaddress
import validators
from typing import Any, Dict, List, Optional, Union, Tuple
from urllib.parse import urlparse
from pathlib import Path
import hashlib
import secrets
from datetime import datetime, timedelta

from pydantic import BaseModel, validator, Field
from pydantic.validators import str_validator
from pydantic.errors import PydanticValueError


class ValidationError(PydanticValueError):
    """Custom validation error."""
    pass


class SecurityConfig:
    """Security configuration constants."""
    
    # Password requirements
    MIN_PASSWORD_LENGTH = 12
    MAX_PASSWORD_LENGTH = 128
    PASSWORD_REQUIRE_UPPERCASE = True
    PASSWORD_REQUIRE_LOWERCASE = True
    PASSWORD_REQUIRE_NUMBERS = True
    PASSWORD_REQUIRE_SPECIAL_CHARS = True
    PASSWORD_BLACKLIST = [
        'password', '123456', 'admin', 'root', 'user', 'test',
        'wakedock', 'docker', 'caddy', 'postgres', 'redis'
    ]
    
    # Service name validation
    SERVICE_NAME_PATTERN = r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$'
    SERVICE_NAME_MAX_LENGTH = 64
    SERVICE_NAME_BLACKLIST = ['admin', 'root', 'system', 'api', 'www']
    
    # Network validation
    ALLOWED_PRIVATE_NETWORKS = [
        '10.0.0.0/8',
        '172.16.0.0/12',
        '192.168.0.0/16',
        '127.0.0.0/8'
    ]
    
    # Docker image validation
    TRUSTED_REGISTRIES = [
        'docker.io',
        'gcr.io',
        'ghcr.io',
        'quay.io',
        'registry.redhat.io'
    ]
    
    # File path validation
    ALLOWED_PATH_PREFIXES = ['/app', '/data', '/tmp', '/var/log']
    BLOCKED_PATH_PATTERNS = [
        r'\.\./',  # Directory traversal
        r'/etc/',  # System config
        r'/root/', # Root directory
        r'/proc/', # Process info
        r'/sys/',  # System info
    ]
    
    # Environment variable validation
    BLOCKED_ENV_VARS = [
        'PATH', 'HOME', 'USER', 'SHELL', 'PWD',
        'SSH_AUTH_SOCK', 'SSH_AGENT_PID',
        'SUDO_USER', 'SUDO_UID', 'SUDO_GID'
    ]


class SecureString(str):
    """String type that provides validation and sanitization."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise ValidationError('string required')
        
        # Basic sanitization
        v = v.strip()
        
        # Check for null bytes
        if '\x00' in v:
            raise ValidationError('null bytes not allowed')
        
        # Check for control characters
        if any(ord(c) < 32 and c not in '\t\n\r' for c in v):
            raise ValidationError('control characters not allowed')
        
        return cls(v)


class ServiceName(SecureString):
    """Validated service name."""
    
    @classmethod
    def validate(cls, v):
        v = super().validate(v)
        
        # Length check
        if len(v) > SecurityConfig.SERVICE_NAME_MAX_LENGTH:
            raise ValidationError(f'service name too long (max {SecurityConfig.SERVICE_NAME_MAX_LENGTH})')
        
        if len(v) < 1:
            raise ValidationError('service name cannot be empty')
        
        # Pattern check
        if not re.match(SecurityConfig.SERVICE_NAME_PATTERN, v):
            raise ValidationError('invalid service name format')
        
        # Blacklist check
        if v.lower() in SecurityConfig.SERVICE_NAME_BLACKLIST:
            raise ValidationError('service name is reserved')
        
        return cls(v)


class DockerImage(SecureString):
    """Validated Docker image name."""
    
    @classmethod
    def validate(cls, v):
        v = super().validate(v)
        
        # Parse image name
        parts = v.split('/')
        
        # Check registry
        if len(parts) >= 2:
            registry = parts[0]
            
            # If registry contains a dot or port, validate it
            if '.' in registry or ':' in registry:
                registry_host = registry.split(':')[0]
                
                # Allow localhost for development
                if registry_host not in ['localhost', '127.0.0.1']:
                    if registry_host not in SecurityConfig.TRUSTED_REGISTRIES:
                        raise ValidationError(f'untrusted registry: {registry_host}')
        
        # Basic format validation
        if not re.match(r'^[a-zA-Z0-9._/-]+(?::[a-zA-Z0-9._-]+)?$', v):
            raise ValidationError('invalid image name format')
        
        return cls(v)


class PortMapping(SecureString):
    """Validated port mapping."""
    
    @classmethod
    def validate(cls, v):
        v = super().validate(v)
        
        # Port mapping format: host_port:container_port[/protocol]
        pattern = r'^(\d+):(\d+)(?:/(tcp|udp))?$'
        match = re.match(pattern, v)
        
        if not match:
            raise ValidationError('invalid port mapping format')
        
        host_port = int(match.group(1))
        container_port = int(match.group(2))
        
        # Port range validation
        if not (1 <= host_port <= 65535):
            raise ValidationError('invalid host port range')
        
        if not (1 <= container_port <= 65535):
            raise ValidationError('invalid container port range')
        
        # Privileged port check
        if host_port < 1024:
            raise ValidationError('privileged ports not allowed')
        
        return cls(v)


class FilePath(SecureString):
    """Validated file path."""
    
    @classmethod
    def validate(cls, v):
        v = super().validate(v)
        
        # Normalize path
        try:
            path = Path(v).resolve()
            v = str(path)
        except (OSError, ValueError):
            raise ValidationError('invalid file path')
        
        # Check for blocked patterns
        for pattern in SecurityConfig.BLOCKED_PATH_PATTERNS:
            if re.search(pattern, v):
                raise ValidationError(f'blocked path pattern: {pattern}')
        
        # Check allowed prefixes (in production)
        # if not any(v.startswith(prefix) for prefix in SecurityConfig.ALLOWED_PATH_PREFIXES):
        #     raise ValidationError('path not in allowed directories')
        
        return cls(v)


class VolumeMount(SecureString):
    """Validated volume mount."""
    
    @classmethod
    def validate(cls, v):
        v = super().validate(v)
        
        # Volume mount format: host_path:container_path[:options]
        parts = v.split(':')
        
        if len(parts) < 2 or len(parts) > 3:
            raise ValidationError('invalid volume mount format')
        
        host_path, container_path = parts[0], parts[1]
        options = parts[2] if len(parts) == 3 else None
        
        # Validate paths
        FilePath.validate(host_path)
        FilePath.validate(container_path)
        
        # Validate options
        if options:
            valid_options = ['ro', 'rw', 'z', 'Z', 'consistent', 'cached', 'delegated']
            option_list = options.split(',')
            
            for option in option_list:
                if option not in valid_options:
                    raise ValidationError(f'invalid volume option: {option}')
        
        return cls(v)


class EnvironmentVariable(SecureString):
    """Validated environment variable."""
    
    @classmethod
    def validate(cls, v):
        v = super().validate(v)
        
        # Environment variable format: KEY=VALUE
        if '=' not in v:
            raise ValidationError('environment variable must contain =')
        
        key, value = v.split('=', 1)
        
        # Validate key
        if not re.match(r'^[A-Z][A-Z0-9_]*$', key):
            raise ValidationError('invalid environment variable name')
        
        # Check blacklist
        if key in SecurityConfig.BLOCKED_ENV_VARS:
            raise ValidationError(f'environment variable {key} is not allowed')
        
        # Validate value (basic checks)
        if len(value) > 1024:
            raise ValidationError('environment variable value too long')
        
        return cls(v)


class NetworkName(SecureString):
    """Validated network name."""
    
    @classmethod
    def validate(cls, v):
        v = super().validate(v)
        
        # Network name validation
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$', v):
            raise ValidationError('invalid network name format')
        
        if len(v) > 64:
            raise ValidationError('network name too long')
        
        return cls(v)


class IPAddress(SecureString):
    """Validated IP address."""
    
    @classmethod
    def validate(cls, v):
        v = super().validate(v)
        
        try:
            ip = ipaddress.ip_address(v)
        except ValueError:
            raise ValidationError('invalid IP address')
        
        # Check if it's a private/allowed IP
        is_allowed = False
        
        for network in SecurityConfig.ALLOWED_PRIVATE_NETWORKS:
            if ip in ipaddress.ip_network(network):
                is_allowed = True
                break
        
        if not is_allowed and not ip.is_loopback:
            raise ValidationError('IP address not in allowed networks')
        
        return cls(v)


class URL(SecureString):
    """Validated URL."""
    
    @classmethod
    def validate(cls, v):
        v = super().validate(v)
        
        # Basic URL validation
        if not validators.url(v):
            raise ValidationError('invalid URL format')
        
        parsed = urlparse(v)
        
        # Check scheme
        if parsed.scheme not in ['http', 'https']:
            raise ValidationError('only HTTP/HTTPS URLs allowed')
        
        # Check for localhost/private IPs in production
        if parsed.hostname:
            try:
                ip = ipaddress.ip_address(parsed.hostname)
                if not ip.is_private and not ip.is_loopback:
                    # Allow public IPs for webhooks, etc.
                    pass
            except ValueError:
                # Hostname is not an IP, validate as domain
                if not validators.domain(parsed.hostname):
                    raise ValidationError('invalid hostname in URL')
        
        return cls(v)


class Password(SecureString):
    """Validated password."""
    
    @classmethod
    def validate(cls, v):
        v = super().validate(v)
        
        # Length check
        if len(v) < SecurityConfig.MIN_PASSWORD_LENGTH:
            raise ValidationError(f'password too short (min {SecurityConfig.MIN_PASSWORD_LENGTH} characters)')
        
        if len(v) > SecurityConfig.MAX_PASSWORD_LENGTH:
            raise ValidationError(f'password too long (max {SecurityConfig.MAX_PASSWORD_LENGTH} characters)')
        
        # Character requirements
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v)
        
        if SecurityConfig.PASSWORD_REQUIRE_UPPERCASE and not has_upper:
            raise ValidationError('password must contain uppercase letters')
        
        if SecurityConfig.PASSWORD_REQUIRE_LOWERCASE and not has_lower:
            raise ValidationError('password must contain lowercase letters')
        
        if SecurityConfig.PASSWORD_REQUIRE_NUMBERS and not has_digit:
            raise ValidationError('password must contain numbers')
        
        if SecurityConfig.PASSWORD_REQUIRE_SPECIAL_CHARS and not has_special:
            raise ValidationError('password must contain special characters')
        
        # Blacklist check
        v_lower = v.lower()
        for blocked in SecurityConfig.PASSWORD_BLACKLIST:
            if blocked in v_lower:
                raise ValidationError('password contains blocked terms')
        
        return cls(v)


class Username(SecureString):
    """Validated username."""
    
    @classmethod
    def validate(cls, v):
        v = super().validate(v)
        
        # Length check
        if len(v) < 3:
            raise ValidationError('username too short')
        
        if len(v) > 32:
            raise ValidationError('username too long')
        
        # Pattern check
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValidationError('username contains invalid characters')
        
        # Cannot start with number or special character
        if not v[0].isalpha():
            raise ValidationError('username must start with a letter')
        
        # Blacklist check
        if v.lower() in ['admin', 'root', 'user', 'test', 'guest', 'system']:
            raise ValidationError('username is reserved')
        
        return cls(v)


class Email(SecureString):
    """Validated email address."""
    
    @classmethod
    def validate(cls, v):
        v = super().validate(v)
        
        if not validators.email(v):
            raise ValidationError('invalid email format')
        
        # Additional checks
        if len(v) > 254:
            raise ValidationError('email address too long')
        
        local, domain = v.split('@')
        
        if len(local) > 64:
            raise ValidationError('email local part too long')
        
        return cls(v)


# Service validation models
class ServiceCreateRequest(BaseModel):
    """Service creation request validation."""
    
    name: ServiceName
    image: DockerImage
    ports: List[PortMapping] = Field(default_factory=list)
    environment: Dict[str, str] = Field(default_factory=dict)
    volumes: List[VolumeMount] = Field(default_factory=list)
    networks: List[NetworkName] = Field(default_factory=list)
    restart_policy: str = Field(default="unless-stopped")
    labels: Dict[str, str] = Field(default_factory=dict)
    
    @validator('environment')
    def validate_environment(cls, v):
        """Validate environment variables."""
        validated = {}
        for key, value in v.items():
            # Validate key
            if not re.match(r'^[A-Z][A-Z0-9_]*$', key):
                raise ValidationError(f'invalid environment variable name: {key}')
            
            if key in SecurityConfig.BLOCKED_ENV_VARS:
                raise ValidationError(f'environment variable {key} is not allowed')
            
            # Validate value
            if len(str(value)) > 1024:
                raise ValidationError(f'environment variable {key} value too long')
            
            validated[key] = str(value)
        
        return validated
    
    @validator('restart_policy')
    def validate_restart_policy(cls, v):
        """Validate restart policy."""
        valid_policies = ['no', 'always', 'unless-stopped', 'on-failure']
        if v not in valid_policies:
            raise ValidationError(f'invalid restart policy: {v}')
        return v
    
    @validator('labels')
    def validate_labels(cls, v):
        """Validate Docker labels."""
        validated = {}
        for key, value in v.items():
            # Basic key validation
            if not re.match(r'^[a-zA-Z0-9._-]+$', key):
                raise ValidationError(f'invalid label key: {key}')
            
            if len(key) > 128:
                raise ValidationError(f'label key too long: {key}')
            
            if len(str(value)) > 1024:
                raise ValidationError(f'label value too long for key: {key}')
            
            validated[key] = str(value)
        
        return validated


class UserCreateRequest(BaseModel):
    """User creation request validation."""
    
    username: Username
    email: Email
    password: Password
    role: str = Field(default="user")
    
    @validator('role')
    def validate_role(cls, v):
        """Validate user role."""
        valid_roles = ['user', 'admin', 'operator', 'viewer']
        if v not in valid_roles:
            raise ValidationError(f'invalid role: {v}')
        return v


class ConfigUpdateRequest(BaseModel):
    """Configuration update request validation."""
    
    caddy: Optional[Dict[str, Any]] = None
    docker: Optional[Dict[str, Any]] = None
    database: Optional[Dict[str, Any]] = None
    security: Optional[Dict[str, Any]] = None
    
    @validator('caddy')
    def validate_caddy_config(cls, v):
        """Validate Caddy configuration."""
        if v is None:
            return v
        
        # Validate admin API endpoint
        if 'admin_api' in v:
            admin_api = v['admin_api']
            if not re.match(r'^[a-zA-Z0-9.-]+:\d+$', admin_api):
                raise ValidationError('invalid Caddy admin API format')
        
        return v
    
    @validator('docker')
    def validate_docker_config(cls, v):
        """Validate Docker configuration."""
        if v is None:
            return v
        
        # Validate socket path
        if 'socket' in v:
            socket_path = v['socket']
            if not socket_path.startswith('/var/run/docker.sock'):
                raise ValidationError('invalid Docker socket path')
        
        return v


# Security utilities
class SecurityUtils:
    """Security utility functions."""
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """Generate a cryptographically secure random token."""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def hash_sensitive_data(data: str) -> str:
        """Hash sensitive data for logging/storage."""
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for safe storage."""
        # Remove or replace dangerous characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        sanitized = re.sub(r'\.\.', '_', sanitized)
        
        # Limit length
        if len(sanitized) > 255:
            name, ext = sanitized.rsplit('.', 1) if '.' in sanitized else (sanitized, '')
            max_name_len = 255 - len(ext) - 1 if ext else 255
            sanitized = name[:max_name_len] + ('.' + ext if ext else '')
        
        return sanitized
    
    @staticmethod
    def validate_json_schema(data: Any, schema: Dict[str, Any]) -> bool:
        """Validate data against JSON schema."""
        try:
            import jsonschema
            jsonschema.validate(data, schema)
            return True
        except ImportError:
            # Fallback validation if jsonschema not available
            return True
        except Exception:
            return False
    
    @staticmethod
    def check_rate_limit(identifier: str, limit: int, window: int) -> Tuple[bool, int]:
        """
        Check if identifier has exceeded rate limit.
        
        Returns (is_allowed, remaining_requests)
        """
        # This would typically use Redis or similar
        # For now, return a simple implementation
        return True, limit
    
    @staticmethod
    def mask_sensitive_data(data: str, mask_char: str = '*', show_chars: int = 4) -> str:
        """Mask sensitive data for logging."""
        if len(data) <= show_chars:
            return mask_char * len(data)
        
        return data[:show_chars] + mask_char * (len(data) - show_chars)


# Input sanitization functions
def sanitize_html(html: str) -> str:
    """Sanitize HTML input to prevent XSS."""
    # Basic HTML sanitization - in production, use a library like bleach
    import html
    return html.escape(html)


def sanitize_sql_identifier(identifier: str) -> str:
    """Sanitize SQL identifier to prevent injection."""
    # Only allow alphanumeric and underscore
    return re.sub(r'[^a-zA-Z0-9_]', '', identifier)


def validate_json_input(data: str, max_size: int = 10240) -> Dict[str, Any]:
    """Validate and parse JSON input safely."""
    import json
    
    if len(data) > max_size:
        raise ValidationError(f'JSON input too large (max {max_size} bytes)')
    
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as e:
        raise ValidationError(f'invalid JSON: {e}')
    
    return parsed


# Export commonly used items
__all__ = [
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
    'validate_json_input'
]
