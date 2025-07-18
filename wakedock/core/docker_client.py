"""
Docker client wrapper for WakeDock
"""

import docker
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class DockerClient:
    """Docker client wrapper"""
    
    def __init__(self):
        try:
            self.client = docker.from_env()
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            self.client = None
    
    def is_connected(self) -> bool:
        """Check if Docker client is connected"""
        if not self.client:
            return False
        try:
            self.client.ping()
            return True
        except Exception:
            return False
    
    def get_containers(self, all: bool = False) -> List[Dict[str, Any]]:
        """Get list of containers"""
        if not self.client:
            return []
        
        try:
            containers = self.client.containers.list(all=all)
            return [
                {
                    'id': container.id,
                    'name': container.name,
                    'image': container.image.tags[0] if container.image.tags else 'unknown',
                    'status': container.status,
                    'created': container.attrs['Created'],
                    'ports': container.attrs.get('NetworkSettings', {}).get('Ports', {}),
                    'labels': container.labels,
                }
                for container in containers
            ]
        except Exception as e:
            logger.error(f"Error getting containers: {e}")
            return []
    
    def get_container(self, container_id: str) -> Optional[Dict[str, Any]]:
        """Get container by ID"""
        if not self.client:
            return None
        
        try:
            container = self.client.containers.get(container_id)
            return {
                'id': container.id,
                'name': container.name,
                'image': container.image.tags[0] if container.image.tags else 'unknown',
                'status': container.status,
                'created': container.attrs['Created'],
                'ports': container.attrs.get('NetworkSettings', {}).get('Ports', {}),
                'labels': container.labels,
                'stats': container.stats(stream=False),
            }
        except Exception as e:
            logger.error(f"Error getting container {container_id}: {e}")
            return None
    
    def get_images(self) -> List[Dict[str, Any]]:
        """Get list of images"""
        if not self.client:
            return []
        
        try:
            images = self.client.images.list()
            return [
                {
                    'id': image.id,
                    'tags': image.tags,
                    'created': image.attrs['Created'],
                    'size': image.attrs['Size'],
                    'labels': image.labels,
                }
                for image in images
            ]
        except Exception as e:
            logger.error(f"Error getting images: {e}")
            return []
    
    def get_networks(self) -> List[Dict[str, Any]]:
        """Get list of networks"""
        if not self.client:
            return []
        
        try:
            networks = self.client.networks.list()
            return [
                {
                    'id': network.id,
                    'name': network.name,
                    'driver': network.attrs['Driver'],
                    'created': network.attrs['Created'],
                    'containers': list(network.attrs.get('Containers', {}).keys()),
                }
                for network in networks
            ]
        except Exception as e:
            logger.error(f"Error getting networks: {e}")
            return []
    
    def get_volumes(self) -> List[Dict[str, Any]]:
        """Get list of volumes"""
        if not self.client:
            return []
        
        try:
            volumes = self.client.volumes.list()
            return [
                {
                    'name': volume.name,
                    'driver': volume.attrs['Driver'],
                    'created': volume.attrs['CreatedAt'],
                    'mountpoint': volume.attrs['Mountpoint'],
                    'labels': volume.attrs.get('Labels', {}),
                }
                for volume in volumes
            ]
        except Exception as e:
            logger.error(f"Error getting volumes: {e}")
            return []
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get Docker system info"""
        if not self.client:
            return {}
        
        try:
            info = self.client.info()
            return {
                'version': info.get('ServerVersion', 'unknown'),
                'containers': info.get('Containers', 0),
                'images': info.get('Images', 0),
                'kernel_version': info.get('KernelVersion', 'unknown'),
                'operating_system': info.get('OperatingSystem', 'unknown'),
                'architecture': info.get('Architecture', 'unknown'),
                'cpus': info.get('NCPU', 0),
                'memory': info.get('MemTotal', 0),
                'storage_driver': info.get('StorageDriver', 'unknown'),
            }
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return {}


# Global Docker client instance
docker_client = DockerClient()
