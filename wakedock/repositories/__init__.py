"""
Repositories package for WakeDock MVC architecture
"""

from .base_repository import BaseRepository
from .services_repository import ServicesRepository
from .auth_repository import AuthRepository

__all__ = [
    'BaseRepository',
    'ServicesRepository',
    'AuthRepository'
]
