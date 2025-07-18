"""
Cache management for WakeDock
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class Cache:
    """Simple in-memory cache"""
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        return self._cache.get(key)
    
    def set(self, key: str, value: Any):
        """Set value in cache"""
        self._cache[key] = value
    
    def delete(self, key: str):
        """Delete value from cache"""
        self._cache.pop(key, None)
    
    def clear(self):
        """Clear all cache"""
        self._cache.clear()


cache = Cache()

# Alias for compatibility
cache_service = cache
