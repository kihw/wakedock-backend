"""
WakeDock Models Package
"""

from .base import Base, BaseModel, AuditableModel, TimestampMixin, UUIDMixin, SoftDeleteMixin, MetadataMixin

# Import all models
from .alerts_models import Alert, AlertRule
from .analytics_models import Metric, MetricData  
# Temporarily disabled - use database.models.User instead
# from .authentication_models import User, Role
from .containers_models import Container, ContainerStack
from .dashboard_models import Dashboard, Widget

__all__ = [
    # Base classes
    "Base",
    "BaseModel", 
    "AuditableModel",
    "TimestampMixin",
    "UUIDMixin", 
    "SoftDeleteMixin",
    "MetadataMixin",
    
    # Domain models
    "Alert",
    "AlertRule",
    "Metric",
    "MetricData",
    # "User", "Role" - use database.models.User instead
    "Container",
    "ContainerStack",
    "Dashboard",
    "Widget",
]
