"""
Tests for system metrics and monitoring functionality.

Tests CPU/memory/disk monitoring, WebSocket broadcasting,
alert thresholds, and metric history retention.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict, Any, List

from wakedock.core.system_metrics import SystemMetricsCollector, SystemMetrics
from wakedock.core.monitoring import MonitoringService
from wakedock.core.docker_events import DockerEventsHandler
from wakedock.core.log_streaming import LogStreamingService
from wakedock.core.notifications import NotificationManager


class TestSystemMetrics:
    """Test system metrics data structures."""
    
    def test_system_metrics_init(self):
        """Test SystemMetrics initialization."""
        metrics = SystemMetrics(
            cpu_percent=45.2,
            memory_percent=62.8,
            disk_percent=78.5,
            network_rx=1024,
            network_tx=2048,
            timestamp=datetime.now()
        )
        
        assert metrics.cpu_percent == 45.2
        assert metrics.memory_percent == 62.8
        assert metrics.disk_percent == 78.5
        assert metrics.network_rx == 1024
        assert metrics.network_tx == 2048
        assert isinstance(metrics.timestamp, datetime)
    
    def test_system_metrics_to_dict(self):
        """Test SystemMetrics conversion to dictionary."""
        timestamp = datetime.now()
        metrics = SystemMetrics(
            cpu_percent=50.0,
            memory_percent=60.0,
            disk_percent=70.0,
            network_rx=1024,
            network_tx=2048,
            timestamp=timestamp
        )
        
        data = metrics.to_dict()
        
        assert data["cpu_percent"] == 50.0
        assert data["memory_percent"] == 60.0
        assert data["disk_percent"] == 70.0
        assert data["network_rx"] == 1024
        assert data["network_tx"] == 2048
        assert data["timestamp"] == timestamp.isoformat()
    
    def test_system_metrics_from_dict(self):
        """Test SystemMetrics creation from dictionary."""
        timestamp = datetime.now()
        data = {
            "cpu_percent": 45.0,
            "memory_percent": 55.0,
            "disk_percent": 65.0,
            "network_rx": 512,
            "network_tx": 1024,
            "timestamp": timestamp.isoformat()
        }
        
        metrics = SystemMetrics.from_dict(data)
        
        assert metrics.cpu_percent == 45.0
        assert metrics.memory_percent == 55.0
        assert metrics.disk_percent == 65.0
        assert metrics.network_rx == 512
        assert metrics.network_tx == 1024
        assert abs((metrics.timestamp - timestamp).total_seconds()) < 1


class TestSystemMetricsCollector:
    """Test system metrics collection."""
    
    @pytest.fixture
    def collector(self):
        """Create system metrics collector."""
        return SystemMetricsCollector(collection_interval=1)
    
    @pytest.fixture
    def mock_psutil(self):
        """Mock psutil for system metrics."""
        with patch('psutil.cpu_percent') as mock_cpu, \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.disk_usage') as mock_disk, \
             patch('psutil.net_io_counters') as mock_net:
            
            # Configure mocks
            mock_cpu.return_value = 45.2
            
            mock_memory_obj = Mock()
            mock_memory_obj.percent = 62.8
            mock_memory.return_value = mock_memory_obj
            
            mock_disk_obj = Mock()
            mock_disk_obj.percent = 78.5
            mock_disk.return_value = mock_disk_obj
            
            mock_net_obj = Mock()
            mock_net_obj.bytes_recv = 1024000
            mock_net_obj.bytes_sent = 2048000
            mock_net.return_value = mock_net_obj
            
            yield {
                'cpu': mock_cpu,
                'memory': mock_memory,
                'disk': mock_disk,
                'net': mock_net
            }
    
    def test_collector_init(self, collector):
        """Test collector initialization."""
        assert collector.collection_interval == 1
        assert collector._running is False
        assert collector._metrics_history == []
        assert collector._subscribers == []
    
    @pytest.mark.asyncio
    async def test_collect_metrics(self, collector, mock_psutil):
        """Test collecting current system metrics."""
        metrics = await collector.collect_current_metrics()
        
        assert isinstance(metrics, SystemMetrics)
        assert metrics.cpu_percent == 45.2
        assert metrics.memory_percent == 62.8
        assert metrics.disk_percent == 78.5
        assert metrics.network_rx == 1024000
        assert metrics.network_tx == 2048000
        assert isinstance(metrics.timestamp, datetime)
    
    @pytest.mark.asyncio
    async def test_collect_metrics_error_handling(self, collector):
        """Test metrics collection error handling."""
        with patch('psutil.cpu_percent', side_effect=Exception("CPU error")):
            metrics = await collector.collect_current_metrics()
            
            # Should still return metrics with default/error values
            assert isinstance(metrics, SystemMetrics)
            assert metrics.cpu_percent == 0.0  # Default on error
    
    @pytest.mark.asyncio
    async def test_start_monitoring(self, collector, mock_psutil):
        """Test starting metrics monitoring."""
        # Start monitoring
        await collector.start_monitoring()
        
        assert collector._running is True
        assert collector._monitor_task is not None
        
        # Stop monitoring
        await collector.stop_monitoring()
        
        assert collector._running is False
    
    @pytest.mark.asyncio
    async def test_metrics_history_retention(self, collector, mock_psutil):
        """Test metrics history retention."""
        # Set short retention for testing
        collector.max_history_size = 5
        
        # Collect multiple metrics
        for i in range(10):
            metrics = await collector.collect_current_metrics()
            collector._add_to_history(metrics)
        
        # Should only keep max_history_size items
        assert len(collector._metrics_history) == 5
    
    def test_add_subscriber(self, collector):
        """Test adding metrics subscriber."""
        callback = AsyncMock()
        
        collector.subscribe(callback)
        
        assert callback in collector._subscribers
    
    def test_remove_subscriber(self, collector):
        """Test removing metrics subscriber."""
        callback = AsyncMock()
        
        collector.subscribe(callback)
        assert callback in collector._subscribers
        
        collector.unsubscribe(callback)
        assert callback not in collector._subscribers
    
    @pytest.mark.asyncio
    async def test_notify_subscribers(self, collector, mock_psutil):
        """Test notifying subscribers with new metrics."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()
        
        collector.subscribe(callback1)
        collector.subscribe(callback2)
        
        # Collect metrics (should notify subscribers)
        metrics = await collector.collect_current_metrics()
        await collector._notify_subscribers(metrics)
        
        callback1.assert_called_once_with(metrics)
        callback2.assert_called_once_with(metrics)
    
    def test_get_metrics_history(self, collector):
        """Test getting metrics history."""
        # Add some mock metrics to history
        timestamp = datetime.now()
        for i in range(5):
            metrics = SystemMetrics(
                cpu_percent=float(i * 10),
                memory_percent=float(i * 15),
                disk_percent=float(i * 20),
                network_rx=i * 1024,
                network_tx=i * 2048,
                timestamp=timestamp - timedelta(minutes=i)
            )
            collector._add_to_history(metrics)
        
        # Get history
        history = collector.get_metrics_history()
        
        assert len(history) == 5
        assert all(isinstance(m, SystemMetrics) for m in history)
    
    def test_get_metrics_history_filtered(self, collector):
        """Test getting filtered metrics history."""
        # Add metrics with different timestamps
        base_time = datetime.now()
        for i in range(10):
            metrics = SystemMetrics(
                cpu_percent=float(i * 10),
                memory_percent=float(i * 15),
                disk_percent=float(i * 20),
                network_rx=i * 1024,
                network_tx=i * 2048,
                timestamp=base_time - timedelta(hours=i)
            )
            collector._add_to_history(metrics)
        
        # Get history for last 5 hours
        since = base_time - timedelta(hours=5)
        history = collector.get_metrics_history(since=since)
        
        # Should return metrics newer than 5 hours
        assert len(history) <= 6  # 0-5 hours = 6 items
        assert all(m.timestamp >= since for m in history)
    
    def test_get_average_metrics(self, collector):
        """Test calculating average metrics."""
        # Add some metrics
        base_time = datetime.now()
        for i in range(5):
            metrics = SystemMetrics(
                cpu_percent=float(i * 20),  # 0, 20, 40, 60, 80
                memory_percent=float(i * 10),  # 0, 10, 20, 30, 40
                disk_percent=50.0,  # Constant
                network_rx=i * 1024,
                network_tx=i * 2048,
                timestamp=base_time - timedelta(minutes=i)
            )
            collector._add_to_history(metrics)
        
        # Calculate averages
        avg_metrics = collector.get_average_metrics()
        
        assert avg_metrics.cpu_percent == 40.0  # Average of 0,20,40,60,80
        assert avg_metrics.memory_percent == 20.0  # Average of 0,10,20,30,40
        assert avg_metrics.disk_percent == 50.0  # Constant value
    
    def test_get_peak_metrics(self, collector):
        """Test getting peak metrics."""
        # Add metrics with varying values
        base_time = datetime.now()
        cpu_values = [30.0, 85.0, 45.0, 92.0, 67.0]
        memory_values = [40.0, 75.0, 55.0, 88.0, 62.0]
        
        for i, (cpu, memory) in enumerate(zip(cpu_values, memory_values)):
            metrics = SystemMetrics(
                cpu_percent=cpu,
                memory_percent=memory,
                disk_percent=50.0,
                network_rx=i * 1024,
                network_tx=i * 2048,
                timestamp=base_time - timedelta(minutes=i)
            )
            collector._add_to_history(metrics)
        
        # Get peak metrics
        peak_metrics = collector.get_peak_metrics()
        
        assert peak_metrics.cpu_percent == 92.0  # Maximum CPU
        assert peak_metrics.memory_percent == 88.0  # Maximum memory


class TestMonitoringService:
    """Test monitoring service functionality."""
    
    @pytest.fixture
    def mock_metrics_collector(self):
        """Create mock metrics collector."""
        collector = Mock(spec=SystemMetricsCollector)
        collector.start_monitoring = AsyncMock()
        collector.stop_monitoring = AsyncMock()
        collector.subscribe = Mock()
        collector.get_metrics_history = Mock(return_value=[])
        collector.get_average_metrics = Mock()
        collector.get_peak_metrics = Mock()
        return collector
    
    @pytest.fixture
    def monitoring_service(self, mock_metrics_collector):
        """Create monitoring service."""
        return MonitoringService(
            metrics_collector=mock_metrics_collector,
            alert_thresholds={
                "cpu_percent": 80.0,
                "memory_percent": 85.0,
                "disk_percent": 90.0
            }
        )
    
    def test_monitoring_service_init(self, monitoring_service, mock_metrics_collector):
        """Test monitoring service initialization."""
        assert monitoring_service.metrics_collector == mock_metrics_collector
        assert monitoring_service.alert_thresholds["cpu_percent"] == 80.0
        assert monitoring_service._alert_callbacks == []
        assert monitoring_service._running is False
    
    @pytest.mark.asyncio
    async def test_start_monitoring_service(self, monitoring_service):
        """Test starting monitoring service."""
        await monitoring_service.start()
        
        assert monitoring_service._running is True
        monitoring_service.metrics_collector.start_monitoring.assert_called_once()
        monitoring_service.metrics_collector.subscribe.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_monitoring_service(self, monitoring_service):
        """Test stopping monitoring service."""
        await monitoring_service.start()
        await monitoring_service.stop()
        
        assert monitoring_service._running is False
        monitoring_service.metrics_collector.stop_monitoring.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_alert_threshold_checking(self, monitoring_service):
        """Test alert threshold checking."""
        # Create metrics that exceed thresholds
        high_cpu_metrics = SystemMetrics(
            cpu_percent=95.0,  # Above 80% threshold
            memory_percent=70.0,
            disk_percent=75.0,
            network_rx=1024,
            network_tx=2048,
            timestamp=datetime.now()
        )
        
        alert_callback = AsyncMock()
        monitoring_service.add_alert_callback(alert_callback)
        
        # Process metrics (should trigger alert)
        await monitoring_service._process_metrics(high_cpu_metrics)
        
        # Verify alert was triggered
        alert_callback.assert_called_once()
        
        # Check alert data
        call_args = alert_callback.call_args[0][0]
        assert call_args["type"] == "threshold_exceeded"
        assert call_args["metric"] == "cpu_percent"
        assert call_args["value"] == 95.0
        assert call_args["threshold"] == 80.0
    
    @pytest.mark.asyncio
    async def test_multiple_threshold_alerts(self, monitoring_service):
        """Test multiple threshold alerts."""
        # Create metrics that exceed multiple thresholds
        high_metrics = SystemMetrics(
            cpu_percent=95.0,  # Above 80%
            memory_percent=90.0,  # Above 85%
            disk_percent=95.0,  # Above 90%
            network_rx=1024,
            network_tx=2048,
            timestamp=datetime.now()
        )
        
        alert_callback = AsyncMock()
        monitoring_service.add_alert_callback(alert_callback)
        
        await monitoring_service._process_metrics(high_metrics)
        
        # Should trigger 3 alerts
        assert alert_callback.call_count == 3
    
    def test_add_alert_callback(self, monitoring_service):
        """Test adding alert callback."""
        callback = AsyncMock()
        
        monitoring_service.add_alert_callback(callback)
        
        assert callback in monitoring_service._alert_callbacks
    
    def test_remove_alert_callback(self, monitoring_service):
        """Test removing alert callback."""
        callback = AsyncMock()
        
        monitoring_service.add_alert_callback(callback)
        assert callback in monitoring_service._alert_callbacks
        
        monitoring_service.remove_alert_callback(callback)
        assert callback not in monitoring_service._alert_callbacks
    
    def test_update_thresholds(self, monitoring_service):
        """Test updating alert thresholds."""
        new_thresholds = {
            "cpu_percent": 75.0,
            "memory_percent": 80.0,
            "disk_percent": 85.0
        }
        
        monitoring_service.update_thresholds(new_thresholds)
        
        assert monitoring_service.alert_thresholds == new_thresholds
    
    def test_get_system_status(self, monitoring_service):
        """Test getting system status."""
        # Mock current metrics
        current_metrics = SystemMetrics(
            cpu_percent=45.0,
            memory_percent=60.0,
            disk_percent=70.0,
            network_rx=1024,
            network_tx=2048,
            timestamp=datetime.now()
        )
        
        monitoring_service.metrics_collector.get_current_metrics = Mock(
            return_value=current_metrics
        )
        
        status = monitoring_service.get_system_status()
        
        assert status["cpu_percent"] == 45.0
        assert status["memory_percent"] == 60.0
        assert status["disk_percent"] == 70.0
        assert status["status"] == "healthy"  # All below thresholds
    
    def test_get_system_status_warning(self, monitoring_service):
        """Test getting system status with warnings."""
        # Mock metrics that exceed some thresholds
        warning_metrics = SystemMetrics(
            cpu_percent=85.0,  # Above 80% threshold
            memory_percent=60.0,
            disk_percent=70.0,
            network_rx=1024,
            network_tx=2048,
            timestamp=datetime.now()
        )
        
        monitoring_service.metrics_collector.get_current_metrics = Mock(
            return_value=warning_metrics
        )
        
        status = monitoring_service.get_system_status()
        
        assert status["status"] == "warning"
        assert "cpu_percent" in status["alerts"]


class TestDockerEventsHandler:
    """Test Docker events handling."""
    
    @pytest.fixture
    def mock_docker_client(self):
        """Create mock Docker client."""
        client = Mock()
        client.events = Mock()
        return client
    
    @pytest.fixture
    def events_handler(self, mock_docker_client):
        """Create Docker events handler."""
        return DockerEventsHandler(docker_client=mock_docker_client)
    
    def test_events_handler_init(self, events_handler):
        """Test events handler initialization."""
        assert events_handler._running is False
        assert events_handler._subscribers == []
        assert events_handler._event_history == []
    
    @pytest.mark.asyncio
    async def test_start_event_monitoring(self, events_handler):
        """Test starting Docker event monitoring."""
        # Mock event stream
        mock_events = [
            {"Type": "container", "Action": "start", "Actor": {"Attributes": {"name": "test-container"}}},
            {"Type": "container", "Action": "stop", "Actor": {"Attributes": {"name": "test-container"}}},
        ]
        
        events_handler._docker_client.events.return_value = iter(mock_events)
        
        await events_handler.start_monitoring()
        
        assert events_handler._running is True
    
    def test_add_event_subscriber(self, events_handler):
        """Test adding event subscriber."""
        callback = AsyncMock()
        
        events_handler.subscribe(callback)
        
        assert callback in events_handler._subscribers
    
    @pytest.mark.asyncio
    async def test_event_processing(self, events_handler):
        """Test Docker event processing."""
        callback = AsyncMock()
        events_handler.subscribe(callback)
        
        # Simulate Docker event
        event = {
            "Type": "container",
            "Action": "start",
            "Actor": {
                "Attributes": {
                    "name": "test-container",
                    "image": "nginx:latest"
                }
            },
            "time": int(time.time())
        }
        
        await events_handler._process_event(event)
        
        # Verify subscriber was called
        callback.assert_called_once_with(event)
        
        # Verify event was added to history
        assert len(events_handler._event_history) == 1
        assert events_handler._event_history[0] == event
    
    def test_get_event_history(self, events_handler):
        """Test getting event history."""
        # Add some mock events
        events = [
            {"Type": "container", "Action": "start", "time": int(time.time()) - 100},
            {"Type": "container", "Action": "stop", "time": int(time.time()) - 50},
            {"Type": "container", "Action": "restart", "time": int(time.time())},
        ]
        
        events_handler._event_history = events
        
        history = events_handler.get_event_history()
        
        assert len(history) == 3
        assert history == events
    
    def test_filter_events_by_type(self, events_handler):
        """Test filtering events by type."""
        events = [
            {"Type": "container", "Action": "start"},
            {"Type": "network", "Action": "create"},
            {"Type": "container", "Action": "stop"},
            {"Type": "image", "Action": "pull"},
        ]
        
        events_handler._event_history = events
        
        container_events = events_handler.get_events_by_type("container")
        
        assert len(container_events) == 2
        assert all(e["Type"] == "container" for e in container_events)


class TestLogStreamingService:
    """Test log streaming service."""
    
    @pytest.fixture
    def log_streaming(self):
        """Create log streaming service."""
        return LogStreamingService()
    
    def test_log_streaming_init(self, log_streaming):
        """Test log streaming initialization."""
        assert log_streaming._active_streams == {}
        assert log_streaming._subscribers == []
    
    @pytest.mark.asyncio
    async def test_start_log_stream(self, log_streaming):
        """Test starting log stream for container."""
        container_id = "test-container-123"
        
        # Mock Docker client and container
        with patch('docker.from_env') as mock_docker:
            mock_client = Mock()
            mock_container = Mock()
            mock_container.logs.return_value = iter([b"Log line 1\n", b"Log line 2\n"])
            mock_client.containers.get.return_value = mock_container
            mock_docker.return_value = mock_client
            
            await log_streaming.start_stream(container_id)
            
            assert container_id in log_streaming._active_streams
    
    @pytest.mark.asyncio
    async def test_stop_log_stream(self, log_streaming):
        """Test stopping log stream."""
        container_id = "test-container-123"
        
        # Add mock stream
        mock_task = Mock()
        log_streaming._active_streams[container_id] = mock_task
        
        await log_streaming.stop_stream(container_id)
        
        assert container_id not in log_streaming._active_streams
    
    def test_add_log_subscriber(self, log_streaming):
        """Test adding log subscriber."""
        callback = AsyncMock()
        
        log_streaming.subscribe(callback)
        
        assert callback in log_streaming._subscribers
    
    @pytest.mark.asyncio
    async def test_log_broadcasting(self, log_streaming):
        """Test log message broadcasting."""
        callback = AsyncMock()
        log_streaming.subscribe(callback)
        
        log_message = {
            "container_id": "test-container",
            "message": "Test log message",
            "timestamp": datetime.now().isoformat()
        }
        
        await log_streaming._broadcast_log(log_message)
        
        callback.assert_called_once_with(log_message)


class TestNotificationManager:
    """Test notification manager."""
    
    @pytest.fixture
    def notification_manager(self):
        """Create notification manager."""
        return NotificationManager()
    
    def test_notification_manager_init(self, notification_manager):
        """Test notification manager initialization."""
        assert notification_manager._channels == {}
        assert notification_manager._subscribers == []
    
    def test_add_notification_channel(self, notification_manager):
        """Test adding notification channel."""
        mock_channel = Mock()
        
        notification_manager.add_channel("email", mock_channel)
        
        assert "email" in notification_manager._channels
        assert notification_manager._channels["email"] == mock_channel
    
    @pytest.mark.asyncio
    async def test_send_notification(self, notification_manager):
        """Test sending notification."""
        mock_channel = AsyncMock()
        notification_manager.add_channel("webhook", mock_channel)
        
        notification = {
            "title": "Alert",
            "message": "CPU usage is high",
            "level": "warning",
            "timestamp": datetime.now().isoformat()
        }
        
        await notification_manager.send_notification(notification, channels=["webhook"])
        
        mock_channel.send.assert_called_once_with(notification)
    
    @pytest.mark.asyncio
    async def test_broadcast_notification(self, notification_manager):
        """Test broadcasting notification to subscribers."""
        callback = AsyncMock()
        notification_manager.subscribe(callback)
        
        notification = {
            "title": "System Update",
            "message": "Service restarted",
            "level": "info"
        }
        
        await notification_manager.broadcast(notification)
        
        callback.assert_called_once_with(notification)
    
    def test_notification_filtering(self, notification_manager):
        """Test notification filtering by level."""
        # Test would verify that notifications are filtered by level
        # e.g., only send critical alerts to SMS, but all to email
        pass


class TestIntegrationMetricsWebSocket:
    """Test integration between metrics and WebSocket."""
    
    @pytest.mark.asyncio
    async def test_metrics_websocket_broadcast(self):
        """Test metrics broadcasting via WebSocket."""
        from wakedock.api.websocket import broadcast_system_update
        
        # Mock WebSocket manager
        with patch('wakedock.api.websocket.manager') as mock_manager:
            mock_manager.broadcast = AsyncMock()
            
            # Create test metrics
            metrics = SystemMetrics(
                cpu_percent=75.0,
                memory_percent=80.0,
                disk_percent=65.0,
                network_rx=1024,
                network_tx=2048,
                timestamp=datetime.now()
            )
            
            # Broadcast metrics
            await broadcast_system_update(metrics)
            
            # Verify WebSocket broadcast was called
            mock_manager.broadcast.assert_called_once()
            
            # Verify message format
            call_args = mock_manager.broadcast.call_args[0][0]
            assert call_args["type"] == "system_update"
            assert "data" in call_args
    
    @pytest.mark.asyncio
    async def test_docker_events_websocket_broadcast(self):
        """Test Docker events broadcasting via WebSocket."""
        from wakedock.api.websocket import handle_docker_event
        
        with patch('wakedock.api.websocket.manager') as mock_manager:
            mock_manager.broadcast = AsyncMock()
            
            # Create test Docker event
            event = {
                "Type": "container",
                "Action": "start",
                "Actor": {
                    "Attributes": {
                        "name": "test-service",
                        "image": "nginx:latest"
                    }
                }
            }
            
            # Handle event
            await handle_docker_event(event)
            
            # Verify WebSocket broadcast
            mock_manager.broadcast.assert_called_once()
            
            call_args = mock_manager.broadcast.call_args[0][0]
            assert call_args["type"] == "docker_event"
            assert call_args["event"] == event