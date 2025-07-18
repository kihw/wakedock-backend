"""
Controller for Docker services management
"""

from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status

from wakedock.controllers.base_controller import BaseController
from wakedock.repositories.services_repository import ServicesRepository
from wakedock.models.stack import StackInfo, StackStatus, StackType
from wakedock.services.docker_service import DockerService
from wakedock.validators.services_validator import ServicesValidator


class ServicesController(BaseController[StackInfo]):
    """Controller for managing Docker services"""
    
    def __init__(
        self, 
        repository: ServicesRepository, 
        docker_service: DockerService,
        validator: ServicesValidator
    ):
        super().__init__(repository)
        self.docker_service = docker_service
        self.validator = validator
    
    async def get_all_services(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[StackStatus] = None,
        service_type: Optional[StackType] = None,
        search: Optional[str] = None
    ) -> List[StackInfo]:
        """Get all services with optional filtering"""
        try:
            # Advanced search if filters are provided
            if status or service_type or search:
                statuses = [status] if status else None
                types = [service_type] if service_type else None
                
                return await self.repository.advanced_search(
                    name_pattern=search,
                    statuses=statuses,
                    types=types,
                    skip=skip,
                    limit=limit
                )
            
            # Get all services
            return await self.repository.get_all(skip=skip, limit=limit)
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve services: {str(e)}"
            )
    
    async def get_service_by_id(self, service_id: str) -> StackInfo:
        """Get a service by ID"""
        return await self.get_by_id(service_id)
    
    async def get_service_by_name(self, name: str) -> Optional[StackInfo]:
        """Get a service by name"""
        try:
            return await self.repository.get_by_name(name)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve service: {str(e)}"
            )
    
    async def create_service(self, service_data: Dict[str, Any]) -> StackInfo:
        """Create a new service"""
        try:
            # Validate service data
            if not self.validator.validate(service_data):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Validation failed: {self.validator.get_errors()}"
                )
            
            # Check if service name already exists
            if await self.repository.exists_by_name(service_data.get('name')):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Service with name '{service_data.get('name')}' already exists"
                )
            
            # Create the service
            service = await self.create(service_data)
            
            # Initialize the service in Docker
            await self.docker_service.create_service(service)
            
            return service
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create service: {str(e)}"
            )
    
    async def update_service(self, service_id: str, update_data: Dict[str, Any]) -> StackInfo:
        """Update a service"""
        try:
            # Validate update data
            if not self.validator.validate_update(update_data):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Validation failed: {self.validator.get_errors()}"
                )
            
            # Update the service
            service = await self.update(service_id, update_data)
            
            # Update the service in Docker if needed
            await self.docker_service.update_service(service)
            
            return service
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update service: {str(e)}"
            )
    
    async def delete_service(self, service_id: str, force: bool = False) -> bool:
        """Delete a service"""
        try:
            # Get the service first
            service = await self.get_by_id(service_id)
            
            # Stop the service in Docker first
            await self.docker_service.stop_service(service)
            
            # Remove from Docker if force is True
            if force:
                await self.docker_service.remove_service(service)
            
            # Delete from database
            return await self.delete(service_id)
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete service: {str(e)}"
            )
    
    async def start_service(self, service_id: str) -> StackInfo:
        """Start a service"""
        try:
            service = await self.get_by_id(service_id)
            
            # Start the service in Docker
            await self.docker_service.start_service(service)
            
            # Update status in database
            updated_service = await self.repository.update_service_status(
                service_id, StackStatus.RUNNING
            )
            
            return updated_service
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to start service: {str(e)}"
            )
    
    async def stop_service(self, service_id: str) -> StackInfo:
        """Stop a service"""
        try:
            service = await self.get_by_id(service_id)
            
            # Stop the service in Docker
            await self.docker_service.stop_service(service)
            
            # Update status in database
            updated_service = await self.repository.update_service_status(
                service_id, StackStatus.STOPPED
            )
            
            return updated_service
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to stop service: {str(e)}"
            )
    
    async def restart_service(self, service_id: str) -> StackInfo:
        """Restart a service"""
        try:
            service = await self.get_by_id(service_id)
            
            # Restart the service in Docker
            await self.docker_service.restart_service(service)
            
            # Update status in database
            updated_service = await self.repository.update_service_status(
                service_id, StackStatus.RUNNING
            )
            
            return updated_service
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to restart service: {str(e)}"
            )
    
    async def rebuild_service(self, service_id: str) -> StackInfo:
        """Rebuild a service"""
        try:
            service = await self.get_by_id(service_id)
            
            # Rebuild the service in Docker
            await self.docker_service.rebuild_service(service)
            
            # Update status in database
            updated_service = await self.repository.update_service_status(
                service_id, StackStatus.RUNNING
            )
            
            return updated_service
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to rebuild service: {str(e)}"
            )
    
    async def get_service_logs(self, service_id: str, lines: int = 100) -> List[str]:
        """Get service logs"""
        try:
            service = await self.get_by_id(service_id)
            return await self.docker_service.get_service_logs(service, lines)
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get service logs: {str(e)}"
            )
    
    async def get_service_stats(self, service_id: str) -> Dict[str, Any]:
        """Get service statistics"""
        try:
            service = await self.get_by_id(service_id)
            return await self.docker_service.get_service_stats(service)
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get service stats: {str(e)}"
            )
    
    async def get_services_summary(self) -> Dict[str, Any]:
        """Get services summary"""
        try:
            return await self.repository.get_services_summary()
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get services summary: {str(e)}"
            )
    
    async def bulk_action(self, service_ids: List[str], action: str) -> Dict[str, Any]:
        """Perform bulk action on multiple services"""
        try:
            results = {
                "success": [],
                "failed": []
            }
            
            for service_id in service_ids:
                try:
                    if action == "start":
                        await self.start_service(service_id)
                    elif action == "stop":
                        await self.stop_service(service_id)
                    elif action == "restart":
                        await self.restart_service(service_id)
                    elif action == "delete":
                        await self.delete_service(service_id)
                    else:
                        raise ValueError(f"Unknown action: {action}")
                    
                    results["success"].append(service_id)
                    
                except Exception as e:
                    results["failed"].append({
                        "service_id": service_id,
                        "error": str(e)
                    })
            
            return results
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to perform bulk action: {str(e)}"
            )
    
    # Override validation hooks
    async def validate_create_data(self, data: Dict[str, Any]) -> None:
        """Validate data before creating a service"""
        if not self.validator.validate(data):
            raise ValueError(f"Service validation failed: {self.validator.get_errors()}")
    
    async def validate_update_data(self, id: str, data: Dict[str, Any]) -> None:
        """Validate data before updating a service"""
        if not self.validator.validate_update(data):
            raise ValueError(f"Service update validation failed: {self.validator.get_errors()}")
    
    async def pre_create_hook(self, data: Dict[str, Any]) -> None:
        """Hook called before creating a service"""
        # Set default values
        data.setdefault('type', StackType.COMPOSE)
        data.setdefault('status', StackStatus.STOPPED)
    
    async def post_create_hook(self, service: StackInfo) -> None:
        """Hook called after creating a service"""
        # Log service creation
        self.logger.info(f"Service '{service.name}' created with ID: {service.id}")
    
    async def pre_delete_hook(self, id: str) -> None:
        """Hook called before deleting a service"""
        # Check if service is running
        service = await self.repository.get_by_id(id)
        if service and service.status == StackStatus.RUNNING:
            raise ValueError("Cannot delete a running service. Stop it first.")
    
    async def post_delete_hook(self, id: str) -> None:
        """Hook called after deleting a service"""
        # Log service deletion
        self.logger.info(f"Service with ID '{id}' deleted successfully")
