"""
Service management endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, status, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

from wakedock.config import ServiceSettings, get_settings
from wakedock.core.orchestrator import DockerOrchestrator

router = APIRouter()


class ServiceResponse(BaseModel):
    id: str
    name: str
    subdomain: str
    status: str
    docker_image: Optional[str] = None
    docker_compose: Optional[str] = None
    ports: List[str] = []
    created_at: datetime
    updated_at: datetime
    last_accessed: Optional[datetime] = None
    resource_usage: Optional[Dict[str, Any]] = None


class ServiceCreateRequest(BaseModel):
    name: str
    subdomain: str
    docker_image: Optional[str] = None
    docker_compose: Optional[str] = None
    ports: List[str] = []
    environment: Dict[str, str] = {}
    auto_shutdown: Optional[Dict[str, Any]] = None
    loading_page: Optional[Dict[str, Any]] = None


class ServiceUpdateRequest(BaseModel):
    name: Optional[str] = None
    subdomain: Optional[str] = None
    docker_image: Optional[str] = None
    docker_compose: Optional[str] = None
    ports: Optional[List[str]] = None
    environment: Optional[Dict[str, str]] = None
    auto_shutdown: Optional[Dict[str, Any]] = None
    loading_page: Optional[Dict[str, Any]] = None


def get_orchestrator(request: Request) -> DockerOrchestrator:
    """Dependency to get orchestrator instance from app state"""
    return request.app.state.orchestrator


@router.get("", response_model=List[ServiceResponse])
async def list_services(orchestrator: DockerOrchestrator = Depends(get_orchestrator)):
    """List all services"""
    try:
        services = await orchestrator.list_services()
        return services
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list services: {str(e)}"
        )


@router.post("", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
async def create_service(
    service_data: ServiceCreateRequest,
    orchestrator: DockerOrchestrator = Depends(get_orchestrator)
):
    """Create a new service"""
    try:
        service = await orchestrator.create_service(service_data.dict())
        return service
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create service: {str(e)}"
        )


@router.get("/{service_id}", response_model=ServiceResponse)
async def get_service(
    service_id: str,
    orchestrator: DockerOrchestrator = Depends(get_orchestrator)
):
    """Get service details"""
    try:
        service = await orchestrator.get_service(service_id)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found"
            )
        return service
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get service: {str(e)}"
        )


@router.put("/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: str,
    service_data: ServiceUpdateRequest,
    orchestrator: DockerOrchestrator = Depends(get_orchestrator)
):
    """Update service configuration"""
    try:
        service = await orchestrator.update_service(service_id, service_data.dict(exclude_unset=True))
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found"
            )
        return service
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update service: {str(e)}"
        )


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: str,
    orchestrator: DockerOrchestrator = Depends(get_orchestrator)
):
    """Delete a service"""
    try:
        success = await orchestrator.delete_service(service_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete service: {str(e)}"
        )


@router.post("/{service_id}/wake", response_model=Dict[str, str])
async def wake_service(
    service_id: str,
    orchestrator: DockerOrchestrator = Depends(get_orchestrator)
):
    """Force wake up a service"""
    try:
        success = await orchestrator.wake_service(service_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found"
            )
        return {"message": "Service wake up initiated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to wake service: {str(e)}"
        )


@router.post("/{service_id}/sleep", response_model=Dict[str, str])
async def sleep_service(
    service_id: str,
    orchestrator: DockerOrchestrator = Depends(get_orchestrator)
):
    """Force sleep a service"""
    try:
        success = await orchestrator.sleep_service(service_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Service not found"
            )
        return {"message": "Service sleep initiated"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sleep service: {str(e)}"
        )
