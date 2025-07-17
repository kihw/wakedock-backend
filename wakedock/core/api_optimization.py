"""
API optimization utilities for WakeDock
"""
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class APIOptimizer:
    """API optimization utilities"""
    
    def __init__(self):
        self.enabled = True
    
    def optimize_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize API response"""
        if not self.enabled:
            return data
        
        # Simple optimization - remove None values
        return {k: v for k, v in data.items() if v is not None}


optimizer = APIOptimizer()
