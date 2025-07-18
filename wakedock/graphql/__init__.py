"""
GraphQL API module for WakeDock
"""

from .schema import schema
from .resolvers import *
from .types import *

__all__ = ["schema"]