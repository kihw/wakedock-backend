"""
Plugin registry for WakeDock
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import aiofiles
import aiohttp

from .base_plugin import PluginInfo, PluginType

logger = logging.getLogger(__name__)


class PluginRegistry:
    """
    Registry for managing plugin information and marketplace
    """
    
    def __init__(self, registry_url: str = "https://registry.wakedock.com"):
        self.registry_url = registry_url
        self.local_cache: Dict[str, PluginInfo] = {}
        self.remote_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_file = Path("plugin_cache.json")
        self.last_sync = None
        self.sync_interval = 3600  # 1 hour
    
    async def initialize(self) -> None:
        """Initialize the plugin registry"""
        try:
            logger.info("Initializing plugin registry")
            
            # Load local cache
            await self.load_local_cache()
            
            # Sync with remote registry
            await self.sync_with_remote()
            
            logger.info("Plugin registry initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize plugin registry: {e}")
    
    async def load_local_cache(self) -> None:
        """Load local plugin cache"""
        try:
            if self.cache_file.exists():
                async with aiofiles.open(self.cache_file, 'r') as f:
                    content = await f.read()
                    cache_data = json.loads(content)
                    
                    for plugin_name, plugin_data in cache_data.get('plugins', {}).items():
                        plugin_info = PluginInfo(
                            name=plugin_data['name'],
                            version=plugin_data['version'],
                            description=plugin_data['description'],
                            author=plugin_data['author'],
                            plugin_type=PluginType(plugin_data['plugin_type']),
                            dependencies=plugin_data.get('dependencies', []),
                            permissions=plugin_data.get('permissions', []),
                            config_schema=plugin_data.get('config_schema'),
                            api_version=plugin_data.get('api_version', '1.0.0'),
                            tags=plugin_data.get('tags', []),
                            homepage=plugin_data.get('homepage'),
                            repository=plugin_data.get('repository'),
                            license=plugin_data.get('license'),
                            min_wakedock_version=plugin_data.get('min_wakedock_version'),
                            max_wakedock_version=plugin_data.get('max_wakedock_version'),
                        )
                        self.local_cache[plugin_name] = plugin_info
                    
                    self.last_sync = datetime.fromisoformat(cache_data.get('last_sync', '1970-01-01T00:00:00'))
                    
            logger.info(f"Loaded {len(self.local_cache)} plugins from local cache")
            
        except Exception as e:
            logger.error(f"Failed to load local cache: {e}")
    
    async def save_local_cache(self) -> None:
        """Save local plugin cache"""
        try:
            cache_data = {
                'last_sync': self.last_sync.isoformat() if self.last_sync else None,
                'plugins': {}
            }
            
            for plugin_name, plugin_info in self.local_cache.items():
                cache_data['plugins'][plugin_name] = {
                    'name': plugin_info.name,
                    'version': plugin_info.version,
                    'description': plugin_info.description,
                    'author': plugin_info.author,
                    'plugin_type': plugin_info.plugin_type.value,
                    'dependencies': plugin_info.dependencies,
                    'permissions': plugin_info.permissions,
                    'config_schema': plugin_info.config_schema,
                    'api_version': plugin_info.api_version,
                    'tags': plugin_info.tags,
                    'homepage': plugin_info.homepage,
                    'repository': plugin_info.repository,
                    'license': plugin_info.license,
                    'min_wakedock_version': plugin_info.min_wakedock_version,
                    'max_wakedock_version': plugin_info.max_wakedock_version,
                }
            
            async with aiofiles.open(self.cache_file, 'w') as f:
                await f.write(json.dumps(cache_data, indent=2))
            
            logger.info("Saved local plugin cache")
            
        except Exception as e:
            logger.error(f"Failed to save local cache: {e}")
    
    async def sync_with_remote(self) -> None:
        """Sync with remote plugin registry"""
        try:
            # Check if sync is needed
            if self.last_sync and (datetime.now() - self.last_sync).seconds < self.sync_interval:
                logger.info("Skipping remote sync - cache is fresh")
                return
            
            logger.info("Syncing with remote plugin registry")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.registry_url}/api/v1/plugins") as response:
                    if response.status == 200:
                        plugins_data = await response.json()
                        
                        # Update remote cache
                        self.remote_cache = {
                            plugin['name']: plugin
                            for plugin in plugins_data.get('plugins', [])
                        }
                        
                        # Update local cache with remote data
                        for plugin_name, plugin_data in self.remote_cache.items():
                            if plugin_name not in self.local_cache:
                                plugin_info = PluginInfo(
                                    name=plugin_data['name'],
                                    version=plugin_data['version'],
                                    description=plugin_data['description'],
                                    author=plugin_data['author'],
                                    plugin_type=PluginType(plugin_data['plugin_type']),
                                    dependencies=plugin_data.get('dependencies', []),
                                    permissions=plugin_data.get('permissions', []),
                                    config_schema=plugin_data.get('config_schema'),
                                    api_version=plugin_data.get('api_version', '1.0.0'),
                                    tags=plugin_data.get('tags', []),
                                    homepage=plugin_data.get('homepage'),
                                    repository=plugin_data.get('repository'),
                                    license=plugin_data.get('license'),
                                    min_wakedock_version=plugin_data.get('min_wakedock_version'),
                                    max_wakedock_version=plugin_data.get('max_wakedock_version'),
                                )
                                self.local_cache[plugin_name] = plugin_info
                        
                        self.last_sync = datetime.now()
                        await self.save_local_cache()
                        
                        logger.info(f"Synced {len(self.remote_cache)} plugins from remote registry")
                    else:
                        logger.error(f"Failed to sync with remote registry: {response.status}")
                        
        except Exception as e:
            logger.error(f"Failed to sync with remote registry: {e}")
    
    async def register_plugin(self, plugin_info: PluginInfo) -> None:
        """Register a plugin locally"""
        try:
            self.local_cache[plugin_info.name] = plugin_info
            await self.save_local_cache()
            
            logger.info(f"Registered plugin locally: {plugin_info.name}")
            
        except Exception as e:
            logger.error(f"Failed to register plugin: {e}")
    
    async def unregister_plugin(self, plugin_name: str) -> None:
        """Unregister a plugin locally"""
        try:
            if plugin_name in self.local_cache:
                del self.local_cache[plugin_name]
                await self.save_local_cache()
                
                logger.info(f"Unregistered plugin locally: {plugin_name}")
            
        except Exception as e:
            logger.error(f"Failed to unregister plugin: {e}")
    
    async def get_plugin_info(self, plugin_name: str) -> Optional[PluginInfo]:
        """Get plugin information"""
        return self.local_cache.get(plugin_name)
    
    async def search_plugins(self, query: str = "", plugin_type: Optional[PluginType] = None,
                           tags: Optional[List[str]] = None, author: Optional[str] = None) -> List[PluginInfo]:
        """Search for plugins"""
        try:
            results = []
            
            for plugin_info in self.local_cache.values():
                # Filter by query
                if query and query.lower() not in plugin_info.name.lower() and \
                   query.lower() not in plugin_info.description.lower():
                    continue
                
                # Filter by type
                if plugin_type and plugin_info.plugin_type != plugin_type:
                    continue
                
                # Filter by tags
                if tags and not any(tag in plugin_info.tags for tag in tags):
                    continue
                
                # Filter by author
                if author and author.lower() not in plugin_info.author.lower():
                    continue
                
                results.append(plugin_info)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search plugins: {e}")
            return []
    
    async def get_popular_plugins(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get popular plugins from remote registry"""
        try:
            # For now, return all plugins sorted by name
            # In a real implementation, this would fetch popularity data
            plugins = []
            
            for plugin_name, plugin_data in self.remote_cache.items():
                plugins.append({
                    'name': plugin_data['name'],
                    'version': plugin_data['version'],
                    'description': plugin_data['description'],
                    'author': plugin_data['author'],
                    'plugin_type': plugin_data['plugin_type'],
                    'tags': plugin_data.get('tags', []),
                    'downloads': plugin_data.get('downloads', 0),
                    'rating': plugin_data.get('rating', 0.0),
                    'updated': plugin_data.get('updated', ''),
                })
            
            # Sort by downloads (if available) or alphabetically
            plugins.sort(key=lambda p: p.get('downloads', 0), reverse=True)
            
            return plugins[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get popular plugins: {e}")
            return []
    
    async def get_plugin_by_type(self, plugin_type: PluginType) -> List[PluginInfo]:
        """Get plugins by type"""
        return [
            plugin_info for plugin_info in self.local_cache.values()
            if plugin_info.plugin_type == plugin_type
        ]
    
    async def get_plugin_dependencies(self, plugin_name: str) -> List[str]:
        """Get plugin dependencies"""
        plugin_info = await self.get_plugin_info(plugin_name)
        return plugin_info.dependencies if plugin_info else []
    
    async def check_plugin_compatibility(self, plugin_name: str, wakedock_version: str) -> bool:
        """Check if plugin is compatible with WakeDock version"""
        plugin_info = await self.get_plugin_info(plugin_name)
        
        if not plugin_info:
            return False
        
        # Simple version check - can be made more sophisticated
        if plugin_info.min_wakedock_version and wakedock_version < plugin_info.min_wakedock_version:
            return False
        
        if plugin_info.max_wakedock_version and wakedock_version > plugin_info.max_wakedock_version:
            return False
        
        return True
    
    async def download_plugin(self, plugin_name: str, version: str = "latest") -> Optional[Path]:
        """Download a plugin from remote registry"""
        try:
            if plugin_name not in self.remote_cache:
                logger.error(f"Plugin {plugin_name} not found in remote registry")
                return None
            
            plugin_data = self.remote_cache[plugin_name]
            download_url = plugin_data.get('download_url')
            
            if not download_url:
                logger.error(f"No download URL for plugin {plugin_name}")
                return None
            
            # Create download directory
            download_dir = Path("downloads")
            download_dir.mkdir(exist_ok=True)
            
            # Download plugin
            async with aiohttp.ClientSession() as session:
                async with session.get(download_url) as response:
                    if response.status == 200:
                        plugin_file = download_dir / f"{plugin_name}-{version}.zip"
                        
                        with open(plugin_file, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                f.write(chunk)
                        
                        logger.info(f"Downloaded plugin {plugin_name} to {plugin_file}")
                        return plugin_file
                    else:
                        logger.error(f"Failed to download plugin {plugin_name}: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Failed to download plugin {plugin_name}: {e}")
            return None
    
    async def publish_plugin(self, plugin_info: PluginInfo, plugin_file: Path) -> bool:
        """Publish a plugin to remote registry"""
        try:
            # This would implement the actual publishing logic
            # For now, just log the action
            logger.info(f"Publishing plugin {plugin_info.name} to remote registry")
            
            # In a real implementation, this would:
            # 1. Upload plugin file
            # 2. Submit plugin metadata
            # 3. Wait for approval
            # 4. Update local cache
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish plugin {plugin_info.name}: {e}")
            return False
    
    async def get_plugin_stats(self, plugin_name: str) -> Dict[str, Any]:
        """Get plugin statistics"""
        plugin_data = self.remote_cache.get(plugin_name, {})
        
        return {
            'name': plugin_name,
            'downloads': plugin_data.get('downloads', 0),
            'rating': plugin_data.get('rating', 0.0),
            'reviews': plugin_data.get('reviews', 0),
            'last_updated': plugin_data.get('updated', ''),
            'size': plugin_data.get('size', 0),
            'license': plugin_data.get('license', ''),
            'repository': plugin_data.get('repository', ''),
            'issues': plugin_data.get('issues', 0),
        }
    
    async def get_plugin_versions(self, plugin_name: str) -> List[str]:
        """Get available versions for a plugin"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.registry_url}/api/v1/plugins/{plugin_name}/versions") as response:
                    if response.status == 200:
                        versions_data = await response.json()
                        return versions_data.get('versions', [])
                    else:
                        logger.error(f"Failed to get versions for plugin {plugin_name}: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Failed to get plugin versions: {e}")
            return []
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        return {
            'total_plugins': len(self.local_cache),
            'remote_plugins': len(self.remote_cache),
            'plugin_types': {
                plugin_type.value: len([p for p in self.local_cache.values() if p.plugin_type == plugin_type])
                for plugin_type in PluginType
            },
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'registry_url': self.registry_url,
        }