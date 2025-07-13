"""Integration tests for WakeDock API endpoints."""

import pytest
from fastapi.testclient import TestClient

from wakedock.database.models import ServiceStatus


@pytest.mark.integration
@pytest.mark.api
class TestHealthEndpoint:
    """Test cases for health check endpoint."""
    
    def test_health_check(self, test_client: TestClient):
        """Test health check endpoint."""
        response = test_client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "services" in data
        assert "version" in data


@pytest.mark.integration
@pytest.mark.api
class TestSystemEndpoints:
    """Test cases for system API endpoints."""
    
    def test_system_overview(self, test_client: TestClient):
        """Test system overview endpoint."""
        response = test_client.get("/api/v1/system/overview")
        assert response.status_code == 200
        
        data = response.json()
        assert "services" in data
        assert "system" in data
        assert "uptime" in data
    
    def test_system_health(self, test_client: TestClient):
        """Test system health endpoint."""
        response = test_client.get("/api/v1/system/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "checks" in data
    
    def test_system_metrics(self, test_client: TestClient):
        """Test system metrics endpoint."""
        response = test_client.get("/api/v1/system/metrics")
        assert response.status_code == 200
        
        data = response.json()
        assert "services" in data
        assert "system" in data


@pytest.mark.integration
@pytest.mark.api
class TestServicesEndpoints:
    """Test cases for services API endpoints."""
    
    def test_list_services_empty(self, test_client: TestClient):
        """Test listing services when none exist."""
        response = test_client.get("/api/v1/services")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_list_services_with_data(self, test_client: TestClient, sample_services):
        """Test listing services with sample data."""
        response = test_client.get("/api/v1/services")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3
        
        # Check service data structure
        service = data[0]
        assert "id" in service
        assert "name" in service
        assert "status" in service
        assert "image" in service
    
    def test_get_service_by_id(self, test_client: TestClient, test_service):
        """Test getting a specific service by ID."""
        response = test_client.get(f"/api/v1/services/{test_service.id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == test_service.id
        assert data["name"] == test_service.name
        assert data["status"] == test_service.status.value
    
    def test_get_service_not_found(self, test_client: TestClient):
        """Test getting a non-existent service."""
        response = test_client.get("/api/v1/services/99999")
        assert response.status_code == 404
    
    def test_start_service(self, test_client: TestClient, test_service):
        """Test starting a service."""
        response = test_client.post(f"/api/v1/services/{test_service.id}/start")
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Service started successfully"
    
    def test_stop_service(self, test_client: TestClient, test_service):
        """Test stopping a service."""
        response = test_client.post(f"/api/v1/services/{test_service.id}/stop")
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Service stopped successfully"
    
    def test_restart_service(self, test_client: TestClient, test_service):
        """Test restarting a service."""
        response = test_client.post(f"/api/v1/services/{test_service.id}/restart")
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Service restarted successfully"


@pytest.mark.integration
@pytest.mark.api
class TestServiceManagement:
    """Test cases for service management operations."""
    
    def test_create_service(self, test_client: TestClient, test_user):
        """Test creating a new service."""
        service_data = {
            "name": "new-service",
            "description": "A new test service",
            "image": "nginx",
            "tag": "latest",
            "domain": "new.example.com",
            "ports": [{"host": 8080, "container": 80}],
            "environment": {"ENV": "test"}
        }
        
        response = test_client.post("/api/v1/services", json=service_data)
        assert response.status_code == 201
        
        data = response.json()
        assert data["name"] == service_data["name"]
        assert data["image"] == service_data["image"]
        assert data["status"] == ServiceStatus.STOPPED.value
    
    def test_update_service(self, test_client: TestClient, test_service):
        """Test updating an existing service."""
        update_data = {
            "description": "Updated description",
            "domain": "updated.example.com"
        }
        
        response = test_client.put(f"/api/v1/services/{test_service.id}", json=update_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["description"] == update_data["description"]
        assert data["domain"] == update_data["domain"]
    
    def test_delete_service(self, test_client: TestClient, test_service):
        """Test deleting a service."""
        response = test_client.delete(f"/api/v1/services/{test_service.id}")
        assert response.status_code == 204
        
        # Verify service is deleted
        response = test_client.get(f"/api/v1/services/{test_service.id}")
        assert response.status_code == 404
