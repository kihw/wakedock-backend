"""Validation utilities for WakeDock."""

import re
import socket
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse
import validators


def validate_service_name(name: str) -> bool:
    """Validate service name format.
    
    Service names must:
    - Be 3-50 characters long
    - Contain only alphanumeric characters, hyphens, and underscores
    - Start and end with alphanumeric characters
    """
    if not name or len(name) < 3 or len(name) > 50:
        return False
    
    pattern = r'^[a-zA-Z0-9][a-zA-Z0-9_-]*[a-zA-Z0-9]$'
    return bool(re.match(pattern, name))


def validate_domain(domain: str) -> bool:
    """Validate domain name format."""
    if not domain:
        return False
    
    # Basic domain validation
    try:
        return validators.domain(domain) is True
    except Exception:
        # Fallback regex validation
        pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
        return bool(re.match(pattern, domain)) and len(domain) <= 253


def validate_port(port: int) -> bool:
    """Validate port number."""
    return isinstance(port, int) and 1 <= port <= 65535


def validate_image_name(image: str) -> bool:
    """Validate Docker image name format.
    
    Examples:
    - nginx
    - nginx:latest
    - registry.example.com/nginx:1.21
    """
    if not image:
        return False
    
    # Docker image name regex (simplified)
    pattern = r'^(?:[a-z0-9]+(?:[._-][a-z0-9]+)*\/)*[a-z0-9]+(?:[._-][a-z0-9]+)*(?::[a-zA-Z0-9._-]+)?$'
    return bool(re.match(pattern, image.lower()))


def validate_email(email: str) -> bool:
    """Validate email address format."""
    if not email:
        return False
    
    try:
        return validators.email(email) is True
    except Exception:
        # Fallback regex validation
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))


def sanitize_string(text: str, max_length: int = 255) -> str:
    """Sanitize string by removing/replacing unsafe characters."""
    if not text:
        return ""
    
    # Remove null bytes and control characters
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    # Truncate to max length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized.strip()


def validate_port_mapping(port_mapping: Dict[str, Any]) -> bool:
    """Validate port mapping configuration.
    
    Expected format:
    {
        "host": 8080,
        "container": 80,
        "protocol": "tcp"  # optional
    }
    """
    if not isinstance(port_mapping, dict):
        return False
    
    # Check required fields
    if "host" not in port_mapping or "container" not in port_mapping:
        return False
    
    # Validate port numbers
    host_port = port_mapping.get("host")
    container_port = port_mapping.get("container")
    
    if not validate_port(host_port) or not validate_port(container_port):
        return False
    
    # Validate protocol if specified
    protocol = port_mapping.get("protocol", "tcp")
    if protocol not in ["tcp", "udp"]:
        return False
    
    return True


def validate_volume_mapping(volume_mapping: Dict[str, Any]) -> bool:
    """Validate volume mapping configuration.
    
    Expected format:
    {
        "host": "/host/path",
        "container": "/container/path",
        "mode": "rw"  # optional: "rw", "ro"
    }
    """
    if not isinstance(volume_mapping, dict):
        return False
    
    # Check required fields
    if "host" not in volume_mapping or "container" not in volume_mapping:
        return False
    
    host_path = volume_mapping.get("host")
    container_path = volume_mapping.get("container")
    
    # Basic path validation
    if not host_path or not container_path:
        return False
    
    if not host_path.startswith("/") or not container_path.startswith("/"):
        return False
    
    # Validate mode if specified
    mode = volume_mapping.get("mode", "rw")
    if mode not in ["rw", "ro"]:
        return False
    
    return True


def validate_environment_variables(env_vars: Dict[str, str]) -> bool:
    """Validate environment variables configuration."""
    if not isinstance(env_vars, dict):
        return False
    
    for key, value in env_vars.items():
        # Environment variable names should be valid
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
            return False
        
        # Values should be strings
        if not isinstance(value, str):
            return False
    
    return True


def validate_labels(labels: Dict[str, str]) -> bool:
    """Validate Docker labels configuration."""
    if not isinstance(labels, dict):
        return False
    
    for key, value in labels.items():
        # Labels should be strings
        if not isinstance(key, str) or not isinstance(value, str):
            return False
        
        # Key validation (Docker label key format)
        if not re.match(r'^[a-z0-9.-]+$', key.lower()):
            return False
    
    return True


def validate_memory_limit(memory_limit: str) -> bool:
    """Validate memory limit format (e.g., '512m', '1g', '2048M')."""
    if not memory_limit:
        return False
    
    pattern = r'^[0-9]+[kmgtKMGT]?[bB]?$'
    return bool(re.match(pattern, memory_limit))


def validate_cpu_limit(cpu_limit: str) -> bool:
    """Validate CPU limit format (e.g., '0.5', '1.0', '2')."""
    if not cpu_limit:
        return False
    
    try:
        value = float(cpu_limit)
        return 0 < value <= 16  # Reasonable CPU limit range
    except (ValueError, TypeError):
        return False


def validate_service_config(config: Dict[str, Any]) -> List[str]:
    """Validate complete service configuration and return list of errors."""
    errors = []
    
    # Required fields
    required_fields = ["name", "image"]
    for field in required_fields:
        if field not in config:
            errors.append(f"Missing required field: {field}")
    
    # Validate service name
    if "name" in config:
        if not validate_service_name(config["name"]):
            errors.append("Invalid service name format")
    
    # Validate image
    if "image" in config:
        if not validate_image_name(config["image"]):
            errors.append("Invalid image name format")
    
    # Validate domain if provided
    if "domain" in config and config["domain"]:
        if not validate_domain(config["domain"]):
            errors.append("Invalid domain format")
    
    # Validate ports if provided
    if "ports" in config and config["ports"]:
        if not isinstance(config["ports"], list):
            errors.append("Ports must be a list")
        else:
            for i, port_mapping in enumerate(config["ports"]):
                if not validate_port_mapping(port_mapping):
                    errors.append(f"Invalid port mapping at index {i}")
    
    # Validate volumes if provided
    if "volumes" in config and config["volumes"]:
        if not isinstance(config["volumes"], list):
            errors.append("Volumes must be a list")
        else:
            for i, volume_mapping in enumerate(config["volumes"]):
                if not validate_volume_mapping(volume_mapping):
                    errors.append(f"Invalid volume mapping at index {i}")
    
    # Validate environment variables if provided
    if "environment" in config and config["environment"]:
        if not validate_environment_variables(config["environment"]):
            errors.append("Invalid environment variables")
    
    # Validate labels if provided
    if "labels" in config and config["labels"]:
        if not validate_labels(config["labels"]):
            errors.append("Invalid labels")
    
    # Validate memory limit if provided
    if "memory_limit" in config and config["memory_limit"]:
        if not validate_memory_limit(config["memory_limit"]):
            errors.append("Invalid memory limit format")
    
    # Validate CPU limit if provided
    if "cpu_limit" in config and config["cpu_limit"]:
        if not validate_cpu_limit(config["cpu_limit"]):
            errors.append("Invalid CPU limit format")
    
    return errors
