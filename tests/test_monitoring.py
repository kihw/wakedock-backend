"""
Unit tests for Monitoring Service
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import time
from datetime import datetime, timedelta

from wakedock.core.monitoring import MonitoringService
from wakedock.exceptions import MonitoringError


class TestMonitoringService:
    """Test cases for MonitoringService"""
    
    @pytest.fixture
    def monitoring_service(self):
        """Create MonitoringService instance"""
        return MonitoringService()
    
    @pytest.fixture
    def mock_orchestrator(self):
        """Mock orchestrator"""
        orchestrator = Mock()
        orchestrator.list_services = AsyncMock(return_value=[
            {
                'id': 'service1',
                'name': 'test-service-1',
                'status': 'running',
                'ports': [{'container_port': 80, 'host_port': 8080}]
            },
            {
                'id': 'service2', 
                'name': 'test-service-2',
                'status': 'stopped',
                'ports': []
            }
        ])
        orchestrator.get_service_stats = AsyncMock(return_value={
            'cpu_usage': 25.5,
            'memory_usage': 1048576,
            'memory_limit': 2097152,
            'network_rx': 1024,
            'network_tx': 2048
        })
        return orchestrator
    
    def test_init(self, monitoring_service):
        """Test MonitoringService initialization"""
        assert monitoring_service.orchestrator is None
        assert monitoring_service.metrics == {}
        assert monitoring_service.alerts == []
        assert monitoring_service.running is False
    
    def test_set_orchestrator(self, monitoring_service, mock_orchestrator):
        """Test setting orchestrator"""
        monitoring_service.set_orchestrator(mock_orchestrator)
        assert monitoring_service.orchestrator is mock_orchestrator
    
    @pytest.mark.asyncio
    async def test_collect_system_metrics(self, monitoring_service):
        """Test system metrics collection"""
        with patch('psutil.cpu_percent') as mock_cpu:
            with patch('psutil.virtual_memory') as mock_memory:
                with patch('psutil.disk_usage') as mock_disk:
                    mock_cpu.return_value = 45.2
                    mock_memory.return_value = Mock(
                        percent=65.8,
                        total=8589934592,
                        available=2684354560
                    )
                    mock_disk.return_value = Mock(
                        percent=78.3,
                        total=1099511627776,
                        free=238609294336
                    )
                    
                    metrics = await monitoring_service.collect_system_metrics()
                    
                    assert metrics['cpu_usage'] == 45.2
                    assert metrics['memory_usage'] == 65.8
                    assert metrics['disk_usage'] == 78.3
                    assert 'timestamp' in metrics
    
    @pytest.mark.asyncio
    async def test_collect_service_metrics(self, monitoring_service, mock_orchestrator):
        """Test service metrics collection"""
        monitoring_service.set_orchestrator(mock_orchestrator)
        
        metrics = await monitoring_service.collect_service_metrics()
        
        assert len(metrics) == 2
        assert metrics[0]['service_name'] == 'test-service-1'
        assert metrics[0]['status'] == 'running'
        assert metrics[0]['cpu_usage'] == 25.5
        assert metrics[1]['service_name'] == 'test-service-2'
        assert metrics[1]['status'] == 'stopped'
        
        mock_orchestrator.list_services.assert_called_once()
        mock_orchestrator.get_service_stats.assert_called_once_with('test-service-1')
    
    @pytest.mark.asyncio
    async def test_collect_service_metrics_no_orchestrator(self, monitoring_service):
        """Test service metrics collection without orchestrator"""
        metrics = await monitoring_service.collect_service_metrics()
        assert metrics == []
    
    @pytest.mark.asyncio
    async def test_collect_all_metrics(self, monitoring_service, mock_orchestrator):
        """Test collecting all metrics"""
        monitoring_service.set_orchestrator(mock_orchestrator)
        
        with patch.object(monitoring_service, 'collect_system_metrics') as mock_system:
            with patch.object(monitoring_service, 'collect_service_metrics') as mock_services:
                mock_system.return_value = {'cpu_usage': 45.2, 'memory_usage': 65.8}
                mock_services.return_value = [{'service_name': 'test', 'cpu_usage': 25.5}]
                
                all_metrics = await monitoring_service.collect_all_metrics()
                
                assert 'system' in all_metrics
                assert 'services' in all_metrics
                assert all_metrics['system']['cpu_usage'] == 45.2
                assert len(all_metrics['services']) == 1
    
    @pytest.mark.asyncio
    async def test_get_metrics_history(self, monitoring_service):
        """Test getting metrics history"""
        # Add some test metrics
        monitoring_service.metrics = {
            'system': [
                {'timestamp': time.time() - 3600, 'cpu_usage': 30.0},
                {'timestamp': time.time() - 1800, 'cpu_usage': 35.0},
                {'timestamp': time.time(), 'cpu_usage': 40.0}
            ]
        }
        
        history = await monitoring_service.get_metrics_history('system', hours=2)
        
        assert len(history) == 3
        assert all('cpu_usage' in metric for metric in history)
    
    @pytest.mark.asyncio
    async def test_get_metrics_history_with_limit(self, monitoring_service):
        """Test getting metrics history with limit"""
        # Add test metrics
        monitoring_service.metrics = {
            'system': [
                {'timestamp': time.time() - i * 300, 'cpu_usage': 30.0 + i}
                for i in range(10)
            ]
        }
        
        history = await monitoring_service.get_metrics_history('system', limit=5)
        
        assert len(history) == 5
    
    @pytest.mark.asyncio
    async def test_get_current_stats(self, monitoring_service, mock_orchestrator):
        """Test getting current stats"""
        monitoring_service.set_orchestrator(mock_orchestrator)
        
        with patch.object(monitoring_service, 'collect_all_metrics') as mock_collect:
            mock_collect.return_value = {
                'system': {'cpu_usage': 45.2, 'memory_usage': 65.8},
                'services': [{'service_name': 'test', 'status': 'running'}]
            }
            
            stats = await monitoring_service.get_current_stats()
            
            assert 'system' in stats
            assert 'services' in stats
            assert stats['system']['cpu_usage'] == 45.2
    
    def test_check_thresholds_cpu_high(self, monitoring_service):
        """Test CPU threshold checking"""
        metrics = {'cpu_usage': 85.0, 'memory_usage': 50.0, 'disk_usage': 60.0}
        
        alerts = monitoring_service._check_thresholds(metrics)
        
        assert len(alerts) == 1
        assert alerts[0]['type'] == 'cpu_high'
        assert alerts[0]['value'] == 85.0
    
    def test_check_thresholds_memory_high(self, monitoring_service):
        """Test memory threshold checking"""
        metrics = {'cpu_usage': 50.0, 'memory_usage': 88.0, 'disk_usage': 60.0}
        
        alerts = monitoring_service._check_thresholds(metrics)
        
        assert len(alerts) == 1
        assert alerts[0]['type'] == 'memory_high'
        assert alerts[0]['value'] == 88.0
    
    def test_check_thresholds_disk_high(self, monitoring_service):
        """Test disk threshold checking"""
        metrics = {'cpu_usage': 50.0, 'memory_usage': 60.0, 'disk_usage': 92.0}
        
        alerts = monitoring_service._check_thresholds(metrics)
        
        assert len(alerts) == 1
        assert alerts[0]['type'] == 'disk_high'
        assert alerts[0]['value'] == 92.0
    
    def test_check_thresholds_multiple(self, monitoring_service):
        """Test multiple threshold violations"""
        metrics = {'cpu_usage': 85.0, 'memory_usage': 88.0, 'disk_usage': 92.0}
        
        alerts = monitoring_service._check_thresholds(metrics)
        
        assert len(alerts) == 3
        alert_types = [alert['type'] for alert in alerts]
        assert 'cpu_high' in alert_types
        assert 'memory_high' in alert_types
        assert 'disk_high' in alert_types
    
    def test_check_thresholds_no_alerts(self, monitoring_service):
        """Test no threshold violations"""
        metrics = {'cpu_usage': 50.0, 'memory_usage': 60.0, 'disk_usage': 70.0}
        
        alerts = monitoring_service._check_thresholds(metrics)
        
        assert len(alerts) == 0
    
    @pytest.mark.asyncio
    async def test_get_alerts(self, monitoring_service):
        """Test getting alerts"""
        # Add test alerts
        monitoring_service.alerts = [
            {
                'id': 'alert1',
                'type': 'cpu_high',
                'message': 'CPU usage is high',
                'timestamp': datetime.now(),
                'resolved': False
            },
            {
                'id': 'alert2',
                'type': 'memory_high',
                'message': 'Memory usage is high',
                'timestamp': datetime.now() - timedelta(hours=1),
                'resolved': True
            }
        ]
        
        all_alerts = await monitoring_service.get_alerts()
        active_alerts = await monitoring_service.get_alerts(active_only=True)
        
        assert len(all_alerts) == 2
        assert len(active_alerts) == 1
        assert active_alerts[0]['type'] == 'cpu_high'
    
    @pytest.mark.asyncio
    async def test_resolve_alert(self, monitoring_service):
        """Test resolving an alert"""
        # Add test alert
        monitoring_service.alerts = [
            {
                'id': 'alert1',
                'type': 'cpu_high',
                'message': 'CPU usage is high',
                'timestamp': datetime.now(),
                'resolved': False
            }
        ]
        
        result = await monitoring_service.resolve_alert('alert1')
        
        assert result is True
        assert monitoring_service.alerts[0]['resolved'] is True
    
    @pytest.mark.asyncio
    async def test_resolve_alert_not_found(self, monitoring_service):
        """Test resolving non-existent alert"""
        result = await monitoring_service.resolve_alert('nonexistent')
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_start_monitoring(self, monitoring_service):
        """Test starting monitoring"""
        with patch.object(monitoring_service, '_monitoring_loop') as mock_loop:
            mock_loop.return_value = AsyncMock()
            
            await monitoring_service.start_monitoring(interval=60)
            
            assert monitoring_service.running is True
            assert monitoring_service.interval == 60
    
    @pytest.mark.asyncio
    async def test_stop_monitoring(self, monitoring_service):
        """Test stopping monitoring"""
        monitoring_service.running = True
        
        await monitoring_service.stop_monitoring()
        
        assert monitoring_service.running is False
    
    @pytest.mark.asyncio
    async def test_monitoring_loop_error_handling(self, monitoring_service, mock_orchestrator):
        """Test monitoring loop error handling"""
        monitoring_service.set_orchestrator(mock_orchestrator)
        monitoring_service.running = True
        
        with patch.object(monitoring_service, 'collect_all_metrics') as mock_collect:
            mock_collect.side_effect = Exception("Collection failed")
            
            # Should not raise exception, just log it
            await monitoring_service._monitoring_loop()
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, monitoring_service):
        """Test successful health check"""
        is_healthy = await monitoring_service.health_check()
        assert is_healthy is True
    
    @pytest.mark.asyncio
    async def test_export_metrics_prometheus(self, monitoring_service):
        """Test Prometheus metrics export"""
        monitoring_service.metrics = {
            'system': [
                {'timestamp': time.time(), 'cpu_usage': 45.2, 'memory_usage': 65.8}
            ]
        }
        
        prometheus_metrics = await monitoring_service.export_metrics('prometheus')
        
        assert 'system_cpu_usage' in prometheus_metrics
        assert 'system_memory_usage' in prometheus_metrics
    
    @pytest.mark.asyncio
    async def test_export_metrics_json(self, monitoring_service):
        """Test JSON metrics export"""
        monitoring_service.metrics = {
            'system': [
                {'timestamp': time.time(), 'cpu_usage': 45.2}
            ]
        }
        
        json_metrics = await monitoring_service.export_metrics('json')
        
        assert 'system' in json_metrics
        assert json_metrics['system'][0]['cpu_usage'] == 45.2
