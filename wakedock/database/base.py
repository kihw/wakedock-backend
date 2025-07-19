"""
Base database configuration for WakeDock.
Single source of truth for SQLAlchemy Base and database configuration.
"""

from sqlalchemy.orm import declarative_base

# Single Base instance for all models
Base = declarative_base()

# Import all models here to ensure they're registered with Base
def init_models():
    """Import all models to register them with SQLAlchemy"""
    # Import auth models (main User model)
    from wakedock.models import auth_models  # noqa: F401
    # Import database models (Service, Configuration, etc.)
    from . import models  # noqa: F401
    # Import any other model files here as needed