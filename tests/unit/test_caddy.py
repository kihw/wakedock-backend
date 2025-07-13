"""
Unit tests for Caddy Manager
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import httpx
from httpx import HTTPStatusError, ConnectError

from wakedock.core.caddy import CaddyManager, caddy_manager
from wakedock.exceptions import CaddyConnectionError, CaddyConfigurationError


class TestCaddyManager:
    """Test cases for CaddyManager"""
    
    @pytest.fixture
    def caddy_config(self):
        """Mock Caddy configuration"""
        return {
            'admin': {'listen': '127.0.0.1:2019'},
            'logging': {'logs': {'default': {'level': 'INFO'}}},
            'apps': {
                'http': {
                    'servers': {
                        'srv0': {
                            'listen': [':80', ':443'],
                            'routes': []
                        }
                    }
                }
            }
        }
    
    @pytest.fixture
    def caddy_manager_instance(self):
        """Create CaddyManager instance"""
        return CaddyManager(
            admin_url='http://localhost:2019',
            config_path='/etc/caddy/Caddyfile'
        )
    
    @pytest.mark.asyncio
    async def test_init_success(self, caddy_manager_instance):
        """Test successful initialization"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'version': '2.7.0'}
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            await caddy_manager_instance.initialize()
            
            assert caddy_manager_instance.is_initialized is True
    
    @pytest.mark.asyncio
    async def test_init_connection_error(self, caddy_manager_instance):
        """Test initialization with connection error"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = ConnectError("Connection failed")
            
            with pytest.raises(CaddyConnectionError):
                await caddy_manager_instance.initialize()
    
    @pytest.mark.asyncio
    async def test_get_config_success(self, caddy_manager_instance, caddy_config):
        """Test successful config retrieval"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = caddy_config
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            config = await caddy_manager_instance.get_config()
            
            assert config == caddy_config
    
    @pytest.mark.asyncio
    async def test_get_config_error(self, caddy_manager_instance):
        """Test config retrieval error"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = HTTPStatusError(
                "Server error", request=Mock(), response=mock_response
            )
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            with pytest.raises(CaddyConnectionError):
                await caddy_manager_instance.get_config()
    
    @pytest.mark.asyncio
    async def test_update_config_success(self, caddy_manager_instance, caddy_config):
        """Test successful config update"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            result = await caddy_manager_instance.update_config(caddy_config)
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_update_config_error(self, caddy_manager_instance, caddy_config):
        """Test config update error"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.raise_for_status.side_effect = HTTPStatusError(
                "Bad request", request=Mock(), response=mock_response
            )
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            with pytest.raises(CaddyConfigurationError):
                await caddy_manager_instance.update_config(caddy_config)
    
    @pytest.mark.asyncio
    async def test_add_service_route(self, caddy_manager_instance, caddy_config):
        """Test adding service route"""
        service_info = {
            'name': 'test-service',
            'domain': 'test.example.com',
            'upstream': 'http://localhost:8080',
            'ports': [{'container_port': 80, 'host_port': 8080}]
        }
        
        with patch.object(caddy_manager_instance, 'get_config') as mock_get_config:
            with patch.object(caddy_manager_instance, 'update_config') as mock_update_config:
                mock_get_config.return_value = caddy_config
                mock_update_config.return_value = True
                
                result = await caddy_manager_instance.add_service_route(service_info)
                
                assert result is True
                mock_get_config.assert_called_once()
                mock_update_config.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_remove_service_route(self, caddy_manager_instance, caddy_config):
        """Test removing service route"""
        # Add a route to the config first
        caddy_config['apps']['http']['servers']['srv0']['routes'] = [
            {
                'match': [{'host': ['test.example.com']}],
                'handle': [
                    {
                        'handler': 'reverse_proxy',
                        'upstreams': [{'dial': 'localhost:8080'}]
                    }
                ],
                'terminal': True
            }
        ]
        
        with patch.object(caddy_manager_instance, 'get_config') as mock_get_config:
            with patch.object(caddy_manager_instance, 'update_config') as mock_update_config:
                mock_get_config.return_value = caddy_config
                mock_update_config.return_value = True
                
                result = await caddy_manager_instance.remove_service_route('test-service')
                
                assert result is True
                mock_get_config.assert_called_once()
                mock_update_config.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reload_config(self, caddy_manager_instance):
        """Test config reload"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response
            
            result = await caddy_manager_instance.reload_config()
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, caddy_manager_instance):
        """Test successful health check"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'healthy': True}
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            is_healthy = await caddy_manager_instance.health_check()
            
            assert is_healthy is True
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, caddy_manager_instance):
        """Test health check failure"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = ConnectError("Connection failed")
            
            is_healthy = await caddy_manager_instance.health_check()
            
            assert is_healthy is False
    
    @pytest.mark.asyncio
    async def test_detect_and_fix_default_page(self, caddy_manager_instance):
        """Test detection and fix of Caddy default page"""
        # Mock config with default page
        default_config = {
            'apps': {
                'http': {
                    'servers': {
                        'srv0': {
                            'routes': [
                                {
                                    'handle': [
                                        {
                                            'handler': 'static_response',
                                            'body': 'Congratulations! Your web server is working.'
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
        }
        
        with patch.object(caddy_manager_instance, 'get_config') as mock_get_config:
            with patch.object(caddy_manager_instance, 'update_config') as mock_update_config:
                mock_get_config.return_value = default_config
                mock_update_config.return_value = True
                
                result = await caddy_manager_instance.detect_and_fix_default_page()
                
                assert result is True
                mock_get_config.assert_called_once()
                mock_update_config.assert_called_once()
    
    def test_build_route_config(self, caddy_manager_instance):
        """Test route configuration building"""
        service_info = {
            'name': 'test-service',
            'domain': 'test.example.com',
            'upstream': 'http://localhost:8080',
            'ports': [{'container_port': 80, 'host_port': 8080}]
        }
        
        route_config = caddy_manager_instance._build_route_config(service_info)
        
        assert route_config['match'][0]['host'] == ['test.example.com']
        assert route_config['handle'][0]['handler'] == 'reverse_proxy'
        assert route_config['handle'][0]['upstreams'][0]['dial'] == 'localhost:8080'
        assert route_config['terminal'] is True
    
    def test_generate_upstream_address(self, caddy_manager_instance):
        """Test upstream address generation"""
        service_info = {
            'name': 'test-service',
            'ports': [{'container_port': 80, 'host_port': 8080}]
        }
        
        upstream = caddy_manager_instance._generate_upstream_address(service_info)
        
        assert upstream == 'localhost:8080'
    
    def test_generate_upstream_address_no_ports(self, caddy_manager_instance):
        """Test upstream address generation with no ports"""
        service_info = {
            'name': 'test-service',
            'ports': []
        }
        
        upstream = caddy_manager_instance._generate_upstream_address(service_info)
        
        assert upstream == 'localhost:80'  # Default port


class TestCaddyManagerGlobal:
    """Test cases for global caddy_manager instance"""
    
    def test_global_instance_creation(self):
        """Test that global caddy_manager instance is created"""
        assert caddy_manager is not None
        assert isinstance(caddy_manager, CaddyManager)
    
    @pytest.mark.asyncio
    async def test_global_instance_methods(self):
        """Test that global instance methods are accessible"""
        # Test that methods exist
        assert hasattr(caddy_manager, 'initialize')
        assert hasattr(caddy_manager, 'get_config')
        assert hasattr(caddy_manager, 'update_config')
        assert hasattr(caddy_manager, 'add_service_route')
        assert hasattr(caddy_manager, 'remove_service_route')
        assert hasattr(caddy_manager, 'health_check')
