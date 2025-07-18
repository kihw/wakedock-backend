"""
Plugin API routes for WakeDock
"""

import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from datetime import datetime
from pathlib import Path
import json
import asyncio

from wakedock.core.auth import get_current_user
from wakedock.plugins.plugin_manager import PluginManager
from wakedock.plugins.plugin_registry import PluginRegistry
from wakedock.plugins.plugin_security import PluginSecurity
from wakedock.plugins.plugin_api import PluginAPI
from wakedock.plugins.base_plugin import PluginInfo, PluginType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plugins", tags=["plugins"])
security = HTTPBearer()

# Plugin manager instance
plugin_manager = PluginManager()
plugin_registry = PluginRegistry()
plugin_security = PluginSecurity()
plugin_api = PluginAPI(None)  # Will be initialized with actual API client


class PluginInstallRequest(BaseModel):
    name: str
    version: str = "latest"
    source: str = "marketplace"
    auto_enable: bool = True


class PluginConfigRequest(BaseModel):
    config: Dict[str, Any]
    permissions: Optional[List[str]] = None
    resource_limits: Optional[Dict[str, Any]] = None


class PluginCreateRequest(BaseModel):
    name: str
    description: str
    author: str
    plugin_type: str
    version: str = "1.0.0"
    license: str = "MIT"
    template: str = "basic"


class PluginSettingsRequest(BaseModel):
    enabled: bool = True
    auto_updates: bool = False
    security_mode: str = "normal"
    max_plugins: int = 50
    max_memory_per_plugin: int = 256
    max_cpu_per_plugin: int = 25
    network_access: bool = False
    file_system_access: str = "restricted"
    database_access: bool = False
    log_level: str = "info"
    plugin_timeout: int = 30
    cache_size: int = 1024
    backup_enabled: bool = True
    backup_interval: int = 24
    marketplace_url: str = "https://registry.wakedock.com"
    allow_dev_mode: bool = False
    require_signatures: bool = True
    auto_cleanup: bool = True
    cleanup_interval: int = 7


@router.get("/")
async def get_plugins(
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get all installed plugins"""
    try:
        plugins = await plugin_manager.get_all_plugins()
        
        plugin_list = []
        for plugin_name, plugin_info in plugins.items():
            plugin_status = await plugin_manager.get_plugin_status(plugin_name)
            plugin_health = await plugin_manager.get_plugin_health(plugin_name)
            plugin_metrics = await plugin_manager.get_plugin_metrics(plugin_name)
            
            plugin_list.append({
                "name": plugin_info.name,
                "version": plugin_info.version,
                "description": plugin_info.description,
                "author": plugin_info.author,
                "type": plugin_info.plugin_type.value,
                "status": plugin_status.get("status", "unknown"),
                "active": plugin_status.get("active", False),
                "enabled": plugin_status.get("enabled", False),
                "dependencies": plugin_info.dependencies,
                "permissions": plugin_info.permissions,
                "health": plugin_health,
                "metrics": plugin_metrics,
                "tags": plugin_info.tags,
                "homepage": plugin_info.homepage,
                "repository": plugin_info.repository,
                "license": plugin_info.license,
            })
        
        return plugin_list
        
    except Exception as e:
        logger.error(f"Failed to get plugins: {e}")
        raise HTTPException(status_code=500, detail="Failed to get plugins")


@router.get("/marketplace")
async def get_marketplace_plugins(
    search: Optional[str] = None,
    type: Optional[str] = None,
    author: Optional[str] = None,
    license: Optional[str] = None,
    sort: str = "popularity",
    user: dict = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Get plugins from marketplace"""
    try:
        # Get installed plugins to mark them
        installed_plugins = await plugin_manager.get_all_plugins()
        
        # Get popular plugins from registry
        popular_plugins = await plugin_registry.get_popular_plugins(limit=100)
        
        # Filter based on parameters
        filtered_plugins = []
        for plugin in popular_plugins:
            # Apply filters
            if search and search.lower() not in plugin.get('name', '').lower() and \
               search.lower() not in plugin.get('description', '').lower():
                continue
            
            if type and plugin.get('plugin_type') != type:
                continue
            
            if author and author.lower() not in plugin.get('author', '').lower():
                continue
            
            if license and plugin.get('license') != license:
                continue
            
            # Add installation status
            plugin['installed'] = plugin['name'] in installed_plugins
            plugin['active'] = False
            
            if plugin['installed']:
                status = await plugin_manager.get_plugin_status(plugin['name'])
                plugin['active'] = status.get('active', False)
            
            filtered_plugins.append(plugin)
        
        # Sort plugins
        if sort == "popularity":
            filtered_plugins.sort(key=lambda p: p.get('downloads', 0), reverse=True)
        elif sort == "recent":
            filtered_plugins.sort(key=lambda p: p.get('updated', ''), reverse=True)
        elif sort == "rating":
            filtered_plugins.sort(key=lambda p: p.get('rating', 0), reverse=True)
        elif sort == "name":
            filtered_plugins.sort(key=lambda p: p.get('name', ''))
        elif sort == "downloads":
            filtered_plugins.sort(key=lambda p: p.get('downloads', 0), reverse=True)
        
        return filtered_plugins
        
    except Exception as e:
        logger.error(f"Failed to get marketplace plugins: {e}")
        raise HTTPException(status_code=500, detail="Failed to get marketplace plugins")


@router.get("/developer")
async def get_developer_plugins(
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get developer plugins and templates"""
    try:
        # Get development plugins
        plugins = await plugin_manager.get_development_plugins()
        
        # Get plugin templates
        templates = [
            {
                "name": "Basic Plugin",
                "description": "A simple plugin template with basic functionality",
                "type": "container_extension",
                "files": {
                    "main.py": "# Basic plugin implementation",
                    "config.json": "{}",
                    "requirements.txt": "wakedock>=1.0.0"
                }
            },
            {
                "name": "Monitoring Plugin",
                "description": "Template for monitoring and metrics collection",
                "type": "monitoring_extension",
                "files": {
                    "main.py": "# Monitoring plugin implementation",
                    "config.json": "{}",
                    "requirements.txt": "wakedock>=1.0.0"
                }
            },
            {
                "name": "UI Extension",
                "description": "Template for UI extensions and components",
                "type": "ui_extension",
                "files": {
                    "main.py": "# UI extension implementation",
                    "config.json": "{}",
                    "requirements.txt": "wakedock>=1.0.0"
                }
            }
        ]
        
        return {
            "plugins": plugins,
            "templates": templates
        }
        
    except Exception as e:
        logger.error(f"Failed to get developer plugins: {e}")
        raise HTTPException(status_code=500, detail="Failed to get developer plugins")


@router.post("/developer/create")
async def create_plugin_project(
    request: PluginCreateRequest,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create a new plugin project"""
    try:
        project_path = await plugin_manager.create_plugin_project(
            name=request.name,
            description=request.description,
            author=request.author,
            plugin_type=request.plugin_type,
            version=request.version,
            license=request.license,
            template=request.template
        )
        
        return {
            "success": True,
            "project_path": str(project_path),
            "message": f"Plugin project {request.name} created successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to create plugin project: {e}")
        raise HTTPException(status_code=500, detail="Failed to create plugin project")


@router.post("/developer/{plugin_name}/build")
async def build_plugin(
    plugin_name: str,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Build a plugin"""
    try:
        build_result = await plugin_manager.build_plugin(plugin_name)
        
        return {
            "success": True,
            "logs": build_result.get("logs", []),
            "artifacts": build_result.get("artifacts", []),
            "message": f"Plugin {plugin_name} built successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to build plugin {plugin_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to build plugin")


@router.post("/developer/{plugin_name}/test")
async def test_plugin(
    plugin_name: str,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Test a plugin"""
    try:
        test_results = await plugin_manager.test_plugin(plugin_name)
        
        return {
            "success": True,
            "passed": test_results.get("passed", 0),
            "failed": test_results.get("failed", 0),
            "coverage": test_results.get("coverage", 0),
            "details": test_results.get("details", {}),
            "message": f"Plugin {plugin_name} tests completed"
        }
        
    except Exception as e:
        logger.error(f"Failed to test plugin {plugin_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to test plugin")


@router.post("/developer/{plugin_name}/publish")
async def publish_plugin(
    plugin_name: str,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Publish a plugin"""
    try:
        publish_result = await plugin_manager.publish_plugin(plugin_name)
        
        return {
            "success": True,
            "url": publish_result.get("url"),
            "message": f"Plugin {plugin_name} published successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to publish plugin {plugin_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to publish plugin")


@router.get("/developer/{plugin_name}/files/{file_name}")
async def get_plugin_file(
    plugin_name: str,
    file_name: str,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get plugin file content"""
    try:
        content = await plugin_manager.get_plugin_file(plugin_name, file_name)
        
        return {
            "success": True,
            "content": content,
            "file_name": file_name
        }
        
    except Exception as e:
        logger.error(f"Failed to get plugin file {file_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get plugin file")


@router.put("/developer/{plugin_name}/files/{file_name}")
async def save_plugin_file(
    plugin_name: str,
    file_name: str,
    request: Dict[str, str],
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Save plugin file content"""
    try:
        await plugin_manager.save_plugin_file(
            plugin_name, file_name, request.get("content", "")
        )
        
        return {
            "success": True,
            "message": f"File {file_name} saved successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to save plugin file {file_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save plugin file")


@router.post("/{plugin_name}/install")
async def install_plugin(
    plugin_name: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Install a plugin"""
    try:
        # Add installation task to background
        background_tasks.add_task(
            plugin_manager.install_plugin,
            plugin_name
        )
        
        return {
            "success": True,
            "message": f"Plugin {plugin_name} installation started"
        }
        
    except Exception as e:
        logger.error(f"Failed to install plugin {plugin_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to install plugin")


@router.delete("/{plugin_name}")
async def uninstall_plugin(
    plugin_name: str,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Uninstall a plugin"""
    try:
        await plugin_manager.uninstall_plugin(plugin_name)
        
        return {
            "success": True,
            "message": f"Plugin {plugin_name} uninstalled successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to uninstall plugin {plugin_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to uninstall plugin")


@router.post("/{plugin_name}/start")
async def start_plugin(
    plugin_name: str,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Start a plugin"""
    try:
        await plugin_manager.start_plugin(plugin_name)
        
        return {
            "success": True,
            "message": f"Plugin {plugin_name} started successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to start plugin {plugin_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to start plugin")


@router.post("/{plugin_name}/stop")
async def stop_plugin(
    plugin_name: str,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Stop a plugin"""
    try:
        await plugin_manager.stop_plugin(plugin_name)
        
        return {
            "success": True,
            "message": f"Plugin {plugin_name} stopped successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to stop plugin {plugin_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop plugin")


@router.post("/{plugin_name}/restart")
async def restart_plugin(
    plugin_name: str,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Restart a plugin"""
    try:
        await plugin_manager.restart_plugin(plugin_name)
        
        return {
            "success": True,
            "message": f"Plugin {plugin_name} restarted successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to restart plugin {plugin_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to restart plugin")


@router.post("/{plugin_name}/enable")
async def enable_plugin(
    plugin_name: str,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Enable a plugin"""
    try:
        await plugin_manager.enable_plugin(plugin_name)
        
        return {
            "success": True,
            "message": f"Plugin {plugin_name} enabled successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to enable plugin {plugin_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to enable plugin")


@router.post("/{plugin_name}/disable")
async def disable_plugin(
    plugin_name: str,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Disable a plugin"""
    try:
        await plugin_manager.disable_plugin(plugin_name)
        
        return {
            "success": True,
            "message": f"Plugin {plugin_name} disabled successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to disable plugin {plugin_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to disable plugin")


@router.get("/{plugin_name}/config")
async def get_plugin_config(
    plugin_name: str,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get plugin configuration"""
    try:
        config = await plugin_manager.get_plugin_config(plugin_name)
        
        return {
            "success": True,
            "config": config
        }
        
    except Exception as e:
        logger.error(f"Failed to get plugin config {plugin_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get plugin config")


@router.put("/{plugin_name}/config")
async def update_plugin_config(
    plugin_name: str,
    request: PluginConfigRequest,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Update plugin configuration"""
    try:
        await plugin_manager.update_plugin_config(
            plugin_name,
            request.config,
            request.permissions,
            request.resource_limits
        )
        
        return {
            "success": True,
            "message": f"Plugin {plugin_name} configuration updated"
        }
        
    except Exception as e:
        logger.error(f"Failed to update plugin config {plugin_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update plugin config")


@router.get("/system/metrics")
async def get_system_metrics(
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get plugin system metrics"""
    try:
        metrics = await plugin_manager.get_system_metrics()
        
        return metrics
        
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system metrics")


@router.get("/system/status")
async def get_system_status(
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get plugin system status"""
    try:
        status = await plugin_manager.get_system_status()
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system status")


@router.get("/settings")
async def get_plugin_settings(
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get plugin settings"""
    try:
        settings = await plugin_manager.get_settings()
        
        return settings
        
    except Exception as e:
        logger.error(f"Failed to get plugin settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to get plugin settings")


@router.put("/settings")
async def update_plugin_settings(
    request: PluginSettingsRequest,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Update plugin settings"""
    try:
        await plugin_manager.update_settings(request.dict())
        
        return {
            "success": True,
            "message": "Plugin settings updated successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to update plugin settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update plugin settings")


@router.post("/settings/reset")
async def reset_plugin_settings(
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Reset plugin settings to defaults"""
    try:
        await plugin_manager.reset_settings()
        
        return {
            "success": True,
            "message": "Plugin settings reset to defaults"
        }
        
    except Exception as e:
        logger.error(f"Failed to reset plugin settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset plugin settings")


@router.get("/security/policies")
async def get_security_policies(
    user: dict = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Get security policies"""
    try:
        policies = await plugin_security.get_security_policies()
        
        return policies
        
    except Exception as e:
        logger.error(f"Failed to get security policies: {e}")
        raise HTTPException(status_code=500, detail="Failed to get security policies")


@router.put("/security/policies/{policy_name}")
async def update_security_policy(
    policy_name: str,
    request: Dict[str, bool],
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Update security policy"""
    try:
        await plugin_security.update_security_policy(
            policy_name, request.get("enabled", False)
        )
        
        return {
            "success": True,
            "message": f"Security policy {policy_name} updated"
        }
        
    except Exception as e:
        logger.error(f"Failed to update security policy {policy_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update security policy")


@router.get("/limits")
async def get_plugin_limits(
    user: dict = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Get plugin resource limits"""
    try:
        limits = await plugin_manager.get_plugin_limits()
        
        return limits
        
    except Exception as e:
        logger.error(f"Failed to get plugin limits: {e}")
        raise HTTPException(status_code=500, detail="Failed to get plugin limits")


@router.get("/api-key")
async def get_api_key(
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get plugin API key"""
    try:
        api_key = await plugin_manager.get_api_key()
        
        return {
            "key": api_key
        }
        
    except Exception as e:
        logger.error(f"Failed to get API key: {e}")
        raise HTTPException(status_code=500, detail="Failed to get API key")


@router.post("/api-key/generate")
async def generate_api_key(
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Generate new plugin API key"""
    try:
        api_key = await plugin_manager.generate_api_key()
        
        return {
            "key": api_key
        }
        
    except Exception as e:
        logger.error(f"Failed to generate API key: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate API key")


@router.post("/cache/clear")
async def clear_plugin_cache(
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Clear plugin cache"""
    try:
        await plugin_manager.clear_cache()
        
        return {
            "success": True,
            "message": "Plugin cache cleared successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to clear plugin cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear plugin cache")


@router.post("/registry/sync")
async def sync_plugin_registry(
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Sync plugin registry"""
    try:
        await plugin_registry.sync_with_remote()
        
        return {
            "success": True,
            "message": "Plugin registry synced successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to sync plugin registry: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync plugin registry")


@router.post("/cleanup")
async def cleanup_plugins(
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Cleanup unused plugins"""
    try:
        cleanup_result = await plugin_manager.cleanup_plugins()
        
        return {
            "success": True,
            "cleaned": cleanup_result.get("cleaned", 0),
            "freed_space": cleanup_result.get("freed_space", 0),
            "message": "Plugin cleanup completed successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup plugins: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup plugins")


@router.post("/restart-all")
async def restart_all_plugins(
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Restart all plugins"""
    try:
        await plugin_manager.restart_all_plugins()
        
        return {
            "success": True,
            "message": "All plugins restarted successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to restart all plugins: {e}")
        raise HTTPException(status_code=500, detail="Failed to restart all plugins")


@router.post("/upload")
async def upload_plugin(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Upload and install a plugin"""
    try:
        # Save uploaded file
        plugin_path = await plugin_manager.save_uploaded_plugin(file)
        
        # Install the plugin
        await plugin_manager.install_plugin_from_file(plugin_path)
        
        return {
            "success": True,
            "message": f"Plugin {file.filename} uploaded and installed successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to upload plugin: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload plugin")


# Initialize plugin system on startup
async def initialize_plugin_system():
    """Initialize the plugin system"""
    try:
        await plugin_manager.initialize()
        await plugin_registry.initialize()
        await plugin_security.initialize()
        await plugin_api.initialize()
        
        logger.info("Plugin system initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize plugin system: {e}")


# Add startup event
@router.on_event("startup")
async def startup_event():
    await initialize_plugin_system()