"""
Notification models for WakeDock
"""
from datetime import datetime


class Notification:
    """Notification model"""
    
    def __init__(self, id: str, message: str, level: str = "info"):
        self.id = id
        self.message = message
        self.level = level
        self.created_at = datetime.utcnow()
        self.read = False
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.read = True
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "message": self.message,
            "level": self.level,
            "created_at": self.created_at.isoformat(),
            "read": self.read
        }
