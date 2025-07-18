"""
Container service for Docker operations - MVC Architecture
"""

import asyncio
import json
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

import docker
from docker.errors import DockerException, NotFound, APIError

from wakedock.core.exceptions import ContainerOperationError, ContainerNotFoundError
from wakedock.services.base_service import BaseService

import logging
logger = logging.getLogger(__name__)


class ContainerService(BaseService):
    """Service for Docker container operations"""
    
    def __init__(self):
        super().__init__()
        try:
            self.client = docker.from_env()
            self.api_client = docker.APIClient()
        except DockerException as e:
            logger.error(f"Failed to connect to Docker daemon: {str(e)}")
            raise ContainerOperationError(f"Docker connection failed: {str(e)}")
    
    async def list_containers(self, all_containers: bool = True) -> List[Dict[str, Any]]:
        """List all containers"""
        try:
            containers = await asyncio.to_thread(
                self.client.containers.list, 
                all=all_containers
            )
            
            container_list = []
            for container in containers:
                container_info = {
                    'Id': container.id,
                    'Name': container.name,
                    'Status': container.status,
                    'State': container.attrs['State'],
                    'Config': container.attrs['Config'],
                    'Created': container.attrs['Created'],
                    'Image': container.image.tags[0] if container.image.tags else 'unknown',
                    'Labels': container.labels,
                    'Ports': container.ports,
                    'Mounts': container.attrs['Mounts']
                }
                container_list.append(container_info)
            
            logger.info(f"Listed {len(container_list)} containers")
            return container_list
            
        except DockerException as e:
            logger.error(f"Error listing containers: {str(e)}")
            raise ContainerOperationError(f"Failed to list containers: {str(e)}")
    
    async def get_container_info(self, container_id: str) -> Dict[str, Any]:
        """Get detailed container information"""
        try:
            container = await asyncio.to_thread(
                self.client.containers.get, 
                container_id
            )
            
            info = {
                'Id': container.id,
                'Name': container.name,
                'Status': container.status,
                'State': container.attrs['State'],
                'Config': container.attrs['Config'],
                'Created': container.attrs['Created'],
                'Image': container.image.tags[0] if container.image.tags else 'unknown',
                'Labels': container.labels,
                'Ports': container.ports,
                'Mounts': container.attrs['Mounts'],
                'NetworkSettings': container.attrs['NetworkSettings'],
                'RestartCount': container.attrs['RestartCount'],
                'Platform': container.attrs.get('Platform', 'unknown')
            }
            
            logger.debug(f"Retrieved info for container {container_id}")
            return info
            
        except NotFound:
            logger.error(f"Container {container_id} not found")
            raise ContainerNotFoundError(f"Container {container_id} not found")
        except DockerException as e:
            logger.error(f"Error getting container info: {str(e)}")
            raise ContainerOperationError(f"Failed to get container info: {str(e)}")
    
    async def create_container(self, container_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new container"""
        try:
            # Prepare container configuration
            config = {
                'image': container_data['image'],
                'name': container_data.get('name'),
                'command': container_data.get('command'),
                'environment': container_data.get('environment', {}),
                'ports': container_data.get('ports', {}),
                'volumes': container_data.get('volumes', {}),
                'labels': container_data.get('labels', {}),
                'restart_policy': container_data.get('restart_policy', {'Name': 'no'}),
                'detach': True
            }
            
            # Create container
            container = await asyncio.to_thread(
                self.client.containers.create, 
                **config
            )
            
            container_info = {
                'Id': container.id,
                'Name': container.name,
                'Status': container.status,
                'Created': datetime.utcnow().isoformat(),
                'Image': container_data['image']
            }
            
            logger.info(f"Created container: {container.name} ({container.id})")
            return container_info
            
        except DockerException as e:
            logger.error(f"Error creating container: {str(e)}")
            raise ContainerOperationError(f"Failed to create container: {str(e)}")
    
    async def start_container(self, container_id: str) -> Dict[str, Any]:
        """Start a container"""
        try:
            container = await asyncio.to_thread(
                self.client.containers.get, 
                container_id
            )
            
            await asyncio.to_thread(container.start)
            
            result = {
                'Id': container.id,
                'Name': container.name,
                'Status': 'running',
                'Started': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Started container: {container.name} ({container_id})")
            return result
            
        except NotFound:
            logger.error(f"Container {container_id} not found")
            raise ContainerNotFoundError(f"Container {container_id} not found")
        except DockerException as e:
            logger.error(f"Error starting container: {str(e)}")
            raise ContainerOperationError(f"Failed to start container: {str(e)}")
    
    async def stop_container(self, container_id: str, timeout: int = 10) -> Dict[str, Any]:
        """Stop a container"""
        try:
            container = await asyncio.to_thread(
                self.client.containers.get, 
                container_id
            )
            
            await asyncio.to_thread(container.stop, timeout=timeout)
            
            result = {
                'Id': container.id,
                'Name': container.name,
                'Status': 'stopped',
                'Stopped': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Stopped container: {container.name} ({container_id})")
            return result
            
        except NotFound:
            logger.error(f"Container {container_id} not found")
            raise ContainerNotFoundError(f"Container {container_id} not found")
        except DockerException as e:
            logger.error(f"Error stopping container: {str(e)}")
            raise ContainerOperationError(f"Failed to stop container: {str(e)}")
    
    async def restart_container(self, container_id: str, timeout: int = 10) -> Dict[str, Any]:
        """Restart a container"""
        try:
            container = await asyncio.to_thread(
                self.client.containers.get, 
                container_id
            )
            
            await asyncio.to_thread(container.restart, timeout=timeout)
            
            result = {
                'Id': container.id,
                'Name': container.name,
                'Status': 'running',
                'Restarted': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Restarted container: {container.name} ({container_id})")
            return result
            
        except NotFound:
            logger.error(f"Container {container_id} not found")
            raise ContainerNotFoundError(f"Container {container_id} not found")
        except DockerException as e:
            logger.error(f"Error restarting container: {str(e)}")
            raise ContainerOperationError(f"Failed to restart container: {str(e)}")
    
    async def remove_container(self, container_id: str, force: bool = False) -> Dict[str, Any]:
        """Remove a container"""
        try:
            container = await asyncio.to_thread(
                self.client.containers.get, 
                container_id
            )
            
            container_name = container.name
            
            await asyncio.to_thread(container.remove, force=force)
            
            result = {
                'Id': container_id,
                'Name': container_name,
                'Removed': True,
                'Timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Removed container: {container_name} ({container_id})")
            return result
            
        except NotFound:
            logger.error(f"Container {container_id} not found")
            raise ContainerNotFoundError(f"Container {container_id} not found")
        except DockerException as e:
            logger.error(f"Error removing container: {str(e)}")
            raise ContainerOperationError(f"Failed to remove container: {str(e)}")
    
    async def pause_container(self, container_id: str) -> Dict[str, Any]:
        """Pause a container"""
        try:
            container = await asyncio.to_thread(
                self.client.containers.get, 
                container_id
            )
            
            await asyncio.to_thread(container.pause)
            
            result = {
                'Id': container.id,
                'Name': container.name,
                'Status': 'paused',
                'Paused': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Paused container: {container.name} ({container_id})")
            return result
            
        except NotFound:
            logger.error(f"Container {container_id} not found")
            raise ContainerNotFoundError(f"Container {container_id} not found")
        except DockerException as e:
            logger.error(f"Error pausing container: {str(e)}")
            raise ContainerOperationError(f"Failed to pause container: {str(e)}")
    
    async def unpause_container(self, container_id: str) -> Dict[str, Any]:
        """Unpause a container"""
        try:
            container = await asyncio.to_thread(
                self.client.containers.get, 
                container_id
            )
            
            await asyncio.to_thread(container.unpause)
            
            result = {
                'Id': container.id,
                'Name': container.name,
                'Status': 'running',
                'Unpaused': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Unpaused container: {container.name} ({container_id})")
            return result
            
        except NotFound:
            logger.error(f"Container {container_id} not found")
            raise ContainerNotFoundError(f"Container {container_id} not found")
        except DockerException as e:
            logger.error(f"Error unpausing container: {str(e)}")
            raise ContainerOperationError(f"Failed to unpause container: {str(e)}")
    
    async def get_container_logs(
        self, 
        container_id: str, 
        limit: int = 100, 
        follow: bool = False
    ) -> List[str]:
        """Get container logs"""
        try:
            container = await asyncio.to_thread(
                self.client.containers.get, 
                container_id
            )
            
            logs = await asyncio.to_thread(
                container.logs, 
                tail=limit, 
                follow=follow,
                stdout=True,
                stderr=True,
                timestamps=True
            )
            
            # Parse logs into list of strings
            log_lines = []
            if isinstance(logs, bytes):
                log_lines = logs.decode('utf-8').split('\n')
            else:
                log_lines = str(logs).split('\n')
            
            # Filter out empty lines
            log_lines = [line.strip() for line in log_lines if line.strip()]
            
            logger.debug(f"Retrieved {len(log_lines)} log lines for container {container_id}")
            return log_lines
            
        except NotFound:
            logger.error(f"Container {container_id} not found")
            raise ContainerNotFoundError(f"Container {container_id} not found")
        except DockerException as e:
            logger.error(f"Error getting container logs: {str(e)}")
            raise ContainerOperationError(f"Failed to get container logs: {str(e)}")
    
    async def get_container_stats(self, container_id: str) -> Dict[str, Any]:
        """Get container statistics"""
        try:
            container = await asyncio.to_thread(
                self.client.containers.get, 
                container_id
            )
            
            stats = await asyncio.to_thread(
                container.stats, 
                stream=False
            )
            
            # Parse and format stats
            formatted_stats = self._format_container_stats(stats)
            
            logger.debug(f"Retrieved stats for container {container_id}")
            return formatted_stats
            
        except NotFound:
            logger.error(f"Container {container_id} not found")
            raise ContainerNotFoundError(f"Container {container_id} not found")
        except DockerException as e:
            logger.error(f"Error getting container stats: {str(e)}")
            raise ContainerOperationError(f"Failed to get container stats: {str(e)}")
    
    async def execute_command(
        self, 
        container_id: str, 
        command: str, 
        workdir: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute command in container"""
        try:
            container = await asyncio.to_thread(
                self.client.containers.get, 
                container_id
            )
            
            exec_result = await asyncio.to_thread(
                container.exec_run, 
                command, 
                workdir=workdir
            )
            
            result = {
                'exit_code': exec_result.exit_code,
                'output': exec_result.output.decode('utf-8') if exec_result.output else '',
                'command': command,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Executed command in container {container_id}: {command}")
            return result
            
        except NotFound:
            logger.error(f"Container {container_id} not found")
            raise ContainerNotFoundError(f"Container {container_id} not found")
        except DockerException as e:
            logger.error(f"Error executing command: {str(e)}")
            raise ContainerOperationError(f"Failed to execute command: {str(e)}")
    
    async def get_system_stats(self) -> Dict[str, Any]:
        """Get Docker system statistics"""
        try:
            # Get system info
            system_info = await asyncio.to_thread(self.client.info)
            
            # Get system events (last 100)
            events = await asyncio.to_thread(
                self.client.events, 
                decode=True, 
                since=datetime.utcnow().timestamp() - 3600  # Last hour
            )
            
            # Get system df
            df_info = await asyncio.to_thread(self.client.df)
            
            stats = {
                'system_info': {
                    'containers': system_info.get('Containers', 0),
                    'containers_running': system_info.get('ContainersRunning', 0),
                    'containers_paused': system_info.get('ContainersPaused', 0),
                    'containers_stopped': system_info.get('ContainersStopped', 0),
                    'images': system_info.get('Images', 0),
                    'server_version': system_info.get('ServerVersion', 'unknown'),
                    'total_memory': system_info.get('MemTotal', 0),
                    'ncpu': system_info.get('NCPU', 0)
                },
                'disk_usage': {
                    'images': df_info.get('Images', []),
                    'containers': df_info.get('Containers', []),
                    'volumes': df_info.get('Volumes', [])
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.debug("Retrieved Docker system stats")
            return stats
            
        except DockerException as e:
            logger.error(f"Error getting system stats: {str(e)}")
            raise ContainerOperationError(f"Failed to get system stats: {str(e)}")
    
    async def pull_image(self, image_name: str) -> Dict[str, Any]:
        """Pull Docker image"""
        try:
            image = await asyncio.to_thread(
                self.client.images.pull, 
                image_name
            )
            
            result = {
                'image_id': image.id,
                'image_name': image_name,
                'tags': image.tags,
                'size': image.attrs['Size'],
                'pulled': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Pulled image: {image_name}")
            return result
            
        except DockerException as e:
            logger.error(f"Error pulling image: {str(e)}")
            raise ContainerOperationError(f"Failed to pull image: {str(e)}")
    
    async def list_images(self) -> List[Dict[str, Any]]:
        """List Docker images"""
        try:
            images = await asyncio.to_thread(self.client.images.list)
            
            image_list = []
            for image in images:
                image_info = {
                    'id': image.id,
                    'tags': image.tags,
                    'size': image.attrs['Size'],
                    'created': image.attrs['Created']
                }
                image_list.append(image_info)
            
            logger.info(f"Listed {len(image_list)} images")
            return image_list
            
        except DockerException as e:
            logger.error(f"Error listing images: {str(e)}")
            raise ContainerOperationError(f"Failed to list images: {str(e)}")
    
    def _format_container_stats(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Format container statistics"""
        try:
            # CPU stats
            cpu_stats = stats.get('cpu_stats', {})
            precpu_stats = stats.get('precpu_stats', {})
            
            cpu_usage = 0.0
            if cpu_stats and precpu_stats:
                cpu_delta = cpu_stats['cpu_usage']['total_usage'] - precpu_stats['cpu_usage']['total_usage']
                system_delta = cpu_stats['system_cpu_usage'] - precpu_stats['system_cpu_usage']
                
                if system_delta > 0:
                    cpu_usage = (cpu_delta / system_delta) * 100.0
            
            # Memory stats
            memory_stats = stats.get('memory_stats', {})
            memory_usage = memory_stats.get('usage', 0)
            memory_limit = memory_stats.get('limit', 0)
            
            # Network stats
            networks = stats.get('networks', {})
            network_rx = sum(net.get('rx_bytes', 0) for net in networks.values())
            network_tx = sum(net.get('tx_bytes', 0) for net in networks.values())
            
            # Block I/O stats
            blkio_stats = stats.get('blkio_stats', {})
            disk_read = 0
            disk_write = 0
            
            for io_stat in blkio_stats.get('io_service_bytes_recursive', []):
                if io_stat['op'] == 'Read':
                    disk_read += io_stat['value']
                elif io_stat['op'] == 'Write':
                    disk_write += io_stat['value']
            
            formatted_stats = {
                'cpu_usage': round(cpu_usage, 2),
                'memory_usage': memory_usage,
                'memory_limit': memory_limit,
                'memory_percentage': round((memory_usage / memory_limit) * 100, 2) if memory_limit > 0 else 0,
                'network_rx': network_rx,
                'network_tx': network_tx,
                'disk_read': disk_read,
                'disk_write': disk_write,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            return formatted_stats
            
        except Exception as e:
            logger.error(f"Error formatting container stats: {str(e)}")
            return {
                'cpu_usage': 0.0,
                'memory_usage': 0,
                'memory_limit': 0,
                'memory_percentage': 0.0,
                'network_rx': 0,
                'network_tx': 0,
                'disk_read': 0,
                'disk_write': 0,
                'timestamp': datetime.utcnow().isoformat()
            }
