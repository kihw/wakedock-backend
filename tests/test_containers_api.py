"""
Tests unitaires pour l'API de gestion des containers
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
import docker

from wakedock.api.app import create_app
from wakedock.core.docker_manager import DockerManager
from wakedock.core.validation import ValidationError


@pytest.fixture
def mock_orchestrator():
    return Mock()


@pytest.fixture
def mock_monitoring():
    return Mock()


@pytest.fixture
def mock_docker_manager():
    with patch('wakedock.api.routes.containers.get_docker_manager') as mock:
        docker_manager = Mock(spec=DockerManager)
        mock.return_value = docker_manager
        yield docker_manager


@pytest.fixture
def mock_auth():
    with patch('wakedock.api.routes.containers.get_current_user') as mock:
        mock.return_value = {"user_id": "test_user", "username": "test"}
        yield mock


@pytest.fixture
def client(mock_orchestrator, mock_monitoring):
    app = create_app(mock_orchestrator, mock_monitoring)
    return TestClient(app)


class TestContainerCRUD:
    """Tests pour les opérations CRUD des containers"""
    
    def test_list_containers_success(self, client, mock_docker_manager, mock_auth):
        """Test de récupération de la liste des containers"""
        # Mock container object
        mock_container = Mock()
        mock_container.id = "test_container_id"
        mock_container.name = "/test_container"
        mock_container.status = "running"
        mock_container.ports = {"80/tcp": [{"HostPort": "8080"}]}
        mock_container.image.tags = ["nginx:latest"]
        mock_container.attrs = {
            'State': {'Status': 'running'},
            'Created': '2023-01-01T00:00:00Z',
            'Config': {'Env': ['PATH=/usr/bin', 'USER=root']}
        }
        
        mock_docker_manager.list_containers.return_value = [mock_container]
        
        response = client.get("/api/v1/containers/")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "test_container_id"
        assert data[0]["name"] == "test_container"
        assert data[0]["status"] == "running"
    
    def test_get_container_success(self, client, mock_docker_manager, mock_auth):
        """Test de récupération d'un container spécifique"""
        mock_container = Mock()
        mock_container.id = "test_container_id"
        mock_container.name = "/test_container"
        mock_container.status = "running"
        mock_container.ports = {}
        mock_container.image.tags = ["nginx:latest"]
        mock_container.attrs = {
            'State': {'Status': 'running'},
            'Created': '2023-01-01T00:00:00Z',
            'Config': {'Env': ['PATH=/usr/bin']},
            'Mounts': []
        }
        
        mock_docker_manager.get_container.return_value = mock_container
        
        response = client.get("/api/v1/containers/test_container_id")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test_container_id"
        assert data["name"] == "test_container"
    
    def test_get_container_not_found(self, client, mock_docker_manager, mock_auth):
        """Test de récupération d'un container inexistant"""
        mock_docker_manager.get_container.return_value = None
        
        response = client.get("/api/v1/containers/nonexistent")
        
        assert response.status_code == 404
        assert "non trouvé" in response.json()["detail"]
    
    def test_create_container_success(self, client, mock_docker_manager, mock_auth):
        """Test de création d'un container avec succès"""
        mock_container = Mock()
        mock_container.id = "new_container_id"
        mock_container.name = "/test_container"
        mock_container.status = "created"
        mock_container.ports = {}
        mock_container.image.tags = ["nginx:latest"]
        mock_container.attrs = {
            'State': {'Status': 'created'},
            'Created': '2023-01-01T00:00:00Z'
        }
        
        mock_docker_manager.create_container.return_value = mock_container
        
        container_data = {
            "name": "test_container",
            "image": "nginx:latest",
            "environment": {"ENV": "test"},
            "ports": {"80": 8080}
        }
        
        response = client.post("/api/v1/containers/", json=container_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "new_container_id"
        assert data["name"] == "test_container"
        
        # Vérifier que la méthode a été appelée avec les bons paramètres
        mock_docker_manager.create_container.assert_called_once()
    
    def test_create_container_validation_error(self, client, mock_docker_manager, mock_auth):
        """Test de création d'un container avec erreur de validation"""
        mock_docker_manager.create_container.side_effect = ValidationError("Configuration invalide")
        
        container_data = {
            "name": "invalid-name-",
            "image": "nginx:latest"
        }
        
        response = client.post("/api/v1/containers/", json=container_data)
        
        assert response.status_code == 422
        assert "Configuration invalide" in response.json()["detail"]
    
    def test_delete_container_success(self, client, mock_docker_manager, mock_auth):
        """Test de suppression d'un container avec succès"""
        mock_docker_manager.remove_container.return_value = None
        
        response = client.delete("/api/v1/containers/test_container_id")
        
        assert response.status_code == 204
        mock_docker_manager.remove_container.assert_called_once_with("test_container_id", force=False)
    
    def test_delete_container_not_found(self, client, mock_docker_manager, mock_auth):
        """Test de suppression d'un container inexistant"""
        from docker.errors import NotFound
        mock_docker_manager.remove_container.side_effect = NotFound("Container not found")
        
        response = client.delete("/api/v1/containers/nonexistent")
        
        assert response.status_code == 404
        assert "non trouvé" in response.json()["detail"]


class TestContainerLifecycle:
    """Tests pour la gestion du cycle de vie des containers"""
    
    def test_start_container_success(self, client, mock_auth):
        """Test de démarrage d'un container avec succès"""
        with patch('wakedock.api.routes.container_lifecycle.get_docker_manager') as mock_get_manager:
            mock_docker_manager = Mock()
            mock_get_manager.return_value = mock_docker_manager
            mock_docker_manager.start_container.return_value = None
            
            response = client.post("/api/v1/containers/test_container/start")
            
            assert response.status_code == 200
            assert "démarré avec succès" in response.json()["message"]
            mock_docker_manager.start_container.assert_called_once_with("test_container")
    
    def test_stop_container_success(self, client, mock_auth):
        """Test d'arrêt d'un container avec succès"""
        with patch('wakedock.api.routes.container_lifecycle.get_docker_manager') as mock_get_manager:
            mock_docker_manager = Mock()
            mock_get_manager.return_value = mock_docker_manager
            mock_docker_manager.stop_container.return_value = None
            
            response = client.post("/api/v1/containers/test_container/stop")
            
            assert response.status_code == 200
            assert "arrêté avec succès" in response.json()["message"]
            mock_docker_manager.stop_container.assert_called_once_with("test_container", timeout=10)
    
    def test_restart_container_success(self, client, mock_auth):
        """Test de redémarrage d'un container avec succès"""
        with patch('wakedock.api.routes.container_lifecycle.get_docker_manager') as mock_get_manager:
            mock_docker_manager = Mock()
            mock_get_manager.return_value = mock_docker_manager
            mock_docker_manager.restart_container.return_value = None
            
            response = client.post("/api/v1/containers/test_container/restart")
            
            assert response.status_code == 200
            assert "redémarré avec succès" in response.json()["message"]
            mock_docker_manager.restart_container.assert_called_once_with("test_container", timeout=10)
    
    def test_get_container_logs_success(self, client, mock_auth):
        """Test de récupération des logs d'un container"""
        with patch('wakedock.api.routes.container_lifecycle.get_docker_manager') as mock_get_manager:
            mock_docker_manager = Mock()
            mock_get_manager.return_value = mock_docker_manager
            mock_docker_manager.get_container_logs.return_value = "Container log output"
            
            response = client.get("/api/v1/containers/test_container/logs?tail=50")
            
            assert response.status_code == 200
            assert response.json()["logs"] == "Container log output"
            mock_docker_manager.get_container_logs.assert_called_once_with("test_container", tail=50, follow=False)


class TestImageManagement:
    """Tests pour la gestion des images"""
    
    def test_list_images_success(self, client, mock_auth):
        """Test de récupération de la liste des images"""
        with patch('wakedock.api.routes.images.get_docker_manager') as mock_get_manager:
            mock_docker_manager = Mock()
            mock_get_manager.return_value = mock_docker_manager
            
            mock_image = Mock()
            mock_image.id = "image_id_123"
            mock_image.tags = ["nginx:latest"]
            mock_image.attrs = {
                'Size': 1024000,
                'Created': '2023-01-01T00:00:00Z',
                'RepoTags': ['nginx:latest']
            }
            
            mock_docker_manager.list_images.return_value = [mock_image]
            
            response = client.get("/api/v1/images/")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["id"] == "image_id_123"
            assert data[0]["tags"] == ["nginx:latest"]
    
    def test_pull_image_success(self, client, mock_auth):
        """Test de téléchargement d'une image"""
        with patch('wakedock.api.routes.images.get_docker_manager') as mock_get_manager:
            mock_docker_manager = Mock()
            mock_get_manager.return_value = mock_docker_manager
            
            mock_image = Mock()
            mock_image.id = "new_image_id"
            mock_image.tags = ["ubuntu:22.04"]
            mock_image.attrs = {
                'Size': 2048000,
                'Created': '2023-01-01T00:00:00Z',
                'RepoTags': ['ubuntu:22.04']
            }
            
            mock_docker_manager.pull_image.return_value = mock_image
            
            pull_data = {
                "image": "ubuntu",
                "tag": "22.04"
            }
            
            response = client.post("/api/v1/images/pull", json=pull_data)
            
            assert response.status_code == 201
            data = response.json()
            assert data["id"] == "new_image_id"
            assert data["tags"] == ["ubuntu:22.04"]
            mock_docker_manager.pull_image.assert_called_once_with("ubuntu", "22.04")


class TestValidation:
    """Tests pour le système de validation"""
    
    def test_container_validation_invalid_name(self):
        """Test de validation avec nom de container invalide"""
        from wakedock.core.validation import ContainerValidator
        
        is_valid, error = ContainerValidator.validate_container_name("invalid-name-")
        assert not is_valid
        assert "tiret" in error
    
    def test_container_validation_valid_name(self):
        """Test de validation avec nom de container valide"""
        from wakedock.core.validation import ContainerValidator
        
        is_valid, error = ContainerValidator.validate_container_name("valid_container_name")
        assert is_valid
        assert error is None
    
    def test_port_validation_reserved_port(self):
        """Test de validation avec port réservé"""
        from wakedock.core.validation import ContainerValidator
        
        ports = {"80": 22}  # Port SSH réservé
        is_valid, errors = ContainerValidator.validate_ports(ports)
        assert not is_valid
        assert any("réservé" in error for error in errors)
    
    def test_environment_validation_dangerous_var(self):
        """Test de validation avec variable d'environnement dangereuse"""
        from wakedock.core.validation import ContainerValidator
        
        env_vars = {"PATH": "/custom/path"}
        is_valid, errors = ContainerValidator.validate_environment_variables(env_vars)
        assert not is_valid
        assert any("dangereuse" in error for error in errors)
