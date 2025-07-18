"""
Notification service for WakeDock
"""
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for handling notifications"""
    
    def __init__(self):
        self.notifications: List[Dict[str, Any]] = []
    
    async def send_notification(self, message: str, level: str = "info"):
        """Send a notification"""
        notification = {
            "message": message,
            "level": level,
            "timestamp": "2024-01-01T00:00:00Z"
        }
        self.notifications.append(notification)
        logger.info(f"Notification: {message}")
        return notification
