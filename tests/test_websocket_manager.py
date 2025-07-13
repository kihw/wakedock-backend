"""
Tests for WebSocket management functionality.

Tests WebSocket connection management, message broadcasting,
authentication, error handling, and real-time communication.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
from typing import Dict, List, Any

from wakedock.api.websocket.manager import WebSocketManager, ConnectionInfo
from wakedock.api.websocket.auth import WebSocketAuthenticator
from wakedock.api.websocket.services import ServiceWebSocketHandler
from wakedock.api.websocket.system import SystemWebSocketHandler
from wakedock.api.websocket.notifications import NotificationWebSocketHandler
from wakedock.api.websocket.types import WebSocketMessage, MessageType


class TestWebSocketMessage:
    """Test WebSocket message data structures."""
    
    def test_websocket_message_init(self):
        """Test WebSocketMessage initialization."""
        message = WebSocketMessage(
            type=MessageType.SYSTEM_UPDATE,
            data={"cpu": 50.0},
            timestamp=datetime.now()
        )
        
        assert message.type == MessageType.SYSTEM_UPDATE
        assert message.data == {"cpu": 50.0}
        assert isinstance(message.timestamp, datetime)
    
    def test_websocket_message_to_dict(self):
        """Test WebSocketMessage conversion to dictionary."""
        timestamp = datetime.now()
        message = WebSocketMessage(
            type=MessageType.SERVICE_UPDATE,
            data={"service": "web-app", "status": "running"},
            timestamp=timestamp
        )
        
        data = message.to_dict()
        
        assert data["type"] == "service_update"
        assert data["data"] == {"service": "web-app", "status": "running"}
        assert data["timestamp"] == timestamp.isoformat()
    
    def test_websocket_message_from_dict(self):
        """Test WebSocketMessage creation from dictionary."""
        timestamp = datetime.now()
        data = {
            "type": "notification",
            "data": {"title": "Alert", "message": "High CPU usage"},
            "timestamp": timestamp.isoformat()
        }
        
        message = WebSocketMessage.from_dict(data)
        
        assert message.type == MessageType.NOTIFICATION
        assert message.data == {"title": "Alert", "message": "High CPU usage"}
        assert abs((message.timestamp - timestamp).total_seconds()) < 1
    
    def test_websocket_message_json_serialization(self):
        """Test WebSocketMessage JSON serialization."""
        message = WebSocketMessage(
            type=MessageType.DOCKER_EVENT,
            data={"container": "test", "action": "start"},
            timestamp=datetime.now()
        )
        
        json_str = message.to_json()
        
        # Should be valid JSON
        parsed = json.loads(json_str)
        assert parsed["type"] == "docker_event"
        assert parsed["data"]["container"] == "test"


class TestConnectionInfo:
    """Test WebSocket connection information."""
    
    def test_connection_info_init(self):
        """Test ConnectionInfo initialization."""
        mock_websocket = Mock(spec=WebSocket)
        
        conn_info = ConnectionInfo(
            websocket=mock_websocket,
            user_id="user123",
            client_ip="192.168.1.100",
            connection_time=datetime.now()
        )
        
        assert conn_info.websocket == mock_websocket
        assert conn_info.user_id == "user123"
        assert conn_info.client_ip == "192.168.1.100"
        assert isinstance(conn_info.connection_time, datetime)
    
    def test_connection_info_subscription_management(self):
        """Test subscription management in ConnectionInfo."""
        mock_websocket = Mock(spec=WebSocket)
        conn_info = ConnectionInfo(
            websocket=mock_websocket,
            user_id="user123"
        )
        
        # Add subscriptions
        conn_info.add_subscription("system_metrics")
        conn_info.add_subscription("service_updates")
        
        assert "system_metrics" in conn_info.subscriptions
        assert "service_updates" in conn_info.subscriptions
        
        # Remove subscription
        conn_info.remove_subscription("system_metrics")
        assert "system_metrics" not in conn_info.subscriptions
        assert "service_updates" in conn_info.subscriptions
    
    def test_connection_info_last_activity_update(self):
        """Test last activity time update."""
        mock_websocket = Mock(spec=WebSocket)
        conn_info = ConnectionInfo(
            websocket=mock_websocket,
            user_id="user123"
        )
        
        initial_time = conn_info.last_activity
        
        # Update activity
        conn_info.update_activity()
        
        assert conn_info.last_activity > initial_time


class TestWebSocketManager:
    """Test WebSocket manager functionality."""
    
    @pytest.fixture
    def websocket_manager(self):
        """Create WebSocket manager instance."""
        return WebSocketManager()
    
    @pytest.fixture
    def mock_websocket(self):
        """Create mock WebSocket connection."""
        websocket = Mock(spec=WebSocket)
        websocket.send_text = AsyncMock()
        websocket.send_json = AsyncMock()
        websocket.accept = AsyncMock()
        websocket.close = AsyncMock()
        websocket.client = Mock()
        websocket.client.host = "192.168.1.100"
        return websocket
    
    def test_websocket_manager_init(self, websocket_manager):
        """Test WebSocket manager initialization."""
        assert websocket_manager._connections == {}
        assert websocket_manager._connection_counter == 0
        assert websocket_manager._message_handlers == {}
    
    @pytest.mark.asyncio
    async def test_add_connection(self, websocket_manager, mock_websocket):
        """Test adding WebSocket connection."""
        connection_id = await websocket_manager.add_connection(
            websocket=mock_websocket,
            user_id="user123"
        )
        
        assert connection_id in websocket_manager._connections
        assert websocket_manager._connections[connection_id].user_id == "user123"
        assert websocket_manager._connections[connection_id].websocket == mock_websocket
        
        # WebSocket should be accepted
        mock_websocket.accept.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_remove_connection(self, websocket_manager, mock_websocket):
        """Test removing WebSocket connection."""
        connection_id = await websocket_manager.add_connection(
            websocket=mock_websocket,
            user_id="user123"
        )
        
        assert connection_id in websocket_manager._connections
        
        await websocket_manager.remove_connection(connection_id)
        
        assert connection_id not in websocket_manager._connections
    
    @pytest.mark.asyncio
    async def test_send_message_to_connection(self, websocket_manager, mock_websocket):
        """Test sending message to specific connection."""
        connection_id = await websocket_manager.add_connection(
            websocket=mock_websocket,
            user_id="user123"
        )
        
        message = WebSocketMessage(
            type=MessageType.SYSTEM_UPDATE,
            data={"cpu": 75.0}
        )
        
        await websocket_manager.send_to_connection(connection_id, message)
        
        # Verify message was sent as JSON
        mock_websocket.send_text.assert_called_once()
        sent_data = mock_websocket.send_text.call_args[0][0]
        parsed_data = json.loads(sent_data)
        assert parsed_data["type"] == "system_update"
        assert parsed_data["data"]["cpu"] == 75.0
    
    @pytest.mark.asyncio
    async def test_send_message_to_invalid_connection(self, websocket_manager):
        """Test sending message to invalid connection ID."""
        message = WebSocketMessage(
            type=MessageType.SYSTEM_UPDATE,
            data={"cpu": 75.0}
        )
        
        # Should not raise exception for invalid connection
        await websocket_manager.send_to_connection("invalid_id", message)
    
    @pytest.mark.asyncio
    async def test_broadcast_message(self, websocket_manager):
        """Test broadcasting message to all connections."""
        # Add multiple connections
        mock_ws1 = Mock(spec=WebSocket)
        mock_ws1.send_text = AsyncMock()
        mock_ws1.accept = AsyncMock()
        mock_ws1.client = Mock()
        mock_ws1.client.host = "192.168.1.100"
        
        mock_ws2 = Mock(spec=WebSocket)
        mock_ws2.send_text = AsyncMock()
        mock_ws2.accept = AsyncMock()
        mock_ws2.client = Mock()
        mock_ws2.client.host = "192.168.1.101"
        
        conn_id1 = await websocket_manager.add_connection(mock_ws1, "user1")
        conn_id2 = await websocket_manager.add_connection(mock_ws2, "user2")
        
        message = WebSocketMessage(
            type=MessageType.NOTIFICATION,
            data={"title": "Broadcast", "message": "Test notification"}
        )
        
        await websocket_manager.broadcast(message)
        
        # Both connections should receive the message
        mock_ws1.send_text.assert_called_once()
        mock_ws2.send_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_broadcast_to_user(self, websocket_manager):
        """Test broadcasting message to specific user."""
        # Add connections for same user
        mock_ws1 = Mock(spec=WebSocket)
        mock_ws1.send_text = AsyncMock()
        mock_ws1.accept = AsyncMock()
        mock_ws1.client = Mock()
        mock_ws1.client.host = "192.168.1.100"
        
        mock_ws2 = Mock(spec=WebSocket)
        mock_ws2.send_text = AsyncMock()
        mock_ws2.accept = AsyncMock()
        mock_ws2.client = Mock()
        mock_ws2.client.host = "192.168.1.101"
        
        mock_ws3 = Mock(spec=WebSocket)
        mock_ws3.send_text = AsyncMock()
        mock_ws3.accept = AsyncMock()
        mock_ws3.client = Mock()
        mock_ws3.client.host = "192.168.1.102"
        
        await websocket_manager.add_connection(mock_ws1, "user1")
        await websocket_manager.add_connection(mock_ws2, "user1")  # Same user
        await websocket_manager.add_connection(mock_ws3, "user2")  # Different user
        
        message = WebSocketMessage(
            type=MessageType.NOTIFICATION,
            data={"title": "User Message", "message": "For user1 only"}
        )
        
        await websocket_manager.broadcast_to_user("user1", message)
        
        # Only user1's connections should receive the message
        mock_ws1.send_text.assert_called_once()
        mock_ws2.send_text.assert_called_once()
        mock_ws3.send_text.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_subscription_management(self, websocket_manager, mock_websocket):
        """Test subscription management."""
        connection_id = await websocket_manager.add_connection(
            websocket=mock_websocket,
            user_id="user123"
        )
        
        # Add subscriptions
        await websocket_manager.subscribe_to_topic(connection_id, "system_metrics")
        await websocket_manager.subscribe_to_topic(connection_id, "docker_events")
        
        connection = websocket_manager._connections[connection_id]
        assert "system_metrics" in connection.subscriptions
        assert "docker_events" in connection.subscriptions
        
        # Remove subscription
        await websocket_manager.unsubscribe_from_topic(connection_id, "system_metrics")
        assert "system_metrics" not in connection.subscriptions
        assert "docker_events" in connection.subscriptions
    
    @pytest.mark.asyncio
    async def test_broadcast_to_topic_subscribers(self, websocket_manager):
        """Test broadcasting to topic subscribers only."""
        # Add connections with different subscriptions
        mock_ws1 = Mock(spec=WebSocket)
        mock_ws1.send_text = AsyncMock()
        mock_ws1.accept = AsyncMock()
        mock_ws1.client = Mock()
        mock_ws1.client.host = "192.168.1.100"
        
        mock_ws2 = Mock(spec=WebSocket)
        mock_ws2.send_text = AsyncMock()
        mock_ws2.accept = AsyncMock()
        mock_ws2.client = Mock()
        mock_ws2.client.host = "192.168.1.101"
        
        conn_id1 = await websocket_manager.add_connection(mock_ws1, "user1")
        conn_id2 = await websocket_manager.add_connection(mock_ws2, "user2")
        
        # Subscribe only conn1 to system_metrics
        await websocket_manager.subscribe_to_topic(conn_id1, "system_metrics")
        await websocket_manager.subscribe_to_topic(conn_id2, "docker_events")
        
        message = WebSocketMessage(
            type=MessageType.SYSTEM_UPDATE,
            data={"cpu": 80.0}
        )
        
        await websocket_manager.broadcast_to_topic("system_metrics", message)
        
        # Only subscribed connection should receive the message
        mock_ws1.send_text.assert_called_once()
        mock_ws2.send_text.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_connection_cleanup_on_error(self, websocket_manager, mock_websocket):
        """Test connection cleanup when WebSocket error occurs."""
        mock_websocket.send_text.side_effect = WebSocketDisconnect()
        
        connection_id = await websocket_manager.add_connection(
            websocket=mock_websocket,
            user_id="user123"
        )
        
        message = WebSocketMessage(
            type=MessageType.SYSTEM_UPDATE,
            data={"test": "data"}
        )
        
        await websocket_manager.send_to_connection(connection_id, message)
        
        # Connection should be automatically removed after error
        assert connection_id not in websocket_manager._connections
    
    def test_get_connection_stats(self, websocket_manager):
        """Test getting connection statistics."""
        stats = websocket_manager.get_connection_stats()
        
        assert "total_connections" in stats
        assert "connections_by_user" in stats
        assert "subscriptions_by_topic" in stats
        assert stats["total_connections"] == 0
    
    @pytest.mark.asyncio
    async def test_get_connection_stats_with_connections(self, websocket_manager):
        """Test connection statistics with active connections."""
        mock_ws1 = Mock(spec=WebSocket)
        mock_ws1.accept = AsyncMock()
        mock_ws1.client = Mock()
        mock_ws1.client.host = "192.168.1.100"
        
        mock_ws2 = Mock(spec=WebSocket)
        mock_ws2.accept = AsyncMock()
        mock_ws2.client = Mock()
        mock_ws2.client.host = "192.168.1.101"
        
        conn_id1 = await websocket_manager.add_connection(mock_ws1, "user1")
        conn_id2 = await websocket_manager.add_connection(mock_ws2, "user1")
        
        await websocket_manager.subscribe_to_topic(conn_id1, "system_metrics")
        await websocket_manager.subscribe_to_topic(conn_id2, "docker_events")
        
        stats = websocket_manager.get_connection_stats()
        
        assert stats["total_connections"] == 2
        assert stats["connections_by_user"]["user1"] == 2
        assert stats["subscriptions_by_topic"]["system_metrics"] == 1
        assert stats["subscriptions_by_topic"]["docker_events"] == 1


class TestWebSocketAuthenticator:
    """Test WebSocket authentication."""
    
    @pytest.fixture
    def authenticator(self):
        """Create WebSocket authenticator."""
        return WebSocketAuthenticator()
    
    @pytest.fixture
    def mock_websocket_with_headers(self):
        """Create mock WebSocket with headers."""
        websocket = Mock(spec=WebSocket)
        websocket.headers = {"authorization": "Bearer valid_token_123"}
        websocket.query_params = {}
        return websocket
    
    @pytest.mark.asyncio
    async def test_authenticate_with_valid_token(self, authenticator, mock_websocket_with_headers):
        """Test authentication with valid token."""
        with patch('wakedock.api.auth.jwt.verify_token') as mock_verify:
            mock_verify.return_value = Mock(user_id="user123")
            
            user = await authenticator.authenticate(mock_websocket_with_headers)
            
            assert user is not None
            assert user.user_id == "user123"
    
    @pytest.mark.asyncio
    async def test_authenticate_with_invalid_token(self, authenticator, mock_websocket_with_headers):
        """Test authentication with invalid token."""
        with patch('wakedock.api.auth.jwt.verify_token') as mock_verify:
            mock_verify.return_value = None
            
            user = await authenticator.authenticate(mock_websocket_with_headers)
            
            assert user is None
    
    @pytest.mark.asyncio
    async def test_authenticate_without_token(self, authenticator):
        """Test authentication without token."""
        websocket = Mock(spec=WebSocket)
        websocket.headers = {}
        websocket.query_params = {}
        
        user = await authenticator.authenticate(websocket)
        
        assert user is None
    
    @pytest.mark.asyncio
    async def test_authenticate_with_query_param_token(self, authenticator):
        """Test authentication with token in query parameters."""
        websocket = Mock(spec=WebSocket)
        websocket.headers = {}
        websocket.query_params = {"token": "query_token_123"}
        
        with patch('wakedock.api.auth.jwt.verify_token') as mock_verify:
            mock_verify.return_value = Mock(user_id="user456")
            
            user = await authenticator.authenticate(websocket)
            
            assert user is not None
            assert user.user_id == "user456"


class TestServiceWebSocketHandler:
    """Test service-related WebSocket handling."""
    
    @pytest.fixture
    def service_handler(self):
        """Create service WebSocket handler."""
        mock_manager = Mock(spec=WebSocketManager)
        mock_manager.broadcast_to_topic = AsyncMock()
        return ServiceWebSocketHandler(websocket_manager=mock_manager)
    
    @pytest.mark.asyncio
    async def test_handle_service_status_update(self, service_handler):
        """Test handling service status update."""
        service_data = {
            "name": "web-app",
            "status": "running",
            "health": "healthy",
            "updated_at": datetime.now().isoformat()
        }
        
        await service_handler.handle_service_update(service_data)
        
        # Verify broadcast was called
        service_handler.websocket_manager.broadcast_to_topic.assert_called_once()
        
        call_args = service_handler.websocket_manager.broadcast_to_topic.call_args
        topic, message = call_args[0]
        
        assert topic == "service_updates"
        assert message.type == MessageType.SERVICE_UPDATE
        assert message.data == service_data
    
    @pytest.mark.asyncio
    async def test_handle_service_logs(self, service_handler):
        """Test handling service log messages."""
        log_data = {
            "service_name": "web-app",
            "container_id": "abc123",
            "message": "Application started successfully",
            "timestamp": datetime.now().isoformat(),
            "level": "info"
        }
        
        await service_handler.handle_service_logs(log_data)
        
        service_handler.websocket_manager.broadcast_to_topic.assert_called_once()
        
        call_args = service_handler.websocket_manager.broadcast_to_topic.call_args
        topic, message = call_args[0]
        
        assert topic == "service_logs"
        assert message.type == MessageType.LOG_ENTRY
        assert message.data == log_data


class TestSystemWebSocketHandler:
    """Test system-related WebSocket handling."""
    
    @pytest.fixture
    def system_handler(self):
        """Create system WebSocket handler."""
        mock_manager = Mock(spec=WebSocketManager)
        mock_manager.broadcast_to_topic = AsyncMock()
        return SystemWebSocketHandler(websocket_manager=mock_manager)
    
    @pytest.mark.asyncio
    async def test_handle_system_metrics_update(self, system_handler):
        """Test handling system metrics update."""
        metrics_data = {
            "cpu_percent": 75.0,
            "memory_percent": 82.0,
            "disk_percent": 68.0,
            "network_rx": 1024000,
            "network_tx": 2048000,
            "timestamp": datetime.now().isoformat()
        }
        
        await system_handler.handle_metrics_update(metrics_data)
        
        system_handler.websocket_manager.broadcast_to_topic.assert_called_once()
        
        call_args = system_handler.websocket_manager.broadcast_to_topic.call_args
        topic, message = call_args[0]
        
        assert topic == "system_metrics"
        assert message.type == MessageType.SYSTEM_UPDATE
        assert message.data == metrics_data
    
    @pytest.mark.asyncio
    async def test_handle_docker_event(self, system_handler):
        """Test handling Docker event."""
        docker_event = {
            "Type": "container",
            "Action": "start",
            "Actor": {
                "Attributes": {
                    "name": "web-app-container",
                    "image": "nginx:latest"
                }
            },
            "time": int(datetime.now().timestamp())
        }
        
        await system_handler.handle_docker_event(docker_event)
        
        system_handler.websocket_manager.broadcast_to_topic.assert_called_once()
        
        call_args = system_handler.websocket_manager.broadcast_to_topic.call_args
        topic, message = call_args[0]
        
        assert topic == "docker_events"
        assert message.type == MessageType.DOCKER_EVENT
        assert message.data == docker_event


class TestNotificationWebSocketHandler:
    """Test notification WebSocket handling."""
    
    @pytest.fixture
    def notification_handler(self):
        """Create notification WebSocket handler."""
        mock_manager = Mock(spec=WebSocketManager)
        mock_manager.broadcast = AsyncMock()
        mock_manager.broadcast_to_user = AsyncMock()
        return NotificationWebSocketHandler(websocket_manager=mock_manager)
    
    @pytest.mark.asyncio
    async def test_handle_global_notification(self, notification_handler):
        """Test handling global notification."""
        notification = {
            "title": "System Maintenance",
            "message": "Scheduled maintenance in 10 minutes",
            "level": "warning",
            "timestamp": datetime.now().isoformat()
        }
        
        await notification_handler.handle_notification(notification, target="global")
        
        notification_handler.websocket_manager.broadcast.assert_called_once()
        
        call_args = notification_handler.websocket_manager.broadcast.call_args
        message = call_args[0][0]
        
        assert message.type == MessageType.NOTIFICATION
        assert message.data == notification
    
    @pytest.mark.asyncio
    async def test_handle_user_specific_notification(self, notification_handler):
        """Test handling user-specific notification."""
        notification = {
            "title": "Service Deployed",
            "message": "Your service 'web-app' has been deployed successfully",
            "level": "success",
            "timestamp": datetime.now().isoformat()
        }
        
        await notification_handler.handle_notification(notification, target="user123")
        
        notification_handler.websocket_manager.broadcast_to_user.assert_called_once()
        
        call_args = notification_handler.websocket_manager.broadcast_to_user.call_args
        user_id, message = call_args[0]
        
        assert user_id == "user123"
        assert message.type == MessageType.NOTIFICATION
        assert message.data == notification


class TestWebSocketIntegration:
    """Test WebSocket integration with other systems."""
    
    @pytest.mark.asyncio
    async def test_websocket_ping_pong(self):
        """Test WebSocket ping/pong mechanism."""
        from wakedock.api.websocket import websocket_ping_task
        
        # Mock WebSocket manager
        with patch('wakedock.api.websocket.manager') as mock_manager:
            mock_manager._connections = {
                "conn1": Mock(websocket=Mock(), last_activity=datetime.now()),
                "conn2": Mock(websocket=Mock(), last_activity=datetime.now() - timedelta(minutes=10))
            }
            mock_manager.remove_connection = AsyncMock()
            
            # Run ping task once
            with patch('asyncio.sleep', side_effect=asyncio.CancelledError):
                try:
                    await websocket_ping_task()
                except asyncio.CancelledError:
                    pass
            
            # Verify inactive connections are cleaned up
            # (Implementation would depend on actual ping logic)
    
    @pytest.mark.asyncio
    async def test_websocket_error_handling(self):
        """Test WebSocket error handling."""
        manager = WebSocketManager()
        
        mock_ws = Mock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock(side_effect=Exception("Connection error"))
        mock_ws.client = Mock()
        mock_ws.client.host = "192.168.1.100"
        
        connection_id = await manager.add_connection(mock_ws, "user123")
        
        message = WebSocketMessage(
            type=MessageType.SYSTEM_UPDATE,
            data={"test": "data"}
        )
        
        # Should handle error gracefully
        await manager.send_to_connection(connection_id, message)
        
        # Connection should be removed after error
        assert connection_id not in manager._connections
    
    @pytest.mark.asyncio
    async def test_websocket_message_rate_limiting(self):
        """Test WebSocket message rate limiting."""
        # Test would verify that excessive message sending is rate limited
        pass
    
    @pytest.mark.asyncio
    async def test_websocket_connection_limits(self):
        """Test WebSocket connection limits per user."""
        # Test would verify that users can't open unlimited connections
        pass