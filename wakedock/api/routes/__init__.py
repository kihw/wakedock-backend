# Routes package
# from .dashboard_api import router as dashboard_router  # Skip dashboard for now
from . import alerts
from . import analytics
from . import centralized_logs
from . import compose_stacks
from . import container_lifecycle
from . import container_logs
from . import containers
from . import env_files
from . import environment
from . import health
from . import images
from . import logs
from . import monitoring
from . import proxy
from . import stacks as services  # services is an alias for stacks
from . import system
from . import user_preferences

__all__ = [
    # 'dashboard_router',
    'alerts',
    'analytics',
    'centralized_logs',
    'compose_stacks',
    'container_lifecycle',
    'container_logs',
    'containers',
    'env_files',
    'environment',
    'health',
    'images',
    'logs',
    'monitoring',
    'proxy',
    'services',
    'system',
    'user_preferences',
]
