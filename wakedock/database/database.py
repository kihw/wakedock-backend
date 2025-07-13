"""Database configuration and session management for WakeDock."""

import os
from typing import Generator, Optional
from contextlib import contextmanager

from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.exc import SQLAlchemyError

from ..config import get_settings

# Create the declarative base for models
Base = declarative_base()


class DatabaseManager:
    """Manages database connections and sessions for WakeDock."""
    
    def __init__(self, database_url: Optional[str] = None):
        """Initialize the database manager.
        
        Args:
            database_url: Database connection URL. If None, uses config settings.
        """
        self.settings = get_settings()
        self.database_url = database_url or self._get_database_url()
        self.engine: Optional[Engine] = None
        self.SessionLocal: Optional[sessionmaker] = None
    
    def _get_database_url(self) -> str:
        """Get database URL from environment or use default SQLite."""
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            return db_url
        
        # Default to SQLite for development
        db_path = os.path.join(self.settings.data_dir, "wakedock.db")
        return f"sqlite:///{db_path}"
    
    def initialize(self) -> None:
        """Initialize database engine and session factory."""
        try:
            # Create engine with appropriate settings
            if self.database_url.startswith("sqlite"):
                # SQLite specific settings
                self.engine = create_engine(
                    self.database_url,
                    connect_args={"check_same_thread": False},
                    echo=self.settings.debug
                )
            else:
                # PostgreSQL/MySQL settings
                self.engine = create_engine(
                    self.database_url,
                    pool_pre_ping=True,
                    pool_recycle=300,
                    echo=self.settings.debug
                )
            
            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to initialize database: {e}")
    
    def create_tables(self) -> None:
        """Create all database tables."""
        if not self.engine:
            raise RuntimeError("Database engine not initialized")
        
        try:
            Base.metadata.create_all(bind=self.engine)
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to create tables: {e}")
    
    def drop_tables(self) -> None:
        """Drop all database tables."""
        if not self.engine:
            raise RuntimeError("Database engine not initialized")
        
        try:
            Base.metadata.drop_all(bind=self.engine)
        except SQLAlchemyError as e:
            raise RuntimeError(f"Failed to drop tables: {e}")
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session with automatic cleanup."""
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized")
        
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# Global database manager instance
db_manager = DatabaseManager()


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    with db_manager.get_session() as session:
        yield session


def init_database() -> None:
    """Initialize the database for the application."""
    db_manager.initialize()
    db_manager.create_tables()
