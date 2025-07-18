"""
Container routes for FastAPI - MVC Architecture
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession

from wakedock.controllers.container_controller import ContainerController
from wakedock.repositories.container_repository import ContainerRepository
from wakedock.validators.container_validator import ContainerValidator
from wakedock.services.container_service import ContainerService
from wakedock.views.container_view import ContainerView
from wakedock.serializers.container_serializers import (
    ContainerCreateSerializer,
    ContainerUpdateSerializer,
    ContainerSearchSerializer,
    ContainerLogsSerializer,
    ContainerStatsSerializer,
    ContainerCommandSerializer,
    ContainerFilterSerializer,
    ContainerImageSerializer
)
from wakedock.core.database import get_db_session
from wakedock.middleware.auth_middleware import get_current_user
from wakedock.models.auth import User

import logging
logger = logging.getLogger(__name__)

# FastAPI router
router = APIRouter(prefix="/api/containers", tags=["Containers"])

# Dependencies
async def get_container_dependencies(db: AsyncSession = Depends(get_db_session)):
    """Get container dependencies"""
    container_repository = ContainerRepository(db)
    container_validator = ContainerValidator()
    container_service = ContainerService()
    container_controller = ContainerController(container_repository, container_validator, container_service)
    container_view = ContainerView()
    
    return container_controller, container_view


@router.get("/", summary="List containers", description="Get list of all containers")
async def list_containers(
    request: Request,
    limit: int = Query(50, ge=1, le=100, description="Number of containers to return"),
    offset: int = Query(0, ge=0, description="Number of containers to skip"),
    status: Optional[str] = Query(None, description="Filter by container status"),
    image: Optional[str] = Query(None, description="Filter by container image"),
    current_user: User = Depends(get_current_user),
    deps = Depends(get_container_dependencies)
):
    """Get list of containers"""
    try:
        container_controller, container_view = deps
        
        # Get containers
        result = await container_controller.get_all_containers(
            limit=limit,
            offset=offset,
            status=status,
            image=image
        )
        
        # Format response
        response = await container_view.containers_list_response(
            containers=result['containers'],
            total_count=result['total_count'],
            limit=result['limit'],
            offset=result['offset'],
            has_more=result['has_more']
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing containers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list containers"
        )


@router.post("/", summary="Create container", description="Create a new container")
async def create_container(
    request: Request,
    container_data: ContainerCreateSerializer,
    current_user: User = Depends(get_current_user),
    deps = Depends(get_container_dependencies)
):
    """Create new container"""
    try:
        container_controller, container_view = deps
        
        # Create container
        result = await container_controller.create_container(container_data.dict())
        
        # Format response
        response = await container_view.container_creation_response(
            container=result['container'],
            docker_info=result.get('docker_info')
        )
        
        logger.info(f"Container created by user '{current_user.username}': {container_data.name}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating container: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create container"
        )


@router.get("/{container_id}", summary="Get container", description="Get container by ID")
async def get_container(
    request: Request,
    container_id: str,
    current_user: User = Depends(get_current_user),
    deps = Depends(get_container_dependencies)
):
    """Get container by ID"""
    try:
        container_controller, container_view = deps
        
        # Get container
        result = await container_controller.get_container_by_id(container_id)
        
        # Format response
        response = await container_view.container_response(
            container=result['container'],
            docker_info=result.get('docker_info')
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting container: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get container"
        )


@router.post("/{container_id}/start", summary="Start container", description="Start a container")
async def start_container(
    request: Request,
    container_id: str,
    current_user: User = Depends(get_current_user),
    deps = Depends(get_container_dependencies)
):
    """Start container"""
    try:
        container_controller, container_view = deps
        
        # Start container
        result = await container_controller.start_container(container_id)
        
        # Format response
        response = await container_view.container_operation_response(
            container=result['container'],
            operation="start",
            success=result['started']
        )
        
        logger.info(f"Container started by user '{current_user.username}': {container_id}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting container: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start container"
        )


@router.post("/{container_id}/stop", summary="Stop container", description="Stop a container")
async def stop_container(
    request: Request,
    container_id: str,
    current_user: User = Depends(get_current_user),
    deps = Depends(get_container_dependencies)
):
    """Stop container"""
    try:
        container_controller, container_view = deps
        
        # Stop container
        result = await container_controller.stop_container(container_id)
        
        # Format response
        response = await container_view.container_operation_response(
            container=result['container'],
            operation="stop",
            success=result['stopped']
        )
        
        logger.info(f"Container stopped by user '{current_user.username}': {container_id}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping container: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop container"
        )


@router.post("/{container_id}/restart", summary="Restart container", description="Restart a container")
async def restart_container(
    request: Request,
    container_id: str,
    current_user: User = Depends(get_current_user),
    deps = Depends(get_container_dependencies)
):
    """Restart container"""
    try:
        container_controller, container_view = deps
        
        # Restart container
        result = await container_controller.restart_container(container_id)
        
        # Format response
        response = await container_view.container_operation_response(
            container=result['container'],
            operation="restart",
            success=result['restarted']
        )
        
        logger.info(f"Container restarted by user '{current_user.username}': {container_id}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restarting container: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restart container"
        )


@router.delete("/{container_id}", summary="Remove container", description="Remove a container")
async def remove_container(
    request: Request,
    container_id: str,
    force: bool = Query(False, description="Force removal of running container"),
    current_user: User = Depends(get_current_user),
    deps = Depends(get_container_dependencies)
):
    """Remove container"""
    try:
        container_controller, container_view = deps
        
        # Remove container
        result = await container_controller.remove_container(container_id, force)
        
        # Format response
        response = await container_view.container_operation_response(
            container=result['container'],
            operation="remove",
            success=result['removed']
        )
        
        logger.info(f"Container removed by user '{current_user.username}': {container_id}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing container: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove container"
        )


@router.get("/{container_id}/logs", summary="Get container logs", description="Get container logs")
async def get_container_logs(
    request: Request,
    container_id: str,
    limit: int = Query(100, ge=1, le=1000, description="Number of log lines to return"),
    follow: bool = Query(False, description="Follow log output"),
    level: Optional[str] = Query(None, description="Log level filter"),
    current_user: User = Depends(get_current_user),
    deps = Depends(get_container_dependencies)
):
    """Get container logs"""
    try:
        container_controller, container_view = deps
        
        # Get logs
        result = await container_controller.get_container_logs(
            container_id, limit, follow, level
        )
        
        # Format response
        response = await container_view.container_logs_response(
            container=result['container'],
            docker_logs=result['docker_logs'],
            db_logs=result['db_logs'],
            total_logs=result['total_logs']
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting container logs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get container logs"
        )


@router.get("/{container_id}/stats", summary="Get container stats", description="Get container statistics")
async def get_container_stats(
    request: Request,
    container_id: str,
    current_user: User = Depends(get_current_user),
    deps = Depends(get_container_dependencies)
):
    """Get container statistics"""
    try:
        container_controller, container_view = deps
        
        # Get stats
        result = await container_controller.get_container_stats(container_id)
        
        # Format response
        response = await container_view.container_stats_response(
            container=result['container'],
            current_stats=result['current_stats'],
            metrics_history=result['metrics_history']
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting container stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get container statistics"
        )


@router.post("/{container_id}/exec", summary="Execute command", description="Execute command in container")
async def execute_command(
    request: Request,
    container_id: str,
    command_data: ContainerCommandSerializer,
    current_user: User = Depends(get_current_user),
    deps = Depends(get_container_dependencies)
):
    """Execute command in container"""
    try:
        container_controller, container_view = deps
        
        # Execute command
        from wakedock.services.container_service import ContainerService
        container_service = ContainerService()
        result = await container_service.execute_command(
            container_id, 
            command_data.command,
            command_data.workdir
        )
        
        # Get container for response
        container_result = await container_controller.get_container_by_id(container_id)
        
        # Format response
        response = await container_view.container_command_response(
            container=container_result['container'],
            command=command_data.command,
            exit_code=result['exit_code'],
            output=result['output']
        )
        
        logger.info(f"Command executed by user '{current_user.username}' in container {container_id}: {command_data.command}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to execute command"
        )


@router.get("/search", summary="Search containers", description="Search containers with filters")
async def search_containers(
    request: Request,
    query: str = Query(..., min_length=2, max_length=100, description="Search query"),
    status: Optional[str] = Query(None, description="Container status filter"),
    image: Optional[str] = Query(None, description="Image name filter"),
    limit: int = Query(50, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    current_user: User = Depends(get_current_user),
    deps = Depends(get_container_dependencies)
):
    """Search containers"""
    try:
        container_controller, container_view = deps
        
        # Search containers
        result = await container_controller.search_containers(
            query, status, image, limit, offset
        )
        
        # Format response
        response = await container_view.container_search_response(
            containers=result['containers'],
            query=result['query'],
            filters=result['filters'],
            total_count=result['total_count'],
            limit=result['limit'],
            offset=result['offset']
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching containers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search containers"
        )


@router.get("/statistics", summary="Get container statistics", description="Get overall container statistics")
async def get_container_statistics(
    request: Request,
    current_user: User = Depends(get_current_user),
    deps = Depends(get_container_dependencies)
):
    """Get container statistics"""
    try:
        container_controller, container_view = deps
        
        # Get statistics
        result = await container_controller.get_container_statistics()
        
        # Format response
        response = await container_view.container_statistics_response(
            database_stats=result['database_stats'],
            docker_stats=result['docker_stats']
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting container statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get container statistics"
        )


@router.post("/sync", summary="Sync containers", description="Synchronize containers with Docker daemon")
async def sync_containers(
    request: Request,
    current_user: User = Depends(get_current_user),
    deps = Depends(get_container_dependencies)
):
    """Synchronize containers with Docker daemon"""
    try:
        # Check admin permission
        if not current_user.has_permission('containers:manage'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        container_controller, container_view = deps
        
        # Sync containers
        result = await container_controller.sync_containers()
        
        # Format response
        response = await container_view.container_sync_response(
            synced_count=result['synced_count'],
            created_count=result['created_count'],
            updated_count=result['updated_count']
        )
        
        logger.info(f"Containers synchronized by user '{current_user.username}'")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing containers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to synchronize containers"
        )


@router.get("/images", summary="List images", description="List Docker images")
async def list_images(
    request: Request,
    current_user: User = Depends(get_current_user),
    deps = Depends(get_container_dependencies)
):
    """List Docker images"""
    try:
        container_controller, container_view = deps
        
        # Get images
        from wakedock.services.container_service import ContainerService
        container_service = ContainerService()
        images = await container_service.list_images()
        
        # Format response
        response = await container_view.image_list_response(images)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing images: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list images"
        )


@router.post("/images/pull", summary="Pull image", description="Pull Docker image")
async def pull_image(
    request: Request,
    image_data: ContainerImageSerializer,
    current_user: User = Depends(get_current_user),
    deps = Depends(get_container_dependencies)
):
    """Pull Docker image"""
    try:
        # Check admin permission
        if not current_user.has_permission('containers:manage'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        
        container_controller, container_view = deps
        
        # Pull image
        from wakedock.services.container_service import ContainerService
        container_service = ContainerService()
        
        image_name = f"{image_data.image_name}:{image_data.tag}"
        result = await container_service.pull_image(image_name)
        
        # Format response
        response = await container_view.image_pull_response(result)
        
        logger.info(f"Image pulled by user '{current_user.username}': {image_name}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pulling image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to pull image"
        )


# Health check endpoint
@router.get("/health", summary="Container health check", description="Check container service health")
async def health_check(request: Request):
    """Container service health check"""
    try:
        from wakedock.services.container_service import ContainerService
        container_service = ContainerService()
        
        # Test Docker connection
        await container_service.list_containers()
        
        return {
            "status": "healthy",
            "service": "containers",
            "docker_connection": "ok",
            "timestamp": "2023-01-01T00:00:00Z"
        }
        
    except Exception as e:
        logger.error(f"Container health check error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Container service unhealthy"
        )
