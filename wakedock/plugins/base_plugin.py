"""
Base plugin class for WakeDock plugins
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PluginType(str, Enum):
    """Plugin type enumeration"""
    CONTAINER_EXTENSION = "container_extension"
    SERVICE_EXTENSION = "service_extension"
    NETWORK_EXTENSION = "network_extension"
    MONITORING_EXTENSION = "monitoring_extension"
    UI_EXTENSION = "ui_extension"
    WEBHOOK_EXTENSION = "webhook_extension"
    STORAGE_EXTENSION = "storage_extension"
    SECURITY_EXTENSION = "security_extension"


class PluginStatus(str, Enum):
    """Plugin status enumeration"""
    INACTIVE = "inactive"
    ACTIVE = "active"
    ERROR = "error"
    LOADING = "loading"
    UNLOADING = "unloading"


@dataclass
class PluginInfo:
    """Plugin information"""
    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    dependencies: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    config_schema: Optional[Dict[str, Any]] = None
    api_version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    homepage: Optional[str] = None
    repository: Optional[str] = None
    license: Optional[str] = None
    min_wakedock_version: Optional[str] = None
    max_wakedock_version: Optional[str] = None


@dataclass
class PluginConfig:
    """Plugin configuration"""
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)
    permissions: List[str] = field(default_factory=list)
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    sandboxed: bool = True
    auto_start: bool = True
    log_level: str = "INFO"


class BasePlugin(ABC):
    """Base class for all WakeDock plugins"""
    
    def __init__(self, plugin_info: PluginInfo, config: PluginConfig):
        self.info = plugin_info
        self.config = config
        self.status = PluginStatus.INACTIVE
        self.logger = logging.getLogger(f"plugin.{plugin_info.name}")
        self._api_client = None
        self._hooks = {}
        self._event_handlers = {}
        
    @property
    def name(self) -> str:
        """Get plugin name"""
        return self.info.name
    
    @property
    def version(self) -> str:
        """Get plugin version"""
        return self.info.version
    
    @property
    def is_active(self) -> bool:
        """Check if plugin is active"""
        return self.status == PluginStatus.ACTIVE
    
    @abstractmethod
    async def initialize(self, api_client) -> bool:
        """
        Initialize the plugin
        
        Args:
            api_client: WakeDock API client instance
            
        Returns:
            bool: True if initialization successful
        """
        pass
    
    @abstractmethod
    async def start(self) -> bool:
        """
        Start the plugin
        
        Returns:
            bool: True if start successful
        """
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """
        Stop the plugin
        
        Returns:
            bool: True if stop successful
        """
        pass
    
    @abstractmethod
    async def cleanup(self) -> bool:
        """
        Cleanup plugin resources
        
        Returns:
            bool: True if cleanup successful
        """
        pass
    
    async def configure(self, config: Dict[str, Any]) -> bool:
        """
        Configure the plugin
        
        Args:
            config: Plugin configuration
            
        Returns:
            bool: True if configuration successful
        """
        try:
            self.config.config.update(config)
            await self.on_config_changed(config)
            return True
        except Exception as e:
            self.logger.error(f"Configuration failed: {e}")
            return False
    
    async def on_config_changed(self, config: Dict[str, Any]) -> None:
        """
        Handle configuration changes
        
        Args:
            config: New configuration
        """
        pass
    
    def register_hook(self, hook_name: str, handler) -> None:
        """
        Register a hook handler
        
        Args:
            hook_name: Name of the hook
            handler: Handler function
        """
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        self._hooks[hook_name].append(handler)
    
    def register_event_handler(self, event_type: str, handler) -> None:
        """
        Register an event handler
        
        Args:
            event_type: Type of event
            handler: Handler function
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
    
    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Handle an event
        
        Args:
            event_type: Type of event
            event_data: Event data
        """
        if event_type in self._event_handlers:
            for handler in self._event_handlers[event_type]:
                try:
                    await handler(event_data)
                except Exception as e:
                    self.logger.error(f"Event handler error: {e}")
    
    async def execute_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """
        Execute hook handlers
        
        Args:
            hook_name: Name of the hook
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            List of results from hook handlers
        """
        results = []
        if hook_name in self._hooks:
            for handler in self._hooks[hook_name]:
                try:
                    result = await handler(*args, **kwargs)
                    results.append(result)
                except Exception as e:
                    self.logger.error(f"Hook handler error: {e}")
        return results
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get plugin health status
        
        Returns:
            Dict with health information
        """
        return {
            "name": self.name,
            "version": self.version,
            "status": self.status.value,
            "active": self.is_active,
            "config": self.config.config,
            "hooks": list(self._hooks.keys()),
            "event_handlers": list(self._event_handlers.keys())
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get plugin metrics
        
        Returns:
            Dict with plugin metrics
        """
        return {
            "name": self.name,
            "version": self.version,
            "status": self.status.value,
            "hooks_count": len(self._hooks),
            "event_handlers_count": len(self._event_handlers),
            "memory_usage": 0,  # To be implemented
            "cpu_usage": 0,     # To be implemented
        }
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate plugin configuration
        
        Args:
            config: Configuration to validate
            
        Returns:
            bool: True if configuration is valid
        """
        if not self.info.config_schema:
            return True
        
        # Basic validation - can be extended with jsonschema
        try:
            for key, value in config.items():
                if key in self.info.config_schema:
                    expected_type = self.info.config_schema[key].get('type')
                    if expected_type and not isinstance(value, expected_type):
                        return False
            return True
        except Exception as e:
            self.logger.error(f"Config validation error: {e}")
            return False
    
    def has_permission(self, permission: str) -> bool:
        """
        Check if plugin has a specific permission
        
        Args:
            permission: Permission to check
            
        Returns:
            bool: True if plugin has permission
        """
        return permission in self.config.permissions
    
    def require_permission(self, permission: str) -> None:
        """
        Require a specific permission
        
        Args:
            permission: Required permission
            
        Raises:
            PermissionError: If permission is not granted
        """
        if not self.has_permission(permission):
            raise PermissionError(f"Plugin {self.name} requires permission: {permission}")
    
    async def call_api(self, method: str, endpoint: str, **kwargs) -> Any:
        """
        Call WakeDock API
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional arguments
            
        Returns:
            API response
        """
        if not self._api_client:
            raise RuntimeError("API client not initialized")
        
        # Check API permissions
        self.require_permission(f"api:{method.lower()}:{endpoint}")
        
        # Make API call through the client
        return await self._api_client.request(method, endpoint, **kwargs)
    
    def __str__(self) -> str:
        return f"Plugin({self.name}:{self.version})"
    
    def __repr__(self) -> str:
        return f"<Plugin {self.name}:{self.version} status={self.status.value}>"


class ContainerPlugin(BasePlugin):
    """Base class for container-related plugins"""
    
    def __init__(self, plugin_info: PluginInfo, config: PluginConfig):
        super().__init__(plugin_info, config)
        self.info.plugin_type = PluginType.CONTAINER_EXTENSION
    
    async def on_container_created(self, container_data: Dict[str, Any]) -> None:
        """Handle container creation event"""
        pass
    
    async def on_container_started(self, container_data: Dict[str, Any]) -> None:
        """Handle container start event"""
        pass
    
    async def on_container_stopped(self, container_data: Dict[str, Any]) -> None:
        """Handle container stop event"""
        pass
    
    async def on_container_removed(self, container_data: Dict[str, Any]) -> None:
        """Handle container removal event"""
        pass


class ServicePlugin(BasePlugin):
    """Base class for service-related plugins"""
    
    def __init__(self, plugin_info: PluginInfo, config: PluginConfig):
        super().__init__(plugin_info, config)
        self.info.plugin_type = PluginType.SERVICE_EXTENSION
    
    async def on_service_created(self, service_data: Dict[str, Any]) -> None:
        """Handle service creation event"""
        pass
    
    async def on_service_updated(self, service_data: Dict[str, Any]) -> None:
        """Handle service update event"""
        pass
    
    async def on_service_removed(self, service_data: Dict[str, Any]) -> None:
        """Handle service removal event"""
        pass


class MonitoringPlugin(BasePlugin):
    """Base class for monitoring-related plugins"""
    
    def __init__(self, plugin_info: PluginInfo, config: PluginConfig):
        super().__init__(plugin_info, config)
        self.info.plugin_type = PluginType.MONITORING_EXTENSION
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """Collect custom metrics"""
        return {}
    
    async def on_alert_triggered(self, alert_data: Dict[str, Any]) -> None:
        """Handle alert trigger event"""
        pass
    
    async def on_threshold_exceeded(self, threshold_data: Dict[str, Any]) -> None:
        """Handle threshold exceeded event"""
        pass


class UIPlugin(BasePlugin):
    """Base class for UI-related plugins"""
    
    def __init__(self, plugin_info: PluginInfo, config: PluginConfig):
        super().__init__(plugin_info, config)
        self.info.plugin_type = PluginType.UI_EXTENSION
    
    def get_ui_components(self) -> Dict[str, Any]:
        """Get UI components provided by plugin"""
        return {}
    
    def get_menu_items(self) -> List[Dict[str, Any]]:
        """Get menu items provided by plugin"""
        return []
    
    def get_dashboard_widgets(self) -> List[Dict[str, Any]]:
        """Get dashboard widgets provided by plugin"""
        return []