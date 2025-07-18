"""
WakeDock Models Package
"""

from .base import Base, BaseModel, AuditableModel, TimestampMixin, UUIDMixin, SoftDeleteMixin, MetadataMixin

# Import all models
from .alerts_models import Alert, AlertRule
from .analytics_models import Metric, MetricData  
from .authentication_models import User, Role
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
    "User",
    "Role", 
    "Container",
    "ContainerStack",
    "Dashboard",
    "Widget",
]
