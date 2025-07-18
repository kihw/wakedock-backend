"""
Example Container Monitor Plugin for WakeDock
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List

from wakedock.plugins.base_plugin import BasePlugin, PluginType
from wakedock.plugins.plugin_api import PluginAPI

logger = logging.getLogger(__name__)


class ContainerMonitorPlugin(BasePlugin):
    """
    Example plugin that monitors container resource usage
    and sends alerts when thresholds are exceeded
    """
    
    def __init__(self, api: PluginAPI):
        super().__init__(
            name="container_monitor",
            version="1.0.0",
            description="Monitor container resource usage and send alerts",
            author="WakeDock Team",
            plugin_type=PluginType.MONITORING_EXTENSION
        )
        
        self.api = api
        self.monitoring_task = None
        self.config = {
            "cpu_threshold": 80.0,
            "memory_threshold": 85.0,
            "check_interval": 60,  # seconds
            "alert_cooldown": 300,  # seconds
            "enabled_alerts": ["cpu", "memory"],
            "alert_level": "warning"
        }
        self.last_alerts = {}
    
    async def initialize(self) -> None:
        """Initialize the plugin"""
        logger.info("Initializing Container Monitor Plugin")
        
        # Load configuration
        config_response = await self.api.get_config(self.name, "config")
        if config_response.success:
            self.config.update(config_response.data)
        
        # Subscribe to container events
        await self.api.subscribe_to_events(self.name, [
            "container.start",
            "container.stop",
            "container.restart"
        ])
        
        logger.info("Container Monitor Plugin initialized")
    
    async def start(self) -> None:
        """Start the plugin"""
        logger.info("Starting Container Monitor Plugin")
        
        # Start monitoring task
        self.monitoring_task = asyncio.create_task(self.monitor_containers())
        
        # Send startup notification
        await self.api.send_notification(
            self.name,
            "Container Monitor Started",
            "Container monitoring plugin is now active",
            "info"
        )
        
        logger.info("Container Monitor Plugin started")
    
    async def stop(self) -> None:
        """Stop the plugin"""
        logger.info("Stopping Container Monitor Plugin")
        
        # Cancel monitoring task
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        # Send shutdown notification
        await self.api.send_notification(
            self.name,
            "Container Monitor Stopped",
            "Container monitoring plugin has been stopped",
            "info"
        )
        
        logger.info("Container Monitor Plugin stopped")
    
    async def configure(self, config: Dict[str, Any]) -> None:
        """Configure the plugin"""
        logger.info(f"Configuring Container Monitor Plugin: {config}")
        
        # Update configuration
        self.config.update(config)
        
        # Save configuration
        await self.api.set_config(self.name, "config", self.config)
        
        logger.info("Container Monitor Plugin configured")
    
    async def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Handle container events"""
        logger.info(f"Received event: {event_type} - {event_data}")
        
        container_name = event_data.get("container_name", "Unknown")
        
        if event_type == "container.start":
            await self.api.send_notification(
                self.name,
                "Container Started",
                f"Container {container_name} has started",
                "info"
            )
        elif event_type == "container.stop":
            await self.api.send_notification(
                self.name,
                "Container Stopped",
                f"Container {container_name} has stopped",
                "warning"
            )
        elif event_type == "container.restart":
            await self.api.send_notification(
                self.name,
                "Container Restarted",
                f"Container {container_name} has restarted",
                "info"
            )
    
    async def monitor_containers(self) -> None:
        """Monitor container resource usage"""
        while True:
            try:
                # Get all containers
                containers_response = await self.api.get_containers(self.name)
                if not containers_response.success:
                    logger.error(f"Failed to get containers: {containers_response.error}")
                    await asyncio.sleep(self.config["check_interval"])
                    continue
                
                containers = containers_response.data
                
                # Check each container
                for container in containers:
                    container_id = container.get("id")
                    container_name = container.get("name", "Unknown")
                    
                    # Get container stats
                    stats_response = await self.api.get_container_stats(self.name, container_id)
                    if not stats_response.success:
                        continue
                    
                    stats = stats_response.data
                    
                    # Check CPU usage
                    if "cpu" in self.config["enabled_alerts"]:
                        cpu_usage = stats.get("cpu_percent", 0)
                        if cpu_usage > self.config["cpu_threshold"]:
                            await self.send_alert(
                                container_name,
                                "High CPU Usage",
                                f"Container {container_name} CPU usage: {cpu_usage:.1f}%",
                                "cpu"
                            )
                    
                    # Check memory usage
                    if "memory" in self.config["enabled_alerts"]:
                        memory_usage = stats.get("memory_percent", 0)
                        if memory_usage > self.config["memory_threshold"]:
                            await self.send_alert(
                                container_name,
                                "High Memory Usage",
                                f"Container {container_name} memory usage: {memory_usage:.1f}%",
                                "memory"
                            )
                
                # Wait before next check
                await asyncio.sleep(self.config["check_interval"])
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error monitoring containers: {e}")
                await asyncio.sleep(self.config["check_interval"])
    
    async def send_alert(self, container_name: str, title: str, message: str, alert_type: str) -> None:
        """Send an alert with cooldown"""
        current_time = datetime.now()
        alert_key = f"{container_name}_{alert_type}"
        
        # Check cooldown
        if alert_key in self.last_alerts:
            time_since_last = (current_time - self.last_alerts[alert_key]).total_seconds()
            if time_since_last < self.config["alert_cooldown"]:
                return
        
        # Send alert
        await self.api.send_notification(
            self.name,
            title,
            message,
            self.config["alert_level"]
        )
        
        # Emit event
        await self.api.emit_event(
            self.name,
            f"container.alert.{alert_type}",
            {
                "container_name": container_name,
                "alert_type": alert_type,
                "message": message,
                "timestamp": current_time.isoformat()
            }
        )
        
        # Update last alert time
        self.last_alerts[alert_key] = current_time
        
        logger.info(f"Alert sent: {title} - {message}")
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get plugin metrics"""
        return {
            "alerts_sent": len(self.last_alerts),
            "monitoring_active": self.monitoring_task is not None and not self.monitoring_task.done(),
            "cpu_threshold": self.config["cpu_threshold"],
            "memory_threshold": self.config["memory_threshold"],
            "check_interval": self.config["check_interval"],
            "enabled_alerts": self.config["enabled_alerts"],
            "last_check": datetime.now().isoformat()
        }
    
    async def get_health(self) -> Dict[str, Any]:
        """Get plugin health status"""
        is_healthy = True
        issues = []
        
        # Check if monitoring task is running
        if not self.monitoring_task or self.monitoring_task.done():
            is_healthy = False
            issues.append("Monitoring task not running")
        
        # Check API connectivity
        try:
            response = await self.api.get_system_info(self.name)
            if not response.success:
                is_healthy = False
                issues.append("API connectivity issues")
        except Exception as e:
            is_healthy = False
            issues.append(f"API error: {str(e)}")
        
        return {
            "healthy": is_healthy,
            "issues": issues,
            "status": "healthy" if is_healthy else "degraded",
            "last_check": datetime.now().isoformat()
        }
    
    def get_config_schema(self) -> Dict[str, Any]:
        """Get configuration schema"""
        return {
            "type": "object",
            "properties": {
                "cpu_threshold": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                    "default": 80.0,
                    "description": "CPU usage threshold for alerts (%)"
                },
                "memory_threshold": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                    "default": 85.0,
                    "description": "Memory usage threshold for alerts (%)"
                },
                "check_interval": {
                    "type": "integer",
                    "minimum": 10,
                    "maximum": 3600,
                    "default": 60,
                    "description": "Monitoring check interval (seconds)"
                },
                "alert_cooldown": {
                    "type": "integer",
                    "minimum": 60,
                    "maximum": 3600,
                    "default": 300,
                    "description": "Alert cooldown period (seconds)"
                },
                "enabled_alerts": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["cpu", "memory"]
                    },
                    "default": ["cpu", "memory"],
                    "description": "Enabled alert types"
                },
                "alert_level": {
                    "type": "string",
                    "enum": ["info", "warning", "error"],
                    "default": "warning",
                    "description": "Alert notification level"
                }
            },
            "required": ["cpu_threshold", "memory_threshold", "check_interval"]
        }


# Plugin factory function
def create_plugin(api: PluginAPI) -> BasePlugin:
    """Create and return the plugin instance"""
    return ContainerMonitorPlugin(api)


# Plugin metadata
PLUGIN_INFO = {
    "name": "container_monitor",
    "version": "1.0.0",
    "description": "Monitor container resource usage and send alerts",
    "author": "WakeDock Team",
    "plugin_type": "monitoring_extension",
    "dependencies": [],
    "permissions": [
        "api:get:/containers",
        "api:get:/containers/*/stats",
        "api:get:/system/info",
        "api:post:/events",
        "api:post:/notifications",
        "api:get:/config/*",
        "api:put:/config/*"
    ],
    "tags": ["monitoring", "alerts", "containers", "resources"],
    "homepage": "https://github.com/wakedock/plugins/container-monitor",
    "repository": "https://github.com/wakedock/plugins/container-monitor",
    "license": "MIT",
    "min_wakedock_version": "1.0.0"
}