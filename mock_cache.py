#!/usr/bin/env python3
"""
WakeDock v0.6.2 Mock Cache for Testing
Simple in-memory cache for testing when Redis is not available
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from wakedock.core.cache import CacheNamespace, CacheEntry


class MockCacheManager:
    """Mock cache manager for testing without Redis"""
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'invalidations': 0
        }
    
    def _generate_key(self, namespace: CacheNamespace, identifier: str) -> str:
        """Generate cache key"""
        return f"wakedock:{namespace.value}:{identifier}"
    
    async def set(
        self,
        namespace: CacheNamespace,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
        nx: bool = False
    ) -> bool:
        """Set cache entry"""
        cache_key = self._generate_key(namespace, key)
        
        if nx and cache_key in self._cache:
            return False
        
        entry = {
            'data': value,
            'created_at': datetime.utcnow(),
            'ttl': ttl,
            'tags': tags or []
        }
        
        self._cache[cache_key] = entry
        self._stats['sets'] += 1
        return True
    
    async def get(
        self,
        namespace: CacheNamespace,
        key: str,
        default: Any = None
    ) -> Any:
        """Get cache entry"""
        cache_key = self._generate_key(namespace, key)
        
        if cache_key not in self._cache:
            self._stats['misses'] += 1
            return default
        
        entry = self._cache[cache_key]
        
        # Check TTL
        if entry['ttl']:
            age = (datetime.utcnow() - entry['created_at']).total_seconds()
            if age > entry['ttl']:
                del self._cache[cache_key]
                self._stats['misses'] += 1
                return default
        
        self._stats['hits'] += 1
        return entry['data']
    
    async def delete(self, namespace: CacheNamespace, key: str) -> bool:
        """Delete cache entry"""
        cache_key = self._generate_key(namespace, key)
        if cache_key in self._cache:
            del self._cache[cache_key]
            self._stats['deletes'] += 1
            return True
        return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = (self._stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'hit_rate': round(hit_rate, 2),
            'total_requests': total_requests,
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'sets': self._stats['sets'],
            'deletes': self._stats['deletes'],
            'invalidations': self._stats['invalidations'],
            'memory_usage': f"{len(self._cache)} items",
            'connected_clients': 1,
            'redis_available': False
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check cache health"""
        return {
            'status': 'healthy',
            'response_time_ms': 0.1,
            'connected': True
        }


# Global mock cache instance
mock_cache: Optional[MockCacheManager] = None


async def get_mock_cache() -> MockCacheManager:
    """Get or create mock cache"""
    global mock_cache
    if mock_cache is None:
        mock_cache = MockCacheManager()
    return mock_cache
