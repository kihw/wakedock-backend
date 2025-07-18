"""
Services package for WakeDock MVC architecture
"""

from .base_service import BaseService
from .docker_service import DockerService
from .auth_service import AuthService

__all__ = [
    'BaseService',
    'DockerService',
    'AuthService'
]
