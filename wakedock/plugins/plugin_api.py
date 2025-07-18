"""
Plugin API for WakeDock
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class APIResponse:
    """API response wrapper"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    status_code: int = 200


class PluginAPI:
    """
    API interface for plugins to interact with WakeDock
    """
    
    def __init__(self, api_client):
        self.api_client = api_client
        self.plugin_permissions = {}
        self.rate_limits = {}
        self.request_logs = {}
    
    async def initialize(self) -> None:
        """Initialize the plugin API"""
        logger.info("Initializing plugin API")
    
    async def request(self, method: str, endpoint: str, plugin_name: str, 
                     **kwargs) -> APIResponse:
        """
        Make an API request on behalf of a plugin
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            plugin_name: Name of the requesting plugin
            **kwargs: Additional request parameters
            
        Returns:
            APIResponse object
        """
        try:
            # Check permissions
            if not await self.check_permission(plugin_name, method, endpoint):
                return APIResponse(
                    success=False,
                    error=f"Plugin {plugin_name} does not have permission for {method} {endpoint}",
                    status_code=403
                )
            
            # Check rate limits
            if not await self.check_rate_limit(plugin_name, endpoint):
                return APIResponse(
                    success=False,
                    error=f"Rate limit exceeded for plugin {plugin_name}",
                    status_code=429
                )
            
            # Log request
            await self.log_request(plugin_name, method, endpoint)
            
            # Make the actual API call
            response = await self.api_client.request(method, endpoint, **kwargs)
            
            return APIResponse(
                success=True,
                data=response
            )
            
        except Exception as e:
            logger.error(f"API request failed for plugin {plugin_name}: {e}")
            return APIResponse(
                success=False,
                error=str(e),
                status_code=500
            )
    
    async def check_permission(self, plugin_name: str, method: str, endpoint: str) -> bool:
        """Check if plugin has permission for the API call"""
        try:
            plugin_perms = self.plugin_permissions.get(plugin_name, [])
            
            # Check specific endpoint permission
            specific_perm = f"api:{method.lower()}:{endpoint}"
            if specific_perm in plugin_perms:
                return True
            
            # Check wildcard permissions
            wildcard_perm = f"api:{method.lower()}:*"
            if wildcard_perm in plugin_perms:
                return True
            
            # Check general API permission
            if "api:*" in plugin_perms:
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Permission check failed: {e}")
            return False
    
    async def check_rate_limit(self, plugin_name: str, endpoint: str) -> bool:
        """Check if plugin has exceeded rate limits"""
        try:
            current_time = datetime.now()
            
            # Get rate limit configuration
            rate_limit = self.rate_limits.get(plugin_name, {
                'requests_per_minute': 60,
                'requests_per_hour': 1000,
                'requests_per_day': 10000
            })
            
            # Get request history
            if plugin_name not in self.request_logs:
                self.request_logs[plugin_name] = []
            
            request_history = self.request_logs[plugin_name]
            
            # Clean old requests
            cutoff_time = current_time.timestamp() - 86400  # 24 hours
            request_history = [req for req in request_history if req['timestamp'] > cutoff_time]
            self.request_logs[plugin_name] = request_history
            
            # Check daily limit
            daily_requests = len(request_history)
            if daily_requests >= rate_limit['requests_per_day']:
                return False
            
            # Check hourly limit
            hourly_cutoff = current_time.timestamp() - 3600  # 1 hour
            hourly_requests = len([req for req in request_history if req['timestamp'] > hourly_cutoff])
            if hourly_requests >= rate_limit['requests_per_hour']:
                return False
            
            # Check minute limit
            minute_cutoff = current_time.timestamp() - 60  # 1 minute
            minute_requests = len([req for req in request_history if req['timestamp'] > minute_cutoff])
            if minute_requests >= rate_limit['requests_per_minute']:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return False
    
    async def log_request(self, plugin_name: str, method: str, endpoint: str) -> None:
        """Log API request"""
        try:
            if plugin_name not in self.request_logs:
                self.request_logs[plugin_name] = []
            
            self.request_logs[plugin_name].append({
                'timestamp': datetime.now().timestamp(),
                'method': method,
                'endpoint': endpoint
            })
            
        except Exception as e:
            logger.error(f"Failed to log request: {e}")
    
    async def set_plugin_permissions(self, plugin_name: str, permissions: List[str]) -> None:
        """Set permissions for a plugin"""
        self.plugin_permissions[plugin_name] = permissions
        logger.info(f"Set permissions for plugin {plugin_name}: {permissions}")
    
    async def set_rate_limits(self, plugin_name: str, limits: Dict[str, int]) -> None:
        """Set rate limits for a plugin"""
        self.rate_limits[plugin_name] = limits
        logger.info(f"Set rate limits for plugin {plugin_name}: {limits}")
    
    # Container API methods
    async def get_containers(self, plugin_name: str, **kwargs) -> APIResponse:
        """Get container list"""
        return await self.request('GET', '/containers', plugin_name, **kwargs)
    
    async def get_container(self, plugin_name: str, container_id: str, **kwargs) -> APIResponse:
        """Get container details"""
        return await self.request('GET', f'/containers/{container_id}', plugin_name, **kwargs)
    
    async def start_container(self, plugin_name: str, container_id: str, **kwargs) -> APIResponse:
        """Start container"""
        return await self.request('POST', f'/containers/{container_id}/start', plugin_name, **kwargs)
    
    async def stop_container(self, plugin_name: str, container_id: str, **kwargs) -> APIResponse:
        """Stop container"""
        return await self.request('POST', f'/containers/{container_id}/stop', plugin_name, **kwargs)
    
    async def restart_container(self, plugin_name: str, container_id: str, **kwargs) -> APIResponse:
        """Restart container"""
        return await self.request('POST', f'/containers/{container_id}/restart', plugin_name, **kwargs)
    
    async def remove_container(self, plugin_name: str, container_id: str, **kwargs) -> APIResponse:
        """Remove container"""
        return await self.request('DELETE', f'/containers/{container_id}', plugin_name, **kwargs)
    
    async def create_container(self, plugin_name: str, config: Dict[str, Any], **kwargs) -> APIResponse:
        """Create container"""
        return await self.request('POST', '/containers', plugin_name, json=config, **kwargs)
    
    # Service API methods
    async def get_services(self, plugin_name: str, **kwargs) -> APIResponse:
        """Get service list"""
        return await self.request('GET', '/services', plugin_name, **kwargs)
    
    async def get_service(self, plugin_name: str, service_id: str, **kwargs) -> APIResponse:
        """Get service details"""
        return await self.request('GET', f'/services/{service_id}', plugin_name, **kwargs)
    
    async def create_service(self, plugin_name: str, config: Dict[str, Any], **kwargs) -> APIResponse:
        """Create service"""
        return await self.request('POST', '/services', plugin_name, json=config, **kwargs)
    
    async def update_service(self, plugin_name: str, service_id: str, config: Dict[str, Any], **kwargs) -> APIResponse:
        """Update service"""
        return await self.request('PUT', f'/services/{service_id}', plugin_name, json=config, **kwargs)
    
    async def delete_service(self, plugin_name: str, service_id: str, **kwargs) -> APIResponse:
        """Delete service"""
        return await self.request('DELETE', f'/services/{service_id}', plugin_name, **kwargs)
    
    # Network API methods
    async def get_networks(self, plugin_name: str, **kwargs) -> APIResponse:
        """Get network list"""
        return await self.request('GET', '/networks', plugin_name, **kwargs)
    
    async def get_network(self, plugin_name: str, network_id: str, **kwargs) -> APIResponse:
        """Get network details"""
        return await self.request('GET', f'/networks/{network_id}', plugin_name, **kwargs)
    
    async def create_network(self, plugin_name: str, config: Dict[str, Any], **kwargs) -> APIResponse:
        """Create network"""
        return await self.request('POST', '/networks', plugin_name, json=config, **kwargs)
    
    async def remove_network(self, plugin_name: str, network_id: str, **kwargs) -> APIResponse:
        """Remove network"""
        return await self.request('DELETE', f'/networks/{network_id}', plugin_name, **kwargs)
    
    # Volume API methods
    async def get_volumes(self, plugin_name: str, **kwargs) -> APIResponse:
        """Get volume list"""
        return await self.request('GET', '/volumes', plugin_name, **kwargs)
    
    async def get_volume(self, plugin_name: str, volume_name: str, **kwargs) -> APIResponse:
        """Get volume details"""
        return await self.request('GET', f'/volumes/{volume_name}', plugin_name, **kwargs)
    
    async def create_volume(self, plugin_name: str, config: Dict[str, Any], **kwargs) -> APIResponse:
        """Create volume"""
        return await self.request('POST', '/volumes', plugin_name, json=config, **kwargs)
    
    async def remove_volume(self, plugin_name: str, volume_name: str, **kwargs) -> APIResponse:
        """Remove volume"""
        return await self.request('DELETE', f'/volumes/{volume_name}', plugin_name, **kwargs)
    
    # System API methods
    async def get_system_info(self, plugin_name: str, **kwargs) -> APIResponse:
        """Get system information"""
        return await self.request('GET', '/system/info', plugin_name, **kwargs)
    
    async def get_system_stats(self, plugin_name: str, **kwargs) -> APIResponse:
        """Get system statistics"""
        return await self.request('GET', '/system/stats', plugin_name, **kwargs)
    
    async def get_system_events(self, plugin_name: str, **kwargs) -> APIResponse:
        """Get system events"""
        return await self.request('GET', '/system/events', plugin_name, **kwargs)
    
    # Monitoring API methods
    async def get_container_stats(self, plugin_name: str, container_id: str, **kwargs) -> APIResponse:
        """Get container statistics"""
        return await self.request('GET', f'/containers/{container_id}/stats', plugin_name, **kwargs)
    
    async def get_container_logs(self, plugin_name: str, container_id: str, **kwargs) -> APIResponse:
        """Get container logs"""
        return await self.request('GET', f'/containers/{container_id}/logs', plugin_name, **kwargs)
    
    async def get_service_logs(self, plugin_name: str, service_id: str, **kwargs) -> APIResponse:
        """Get service logs"""
        return await self.request('GET', f'/services/{service_id}/logs', plugin_name, **kwargs)
    
    # Configuration API methods
    async def get_config(self, plugin_name: str, key: str, **kwargs) -> APIResponse:
        """Get configuration value"""
        return await self.request('GET', f'/config/{key}', plugin_name, **kwargs)
    
    async def set_config(self, plugin_name: str, key: str, value: Any, **kwargs) -> APIResponse:
        """Set configuration value"""
        return await self.request('PUT', f'/config/{key}', plugin_name, json={'value': value}, **kwargs)
    
    # Event API methods
    async def emit_event(self, plugin_name: str, event_type: str, event_data: Dict[str, Any], **kwargs) -> APIResponse:
        """Emit an event"""
        return await self.request('POST', '/events', plugin_name, json={
            'type': event_type,
            'data': event_data,
            'source': plugin_name
        }, **kwargs)
    
    async def subscribe_to_events(self, plugin_name: str, event_types: List[str], **kwargs) -> APIResponse:
        """Subscribe to events"""
        return await self.request('POST', '/events/subscribe', plugin_name, json={
            'event_types': event_types,
            'subscriber': plugin_name
        }, **kwargs)
    
    # Notification API methods
    async def send_notification(self, plugin_name: str, title: str, message: str, 
                               level: str = 'info', **kwargs) -> APIResponse:
        """Send notification"""
        return await self.request('POST', '/notifications', plugin_name, json={
            'title': title,
            'message': message,
            'level': level,
            'source': plugin_name
        }, **kwargs)
    
    # Database API methods (limited access)
    async def store_data(self, plugin_name: str, key: str, data: Dict[str, Any], **kwargs) -> APIResponse:
        """Store plugin data"""
        return await self.request('POST', f'/plugins/{plugin_name}/data/{key}', plugin_name, json=data, **kwargs)
    
    async def retrieve_data(self, plugin_name: str, key: str, **kwargs) -> APIResponse:
        """Retrieve plugin data"""
        return await self.request('GET', f'/plugins/{plugin_name}/data/{key}', plugin_name, **kwargs)
    
    async def delete_data(self, plugin_name: str, key: str, **kwargs) -> APIResponse:
        """Delete plugin data"""
        return await self.request('DELETE', f'/plugins/{plugin_name}/data/{key}', plugin_name, **kwargs)
    
    # Utility methods
    async def get_plugin_info(self, plugin_name: str, target_plugin: str, **kwargs) -> APIResponse:
        """Get information about another plugin"""
        return await self.request('GET', f'/plugins/{target_plugin}/info', plugin_name, **kwargs)
    
    async def call_plugin_method(self, plugin_name: str, target_plugin: str, method: str, 
                                args: List[Any], kwargs_dict: Dict[str, Any], **kwargs) -> APIResponse:
        """Call a method on another plugin"""
        return await self.request('POST', f'/plugins/{target_plugin}/call/{method}', plugin_name, json={
            'args': args,
            'kwargs': kwargs_dict,
            'caller': plugin_name
        }, **kwargs)
    
    def get_api_stats(self, plugin_name: str) -> Dict[str, Any]:
        """Get API usage statistics for a plugin"""
        request_history = self.request_logs.get(plugin_name, [])
        
        # Calculate statistics
        total_requests = len(request_history)
        
        # Group by endpoint
        endpoint_stats = {}
        method_stats = {}
        
        for req in request_history:
            endpoint = req['endpoint']
            method = req['method']
            
            if endpoint not in endpoint_stats:
                endpoint_stats[endpoint] = 0
            endpoint_stats[endpoint] += 1
            
            if method not in method_stats:
                method_stats[method] = 0
            method_stats[method] += 1
        
        # Calculate rate limits
        current_time = datetime.now()
        minute_cutoff = current_time.timestamp() - 60
        hour_cutoff = current_time.timestamp() - 3600
        day_cutoff = current_time.timestamp() - 86400
        
        requests_last_minute = len([req for req in request_history if req['timestamp'] > minute_cutoff])
        requests_last_hour = len([req for req in request_history if req['timestamp'] > hour_cutoff])
        requests_last_day = len([req for req in request_history if req['timestamp'] > day_cutoff])
        
        rate_limit_config = self.rate_limits.get(plugin_name, {
            'requests_per_minute': 60,
            'requests_per_hour': 1000,
            'requests_per_day': 10000
        })
        
        return {
            'plugin_name': plugin_name,
            'total_requests': total_requests,
            'endpoint_stats': endpoint_stats,
            'method_stats': method_stats,
            'rate_limit_usage': {
                'minute': f"{requests_last_minute}/{rate_limit_config['requests_per_minute']}",
                'hour': f"{requests_last_hour}/{rate_limit_config['requests_per_hour']}",
                'day': f"{requests_last_day}/{rate_limit_config['requests_per_day']}"
            },
            'permissions': self.plugin_permissions.get(plugin_name, [])
        }
    
    def get_system_api_stats(self) -> Dict[str, Any]:
        """Get system-wide API statistics"""
        total_requests = sum(len(history) for history in self.request_logs.values())
        
        return {
            'total_requests': total_requests,
            'active_plugins': len(self.request_logs),
            'plugins_with_permissions': len(self.plugin_permissions),
            'plugins_with_rate_limits': len(self.rate_limits),
            'plugin_stats': {
                plugin_name: len(history)
                for plugin_name, history in self.request_logs.items()
            }
        }