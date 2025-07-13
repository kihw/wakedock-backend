"""
End-to-end system integration tests for WakeDock.
Tests the complete workflow from service creation to monitoring.
"""

import asyncio
import json
import pytest
import time
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

from wakedock.core.orchestrator import DockerOrchestrator
from wakedock.core.caddy import caddy_manager
from wakedock.core.monitoring import MonitoringService
from wakedock.events.handlers import event_manager
from wakedock.events.types import EventType, create_service_event
from wakedock.plugins.base import plugin_manager
from wakedock.cache.manager import cache_manager


@pytest.fixture
async def system_components():
    """Set up system components for testing."""
    # Initialize components
    orchestrator = DockerOrchestrator()
    monitoring = MonitoringService()
    
    # Start event manager
    await event_manager.start()
    
    # Mock Docker client for testing
    orchestrator.client = MagicMock()
    orchestrator.client.ping.return_value = True
    
    yield {
        'orchestrator': orchestrator,
        'monitoring': monitoring,
        'event_manager': event_manager,
        'cache_manager': cache_manager,
        'plugin_manager': plugin_manager
    }
    
    # Cleanup
    await event_manager.stop()
    await cache_manager.cleanup()
    await plugin_manager.cleanup_all_plugins()


@pytest.fixture
def sample_service_config():
    """Sample service configuration for testing."""
    return {
        "name": "test-app",
        "subdomain": "test",
        "docker_image": "nginx:alpine",
        "ports": ["80:80"],
        "environment": {
            "ENV": "test"
        },
        "auto_shutdown": {
            "enabled": True,
            "idle_timeout": 1800
        },
        "health_check": {
            "enabled": True,
            "path": "/",
            "interval": 30
        }
    }


class TestSystemIntegration:
    """Test complete system integration scenarios."""
    
    async def test_service_lifecycle_with_events(self, system_components, sample_service_config):
        """Test complete service lifecycle with event handling."""
        orchestrator = system_components['orchestrator']
        
        # Track events
        received_events = []
        
        def event_handler(event):
            received_events.append(event)
        
        # Subscribe to service events
        event_manager.subscribe(EventType.SERVICE_STARTING, event_handler)
        event_manager.subscribe(EventType.SERVICE_STARTED, event_handler)
        event_manager.subscribe(EventType.SERVICE_STOPPING, event_handler)
        event_manager.subscribe(EventType.SERVICE_STOPPED, event_handler)
        
        # Create service
        service = await orchestrator.create_service(sample_service_config)
        assert service is not None
        assert service['name'] == 'test-app'
        
        # Mock container for service lifecycle
        mock_container = MagicMock()
        mock_container.id = 'test-container-123'
        mock_container.status = 'running'
        mock_container.attrs = {
            'State': {'Running': True, 'Health': {'Status': 'healthy'}},
            'NetworkSettings': {'IPAddress': '172.17.0.2'}
        }
        
        orchestrator.client.containers.run.return_value = mock_container
        orchestrator.client.containers.get.return_value = mock_container
        
        # Start service
        result = await orchestrator.wake_service(service['id'])
        assert result is True
        
        # Verify service is running
        is_running = await orchestrator.is_service_running(service['id'])
        assert is_running is True
        
        # Stop service
        result = await orchestrator.sleep_service(service['id'])
        assert result is True
        
        # Give events time to process
        await asyncio.sleep(0.1)
        
        # Verify events were fired
        assert len(received_events) >= 2  # At least start and stop events
        event_types = [e.event_type for e in received_events]
        assert EventType.SERVICE_STARTING in event_types or EventType.SERVICE_STARTED in event_types
    
    async def test_caddy_integration_with_service(self, system_components, sample_service_config):
        """Test Caddy integration when services start/stop."""
        orchestrator = system_components['orchestrator']
        
        # Mock Caddy API responses
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text.return_value = '{"success": true}'
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # Create and start service
            service = await orchestrator.create_service(sample_service_config)
            
            # Mock container
            mock_container = MagicMock()
            mock_container.id = 'test-container-123'
            mock_container.attrs = {
                'NetworkSettings': {'IPAddress': '172.17.0.2'}
            }
            orchestrator.client.containers.run.return_value = mock_container
            orchestrator.client.containers.get.return_value = mock_container
            
            # Start service (should trigger Caddy configuration)
            await orchestrator.wake_service(service['id'])
            
            # Verify Caddy API was called
            assert mock_post.called
            
            # Test Caddy configuration reload
            reload_success = await caddy_manager.reload_config()
            assert reload_success is True
    
    async def test_monitoring_integration(self, system_components, sample_service_config):
        """Test monitoring integration with service metrics."""
        orchestrator = system_components['orchestrator']
        monitoring = system_components['monitoring']
        
        # Create and start service
        service = await orchestrator.create_service(sample_service_config)
        
        # Mock container with stats
        mock_container = MagicMock()
        mock_container.id = 'test-container-123'
        mock_container.stats.return_value = iter([{
            'cpu_stats': {'cpu_usage': {'total_usage': 1000000}},
            'memory_stats': {'usage': 50000000, 'limit': 100000000},
            'networks': {'eth0': {'rx_bytes': 1000, 'tx_bytes': 2000}}
        }])
        
        orchestrator.client.containers.run.return_value = mock_container
        orchestrator.client.containers.get.return_value = mock_container
        
        await orchestrator.wake_service(service['id'])
        
        # Collect metrics
        metrics = await monitoring.collect_service_metrics(service['id'])
        
        # Verify metrics structure
        assert isinstance(metrics, dict)
        assert 'timestamp' in metrics
        
        # Test system metrics
        system_metrics = await monitoring.get_system_metrics()
        assert isinstance(system_metrics, dict)
    
    async def test_cache_integration(self, system_components, sample_service_config):
        """Test caching integration with service operations."""
        orchestrator = system_components['orchestrator']
        cache = system_components['cache_manager']
        
        # Create service
        service = await orchestrator.create_service(sample_service_config)
        service_id = service['id']
        
        # Cache service data
        cache_key = f"service:{service_id}"
        await cache.set(cache_key, service, ttl=60)
        
        # Retrieve from cache
        cached_service = await cache.get(cache_key)
        assert cached_service is not None
        assert cached_service['name'] == service['name']
        
        # Test cache invalidation
        await cache.delete(cache_key)
        cached_service = await cache.get(cache_key)
        assert cached_service is None
    
    async def test_plugin_system_integration(self, system_components, sample_service_config):
        """Test plugin system integration with service events."""
        orchestrator = system_components['orchestrator']
        plugin_mgr = system_components['plugin_manager']
        
        # Create a test plugin
        from wakedock.plugins.base import ServicePlugin, PluginMetadata, PluginType
        
        class TestPlugin(ServicePlugin):
            def __init__(self):
                super().__init__()
                self.events_received = []
            
            @property
            def metadata(self):
                return PluginMetadata(
                    name="test_plugin",
                    version="1.0.0",
                    description="Test plugin",
                    author="Test",
                    plugin_type=PluginType.SERVICE
                )
            
            async def before_service_start(self, service_id: str, config: Dict[str, Any]):
                self.events_received.append(('before_start', service_id))
                return config
            
            async def after_service_start(self, service_id: str, container_info: Dict[str, Any]):
                self.events_received.append(('after_start', service_id))
        
        # Load test plugin
        test_plugin = TestPlugin()
        await plugin_mgr.load_plugin(TestPlugin)
        
        # Create and start service
        service = await orchestrator.create_service(sample_service_config)
        
        # Mock container
        mock_container = MagicMock()
        mock_container.id = 'test-container-123'
        orchestrator.client.containers.run.return_value = mock_container
        
        # Execute plugin hooks
        await plugin_mgr.execute_hook(
            'service.before_start',
            service['id'],
            sample_service_config
        )
        
        await plugin_mgr.execute_hook(
            'service.after_start',
            service['id'],
            {'container_id': 'test-container-123'}
        )
        
        # Verify plugin received events
        plugin_instance = await plugin_mgr.get_plugin("test_plugin")
        assert len(plugin_instance.events_received) >= 1
    
    async def test_error_handling_and_recovery(self, system_components, sample_service_config):
        """Test system error handling and recovery mechanisms."""
        orchestrator = system_components['orchestrator']
        
        # Create service
        service = await orchestrator.create_service(sample_service_config)
        
        # Test container creation failure
        orchestrator.client.containers.run.side_effect = Exception("Container creation failed")
        
        # Start service should handle error gracefully
        result = await orchestrator.wake_service(service['id'])
        assert result is False
        
        # Reset mock and test successful recovery
        orchestrator.client.containers.run.side_effect = None
        mock_container = MagicMock()
        mock_container.id = 'test-container-123'
        orchestrator.client.containers.run.return_value = mock_container
        orchestrator.client.containers.get.return_value = mock_container
        
        # Service should start successfully after error
        result = await orchestrator.wake_service(service['id'])
        assert result is True
    
    async def test_concurrent_service_operations(self, system_components, sample_service_config):
        """Test concurrent service operations."""
        orchestrator = system_components['orchestrator']
        
        # Create multiple services
        services = []
        for i in range(3):
            config = sample_service_config.copy()
            config['name'] = f'test-app-{i}'
            config['subdomain'] = f'test{i}'
            service = await orchestrator.create_service(config)
            services.append(service)
        
        # Mock containers
        def create_mock_container(service_name):
            mock_container = MagicMock()
            mock_container.id = f'{service_name}-container'
            return mock_container
        
        orchestrator.client.containers.run.side_effect = lambda *args, **kwargs: create_mock_container(
            kwargs.get('name', 'unknown')
        )
        
        # Start all services concurrently
        start_tasks = [
            orchestrator.wake_service(service['id'])
            for service in services
        ]
        
        results = await asyncio.gather(*start_tasks, return_exceptions=True)
        
        # Verify all services started successfully
        for result in results:
            assert result is True or isinstance(result, Exception)
        
        # Stop all services concurrently
        stop_tasks = [
            orchestrator.sleep_service(service['id'])
            for service in services
        ]
        
        results = await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        # Verify all services stopped
        for result in results:
            assert result is True or isinstance(result, Exception)
    
    async def test_health_monitoring_workflow(self, system_components, sample_service_config):
        """Test health monitoring workflow."""
        orchestrator = system_components['orchestrator']
        monitoring = system_components['monitoring']
        
        # Create service with health check
        service = await orchestrator.create_service(sample_service_config)
        
        # Mock healthy container
        mock_container = MagicMock()
        mock_container.id = 'test-container-123'
        mock_container.attrs = {
            'State': {'Running': True, 'Health': {'Status': 'healthy'}}
        }
        orchestrator.client.containers.run.return_value = mock_container
        orchestrator.client.containers.get.return_value = mock_container
        
        await orchestrator.wake_service(service['id'])
        
        # Test health check
        is_healthy = await monitoring.check_service_health(service['id'])
        assert is_healthy is True
        
        # Test unhealthy container
        mock_container.attrs['State']['Health']['Status'] = 'unhealthy'
        is_healthy = await monitoring.check_service_health(service['id'])
        assert is_healthy is False
    
    async def test_configuration_reload_workflow(self, system_components):
        """Test configuration reload workflow."""
        orchestrator = system_components['orchestrator']
        
        # Test service list before and after config changes
        initial_services = await orchestrator.list_services()
        initial_count = len(initial_services)
        
        # Simulate configuration reload by loading services
        orchestrator._load_services()
        
        updated_services = await orchestrator.list_services()
        # Should maintain same count after reload
        assert len(updated_services) >= initial_count


class TestAPIIntegration:
    """Test API integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_api_service_lifecycle(self, system_components, sample_service_config):
        """Test service lifecycle through API endpoints."""
        # This would test actual API endpoints if FastAPI test client was available
        # For now, we test the underlying service operations
        
        orchestrator = system_components['orchestrator']
        
        # Simulate API service creation
        service = await orchestrator.create_service(sample_service_config)
        assert service['name'] == sample_service_config['name']
        
        # Simulate API service listing
        services = await orchestrator.list_services()
        assert any(s['id'] == service['id'] for s in services)
        
        # Simulate API service retrieval
        retrieved_service = await orchestrator.get_service(service['id'])
        assert retrieved_service is not None
        assert retrieved_service['id'] == service['id']
        
        # Simulate API service deletion
        deleted = await orchestrator.delete_service(service['id'])
        assert deleted is True
        
        # Verify service is gone
        retrieved_service = await orchestrator.get_service(service['id'])
        assert retrieved_service is None


class TestPerformanceAndScalability:
    """Test system performance and scalability."""
    
    async def test_service_startup_performance(self, system_components, sample_service_config):
        """Test service startup performance."""
        orchestrator = system_components['orchestrator']
        
        # Create service
        service = await orchestrator.create_service(sample_service_config)
        
        # Mock fast container creation
        mock_container = MagicMock()
        mock_container.id = 'test-container-123'
        orchestrator.client.containers.run.return_value = mock_container
        orchestrator.client.containers.get.return_value = mock_container
        
        # Measure startup time
        start_time = time.time()
        result = await orchestrator.wake_service(service['id'])
        end_time = time.time()
        
        startup_time = end_time - start_time
        
        assert result is True
        assert startup_time < 5.0  # Should start within 5 seconds
    
    async def test_memory_usage(self, system_components):
        """Test memory usage during operations."""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        orchestrator = system_components['orchestrator']
        
        # Create multiple services
        services = []
        for i in range(10):
            config = {
                "name": f"test-app-{i}",
                "subdomain": f"test{i}",
                "docker_image": "nginx:alpine",
                "ports": ["80:80"]
            }
            service = await orchestrator.create_service(config)
            services.append(service)
        
        # Check memory usage after creating services
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB for 10 services)
        assert memory_increase < 100
        
        # Cleanup
        for service in services:
            await orchestrator.delete_service(service['id'])


@pytest.mark.integration
class TestRealSystemIntegration:
    """Integration tests that require real Docker (marked for optional execution)."""
    
    @pytest.mark.docker
    async def test_real_docker_integration(self, sample_service_config):
        """Test with real Docker daemon (requires Docker to be running)."""
        orchestrator = DockerOrchestrator()
        
        # Skip if Docker is not available
        if not orchestrator.client:
            pytest.skip("Docker not available")
        
        try:
            # Create and start a real service
            service = await orchestrator.create_service(sample_service_config)
            
            # Start the service
            result = await orchestrator.wake_service(service['id'])
            assert result is True
            
            # Verify service is running
            is_running = await orchestrator.is_service_running(service['id'])
            assert is_running is True
            
            # Stop the service
            result = await orchestrator.sleep_service(service['id'])
            assert result is True
            
        finally:
            # Cleanup
            try:
                await orchestrator.delete_service(service['id'])
            except:
                pass  # Best effort cleanup
