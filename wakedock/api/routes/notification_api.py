"""
Notification API routes for WakeDock
"""
from typing import Any, Dict, List

from fastapi import APIRouter

router = APIRouter()


@router.get("/notifications", response_model=List[Dict[str, Any]])
async def get_notifications():
    """Get all notifications"""
    return []


@router.post("/notifications")
async def create_notification(message: str, level: str = "info"):
    """Create a new notification"""
    return {
        "id": "1",
        "message": message,
        "level": level,
        "created_at": "2024-01-01T00:00:00Z"
    }


@router.put("/notifications/{notification_id}/read")
async def mark_notification_as_read(notification_id: str):
    """Mark notification as read"""
    return {"success": True}
