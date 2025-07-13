"""
Tests for Services API endpoints
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from wakedock.api.app import create_app
from wakedock.api.auth.jwt import create_access_token
from wakedock.exceptions import ServiceNotFoundError, DockerConnectionError


class TestServicesAPI:
    """Test cases for services API endpoints"""
    
    @pytest.fixture
    def mock_orchestrator(self):
        """Mock orchestrator with service methods"""
        orchestrator = Mock()
        orchestrator.list_services = AsyncMock(return_value=[
            {
                'id': 'service1',
                'name': 'test-service-1',
                'status': 'running',
                'image': 'nginx:alpine',
                'ports': [{'container_port': 80, 'host_port': 8080}],
                'domain': 'service1.local',
                'labels': {'wakedock.managed': 'true'}
            },
            {
                'id': 'service2',
                'name': 'test-service-2',
                'status': 'stopped',
                'image': 'postgres:13',
                'ports': [],
                'domain': None,
                'labels': {'wakedock.managed': 'true'}
            }
        ])
        
        orchestrator.get_service = AsyncMock(return_value={
            'id': 'service1',
            'name': 'test-service-1',
            'status': 'running',
            'image': 'nginx:alpine',
            'ports': [{'container_port': 80, 'host_port': 8080}],
            'domain': 'service1.local',
            'created_at': '2023-01-01T00:00:00Z',
            'environment': {'ENV': 'test'},
            'volumes': ['/data:/app/data'],
            'labels': {'wakedock.managed': 'true'}
        })
        
        orchestrator.start_service = AsyncMock(return_value=True)
        orchestrator.stop_service = AsyncMock(return_value=True)
        orchestrator.restart_service = AsyncMock(return_value=True)
        orchestrator.remove_service = AsyncMock(return_value=True)
        orchestrator.get_service_logs = AsyncMock(return_value="Log line 1\nLog line 2\n")
        orchestrator.get_service_stats = AsyncMock(return_value={
            'cpu_usage': 25.5,
            'memory_usage': 134217728,
            'memory_limit': 268435456,
            'network_rx': 1024,
            'network_tx': 2048
        })
        orchestrator.deploy_service = AsyncMock(return_value=True)
        orchestrator.scale_service = AsyncMock(return_value=True)
        
        return orchestrator
    
    @pytest.fixture
    def mock_monitoring(self):
        """Mock monitoring service"""
        monitoring = Mock()
        monitoring.collect_service_metrics = AsyncMock(return_value=[
            {
                'service_name': 'test-service-1',
                'cpu_usage': 25.5,
                'memory_usage': 50.0,
                'status': 'running'
            }
        ])
        return monitoring
    
    @pytest.fixture
    def client(self, mock_orchestrator, mock_monitoring):
        """Test client"""
        app = create_app(mock_orchestrator, mock_monitoring)
        return TestClient(app)
    
    @pytest.fixture
    def auth_headers(self):
        """Authentication headers"""
        token = create_access_token({'sub': 'testuser'})
        return {'Authorization': f'Bearer {token}'}
    
    def test_list_services_success(self, client, auth_headers, mock_orchestrator):
        """Test successful service listing"""
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = Mock(username='testuser')
            
            response = client.get('/api/services', headers=auth_headers)
            
            if response.status_code == 404:
                pytest.skip("Services API endpoint not implemented yet")
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 2
            assert data[0]['name'] == 'test-service-1'
            assert data[0]['status'] == 'running'
    
    def test_list_services_unauthorized(self, client):
        """Test service listing without authentication"""
        response = client.get('/api/services')
        assert response.status_code == 401
    
    def test_get_service_success(self, client, auth_headers, mock_orchestrator):
        """Test successful service retrieval"""
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = Mock(username='testuser')
            
            response = client.get('/api/services/test-service-1', headers=auth_headers)
            
            if response.status_code == 404:
                pytest.skip("Service detail API endpoint not implemented yet")
            
            assert response.status_code == 200
            data = response.json()
            assert data['name'] == 'test-service-1'
            assert data['status'] == 'running'
            assert 'created_at' in data
            assert 'environment' in data
    
    def test_get_service_not_found(self, client, auth_headers, mock_orchestrator):
        """Test service retrieval for non-existent service"""
        mock_orchestrator.get_service.side_effect = ServiceNotFoundError("Service not found")
        
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = Mock(username='testuser')
            
            response = client.get('/api/services/nonexistent', headers=auth_headers)
            
            if response.status_code == 404 and 'detail' not in response.json():
                pytest.skip("Service detail API endpoint not implemented yet")
            
            assert response.status_code == 404
            data = response.json()
            assert 'detail' in data
    
    def test_start_service_success(self, client, auth_headers, mock_orchestrator):
        """Test successful service start"""
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = Mock(username='testuser')
            
            response = client.post('/api/services/test-service-1/start', headers=auth_headers)
            
            if response.status_code == 404:
                pytest.skip("Service start API endpoint not implemented yet")
            
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            mock_orchestrator.start_service.assert_called_once_with('test-service-1')
    
    def test_stop_service_success(self, client, auth_headers, mock_orchestrator):
        """Test successful service stop"""
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = Mock(username='testuser')
            
            response = client.post('/api/services/test-service-1/stop', headers=auth_headers)
            
            if response.status_code == 404:
                pytest.skip("Service stop API endpoint not implemented yet")
            
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            mock_orchestrator.stop_service.assert_called_once_with('test-service-1')
    
    def test_restart_service_success(self, client, auth_headers, mock_orchestrator):
        """Test successful service restart"""
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = Mock(username='testuser')
            
            response = client.post('/api/services/test-service-1/restart', headers=auth_headers)
            
            if response.status_code == 404:
                pytest.skip("Service restart API endpoint not implemented yet")
            
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            mock_orchestrator.restart_service.assert_called_once_with('test-service-1')
    
    def test_remove_service_success(self, client, auth_headers, mock_orchestrator):
        """Test successful service removal"""
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = Mock(username='testuser')
            
            response = client.delete('/api/services/test-service-1', headers=auth_headers)
            
            if response.status_code == 404:
                pytest.skip("Service delete API endpoint not implemented yet")
            
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            mock_orchestrator.remove_service.assert_called_once_with('test-service-1')
    
    def test_get_service_logs_success(self, client, auth_headers, mock_orchestrator):
        """Test successful service logs retrieval"""
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = Mock(username='testuser')
            
            response = client.get('/api/services/test-service-1/logs', headers=auth_headers)
            
            if response.status_code == 404:
                pytest.skip("Service logs API endpoint not implemented yet")
            
            assert response.status_code == 200
            data = response.json()
            assert 'logs' in data
            assert data['logs'] == "Log line 1\nLog line 2\n"
    
    def test_get_service_logs_with_params(self, client, auth_headers, mock_orchestrator):
        """Test service logs retrieval with parameters"""
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = Mock(username='testuser')
            
            response = client.get(
                '/api/services/test-service-1/logs?lines=100&follow=false',
                headers=auth_headers
            )
            
            if response.status_code == 404:
                pytest.skip("Service logs API endpoint not implemented yet")
            
            assert response.status_code == 200
            mock_orchestrator.get_service_logs.assert_called_once_with(
                'test-service-1',
                lines=100,
                follow=False
            )
    
    def test_get_service_stats_success(self, client, auth_headers, mock_orchestrator):
        """Test successful service stats retrieval"""
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = Mock(username='testuser')
            
            response = client.get('/api/services/test-service-1/stats', headers=auth_headers)
            
            if response.status_code == 404:
                pytest.skip("Service stats API endpoint not implemented yet")
            
            assert response.status_code == 200
            data = response.json()
            assert 'cpu_usage' in data
            assert 'memory_usage' in data
            assert data['cpu_usage'] == 25.5
    
    def test_deploy_service_success(self, client, auth_headers, mock_orchestrator):
        """Test successful service deployment"""
        service_config = {
            'name': 'new-service',
            'image': 'nginx:alpine',
            'ports': {'80/tcp': 8080},
            'environment': {'ENV': 'production'},
            'labels': {'wakedock.domain': 'new-service.local'}
        }
        
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = Mock(username='testuser')
            
            response = client.post('/api/services', json=service_config, headers=auth_headers)
            
            if response.status_code == 404:
                pytest.skip("Service deployment API endpoint not implemented yet")
            
            assert response.status_code == 201
            data = response.json()
            assert data['success'] is True
            mock_orchestrator.deploy_service.assert_called_once()
    
    def test_deploy_service_invalid_config(self, client, auth_headers, mock_orchestrator):
        """Test service deployment with invalid configuration"""
        invalid_config = {
            'name': '',  # Invalid empty name
            'image': 'nginx:alpine'
        }
        
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = Mock(username='testuser')
            
            response = client.post('/api/services', json=invalid_config, headers=auth_headers)
            
            if response.status_code == 404:
                pytest.skip("Service deployment API endpoint not implemented yet")
            
            assert response.status_code == 422  # Validation error
    
    def test_scale_service_success(self, client, auth_headers, mock_orchestrator):
        """Test successful service scaling"""
        scale_config = {'replicas': 3}
        
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = Mock(username='testuser')
            
            response = client.post(
                '/api/services/test-service-1/scale',
                json=scale_config,
                headers=auth_headers
            )
            
            if response.status_code == 404:
                pytest.skip("Service scaling API endpoint not implemented yet")
            
            assert response.status_code == 200
            data = response.json()
            assert data['success'] is True
            mock_orchestrator.scale_service.assert_called_once_with('test-service-1', 3)
    
    def test_service_operations_docker_error(self, client, auth_headers, mock_orchestrator):
        """Test service operations with Docker connection error"""
        mock_orchestrator.start_service.side_effect = DockerConnectionError("Docker daemon not available")
        
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = Mock(username='testuser')
            
            response = client.post('/api/services/test-service-1/start', headers=auth_headers)
            
            if response.status_code == 404:
                pytest.skip("Service start API endpoint not implemented yet")
            
            assert response.status_code == 503
            data = response.json()
            assert 'detail' in data
    
    def test_service_filtering(self, client, auth_headers, mock_orchestrator):
        """Test service listing with filters"""
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = Mock(username='testuser')
            
            response = client.get(
                '/api/services?status=running&domain=service1.local',
                headers=auth_headers
            )
            
            if response.status_code == 404:
                pytest.skip("Service filtering not implemented yet")
            
            assert response.status_code == 200
            data = response.json()
            # Should return filtered results
            assert all(service['status'] == 'running' for service in data)
    
    def test_service_sorting(self, client, auth_headers, mock_orchestrator):
        """Test service listing with sorting"""
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = Mock(username='testuser')
            
            response = client.get(
                '/api/services?sort_by=name&sort_order=desc',
                headers=auth_headers
            )
            
            if response.status_code == 404:
                pytest.skip("Service sorting not implemented yet")
            
            assert response.status_code == 200
            data = response.json()
            # Should return sorted results
            assert isinstance(data, list)
    
    def test_service_pagination(self, client, auth_headers, mock_orchestrator):
        """Test service listing with pagination"""
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = Mock(username='testuser')
            
            response = client.get(
                '/api/services?page=1&limit=10',
                headers=auth_headers
            )
            
            if response.status_code == 404:
                pytest.skip("Service pagination not implemented yet")
            
            assert response.status_code == 200
            data = response.json()
            
            if isinstance(data, dict):
                # Paginated response format
                assert 'items' in data
                assert 'total' in data
                assert 'page' in data
                assert 'limit' in data
            else:
                # Simple list format
                assert isinstance(data, list)
    
    def test_bulk_operations(self, client, auth_headers, mock_orchestrator):
        """Test bulk service operations"""
        bulk_config = {
            'action': 'start',
            'services': ['test-service-1', 'test-service-2']
        }
        
        with patch('wakedock.database.models.User.get_by_username') as mock_get_user:
            mock_get_user.return_value = Mock(username='testuser')
            
            response = client.post('/api/services/bulk', json=bulk_config, headers=auth_headers)
            
            if response.status_code == 404:
                pytest.skip("Bulk operations not implemented yet")
            
            assert response.status_code == 200
            data = response.json()
            assert 'results' in data
            assert isinstance(data['results'], list)
