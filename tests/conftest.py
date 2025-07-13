"""Test configuration and shared fixtures for WakeDock tests."""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from typing import Generator, AsyncGenerator
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from wakedock.config import Settings
from wakedock.database.database import Base, get_db_session
from wakedock.database.models import User, Service, UserRole, ServiceStatus
from wakedock.api.app import create_app
from wakedock.core.orchestrator import DockerOrchestrator
from wakedock.core.monitoring import MonitoringService


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def test_settings(temp_dir: Path) -> Settings:
    """Create test settings with temporary directories."""
    return Settings(
        wakedock={
            "host": "127.0.0.1",
            "port": 8000,
            "data_path": str(temp_dir / "data"),
            "config_path": str(temp_dir / "config.yml")
        },
        logging={
            "level": "DEBUG",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file": str(temp_dir / "logs" / "wakedock.log")
        },
        monitoring={
            "enabled": True,
            "interval": 60,
            "retention_days": 7
        },
        caddy={
            "config_path": str(temp_dir / "caddy" / "Caddyfile"),
            "reload_endpoint": "http://localhost:2019/load"
        }
    )


@pytest.fixture
def test_db_engine(temp_dir: Path):
    """Create a test database engine."""
    db_path = temp_dir / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db_session(test_db_engine):
    """Create a test database session."""
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def mock_orchestrator() -> MagicMock:
    """Create a mock Docker orchestrator."""
    mock = MagicMock(spec=DockerOrchestrator)
    mock.list_services.return_value = []
    mock.get_service_status.return_value = ServiceStatus.STOPPED
    mock.start_service.return_value = True
    mock.stop_service.return_value = True
    mock.is_healthy.return_value = True
    return mock


@pytest.fixture
def mock_monitoring_service() -> MagicMock:
    """Create a mock monitoring service."""
    mock = MagicMock(spec=MonitoringService)
    mock.is_running = False
    mock.start = MagicMock()
    mock.stop = MagicMock()
    mock.get_metrics.return_value = {
        "services": {"total": 0, "running": 0, "stopped": 0},
        "system": {"cpu": 0.0, "memory": 0.0, "disk": 0.0}
    }
    return mock


@pytest.fixture
def test_app(test_settings: Settings, mock_orchestrator: MagicMock, mock_monitoring_service: MagicMock):
    """Create a test FastAPI app."""
    app = create_app(mock_orchestrator, mock_monitoring_service)
    return app


@pytest.fixture
def test_client(test_app, test_db_session) -> TestClient:
    """Create a test client with database session override."""
    def override_get_db():
        yield test_db_session
    
    test_app.dependency_overrides[get_db_session] = override_get_db
    return TestClient(test_app)


@pytest.fixture
def test_user(test_db_session) -> User:
    """Create a test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashed_password",
        full_name="Test User",
        role=UserRole.USER,
        is_active=True,
        is_verified=True
    )
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)
    return user


@pytest.fixture
def test_admin_user(test_db_session) -> User:
    """Create a test admin user."""
    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password="hashed_password",
        full_name="Admin User",
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True
    )
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)
    return user


@pytest.fixture
def test_service(test_db_session, test_user: User) -> Service:
    """Create a test service."""
    service = Service(
        name="test-service",
        description="Test service for integration tests",
        image="nginx",
        tag="latest",
        domain="test.example.com",
        status=ServiceStatus.STOPPED,
        owner_id=test_user.id
    )
    test_db_session.add(service)
    test_db_session.commit()
    test_db_session.refresh(service)
    return service


@pytest.fixture
def sample_services(test_db_session, test_user: User) -> list[Service]:
    """Create multiple test services."""
    services = [
        Service(
            name=f"service-{i}",
            description=f"Test service {i}",
            image="nginx",
            tag="latest",
            domain=f"service{i}.example.com",
            status=ServiceStatus.STOPPED if i % 2 == 0 else ServiceStatus.RUNNING,
            owner_id=test_user.id
        )
        for i in range(1, 4)
    ]
    
    for service in services:
        test_db_session.add(service)
    
    test_db_session.commit()
    
    for service in services:
        test_db_session.refresh(service)
    
    return services
