"""
Docker orchestration service
"""

import asyncio
import logging
import os
import subprocess
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

import docker
from docker.models.containers import Container
from docker.models.images import Image

from wakedock.config import get_settings, ServiceSettings
from wakedock.core.caddy import caddy_manager

logger = logging.getLogger(__name__)


class DockerOrchestrator:
    """Manages Docker containers and services"""
    
    def __init__(self):
        self.client = docker.from_env()
        self.settings = get_settings()
        self.services: Dict[str, Dict[str, Any]] = {}
        self.container_map: Dict[str, str] = {}  # container_id -> service_id
        self._load_services()
    
    def _load_services(self):
        """Load services from configuration"""
        for service_config in self.settings.services:
            service_id = f"wakedock-{service_config.name}"
            self.services[service_id] = {
                "id": service_id,
                "name": service_config.name,
                "subdomain": service_config.subdomain,
                "docker_image": service_config.docker_image,
                "docker_compose": service_config.docker_compose,
                "ports": service_config.ports,
                "environment": service_config.environment,
                "auto_shutdown": service_config.auto_shutdown.dict(),
                "loading_page": service_config.loading_page.dict(),
                "health_check": service_config.health_check.dict(),
                "status": "stopped",
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "last_accessed": None,
                "resource_usage": None,
                "container_id": None
            }
    
    async def list_services(self) -> List[Dict[str, Any]]:
        """List all services"""
        return list(self.services.values())
    
    async def get_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Get service by ID"""
        return self.services.get(service_id)
    
    async def get_service_by_subdomain(self, subdomain: str) -> Optional[Dict[str, Any]]:
        """Get service by subdomain"""
        for service in self.services.values():
            if service["subdomain"] == subdomain:
                return service
        return None
    
    async def create_service(self, service_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new service"""
        service_id = f"wakedock-{service_data['name']}"
        
        if service_id in self.services:
            raise ValueError(f"Service {service_data['name']} already exists")
        
        # Validate service data
        if not service_data.get("docker_image") and not service_data.get("docker_compose"):
            raise ValueError("Either docker_image or docker_compose must be specified")
        
        # Create service entry
        service = {
            "id": service_id,
            "name": service_data["name"],
            "subdomain": service_data["subdomain"],
            "docker_image": service_data.get("docker_image"),
            "docker_compose": service_data.get("docker_compose"),
            "ports": service_data.get("ports", []),
            "environment": service_data.get("environment", {}),
            "auto_shutdown": service_data.get("auto_shutdown", {}),
            "loading_page": service_data.get("loading_page", {}),
            "status": "stopped",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "last_accessed": None,
            "resource_usage": None,
            "container_id": None
        }
        
        self.services[service_id] = service
        return service
    
    async def update_service(self, service_id: str, service_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update service configuration"""
        if service_id not in self.services:
            return None
        
        service = self.services[service_id]
        
        # Update fields
        for key, value in service_data.items():
            if key in ["name", "subdomain", "docker_image", "docker_compose", "ports", "environment", "auto_shutdown", "loading_page"]:
                service[key] = value
        
        service["updated_at"] = datetime.now()
        return service
    
    async def delete_service(self, service_id: str) -> bool:
        """Delete a service"""
        if service_id not in self.services:
            return False
        
        # Stop service if running
        await self.sleep_service(service_id)
        
        # Remove from services
        del self.services[service_id]
        return True
    
    async def is_service_running(self, service_id: str) -> bool:
        """Check if service is running"""
        service = self.services.get(service_id)
        if not service:
            return False
        
        container_id = service.get("container_id")
        if not container_id:
            return False
        
        try:
            container = self.client.containers.get(container_id)
            is_running = container.status == "running"
            
            # Update service status
            service["status"] = "running" if is_running else "stopped"
            return is_running
        except docker.errors.NotFound:
            service["status"] = "stopped"
            service["container_id"] = None
            return False
    
    async def wake_service(self, service_id: str) -> bool:
        """Wake up a service"""
        service = self.services.get(service_id)
        if not service:
            return False
        
        logger.info(f"Waking up service: {service['name']}")
        
        try:
            success = False
            if service.get("docker_compose"):
                # Use docker-compose
                success = await self._start_compose_service(service)
            else:
                # Use docker image
                success = await self._start_docker_service(service)
            
            # Update Caddy configuration if service started successfully
            if success and service.get("domain"):
                from wakedock.database.models import Service, ServiceStatus
                # Create a service object for Caddy
                caddy_service = type('Service', (), {
                    'name': service['name'],
                    'domain': service.get('domain'),
                    'status': ServiceStatus.RUNNING,
                    'ports': service.get('ports', []),
                    'enable_ssl': service.get('enable_ssl', True),
                    'enable_auth': service.get('enable_auth', False)
                })()
                
                # Add route to Caddy
                await caddy_manager.add_service_route(caddy_service)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to wake service {service['name']}: {str(e)}")
            return False
    
    async def _start_docker_service(self, service: Dict[str, Any]) -> bool:
        """Start a Docker service from image"""
        try:
            # Check if container already exists
            container_name = f"wakedock-{service['name']}"
            
            try:
                container = self.client.containers.get(container_name)
                if container.status == "running":
                    service["status"] = "running"
                    service["container_id"] = container.id
                    return True
                else:
                    # Start existing container
                    container.start()
                    service["status"] = "running"
                    service["container_id"] = container.id
                    return True
            except docker.errors.NotFound:
                pass
            
            # Create new container
            ports = {}
            if service["ports"]:
                for port_mapping in service["ports"]:
                    if ":" in port_mapping:
                        host_port, container_port = port_mapping.split(":")
                        ports[container_port] = host_port
            
            container = self.client.containers.run(
                service["docker_image"],
                name=container_name,
                ports=ports,
                environment=service["environment"],
                detach=True,
                network="wakedock-network"
            )
            
            service["status"] = "running"
            service["container_id"] = container.id
            self.container_map[container.id] = service["id"]
            
            logger.info(f"Started container {container_name} with ID {container.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Docker service {service['name']}: {str(e)}")
            service["status"] = "error"
            return False
    
    async def _start_compose_service(self, service: Dict[str, Any]) -> bool:
        """Start a Docker Compose service"""
        try:
            compose_file = service["docker_compose"]
            if not os.path.exists(compose_file):
                logger.error(f"Docker Compose file not found: {compose_file}")
                return False
            
            # Use docker-compose to start service
            result = subprocess.run([
                "docker-compose", "-f", compose_file, "up", "-d"
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Failed to start compose service: {result.stderr}")
                return False
            
            service["status"] = "running"
            logger.info(f"Started compose service: {service['name']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start compose service {service['name']}: {str(e)}")
            service["status"] = "error"
            return False
    
    async def sleep_service(self, service_id: str) -> bool:
        """Put a service to sleep"""
        service = self.services.get(service_id)
        if not service:
            return False
        
        logger.info(f"Putting service to sleep: {service['name']}")
        
        try:
            success = False
            if service.get("docker_compose"):
                success = await self._stop_compose_service(service)
            else:
                success = await self._stop_docker_service(service)
            
            # Remove route from Caddy if service stopped successfully
            if success and service.get("domain"):
                from wakedock.database.models import Service, ServiceStatus
                # Create a service object for Caddy
                caddy_service = type('Service', (), {
                    'name': service['name'],
                    'domain': service.get('domain'),
                    'status': ServiceStatus.STOPPED
                })()
                
                # Remove route from Caddy
                await caddy_manager.remove_service_route(caddy_service)
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to sleep service {service['name']}: {str(e)}")
            return False
    
    async def _stop_docker_service(self, service: Dict[str, Any]) -> bool:
        """Stop a Docker service"""
        try:
            container_id = service.get("container_id")
            if container_id:
                try:
                    container = self.client.containers.get(container_id)
                    container.stop()
                    service["status"] = "stopped"
                    service["container_id"] = None
                    self.container_map.pop(container_id, None)
                    logger.info(f"Stopped container for service: {service['name']}")
                    return True
                except docker.errors.NotFound:
                    service["status"] = "stopped"
                    service["container_id"] = None
                    return True
            
            # Try to find container by name
            container_name = f"wakedock-{service['name']}"
            try:
                container = self.client.containers.get(container_name)
                container.stop()
                service["status"] = "stopped"
                logger.info(f"Stopped container: {container_name}")
                return True
            except docker.errors.NotFound:
                service["status"] = "stopped"
                return True
            
        except Exception as e:
            logger.error(f"Failed to stop Docker service {service['name']}: {str(e)}")
            return False
    
    async def _stop_compose_service(self, service: Dict[str, Any]) -> bool:
        """Stop a Docker Compose service"""
        try:
            compose_file = service["docker_compose"]
            if not os.path.exists(compose_file):
                logger.error(f"Docker Compose file not found: {compose_file}")
                return False
            
            # Use docker-compose to stop service
            result = subprocess.run([
                "docker-compose", "-f", compose_file, "down"
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Failed to stop compose service: {result.stderr}")
                return False
            
            service["status"] = "stopped"
            logger.info(f"Stopped compose service: {service['name']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop compose service {service['name']}: {str(e)}")
            return False
    
    async def get_service_url(self, service_id: str) -> Optional[str]:
        """Get the URL for a running service"""
        service = self.services.get(service_id)
        if not service or service["status"] != "running":
            return None
        
        # For now, assume services run on their first port
        ports = service.get("ports", [])
        if ports:
            port_mapping = ports[0]
            if ":" in port_mapping:
                host_port = port_mapping.split(":")[0]
                return f"http://localhost:{host_port}"
        
        # Default to container name and port 80
        container_name = f"wakedock-{service['name']}"
        return f"http://{container_name}:80"
    
    async def update_service_access(self, service_id: str):
        """Update last accessed time for a service"""
        service = self.services.get(service_id)
        if service:
            service["last_accessed"] = datetime.now()
    
    async def get_service_stats(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Get resource usage statistics for a service"""
        service = self.services.get(service_id)
        if not service or not service.get("container_id"):
            return None
        
        try:
            container = self.client.containers.get(service["container_id"])
            stats = container.stats(stream=False)
            
            # Calculate CPU percentage
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
            cpu_percent = (cpu_delta / system_delta) * len(stats["cpu_stats"]["cpu_usage"]["percpu_usage"]) * 100
            
            # Calculate memory usage
            memory_usage = stats["memory_stats"]["usage"]
            memory_limit = stats["memory_stats"]["limit"]
            memory_percent = (memory_usage / memory_limit) * 100
            
            resource_stats = {
                "cpu_percent": round(cpu_percent, 2),
                "memory_usage": memory_usage,
                "memory_limit": memory_limit,
                "memory_percent": round(memory_percent, 2),
                "network_rx": stats["networks"]["eth0"]["rx_bytes"] if "networks" in stats else 0,
                "network_tx": stats["networks"]["eth0"]["tx_bytes"] if "networks" in stats else 0,
                "timestamp": datetime.now()
            }
            
            service["resource_usage"] = resource_stats
            return resource_stats
            
        except Exception as e:
            logger.error(f"Failed to get stats for service {service['name']}: {str(e)}")
            return None
