"""
Database initialization script for WakeDock.
Creates tables and initial data.
"""

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from wakedock.database.base import Base, init_models
from wakedock.models.auth_models import User, UserRole
from wakedock.core.auth.jwt_service import JWTService
from wakedock.config import get_settings

logger = logging.getLogger(__name__)


def init_database():
    """Initialize database with tables and default data."""
    settings = get_settings()
    
    # Get database URL
    database_url = settings.database.url
    if not database_url:
        database_url = f"postgresql://{settings.database.user}:{settings.database.password}@{settings.database.host}:{settings.database.port}/{settings.database.name}"
    
    # Create engine
    engine = create_engine(database_url, echo=settings.wakedock.debug)
    
    # Import all models to register them
    init_models()
    
    # Create all tables
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")
    
    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Check if admin user exists
        admin_user = db.query(User).filter(User.username == "admin").first()
        
        if not admin_user:
            logger.info("Creating default admin user...")
            
            # Create admin user
            jwt_service = JWTService()
            admin_user = User(
                username="admin",
                email="admin@wakedock.local",
                hashed_password=jwt_service.get_password_hash("admin"),
                full_name="Administrator",
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True
            )
            db.add(admin_user)
            db.commit()
            
            logger.info("Default admin user created (username: admin, password: admin)")
        else:
            logger.info("Admin user already exists")
        
        # Create demo users if needed
        demo_user = db.query(User).filter(User.username == "demo").first()
        if not demo_user:
            logger.info("Creating demo user...")
            
            demo_user = User(
                username="demo",
                email="demo@wakedock.local",
                hashed_password=jwt_service.get_password_hash("demo"),
                full_name="Demo User",
                role=UserRole.USER,
                is_active=True,
                is_verified=True
            )
            db.add(demo_user)
            db.commit()
            
            logger.info("Demo user created (username: demo, password: demo)")
        
        logger.info("Database initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Initialize database
    init_database()