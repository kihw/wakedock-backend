"""
Plugin manager for WakeDock
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Type
from pathlib import Path
import json
import importlib.util
import sys
import traceback

from .base_plugin import BasePlugin, PluginInfo, PluginConfig, PluginStatus, PluginType
from .plugin_loader import PluginLoader
from .plugin_registry import PluginRegistry
from .plugin_security import PluginSecurity
from .plugin_api import PluginAPI

logger = logging.getLogger(__name__)


class PluginManager:
    """
    Central manager for all plugins in WakeDock
    """
    
    def __init__(self, plugin_dir: Path, api_client):
        self.plugin_dir = plugin_dir
        self.api_client = api_client
        self.plugins: Dict[str, BasePlugin] = {}
        self.plugin_configs: Dict[str, PluginConfig] = {}
        self.plugin_loader = PluginLoader(plugin_dir)
        self.plugin_registry = PluginRegistry()
        self.plugin_security = PluginSecurity()
        self.plugin_api = PluginAPI(api_client)
        
        # Event system
        self.event_handlers: Dict[str, List[BasePlugin]] = {}
        self.hook_handlers: Dict[str, List[BasePlugin]] = {}
        
        # Plugin lifecycle
        self.startup_order: List[str] = []
        self.shutdown_order: List[str] = []
        
        # Metrics
        self.metrics = {
            'total_plugins': 0,
            'active_plugins': 0,
            'failed_plugins': 0,
            'load_time': 0,
        }
    
    async def initialize(self) -> None:
        """Initialize the plugin manager"""
        try:
            logger.info("Initializing plugin manager")
            
            # Create plugin directory if it doesn't exist
            self.plugin_dir.mkdir(parents=True, exist_ok=True)
            
            # Load plugin configurations
            await self.load_plugin_configs()
            
            # Initialize components
            await self.plugin_registry.initialize()
            await self.plugin_security.initialize()
            await self.plugin_api.initialize()
            
            logger.info("Plugin manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize plugin manager: {e}")
            raise
    
    async def load_plugin_configs(self) -> None:
        """Load plugin configurations"""
        config_file = self.plugin_dir / "plugins.json"
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    configs = json.load(f)
                
                for plugin_name, config_data in configs.items():
                    self.plugin_configs[plugin_name] = PluginConfig(**config_data)
                    
            except Exception as e:
                logger.error(f"Failed to load plugin configs: {e}")
        
        logger.info(f"Loaded {len(self.plugin_configs)} plugin configurations")
    
    async def save_plugin_configs(self) -> None:
        """Save plugin configurations"""
        config_file = self.plugin_dir / "plugins.json"
        
        try:
            configs = {}
            for plugin_name, config in self.plugin_configs.items():
                configs[plugin_name] = {
                    'enabled': config.enabled,
                    'config': config.config,
                    'permissions': config.permissions,
                    'resource_limits': config.resource_limits,
                    'sandboxed': config.sandboxed,
                    'auto_start': config.auto_start,
                    'log_level': config.log_level,
                }
            
            with open(config_file, 'w') as f:
                json.dump(configs, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save plugin configs: {e}")
    
    async def discover_plugins(self) -> List[PluginInfo]:
        """Discover available plugins"""
        discovered_plugins = []
        
        # Scan plugin directory
        for plugin_path in self.plugin_dir.iterdir():
            if plugin_path.is_dir():
                plugin_info = await self.plugin_loader.load_plugin_info(plugin_path)
                if plugin_info:
                    discovered_plugins.append(plugin_info)
        
        # Update registry
        for plugin_info in discovered_plugins:
            await self.plugin_registry.register_plugin(plugin_info)
        
        logger.info(f"Discovered {len(discovered_plugins)} plugins")
        return discovered_plugins
    
    async def load_plugin(self, plugin_name: str) -> bool:
        """Load a specific plugin"""
        try:
            # Check if plugin is already loaded
            if plugin_name in self.plugins:
                logger.warning(f"Plugin {plugin_name} is already loaded")
                return True
            
            # Load plugin info
            plugin_path = self.plugin_dir / plugin_name
            plugin_info = await self.plugin_loader.load_plugin_info(plugin_path)
            
            if not plugin_info:
                logger.error(f"Failed to load plugin info for {plugin_name}")
                return False
            
            # Security check
            if not await self.plugin_security.validate_plugin(plugin_path):
                logger.error(f"Security validation failed for plugin {plugin_name}")
                return False
            
            # Load plugin class
            plugin_class = await self.plugin_loader.load_plugin_class(plugin_path)
            if not plugin_class:
                logger.error(f"Failed to load plugin class for {plugin_name}")
                return False
            
            # Get or create plugin config
            plugin_config = self.plugin_configs.get(plugin_name, PluginConfig())
            
            # Create plugin instance
            plugin = plugin_class(plugin_info, plugin_config)
            
            # Check dependencies
            if not await self.check_dependencies(plugin_info):
                logger.error(f"Dependencies not satisfied for plugin {plugin_name}")
                return False
            
            # Initialize plugin
            plugin.status = PluginStatus.LOADING
            if await plugin.initialize(self.plugin_api):
                self.plugins[plugin_name] = plugin
                self.plugin_configs[plugin_name] = plugin_config
                
                # Register event handlers
                await self.register_plugin_handlers(plugin)
                
                plugin.status = PluginStatus.INACTIVE
                logger.info(f"Plugin {plugin_name} loaded successfully")
                
                # Update metrics
                self.metrics['total_plugins'] += 1
                
                return True
            else:
                plugin.status = PluginStatus.ERROR
                logger.error(f"Failed to initialize plugin {plugin_name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_name}: {e}")
            logger.error(traceback.format_exc())
            return False
    
    async def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a specific plugin"""
        try:
            if plugin_name not in self.plugins:
                logger.warning(f"Plugin {plugin_name} is not loaded")
                return True
            
            plugin = self.plugins[plugin_name]
            
            # Stop plugin if it's running
            if plugin.is_active:
                await self.stop_plugin(plugin_name)
            
            # Set status to unloading
            plugin.status = PluginStatus.UNLOADING
            
            # Cleanup plugin resources
            await plugin.cleanup()
            
            # Unregister event handlers
            await self.unregister_plugin_handlers(plugin)
            
            # Remove from plugins dict
            del self.plugins[plugin_name]
            
            # Update metrics
            self.metrics['total_plugins'] -= 1
            
            logger.info(f"Plugin {plugin_name} unloaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_name}: {e}")
            return False
    
    async def start_plugin(self, plugin_name: str) -> bool:
        """Start a specific plugin"""
        try:
            if plugin_name not in self.plugins:
                logger.error(f"Plugin {plugin_name} is not loaded")
                return False
            
            plugin = self.plugins[plugin_name]
            
            if plugin.is_active:
                logger.warning(f"Plugin {plugin_name} is already active")
                return True
            
            # Check if plugin is enabled
            if not self.plugin_configs[plugin_name].enabled:
                logger.info(f"Plugin {plugin_name} is disabled")
                return False
            
            # Start plugin
            if await plugin.start():
                plugin.status = PluginStatus.ACTIVE
                
                # Update metrics
                self.metrics['active_plugins'] += 1
                
                logger.info(f"Plugin {plugin_name} started successfully")
                return True
            else:
                plugin.status = PluginStatus.ERROR
                self.metrics['failed_plugins'] += 1
                logger.error(f"Failed to start plugin {plugin_name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start plugin {plugin_name}: {e}")
            return False
    
    async def stop_plugin(self, plugin_name: str) -> bool:
        """Stop a specific plugin"""
        try:
            if plugin_name not in self.plugins:
                logger.error(f"Plugin {plugin_name} is not loaded")
                return False
            
            plugin = self.plugins[plugin_name]
            
            if not plugin.is_active:
                logger.warning(f"Plugin {plugin_name} is not active")
                return True
            
            # Stop plugin
            if await plugin.stop():
                plugin.status = PluginStatus.INACTIVE
                
                # Update metrics
                self.metrics['active_plugins'] -= 1
                
                logger.info(f"Plugin {plugin_name} stopped successfully")
                return True
            else:
                plugin.status = PluginStatus.ERROR
                logger.error(f"Failed to stop plugin {plugin_name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to stop plugin {plugin_name}: {e}")
            return False
    
    async def restart_plugin(self, plugin_name: str) -> bool:
        """Restart a specific plugin"""
        if await self.stop_plugin(plugin_name):
            return await self.start_plugin(plugin_name)
        return False
    
    async def load_all_plugins(self) -> None:
        """Load all discovered plugins"""
        discovered_plugins = await self.discover_plugins()
        
        for plugin_info in discovered_plugins:
            await self.load_plugin(plugin_info.name)
    
    async def start_all_plugins(self) -> None:
        """Start all loaded plugins"""
        # Sort plugins by startup order
        plugins_to_start = []
        
        for plugin_name in self.plugins:
            plugin_config = self.plugin_configs.get(plugin_name, PluginConfig())
            if plugin_config.enabled and plugin_config.auto_start:
                plugins_to_start.append(plugin_name)
        
        # Start plugins in dependency order
        for plugin_name in plugins_to_start:
            await self.start_plugin(plugin_name)
    
    async def stop_all_plugins(self) -> None:
        """Stop all active plugins"""
        # Stop plugins in reverse order
        for plugin_name in reversed(list(self.plugins.keys())):
            await self.stop_plugin(plugin_name)
    
    async def configure_plugin(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """Configure a specific plugin"""
        try:
            if plugin_name not in self.plugins:
                logger.error(f"Plugin {plugin_name} is not loaded")
                return False
            
            plugin = self.plugins[plugin_name]
            
            # Update configuration
            if await plugin.configure(config):
                # Save configuration
                await self.save_plugin_configs()
                logger.info(f"Plugin {plugin_name} configured successfully")
                return True
            else:
                logger.error(f"Failed to configure plugin {plugin_name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to configure plugin {plugin_name}: {e}")
            return False
    
    async def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a specific plugin"""
        if plugin_name in self.plugin_configs:
            self.plugin_configs[plugin_name].enabled = True
            await self.save_plugin_configs()
            return True
        return False
    
    async def disable_plugin(self, plugin_name: str) -> bool:
        """Disable a specific plugin"""
        # Stop plugin if it's running
        if plugin_name in self.plugins and self.plugins[plugin_name].is_active:
            await self.stop_plugin(plugin_name)
        
        # Disable in config
        if plugin_name in self.plugin_configs:
            self.plugin_configs[plugin_name].enabled = False
            await self.save_plugin_configs()
            return True
        return False
    
    async def check_dependencies(self, plugin_info: PluginInfo) -> bool:
        """Check if plugin dependencies are satisfied"""
        for dependency in plugin_info.dependencies:
            if dependency not in self.plugins:
                logger.error(f"Dependency {dependency} not found for plugin {plugin_info.name}")
                return False
        return True
    
    async def register_plugin_handlers(self, plugin: BasePlugin) -> None:
        """Register plugin event and hook handlers"""
        # Register based on plugin type
        if plugin.info.plugin_type == PluginType.CONTAINER_EXTENSION:
            await self.register_event_handler('container_created', plugin)
            await self.register_event_handler('container_started', plugin)
            await self.register_event_handler('container_stopped', plugin)
            await self.register_event_handler('container_removed', plugin)
        
        elif plugin.info.plugin_type == PluginType.SERVICE_EXTENSION:
            await self.register_event_handler('service_created', plugin)
            await self.register_event_handler('service_updated', plugin)
            await self.register_event_handler('service_removed', plugin)
        
        elif plugin.info.plugin_type == PluginType.MONITORING_EXTENSION:
            await self.register_event_handler('alert_triggered', plugin)
            await self.register_event_handler('threshold_exceeded', plugin)
    
    async def unregister_plugin_handlers(self, plugin: BasePlugin) -> None:
        """Unregister plugin event and hook handlers"""
        for event_type, handlers in self.event_handlers.items():
            if plugin in handlers:
                handlers.remove(plugin)
        
        for hook_name, handlers in self.hook_handlers.items():
            if plugin in handlers:
                handlers.remove(plugin)
    
    async def register_event_handler(self, event_type: str, plugin: BasePlugin) -> None:
        """Register an event handler"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        
        if plugin not in self.event_handlers[event_type]:
            self.event_handlers[event_type].append(plugin)
    
    async def emit_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Emit an event to all registered handlers"""
        if event_type in self.event_handlers:
            for plugin in self.event_handlers[event_type]:
                try:
                    await plugin.handle_event(event_type, event_data)
                except Exception as e:
                    logger.error(f"Event handler error in plugin {plugin.name}: {e}")
    
    async def execute_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """Execute hook handlers"""
        results = []
        
        if hook_name in self.hook_handlers:
            for plugin in self.hook_handlers[hook_name]:
                try:
                    result = await plugin.execute_hook(hook_name, *args, **kwargs)
                    results.extend(result)
                except Exception as e:
                    logger.error(f"Hook handler error in plugin {plugin.name}: {e}")
        
        return results
    
    def get_plugin_list(self) -> List[Dict[str, Any]]:
        """Get list of all plugins"""
        plugin_list = []
        
        for plugin_name, plugin in self.plugins.items():
            plugin_list.append({
                'name': plugin.name,
                'version': plugin.version,
                'description': plugin.info.description,
                'author': plugin.info.author,
                'type': plugin.info.plugin_type.value,
                'status': plugin.status.value,
                'active': plugin.is_active,
                'enabled': self.plugin_configs[plugin_name].enabled,
                'dependencies': plugin.info.dependencies,
                'permissions': plugin.info.permissions,
            })
        
        return plugin_list
    
    def get_plugin_info(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific plugin"""
        if plugin_name not in self.plugins:
            return None
        
        plugin = self.plugins[plugin_name]
        config = self.plugin_configs[plugin_name]
        
        return {
            'name': plugin.name,
            'version': plugin.version,
            'description': plugin.info.description,
            'author': plugin.info.author,
            'type': plugin.info.plugin_type.value,
            'status': plugin.status.value,
            'active': plugin.is_active,
            'enabled': config.enabled,
            'config': config.config,
            'dependencies': plugin.info.dependencies,
            'permissions': plugin.info.permissions,
            'health': plugin.get_health_status(),
            'metrics': plugin.get_metrics(),
            'tags': plugin.info.tags,
            'homepage': plugin.info.homepage,
            'repository': plugin.info.repository,
            'license': plugin.info.license,
        }
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get plugin system metrics"""
        return {
            **self.metrics,
            'loaded_plugins': len(self.plugins),
            'plugin_types': {
                plugin_type.value: sum(1 for p in self.plugins.values() 
                                     if p.info.plugin_type == plugin_type)
                for plugin_type in PluginType
            }
        }
    
    async def shutdown(self) -> None:
        """Shutdown the plugin manager"""
        logger.info("Shutting down plugin manager")
        
        # Stop all plugins
        await self.stop_all_plugins()
        
        # Unload all plugins
        for plugin_name in list(self.plugins.keys()):
            await self.unload_plugin(plugin_name)
        
        # Save configurations
        await self.save_plugin_configs()
        
        logger.info("Plugin manager shutdown complete")