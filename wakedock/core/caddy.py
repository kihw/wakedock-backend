"""Caddy integration for WakeDock dynamic reverse proxy management."""

import os
import httpx
import asyncio
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template

from wakedock.config import get_settings
from wakedock.database.models import Service, ServiceStatus

logger = logging.getLogger(__name__)


class CaddyManager:
    """Manages Caddy configuration and API interactions."""
    
    def __init__(self):
        """Initialize Caddy manager with settings."""
        self.settings = get_settings()
        self.config_path = Path(self.settings.caddy.config_path)
        self.reload_endpoint = self.settings.caddy.reload_endpoint
        self.admin_port = getattr(self.settings.caddy, 'admin_port', 2019)
        self.admin_host = getattr(self.settings.caddy, 'admin_host', 'localhost')
        
        # Initialize Jinja2 environment for templates
        template_dir = self.config_path.parent / "templates"
        if template_dir.exists():
            self.jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))
        else:
            # Create basic template environment
            self.jinja_env = Environment(loader=FileSystemLoader("."))
    
    async def reload_caddy(self) -> bool:
        """Reload Caddy configuration via API."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"http://{self.admin_host}:{self.admin_port}/load",
                    headers={"Content-Type": "application/json"},
                    json={"config": self._get_caddy_config()}
                )
                
                if response.status_code == 200:
                    logger.info("Caddy configuration reloaded successfully")
                    return True
                else:
                    logger.error(f"Failed to reload Caddy: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error reloading Caddy: {e}")
            return False
    
    def _get_caddy_config(self) -> Dict[str, Any]:
        """Generate Caddy configuration from current services."""
        try:
            # Read current Caddyfile and convert to JSON config
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    caddyfile_content = f.read()
                return self._caddyfile_to_json(caddyfile_content)
            return {}
        except Exception as e:
            logger.error(f"Error reading Caddy config: {e}")
            return {}
    
    def _caddyfile_to_json(self, caddyfile: str) -> Dict[str, Any]:
        """Convert Caddyfile to JSON config (simplified version)."""
        # This is a simplified converter - in production you'd use Caddy's adapter
        config = {
            "apps": {
                "http": {
                    "servers": {
                        "srv0": {
                            "listen": [":80", ":443"],
                            "routes": []
                        }
                    }
                }
            }
        }
        return config
    
    def generate_service_config(self, service: Service) -> str:
        """Generate Caddy configuration for a service."""
        if not service.domain:
            return ""
        
        # Build upstream URL
        upstream_url = f"http://localhost:{self._get_service_port(service)}"
        
        # Generate configuration block
        config_lines = [
            f"{service.domain} {{",
            f"    reverse_proxy {upstream_url}",
        ]
        
        # Add SSL configuration
        if service.enable_ssl:
            config_lines.extend([
                "    tls {",
                "        on_demand",
                "    }"
            ])
        
        # Add authentication if enabled
        if service.enable_auth:
            config_lines.extend([
                "    basicauth {",
                "        admin $2a$14$hashed_password_here",
                "    }"
            ])
        
        # Add health check
        config_lines.extend([
            "    health_uri /health",
            "    health_interval 30s",
        ])
        
        config_lines.append("}")
        
        return "\n".join(config_lines)
    
    def _get_service_port(self, service: Service) -> int:
        """Extract the main port from service configuration."""
        if service.ports and isinstance(service.ports, list) and len(service.ports) > 0:
            port_mapping = service.ports[0]
            if isinstance(port_mapping, dict) and 'host' in port_mapping:
                return port_mapping['host']
        
        # Default port if not configured
        return 8080
    
    async def update_service_config(self, services: List[Service]) -> bool:
        """Update Caddy configuration with current services."""
        try:
            # Generate configuration for all running services
            config_blocks = []
            
            for service in services:
                if service.status == ServiceStatus.RUNNING and service.domain:
                    config_block = self.generate_service_config(service)
                    if config_block:
                        config_blocks.append(config_block)
            
            # Generate global configuration
            global_config = self._generate_global_config()
            
            # Combine all configurations
            full_config = "\n\n".join([global_config] + config_blocks)
            
            # Write to Caddyfile
            await self._write_caddyfile(full_config)
            
            # Reload Caddy
            return await self.reload_caddy()
            
        except Exception as e:
            logger.error(f"Error updating service config: {e}")
            return False
    
    def _generate_global_config(self) -> str:
        """Generate global Caddy configuration."""
        return """# WakeDock Generated Caddyfile
{
    admin localhost:2019
    auto_https on
}"""
    
    async def _write_caddyfile(self, content: str) -> None:
        """Write content to Caddyfile."""
        # Ensure directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write configuration
        with open(self.config_path, 'w') as f:
            f.write(content)
        
        logger.info(f"Updated Caddyfile at {self.config_path}")
    
    async def add_service_route(self, service: Service) -> bool:
        """Add a route for a new service."""
        if service.status != ServiceStatus.RUNNING or not service.domain:
            return False
        
        try:
            # Use Caddy API to add route dynamically
            route_config = {
                "@id": f"wakedock-{service.name}",
                "match": [{"host": [service.domain]}],
                "handle": [{
                    "handler": "reverse_proxy",
                    "upstreams": [{
                        "dial": f"localhost:{self._get_service_port(service)}"
                    }]
                }]
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"http://{self.admin_host}:{self.admin_port}/config/apps/http/servers/srv0/routes",
                    json=route_config
                )
                
                if response.status_code in [200, 201]:
                    logger.info(f"Added route for service {service.name}")
                    return True
                else:
                    logger.error(f"Failed to add route: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error adding service route: {e}")
            return False
    
    async def remove_service_route(self, service: Service) -> bool:
        """Remove a route for a service."""
        try:
            route_id = f"wakedock-{service.name}"
            
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"http://{self.admin_host}:{self.admin_port}/id/{route_id}"
                )
                
                if response.status_code == 200:
                    logger.info(f"Removed route for service {service.name}")
                    return True
                else:
                    logger.warning(f"Failed to remove route (may not exist): {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error removing service route: {e}")
            return False
    
    async def get_caddy_status(self) -> Dict[str, Any]:
        """Get Caddy server status."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://{self.admin_host}:{self.admin_port}/config/"
                )
                
                if response.status_code == 200:
                    return {
                        "status": "running",
                        "config": response.json()
                    }
                else:
                    return {"status": "error", "message": f"HTTP {response.status_code}"}
                    
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    async def validate_domain(self, domain: str) -> bool:
        """Validate if a domain is available for use."""
        try:
            # Check if domain is already in use
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"http://{self.admin_host}:{self.admin_port}/config/apps/http/servers/srv0/routes"
                )
                
                if response.status_code == 200:
                    routes = response.json()
                    for route in routes:
                        for match in route.get("match", []):
                            if domain in match.get("host", []):
                                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error validating domain: {e}")
            return False


# Global Caddy manager instance
caddy_manager = CaddyManager()
