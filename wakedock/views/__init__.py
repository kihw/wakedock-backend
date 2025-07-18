"""
Views package for WakeDock MVC architecture
"""

from .base_view import BaseView
from .services_view import ServicesView
from .auth_view import AuthView

__all__ = [
    'BaseView',
    'ServicesView',
    'AuthView'
]
