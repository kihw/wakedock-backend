"""
Tests for cache management system.

Tests cache backends, decorators, key generation, TTL handling,
and fallback mechanisms.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Any, Dict

from wakedock.cache.manager import CacheManager
from wakedock.cache.backends import MemoryBackend, RedisBackend
from wakedock.infrastructure.cache.intelligent import IntelligentCache
from wakedock.infrastructure.cache.service import CacheService


class TestCacheManager:
    """Test cache manager functionality."""
    
    @pytest.fixture
    def memory_backend(self):
        """Create memory cache backend."""
        return MemoryBackend()
    
    @pytest.fixture
    def mock_redis_backend(self):
        """Create mock Redis backend."""
        backend = Mock(spec=RedisBackend)
        backend.get = AsyncMock(return_value=None)
        backend.set = AsyncMock(return_value=True)
        backend.delete = AsyncMock(return_value=True)
        backend.clear = AsyncMock(return_value=True)
        backend.exists = AsyncMock(return_value=False)
        backend.expire = AsyncMock(return_value=True)
        backend.ttl = AsyncMock(return_value=-1)
        backend.keys = AsyncMock(return_value=[])
        backend.is_connected = AsyncMock(return_value=True)
        return backend
    
    @pytest.fixture
    def cache_manager(self, memory_backend):
        """Create cache manager with memory backend."""
        return CacheManager(backend=memory_backend)
    
    @pytest.fixture
    def cache_manager_with_redis(self, mock_redis_backend):
        """Create cache manager with Redis backend."""
        return CacheManager(backend=mock_redis_backend)
    
    def test_cache_manager_init(self, memory_backend):
        """Test cache manager initialization."""
        manager = CacheManager(backend=memory_backend)
        assert manager.backend == memory_backend
        assert manager.default_ttl == 3600  # 1 hour default
    
    def test_cache_manager_init_with_custom_ttl(self, memory_backend):
        """Test cache manager with custom TTL."""
        manager = CacheManager(backend=memory_backend, default_ttl=1800)
        assert manager.default_ttl == 1800
    
    @pytest.mark.asyncio
    async def test_get_non_existent_key(self, cache_manager):
        """Test getting non-existent key returns None."""
        result = await cache_manager.get("non_existent")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_set_and_get_string(self, cache_manager):
        """Test setting and getting string value."""
        key = "test_string"
        value = "test_value"
        
        await cache_manager.set(key, value)
        result = await cache_manager.get(key)
        
        assert result == value
    
    @pytest.mark.asyncio
    async def test_set_and_get_dict(self, cache_manager):
        """Test setting and getting dictionary value."""
        key = "test_dict"
        value = {"name": "test", "count": 42}
        
        await cache_manager.set(key, value)
        result = await cache_manager.get(key)
        
        assert result == value
    
    @pytest.mark.asyncio
    async def test_set_with_ttl(self, cache_manager):
        """Test setting value with TTL."""
        key = "test_ttl"
        value = "expires_soon"
        ttl = 1
        
        await cache_manager.set(key, value, ttl=ttl)
        
        # Value should exist immediately
        result = await cache_manager.get(key)
        assert result == value
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Value should be expired
        result = await cache_manager.get(key)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_key(self, cache_manager):
        """Test deleting cached key."""
        key = "test_delete"
        value = "to_be_deleted"
        
        await cache_manager.set(key, value)
        assert await cache_manager.get(key) == value
        
        await cache_manager.delete(key)
        assert await cache_manager.get(key) is None
    
    @pytest.mark.asyncio
    async def test_clear_cache(self, cache_manager):
        """Test clearing entire cache."""
        # Set multiple values
        await cache_manager.set("key1", "value1")
        await cache_manager.set("key2", "value2")
        await cache_manager.set("key3", "value3")
        
        # Verify values exist
        assert await cache_manager.get("key1") == "value1"
        assert await cache_manager.get("key2") == "value2"
        
        # Clear cache
        await cache_manager.clear()
        
        # Verify values are gone
        assert await cache_manager.get("key1") is None
        assert await cache_manager.get("key2") is None
        assert await cache_manager.get("key3") is None
    
    @pytest.mark.asyncio
    async def test_exists_key(self, cache_manager):
        """Test checking if key exists."""
        key = "test_exists"
        value = "exists_value"
        
        # Key doesn't exist initially
        assert not await cache_manager.exists(key)
        
        # Set key
        await cache_manager.set(key, value)
        
        # Key should exist now
        assert await cache_manager.exists(key)
        
        # Delete key
        await cache_manager.delete(key)
        
        # Key shouldn't exist anymore
        assert not await cache_manager.exists(key)
    
    @pytest.mark.asyncio
    async def test_expire_key(self, cache_manager):
        """Test setting expiration on existing key."""
        key = "test_expire"
        value = "expire_value"
        
        # Set key without TTL
        await cache_manager.set(key, value)
        assert await cache_manager.get(key) == value
        
        # Set expiration
        await cache_manager.expire(key, 1)
        
        # Value should still exist
        assert await cache_manager.get(key) == value
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Value should be expired
        assert await cache_manager.get(key) is None
    
    @pytest.mark.asyncio
    async def test_ttl_key(self, cache_manager):
        """Test getting TTL of key."""
        key = "test_ttl_check"
        value = "ttl_value"
        
        # Set key with TTL
        await cache_manager.set(key, value, ttl=3600)
        
        # Check TTL (should be around 3600, allow some variance)
        ttl = await cache_manager.ttl(key)
        assert 3590 <= ttl <= 3600
    
    @pytest.mark.asyncio
    async def test_keys_pattern(self, cache_manager):
        """Test getting keys by pattern."""
        # Set multiple keys
        await cache_manager.set("user:1", "user1_data")
        await cache_manager.set("user:2", "user2_data")
        await cache_manager.set("service:1", "service1_data")
        
        # Get user keys
        user_keys = await cache_manager.keys("user:*")
        assert "user:1" in user_keys
        assert "user:2" in user_keys
        assert "service:1" not in user_keys
    
    @pytest.mark.asyncio
    async def test_redis_backend_delegation(self, cache_manager_with_redis):
        """Test that operations are properly delegated to Redis backend."""
        manager = cache_manager_with_redis
        backend = manager.backend
        
        # Test set operation
        await manager.set("test_key", "test_value", ttl=1800)
        backend.set.assert_called_once_with("test_key", "test_value", ttl=1800)
        
        # Test get operation
        backend.get.return_value = "test_value"
        result = await manager.get("test_key")
        backend.get.assert_called_once_with("test_key")
        assert result == "test_value"
        
        # Test delete operation
        await manager.delete("test_key")
        backend.delete.assert_called_once_with("test_key")
        
        # Test exists operation
        backend.exists.return_value = True
        result = await manager.exists("test_key")
        backend.exists.assert_called_once_with("test_key")
        assert result is True


class TestCacheDecorators:
    """Test cache decorators functionality."""
    
    @pytest.fixture
    def cache_manager(self):
        """Create cache manager for decorator tests."""
        backend = MemoryBackend()
        return CacheManager(backend=backend)
    
    @pytest.mark.asyncio
    async def test_cached_decorator_basic(self, cache_manager):
        """Test basic cached decorator functionality."""
        from wakedock.cache.manager import cached
        
        call_count = 0
        
        @cached(cache_manager, ttl=3600)
        async def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # First call - should execute function
        result1 = await expensive_function(5)
        assert result1 == 10
        assert call_count == 1
        
        # Second call - should use cache
        result2 = await expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Function not called again
        
        # Different argument - should execute function
        result3 = await expensive_function(10)
        assert result3 == 20
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_cached_decorator_with_custom_key(self, cache_manager):
        """Test cached decorator with custom key function."""
        from wakedock.cache.manager import cached
        
        call_count = 0
        
        def key_func(user_id: int, action: str) -> str:
            return f"user_action:{user_id}:{action}"
        
        @cached(cache_manager, key_func=key_func, ttl=3600)
        async def user_action(user_id: int, action: str) -> str:
            nonlocal call_count
            call_count += 1
            return f"User {user_id} performed {action}"
        
        # First call
        result1 = await user_action(1, "login")
        assert result1 == "User 1 performed login"
        assert call_count == 1
        
        # Same call - should use cache
        result2 = await user_action(1, "login")
        assert result2 == "User 1 performed login"
        assert call_count == 1
        
        # Verify cache key was used correctly
        cache_key = key_func(1, "login")
        cached_value = await cache_manager.get(cache_key)
        assert cached_value == "User 1 performed login"
    
    @pytest.mark.asyncio
    async def test_cached_decorator_ttl_expiration(self, cache_manager):
        """Test cached decorator TTL expiration."""
        from wakedock.cache.manager import cached
        
        call_count = 0
        
        @cached(cache_manager, ttl=1)  # 1 second TTL
        async def short_cache_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 3
        
        # First call
        result1 = await short_cache_function(5)
        assert result1 == 15
        assert call_count == 1
        
        # Second call - should use cache
        result2 = await short_cache_function(5)
        assert result2 == 15
        assert call_count == 1
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Third call - cache expired, should execute function
        result3 = await short_cache_function(5)
        assert result3 == 15
        assert call_count == 2


class TestIntelligentCache:
    """Test intelligent cache functionality."""
    
    @pytest.fixture
    def mock_cache_service(self):
        """Create mock cache service."""
        service = Mock(spec=CacheService)
        service.get = AsyncMock(return_value=None)
        service.set = AsyncMock(return_value=True)
        service.delete = AsyncMock(return_value=True)
        service.exists = AsyncMock(return_value=False)
        service.get_stats = Mock(return_value={"hits": 0, "misses": 0})
        return service
    
    @pytest.fixture
    def intelligent_cache(self, mock_cache_service):
        """Create intelligent cache."""
        return IntelligentCache(cache_service=mock_cache_service)
    
    @pytest.mark.asyncio
    async def test_adaptive_ttl(self, intelligent_cache):
        """Test adaptive TTL based on access patterns."""
        cache = intelligent_cache
        
        # Simulate frequent access
        for i in range(10):
            await cache.get("popular_key")
        
        # Popular key should get longer TTL
        ttl = cache._calculate_adaptive_ttl("popular_key", base_ttl=3600)
        assert ttl > 3600  # Should be extended
    
    @pytest.mark.asyncio
    async def test_smart_prefetching(self, intelligent_cache):
        """Test smart prefetching functionality."""
        cache = intelligent_cache
        
        # Mock prefetch function
        prefetch_func = AsyncMock(return_value="prefetched_value")
        
        # Register prefetch pattern
        cache.register_prefetch_pattern("user:*", prefetch_func)
        
        # Access user key - should trigger prefetching
        await cache.get("user:123")
        
        # Verify prefetch was called (implementation dependent)
        # This would depend on the actual intelligent cache implementation
    
    @pytest.mark.asyncio
    async def test_cache_warming(self, intelligent_cache):
        """Test cache warming functionality."""
        cache = intelligent_cache
        
        # Mock warm function
        warm_func = AsyncMock(return_value={"key1": "value1", "key2": "value2"})
        
        # Warm cache
        await cache.warm_cache(warm_func)
        
        # Verify warm function was called
        warm_func.assert_called_once()
    
    def test_cache_analytics(self, intelligent_cache):
        """Test cache analytics and metrics."""
        cache = intelligent_cache
        
        # Get analytics (this would track hits/misses/patterns)
        analytics = cache.get_analytics()
        
        # Should return analytics data structure
        assert isinstance(analytics, dict)
        assert "hit_rate" in analytics
        assert "popular_keys" in analytics
        assert "access_patterns" in analytics


class TestCacheBackends:
    """Test cache backends (Memory and Redis)."""
    
    def test_memory_backend_init(self):
        """Test memory backend initialization."""
        backend = MemoryBackend()
        assert backend._data == {}
        assert backend._expiry == {}
    
    @pytest.mark.asyncio
    async def test_memory_backend_basic_operations(self):
        """Test memory backend basic operations."""
        backend = MemoryBackend()
        
        # Test set and get
        await backend.set("key1", "value1")
        result = await backend.get("key1")
        assert result == "value1"
        
        # Test non-existent key
        result = await backend.get("non_existent")
        assert result is None
        
        # Test delete
        await backend.delete("key1")
        result = await backend.get("key1")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_memory_backend_ttl(self):
        """Test memory backend TTL functionality."""
        backend = MemoryBackend()
        
        # Set with TTL
        await backend.set("ttl_key", "ttl_value", ttl=1)
        
        # Should exist immediately
        assert await backend.exists("ttl_key")
        result = await backend.get("ttl_key")
        assert result == "ttl_value"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired
        assert not await backend.exists("ttl_key")
        result = await backend.get("ttl_key")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_memory_backend_keys_pattern(self):
        """Test memory backend keys pattern matching."""
        backend = MemoryBackend()
        
        # Set multiple keys
        await backend.set("user:1", "data1")
        await backend.set("user:2", "data2")
        await backend.set("service:1", "data3")
        
        # Get keys with pattern
        user_keys = await backend.keys("user:*")
        assert "user:1" in user_keys
        assert "user:2" in user_keys
        assert "service:1" not in user_keys
    
    @pytest.mark.asyncio
    async def test_redis_backend_connection_handling(self):
        """Test Redis backend connection handling."""
        # Mock Redis connection
        with patch('aioredis.from_url') as mock_redis:
            mock_connection = AsyncMock()
            mock_redis.return_value = mock_connection
            
            backend = RedisBackend(url="redis://localhost:6379")
            
            # Test connection
            await backend._get_connection()
            mock_redis.assert_called_once_with("redis://localhost:6379")
    
    @pytest.mark.asyncio
    async def test_redis_backend_error_handling(self):
        """Test Redis backend error handling."""
        # Mock Redis connection that fails
        with patch('aioredis.from_url') as mock_redis:
            mock_redis.side_effect = Exception("Connection failed")
            
            backend = RedisBackend(url="redis://localhost:6379")
            
            # Should handle connection errors gracefully
            with pytest.raises(Exception):
                await backend._get_connection()


class TestCacheService:
    """Test cache service integration."""
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock cache settings."""
        settings = Mock()
        settings.cache = Mock()
        settings.cache.enabled = True
        settings.cache.backend = "memory"
        settings.cache.default_ttl = 3600
        settings.cache.redis = Mock()
        settings.cache.redis.url = "redis://localhost:6379"
        return settings
    
    def test_cache_service_init(self, mock_settings):
        """Test cache service initialization."""
        service = CacheService(mock_settings)
        assert service.settings == mock_settings
        assert not service._initialized
    
    @pytest.mark.asyncio
    async def test_cache_service_initialization(self, mock_settings):
        """Test cache service initialization process."""
        service = CacheService(mock_settings)
        
        # Initialize service
        await service.initialize()
        
        assert service._initialized
        assert service.cache_manager is not None
    
    @pytest.mark.asyncio
    async def test_cache_service_fallback_to_memory(self):
        """Test cache service fallback to memory when Redis fails."""
        settings = Mock()
        settings.cache = Mock()
        settings.cache.enabled = True
        settings.cache.backend = "redis"
        settings.cache.redis = Mock()
        settings.cache.redis.url = "redis://invalid:6379"
        
        with patch('aioredis.from_url', side_effect=Exception("Connection failed")):
            service = CacheService(settings)
            await service.initialize()
            
            # Should fall back to memory backend
            assert isinstance(service.cache_manager.backend, MemoryBackend)
    
    def test_cache_service_disabled(self):
        """Test cache service when caching is disabled."""
        settings = Mock()
        settings.cache = Mock()
        settings.cache.enabled = False
        
        service = CacheService(settings)
        assert service.cache_manager is None
    
    @pytest.mark.asyncio
    async def test_cache_service_stats(self, mock_settings):
        """Test cache service statistics."""
        service = CacheService(mock_settings)
        await service.initialize()
        
        # Get stats
        stats = service.get_stats()
        
        assert isinstance(stats, dict)
        assert "backend" in stats
        assert "enabled" in stats
        assert "stats" in stats