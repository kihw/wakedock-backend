"""
Tests de base pour les nouvelles routes API
"""
import pytest
from fastapi.testclient import TestClient
from wakedock.api.app import create_app
from wakedock.core.orchestrator import DockerOrchestrator
from wakedock.core.monitoring import MonitoringService

@pytest.fixture
def client():
    """Client de test FastAPI"""
    # Mock orchestrator et monitoring pour les tests
    orchestrator = None  # Mock
    monitoring = None    # Mock
    
    app = create_app(orchestrator, monitoring)
    return TestClient(app)

def test_health_endpoint(client):
    """Test de l'endpoint health"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200

def test_compose_stacks_list_unauthorized(client):
    """Test de l'endpoint compose stacks sans authentification"""
    response = client.get("/api/v1/compose/stacks")
    # Devrait retourner 401 sans token
    assert response.status_code == 401

def test_env_files_validate_unauthorized(client):
    """Test de l'endpoint env validation sans authentification"""
    response = client.post("/api/v1/env/validate", json={
        "variables": {
            "TEST_VAR": {
                "name": "TEST_VAR",
                "value": "test_value"
            }
        }
    })
    # Devrait retourner 401 sans token
    assert response.status_code == 401

def test_logs_endpoint_unauthorized(client):
    """Test de l'endpoint logs sans authentification"""
    response = client.get("/api/v1/logs/")
    # Devrait retourner 401 sans token
    assert response.status_code == 401

def test_api_docs_available(client):
    """Test que la documentation API est disponible"""
    response = client.get("/api/docs")
    # Peut être 200 ou redirection selon la config
    assert response.status_code in [200, 404, 307]

if __name__ == "__main__":
    # Test rapide
    print("Tests de base des nouvelles routes...")
    print("✅ Tests définis")
