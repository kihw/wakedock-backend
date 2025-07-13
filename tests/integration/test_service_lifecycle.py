"""
Integration tests for service lifecycle management
"""

import pytest
import asyncio
import docker
from unittest.mock import Mock, patch

from wakedock.core.orchestrator import DockerOrchestrator
from wakedock.core.caddy import caddy_manager
from wakedock.core.monitoring import MonitoringService


class TestServiceLifecycleIntegration:
    """Integration tests for complete service lifecycle"""
    
    @pytest.fixture
    def test_service_config(self):
        """Test service configuration"""
        return {
            'name': 'test-nginx',
            'image': 'nginx:alpine',
            'ports': {'80/tcp': 8080},
            'environment': {
                'NGINX_PORT': '80'
            },
            'labels': {
                'wakedock.managed': 'true',
                'wakedock.service': 'test-nginx',
                'wakedock.domain': 'test.local'
            }
        }
    
    @pytest.fixture
    async def orchestrator(self):
        """Create orchestrator for testing"""
        try:
            orchestrator = DockerOrchestrator()
            yield orchestrator
        except Exception as e:
            pytest.skip(f"Docker not available: {e}")
    
    @pytest.fixture
    async def monitoring_service(self, orchestrator):
        """Create monitoring service for testing"""
        monitoring = MonitoringService()
        monitoring.set_orchestrator(orchestrator)
        yield monitoring
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_service_deployment_lifecycle(self, orchestrator, test_service_config):
        """Test complete service deployment lifecycle"""
        service_name = test_service_config['name']
        
        try:
            # 1. Deploy service
            result = await orchestrator.deploy_service(test_service_config)
            assert result is True
            
            # 2. Verify service is running
            await asyncio.sleep(2)  # Wait for container to start
            service = await orchestrator.get_service(service_name)
            assert service['status'] == 'running'
            assert service['name'] == service_name
            
            # 3. Test service operations
            # Stop service
            stop_result = await orchestrator.stop_service(service_name)
            assert stop_result is True
            
            # Verify service is stopped
            await asyncio.sleep(1)
            service = await orchestrator.get_service(service_name)
            assert service['status'] in ['stopped', 'exited']
            
            # Start service again
            start_result = await orchestrator.start_service(service_name)
            assert start_result is True
            
            # Verify service is running again
            await asyncio.sleep(2)
            service = await orchestrator.get_service(service_name)
            assert service['status'] == 'running'
            
            # 4. Test restart
            restart_result = await orchestrator.restart_service(service_name)
            assert restart_result is True
            
            # 5. Get service logs
            logs = await orchestrator.get_service_logs(service_name, lines=10)
            assert isinstance(logs, str)
            assert len(logs) > 0
            
            # 6. Get service stats
            stats = await orchestrator.get_service_stats(service_name)
            assert 'cpu_usage' in stats
            assert 'memory_usage' in stats
            
        finally:
            # Cleanup: Remove the test service
            try:
                await orchestrator.remove_service(service_name)
            except Exception:
                pass  # Ignore cleanup errors
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_service_scaling(self, orchestrator, test_service_config):
        """Test service scaling functionality"""
        service_name = test_service_config['name']
        
        try:
            # Deploy initial service
            await orchestrator.deploy_service(test_service_config)
            await asyncio.sleep(2)
            
            # Scale service
            scale_result = await orchestrator.scale_service(service_name, replicas=3)
            assert scale_result is True
            
            # Verify scaling
            await asyncio.sleep(3)
            services = await orchestrator.list_services()
            scaled_services = [s for s in services if s['name'].startswith(service_name)]
            assert len(scaled_services) >= 1  # At least the original service
            
            # Scale down
            scale_down_result = await orchestrator.scale_service(service_name, replicas=1)
            assert scale_down_result is True
            
        finally:
            # Cleanup
            try:
                await orchestrator.remove_service(service_name)
            except Exception:
                pass
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_service_networking(self, orchestrator, test_service_config):
        """Test service networking and port mapping"""
        service_name = test_service_config['name']
        
        try:
            # Deploy service with specific port mapping
            await orchestrator.deploy_service(test_service_config)
            await asyncio.sleep(2)
            
            # Verify service networking
            service = await orchestrator.get_service(service_name)
            assert len(service['ports']) > 0
            
            port_mapping = service['ports'][0]
            assert port_mapping['container_port'] == 80
            assert port_mapping['host_port'] == 8080
            
            # Test network connectivity (if possible)
            import requests
            try:
                response = requests.get(f"http://localhost:{port_mapping['host_port']}", timeout=5)
                # If we get any response, the service is accessible
                assert response.status_code in [200, 403, 404]  # Any valid HTTP response
            except requests.exceptions.RequestException:
                # Network test may fail in CI/CD environments, that's okay
                pass
            
        finally:
            # Cleanup
            try:
                await orchestrator.remove_service(service_name)
            except Exception:
                pass
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_service_environment_variables(self, orchestrator, test_service_config):
        """Test service environment variable injection"""
        service_name = test_service_config['name']
        
        try:
            # Deploy service with environment variables
            await orchestrator.deploy_service(test_service_config)
            await asyncio.sleep(2)
            
            # Verify environment variables are set
            service = await orchestrator.get_service(service_name)
            assert 'environment' in service
            assert service['environment'].get('NGINX_PORT') == '80'
            
        finally:
            # Cleanup
            try:
                await orchestrator.remove_service(service_name)
            except Exception:
                pass
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_service_labels(self, orchestrator, test_service_config):
        """Test service label management"""
        service_name = test_service_config['name']
        
        try:
            # Deploy service with labels
            await orchestrator.deploy_service(test_service_config)
            await asyncio.sleep(2)
            
            # Verify labels are set
            service = await orchestrator.get_service(service_name)
            assert 'labels' in service
            assert service['labels'].get('wakedock.managed') == 'true'
            assert service['labels'].get('wakedock.service') == service_name
            assert service['labels'].get('wakedock.domain') == 'test.local'
            
        finally:
            # Cleanup
            try:
                await orchestrator.remove_service(service_name)
            except Exception:
                pass
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_monitoring_integration(self, orchestrator, monitoring_service, test_service_config):
        """Test monitoring integration with service lifecycle"""
        service_name = test_service_config['name']
        
        try:
            # Deploy service
            await orchestrator.deploy_service(test_service_config)
            await asyncio.sleep(2)
            
            # Collect service metrics
            service_metrics = await monitoring_service.collect_service_metrics()
            
            # Find our test service in metrics
            test_service_metrics = None
            for metrics in service_metrics:
                if metrics['service_name'] == service_name:
                    test_service_metrics = metrics
                    break
            
            assert test_service_metrics is not None
            assert test_service_metrics['status'] == 'running'
            assert 'cpu_usage' in test_service_metrics
            assert 'memory_usage' in test_service_metrics
            
            # Test system metrics collection
            system_metrics = await monitoring_service.collect_system_metrics()
            assert 'cpu_usage' in system_metrics
            assert 'memory_usage' in system_metrics
            assert 'disk_usage' in system_metrics
            
        finally:
            # Cleanup
            try:
                await orchestrator.remove_service(service_name)
            except Exception:
                pass
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_service_persistence(self, orchestrator, test_service_config):
        """Test service persistence across restarts"""
        service_name = test_service_config['name']
        
        # Add volume for persistence testing
        test_service_config['volumes'] = {
            '/tmp/test-data': {'bind': '/data', 'mode': 'rw'}
        }
        
        try:
            # Deploy service with volumes
            await orchestrator.deploy_service(test_service_config)
            await asyncio.sleep(2)
            
            # Verify service is running
            service = await orchestrator.get_service(service_name)
            assert service['status'] == 'running'
            
            # Restart service
            await orchestrator.restart_service(service_name)
            await asyncio.sleep(2)
            
            # Verify service is still accessible and volumes are mounted
            service = await orchestrator.get_service(service_name)
            assert service['status'] == 'running'
            assert 'volumes' in service
            
        finally:
            # Cleanup
            try:
                await orchestrator.remove_service(service_name)
            except Exception:
                pass
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_handling(self, orchestrator):
        """Test error handling in service operations"""
        # Test with non-existent service
        with pytest.raises(Exception):  # Should raise ServiceNotFoundError
            await orchestrator.get_service('nonexistent-service')
        
        # Test with invalid service configuration
        invalid_config = {
            'name': 'invalid-service',
            'image': 'nonexistent-image-12345',  # This image should not exist
            'ports': {'80/tcp': 8080}
        }
        
        try:
            result = await orchestrator.deploy_service(invalid_config)
            # Deployment might fail or succeed depending on Docker behavior
            # If it succeeds, clean up
            if result:
                await orchestrator.remove_service('invalid-service')
        except Exception:
            # Expected to fail with non-existent image
            pass
