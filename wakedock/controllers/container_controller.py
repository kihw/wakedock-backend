"""
Container controller for business logic - MVC Architecture
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import HTTPException, status

from wakedock.controllers.base_controller import BaseController
from wakedock.repositories.container_repository import ContainerRepository
from wakedock.validators.container_validator import ContainerValidator
from wakedock.services.container_service import ContainerService
from wakedock.core.exceptions import ContainerNotFoundError, ContainerOperationError, ValidationError

import logging
logger = logging.getLogger(__name__)


class ContainerController(BaseController):
    """Controller for container business logic"""
    
    def __init__(
        self,
        container_repository: ContainerRepository,
        container_validator: ContainerValidator,
        container_service: ContainerService
    ):
        super().__init__(container_repository, container_validator)
        self.container_service = container_service
    
    async def get_all_containers(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        image: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get all containers with optional filters"""
        try:
            # Validate parameters
            await self.validator.validate_pagination(limit, offset)
            if status:
                await self.validator.validate_container_status(status)
            
            # Get containers from repository
            containers = await self.repository.get_all(limit=limit, offset=offset)
            
            # Apply filters
            if status:
                containers = [c for c in containers if c.status == status]
            if image:
                containers = [c for c in containers if image.lower() in c.image.lower()]
            
            # Get total count
            total_count = await self.repository.count()
            
            return {
                "containers": containers,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total_count
            }
            
        except ValidationError as e:
            logger.error(f"Validation error in get_all_containers: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error getting all containers: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve containers"
            )
    
    async def get_container_by_id(self, container_id: str) -> Dict[str, Any]:
        """Get container by ID"""
        try:
            # Validate container ID
            await self.validator.validate_container_id(container_id)
            
            # Get container from repository
            container = await self.repository.get_by_container_id(container_id)
            if not container:
                raise ContainerNotFoundError(f"Container {container_id} not found")
            
            # Get additional container info from Docker service
            docker_info = await self.container_service.get_container_info(container_id)
            
            return {
                "container": container,
                "docker_info": docker_info,
                "status": container.status,
                "uptime": self._calculate_uptime(container.created_at)
            }
            
        except ContainerNotFoundError as e:
            logger.error(f"Container not found: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        except ValidationError as e:
            logger.error(f"Validation error in get_container_by_id: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error getting container by ID: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve container"
            )
    
    async def create_container(self, container_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new container"""
        try:
            # Validate container data
            await self.validator.validate_container_creation(container_data)
            
            # Create container in Docker
            docker_container = await self.container_service.create_container(container_data)
            
            # Create container record in database
            container = await self.repository.create_container(
                container_id=docker_container['Id'],
                name=container_data.get('name'),
                image=container_data.get('image'),
                command=container_data.get('command', ''),
                environment=container_data.get('environment', {}),
                ports=container_data.get('ports', {}),
                volumes=container_data.get('volumes', {}),
                status='created',
                created_at=datetime.utcnow()
            )
            
            logger.info(f"Created container: {container.name} ({container.container_id})")
            
            return {
                "container": container,
                "docker_info": docker_container,
                "created": True
            }
            
        except ValidationError as e:
            logger.error(f"Validation error in create_container: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except ContainerOperationError as e:
            logger.error(f"Container operation error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error creating container: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create container"
            )
    
    async def start_container(self, container_id: str) -> Dict[str, Any]:
        """Start container"""
        try:
            # Validate container ID
            await self.validator.validate_container_id(container_id)
            
            # Get container from repository
            container = await self.repository.get_by_container_id(container_id)
            if not container:
                raise ContainerNotFoundError(f"Container {container_id} not found")
            
            # Start container in Docker
            result = await self.container_service.start_container(container_id)
            
            # Update container status
            await self.repository.update_container_status(container_id, 'running')
            
            logger.info(f"Started container: {container.name} ({container_id})")
            
            return {
                "container": container,
                "started": True,
                "status": "running"
            }
            
        except ContainerNotFoundError as e:
            logger.error(f"Container not found: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        except ValidationError as e:
            logger.error(f"Validation error in start_container: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except ContainerOperationError as e:
            logger.error(f"Container operation error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error starting container: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to start container"
            )
    
    async def stop_container(self, container_id: str) -> Dict[str, Any]:
        """Stop container"""
        try:
            # Validate container ID
            await self.validator.validate_container_id(container_id)
            
            # Get container from repository
            container = await self.repository.get_by_container_id(container_id)
            if not container:
                raise ContainerNotFoundError(f"Container {container_id} not found")
            
            # Stop container in Docker
            result = await self.container_service.stop_container(container_id)
            
            # Update container status
            await self.repository.update_container_status(container_id, 'stopped')
            
            logger.info(f"Stopped container: {container.name} ({container_id})")
            
            return {
                "container": container,
                "stopped": True,
                "status": "stopped"
            }
            
        except ContainerNotFoundError as e:
            logger.error(f"Container not found: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        except ValidationError as e:
            logger.error(f"Validation error in stop_container: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except ContainerOperationError as e:
            logger.error(f"Container operation error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error stopping container: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to stop container"
            )
    
    async def restart_container(self, container_id: str) -> Dict[str, Any]:
        """Restart container"""
        try:
            # Validate container ID
            await self.validator.validate_container_id(container_id)
            
            # Get container from repository
            container = await self.repository.get_by_container_id(container_id)
            if not container:
                raise ContainerNotFoundError(f"Container {container_id} not found")
            
            # Restart container in Docker
            result = await self.container_service.restart_container(container_id)
            
            # Update container status
            await self.repository.update_container_status(container_id, 'running')
            
            logger.info(f"Restarted container: {container.name} ({container_id})")
            
            return {
                "container": container,
                "restarted": True,
                "status": "running"
            }
            
        except ContainerNotFoundError as e:
            logger.error(f"Container not found: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        except ValidationError as e:
            logger.error(f"Validation error in restart_container: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except ContainerOperationError as e:
            logger.error(f"Container operation error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error restarting container: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to restart container"
            )
    
    async def remove_container(self, container_id: str, force: bool = False) -> Dict[str, Any]:
        """Remove container"""
        try:
            # Validate container ID
            await self.validator.validate_container_id(container_id)
            
            # Get container from repository
            container = await self.repository.get_by_container_id(container_id)
            if not container:
                raise ContainerNotFoundError(f"Container {container_id} not found")
            
            # Remove container from Docker
            result = await self.container_service.remove_container(container_id, force)
            
            # Remove container record from database
            await self.repository.delete(container.id)
            
            logger.info(f"Removed container: {container.name} ({container_id})")
            
            return {
                "container": container,
                "removed": True
            }
            
        except ContainerNotFoundError as e:
            logger.error(f"Container not found: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        except ValidationError as e:
            logger.error(f"Validation error in remove_container: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except ContainerOperationError as e:
            logger.error(f"Container operation error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error removing container: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to remove container"
            )
    
    async def get_container_logs(
        self,
        container_id: str,
        limit: int = 100,
        follow: bool = False,
        level: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get container logs"""
        try:
            # Validate parameters
            await self.validator.validate_container_id(container_id)
            await self.validator.validate_pagination(limit, 0)
            
            # Get container from repository
            container = await self.repository.get_by_container_id(container_id)
            if not container:
                raise ContainerNotFoundError(f"Container {container_id} not found")
            
            # Get logs from Docker service
            docker_logs = await self.container_service.get_container_logs(
                container_id, limit, follow
            )
            
            # Get logs from database
            db_logs = await self.repository.get_container_logs(container_id, limit, level)
            
            return {
                "container": container,
                "docker_logs": docker_logs,
                "db_logs": db_logs,
                "total_logs": len(docker_logs) + len(db_logs)
            }
            
        except ContainerNotFoundError as e:
            logger.error(f"Container not found: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        except ValidationError as e:
            logger.error(f"Validation error in get_container_logs: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error getting container logs: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve container logs"
            )
    
    async def get_container_stats(self, container_id: str) -> Dict[str, Any]:
        """Get container statistics"""
        try:
            # Validate container ID
            await self.validator.validate_container_id(container_id)
            
            # Get container from repository
            container = await self.repository.get_by_container_id(container_id)
            if not container:
                raise ContainerNotFoundError(f"Container {container_id} not found")
            
            # Get stats from Docker service
            docker_stats = await self.container_service.get_container_stats(container_id)
            
            # Get metrics history from database
            metrics_history = await self.repository.get_container_metrics_history(container_id)
            
            return {
                "container": container,
                "current_stats": docker_stats,
                "metrics_history": metrics_history,
                "uptime": self._calculate_uptime(container.created_at)
            }
            
        except ContainerNotFoundError as e:
            logger.error(f"Container not found: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        except ValidationError as e:
            logger.error(f"Validation error in get_container_stats: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error getting container stats: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve container statistics"
            )
    
    async def search_containers(
        self,
        query: str,
        status: Optional[str] = None,
        image: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Search containers"""
        try:
            # Validate parameters
            await self.validator.validate_search_query(query)
            await self.validator.validate_pagination(limit, offset)
            if status:
                await self.validator.validate_container_status(status)
            
            # Search containers in repository
            containers = await self.repository.search_containers(
                query, status, image, limit, offset
            )
            
            # Get total count for pagination
            total_count = len(containers)
            
            return {
                "containers": containers,
                "total_count": total_count,
                "query": query,
                "filters": {
                    "status": status,
                    "image": image
                },
                "limit": limit,
                "offset": offset
            }
            
        except ValidationError as e:
            logger.error(f"Validation error in search_containers: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error searching containers: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to search containers"
            )
    
    async def get_container_statistics(self) -> Dict[str, Any]:
        """Get overall container statistics"""
        try:
            # Get statistics from repository
            stats = await self.repository.get_container_statistics()
            
            # Get additional stats from Docker service
            docker_stats = await self.container_service.get_system_stats()
            
            return {
                "database_stats": stats,
                "docker_stats": docker_stats,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting container statistics: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve container statistics"
            )
    
    async def sync_containers(self) -> Dict[str, Any]:
        """Synchronize containers with Docker daemon"""
        try:
            # Get containers from Docker service
            docker_containers = await self.container_service.list_containers()
            
            # Get containers from database
            db_containers = await self.repository.get_all()
            
            # Sync containers
            synced_count = 0
            created_count = 0
            updated_count = 0
            
            for docker_container in docker_containers:
                container_id = docker_container['Id']
                
                # Check if container exists in database
                db_container = await self.repository.get_by_container_id(container_id)
                
                if db_container:
                    # Update existing container
                    await self.repository.update_container_status(
                        container_id, 
                        docker_container['State']['Status']
                    )
                    updated_count += 1
                else:
                    # Create new container record
                    await self.repository.create_container(
                        container_id=container_id,
                        name=docker_container['Name'],
                        image=docker_container['Config']['Image'],
                        command=docker_container['Config']['Cmd'],
                        status=docker_container['State']['Status'],
                        created_at=datetime.utcnow()
                    )
                    created_count += 1
                
                synced_count += 1
            
            logger.info(f"Synchronized {synced_count} containers")
            
            return {
                "synced_count": synced_count,
                "created_count": created_count,
                "updated_count": updated_count,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error synchronizing containers: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to synchronize containers"
            )
    
    def _calculate_uptime(self, created_at: datetime) -> str:
        """Calculate container uptime"""
        if not created_at:
            return "Unknown"
        
        uptime = datetime.utcnow() - created_at
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
