"""
Unit tests for Docker Orchestrator
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import docker
from docker.errors import APIError, NotFound

from wakedock.core.orchestrator import DockerOrchestrator
from wakedock.exceptions import DockerConnectionError, ServiceNotFoundError


class TestDockerOrchestrator:
    """Test cases for DockerOrchestrator"""
    
    @pytest.fixture
    def mock_docker_client(self):
        """Mock Docker client"""
        with patch('wakedock.core.orchestrator.docker.from_env') as mock_from_env:
            mock_client = Mock()
            mock_from_env.return_value = mock_client
            yield mock_client
    
    @pytest.fixture
    def orchestrator(self, mock_docker_client):
        """Create orchestrator instance with mocked Docker client"""
        return DockerOrchestrator()
    
    def test_init_success(self, mock_docker_client):
        """Test successful initialization"""
        orchestrator = DockerOrchestrator()
        assert orchestrator.client is not None
        mock_docker_client.ping.assert_called_once()
    
    def test_init_docker_connection_error(self):
        """Test initialization with Docker connection error"""
        with patch('wakedock.core.orchestrator.docker.from_env') as mock_from_env:
            mock_from_env.side_effect = docker.errors.DockerException("Connection failed")
            
            with pytest.raises(DockerConnectionError):
                DockerOrchestrator()
    
    @pytest.mark.asyncio
    async def test_list_services_success(self, orchestrator, mock_docker_client):
        """Test successful service listing"""
        # Mock containers
        mock_container1 = Mock()
        mock_container1.attrs = {
            'Id': 'container1',
            'Name': '/test-service-1',
            'Config': {
                'Labels': {
                    'wakedock.managed': 'true',
                    'wakedock.service': 'test-service-1'
                }
            },
            'State': {'Status': 'running'},
            'NetworkSettings': {
                'Ports': {'80/tcp': [{'HostPort': '8080'}]}
            }
        }
        
        mock_container2 = Mock()
        mock_container2.attrs = {
            'Id': 'container2', 
            'Name': '/test-service-2',
            'Config': {
                'Labels': {
                    'wakedock.managed': 'true',
                    'wakedock.service': 'test-service-2'
                }
            },
            'State': {'Status': 'stopped'},
            'NetworkSettings': {'Ports': {}}
        }
        
        mock_docker_client.containers.list.return_value = [mock_container1, mock_container2]
        
        services = await orchestrator.list_services()
        
        assert len(services) == 2
        assert services[0]['name'] == 'test-service-1'
        assert services[0]['status'] == 'running'
        assert services[1]['name'] == 'test-service-2'
        assert services[1]['status'] == 'stopped'
    
    @pytest.mark.asyncio
    async def test_list_services_docker_error(self, orchestrator, mock_docker_client):
        """Test service listing with Docker API error"""
        mock_docker_client.containers.list.side_effect = APIError("API Error")
        
        with pytest.raises(DockerConnectionError):
            await orchestrator.list_services()
    
    @pytest.mark.asyncio
    async def test_get_service_success(self, orchestrator, mock_docker_client):
        """Test successful service retrieval"""
        mock_container = Mock()
        mock_container.attrs = {
            'Id': 'container1',
            'Name': '/test-service',
            'Config': {
                'Labels': {
                    'wakedock.managed': 'true',
                    'wakedock.service': 'test-service'
                }
            },
            'State': {'Status': 'running'},
            'NetworkSettings': {
                'Ports': {'80/tcp': [{'HostPort': '8080'}]}
            }
        }
        
        mock_docker_client.containers.get.return_value = mock_container
        
        service = await orchestrator.get_service('test-service')
        
        assert service['name'] == 'test-service'
        assert service['status'] == 'running'
        mock_docker_client.containers.get.assert_called_once_with('test-service')
    
    @pytest.mark.asyncio
    async def test_get_service_not_found(self, orchestrator, mock_docker_client):
        """Test service retrieval when service not found"""
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")
        
        with pytest.raises(ServiceNotFoundError):
            await orchestrator.get_service('nonexistent-service')
    
    @pytest.mark.asyncio
    async def test_start_service_success(self, orchestrator, mock_docker_client):
        """Test successful service start"""
        mock_container = Mock()
        mock_docker_client.containers.get.return_value = mock_container
        
        with patch.object(orchestrator, '_update_caddy_configuration') as mock_update_caddy:
            mock_update_caddy.return_value = AsyncMock()
            
            result = await orchestrator.start_service('test-service')
            
            assert result is True
            mock_container.start.assert_called_once()
            mock_update_caddy.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_service_success(self, orchestrator, mock_docker_client):
        """Test successful service stop"""
        mock_container = Mock()
        mock_docker_client.containers.get.return_value = mock_container
        
        with patch.object(orchestrator, '_update_caddy_configuration') as mock_update_caddy:
            mock_update_caddy.return_value = AsyncMock()
            
            result = await orchestrator.stop_service('test-service')
            
            assert result is True
            mock_container.stop.assert_called_once()
            mock_update_caddy.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_restart_service_success(self, orchestrator, mock_docker_client):
        """Test successful service restart"""
        mock_container = Mock()
        mock_docker_client.containers.get.return_value = mock_container
        
        with patch.object(orchestrator, '_update_caddy_configuration') as mock_update_caddy:
            mock_update_caddy.return_value = AsyncMock()
            
            result = await orchestrator.restart_service('test-service')
            
            assert result is True
            mock_container.restart.assert_called_once()
            mock_update_caddy.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_service_logs_success(self, orchestrator, mock_docker_client):
        """Test successful service logs retrieval"""
        mock_container = Mock()
        mock_container.logs.return_value = b"log line 1\nlog line 2\n"
        mock_docker_client.containers.get.return_value = mock_container
        
        logs = await orchestrator.get_service_logs('test-service', lines=100)
        
        assert logs == "log line 1\nlog line 2\n"
        mock_container.logs.assert_called_once_with(tail=100)
    
    @pytest.mark.asyncio
    async def test_get_service_stats_success(self, orchestrator, mock_docker_client):
        """Test successful service stats retrieval"""
        mock_container = Mock()
        mock_stats = {
            'cpu_stats': {'cpu_usage': {'total_usage': 1000000}},
            'precpu_stats': {'cpu_usage': {'total_usage': 500000}},
            'memory_stats': {'usage': 1048576, 'limit': 2097152}
        }
        mock_container.stats.return_value = [mock_stats]
        mock_docker_client.containers.get.return_value = mock_container
        
        stats = await orchestrator.get_service_stats('test-service')
        
        assert 'cpu_usage' in stats
        assert 'memory_usage' in stats
        assert 'memory_limit' in stats
    
    def test_parse_container_info(self, orchestrator):
        """Test container info parsing"""
        container_attrs = {
            'Id': 'abc123',
            'Name': '/test-service',
            'Config': {
                'Labels': {
                    'wakedock.managed': 'true',
                    'wakedock.service': 'test-service',
                    'wakedock.domain': 'test.example.com'
                }
            },
            'State': {
                'Status': 'running',
                'StartedAt': '2023-01-01T00:00:00Z'
            },
            'NetworkSettings': {
                'Ports': {
                    '80/tcp': [{'HostPort': '8080'}],
                    '443/tcp': [{'HostPort': '8443'}]
                }
            }
        }
        
        info = orchestrator._parse_container_info(container_attrs)
        
        assert info['id'] == 'abc123'
        assert info['name'] == 'test-service'
        assert info['status'] == 'running'
        assert info['domain'] == 'test.example.com'
        assert len(info['ports']) == 2
        assert info['ports'][0]['container_port'] == 80
        assert info['ports'][0]['host_port'] == 8080
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, orchestrator, mock_docker_client):
        """Test successful health check"""
        mock_docker_client.ping.return_value = True
        
        is_healthy = await orchestrator.health_check()
        
        assert is_healthy is True
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, orchestrator, mock_docker_client):
        """Test health check failure"""
        mock_docker_client.ping.side_effect = APIError("Connection failed")
        
        is_healthy = await orchestrator.health_check()
        
        assert is_healthy is False


class TestDockerOrchestratorIntegration:
    """Integration tests for DockerOrchestrator"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_service_lifecycle(self):
        """Test full service lifecycle (requires Docker)"""
        # This test would require a real Docker environment
        # and is marked as integration test
        pytest.skip("Integration test - requires Docker daemon")
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_caddy_integration(self):
        """Test Caddy configuration updates (requires Caddy)"""
        # This test would require a real Caddy instance
        # and is marked as integration test
        pytest.skip("Integration test - requires Caddy instance")
