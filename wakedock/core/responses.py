"""
Response utilities for WakeDock
"""
from typing import Any, Dict, Optional


class APIResponse:
    """Standard API response format"""
    
    @staticmethod
    def success(data: Any = None, message: str = "Success") -> Dict[str, Any]:
        """Create success response"""
        return {
            "success": True,
            "message": message,
            "data": data
        }
    
    @staticmethod
    def error(message: str, code: int = 400, details: Optional[Dict] = None) -> Dict[str, Any]:
        """Create error response"""
        response = {
            "success": False,
            "message": message,
            "code": code
        }
        if details:
            response["details"] = details
        return response
