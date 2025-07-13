"""
Simple cache tests to verify the implementation works.
"""

import pytest
import asyncio
from wakedock.cache.manager import get_cache_manager
from wakedock.cache.backends import MemoryCache


class TestCacheSimple:
    """Simple cache tests."""
    
    @pytest.mark.asyncio
    async def test_cache_manager_creation(self):
        """Test that cache manager can be created."""
        manager = get_cache_manager()
        assert manager is not None
    
    @pytest.mark.asyncio
    async def test_memory_cache_basic_operations(self):
        """Test basic memory cache operations."""
        cache = MemoryCache()
        
        # Test set and get
        await cache.set("test_key", "test_value")
        result = await cache.get("test_key")
        assert result == "test_value"
        
        # Test non-existent key
        result = await cache.get("non_existent")
        assert result is None
        
        # Test delete
        await cache.delete("test_key")
        result = await cache.get("test_key")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_manager_operations(self):
        """Test cache manager operations."""
        manager = get_cache_manager()
        
        # Test set and get through manager
        await manager.set("manager_key", "manager_value")
        result = await manager.get("manager_key")
        assert result == "manager_value"
        
        # Test delete
        await manager.delete("manager_key")
        result = await manager.get("manager_key")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_with_ttl(self):
        """Test cache with TTL."""
        cache = MemoryCache()
        
        # Set with short TTL
        await cache.set("ttl_key", "ttl_value", ttl=1)
        
        # Should exist immediately
        result = await cache.get("ttl_key")
        assert result == "ttl_value"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired
        result = await cache.get("ttl_key")
        assert result is None