"""Unit tests for WakeDock database models."""

import pytest
from datetime import datetime

from wakedock.database.models import User, Service, UserRole, ServiceStatus


@pytest.mark.unit
class TestUserModel:
    """Test cases for the User model."""
    
    def test_user_creation(self, test_db_session):
        """Test creating a new user."""
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="hashed_password",
            full_name="Test User",
            role=UserRole.USER
        )
        
        test_db_session.add(user)
        test_db_session.commit()
        test_db_session.refresh(user)
        
        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.role == UserRole.USER
        assert user.is_active is True
        assert user.is_verified is False
        assert user.created_at is not None
    
    def test_user_repr(self):
        """Test user string representation."""
        user = User(username="testuser", role=UserRole.ADMIN)
        assert repr(user) == "<User(username='testuser', role='admin')>"
    
    def test_user_unique_constraints(self, test_db_session):
        """Test unique constraints on username and email."""
        user1 = User(
            username="testuser",
            email="test@example.com",
            hashed_password="password1"
        )
        user2 = User(
            username="testuser",
            email="different@example.com",  
            hashed_password="password2"
        )
        
        test_db_session.add(user1)
        test_db_session.commit()
        
        test_db_session.add(user2)
        with pytest.raises(Exception):  # Should raise integrity error
            test_db_session.commit()


@pytest.mark.unit  
class TestServiceModel:
    """Test cases for the Service model."""
    
    def test_service_creation(self, test_db_session, test_user):
        """Test creating a new service."""
        service = Service(
            name="test-service",
            description="Test service",
            image="nginx",
            tag="latest",
            domain="test.example.com",
            owner_id=test_user.id
        )
        
        test_db_session.add(service)
        test_db_session.commit()
        test_db_session.refresh(service)
        
        assert service.id is not None
        assert service.name == "test-service"
        assert service.image == "nginx"
        assert service.tag == "latest"
        assert service.status == ServiceStatus.STOPPED
        assert service.wake_enabled is True
        assert service.sleep_timeout == 300
        assert service.created_at is not None
        assert service.owner_id == test_user.id
    
    def test_service_repr(self):
        """Test service string representation."""
        service = Service(name="test-service", status=ServiceStatus.RUNNING)
        assert repr(service) == "<Service(name='test-service', status='running')>"
    
    def test_service_relationships(self, test_db_session, test_user):
        """Test service-user relationship."""
        service = Service(
            name="test-service",
            image="nginx",
            owner_id=test_user.id
        )
        
        test_db_session.add(service)
        test_db_session.commit()
        test_db_session.refresh(service)
        
        # Test relationship
        assert service.owner.id == test_user.id
        assert service in test_user.services
    
    def test_service_unique_name(self, test_db_session, test_user):
        """Test unique constraint on service name."""
        service1 = Service(
            name="duplicate-service",
            image="nginx",
            owner_id=test_user.id
        )
        service2 = Service(
            name="duplicate-service",
            image="apache",
            owner_id=test_user.id
        )
        
        test_db_session.add(service1)
        test_db_session.commit()
        
        test_db_session.add(service2)
        with pytest.raises(Exception):  # Should raise integrity error
            test_db_session.commit()


@pytest.mark.unit
class TestEnums:
    """Test cases for enum types."""
    
    def test_service_status_values(self):
        """Test ServiceStatus enum values."""
        assert ServiceStatus.STOPPED.value == "stopped"
        assert ServiceStatus.STARTING.value == "starting"
        assert ServiceStatus.RUNNING.value == "running"
        assert ServiceStatus.STOPPING.value == "stopping"
        assert ServiceStatus.ERROR.value == "error"
        assert ServiceStatus.UNKNOWN.value == "unknown"
    
    def test_user_role_values(self):
        """Test UserRole enum values."""
        assert UserRole.ADMIN.value == "admin"
        assert UserRole.USER.value == "user"
        assert UserRole.VIEWER.value == "viewer"
