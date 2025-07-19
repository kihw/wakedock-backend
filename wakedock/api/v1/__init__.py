"""
WakeDock v1.0.0 API Router Configuration

This module configures all API routes for the advanced service management
and container orchestration features introduced in version 1.0.0.
"""

from fastapi import APIRouter, Depends
from wakedock.core.security import get_current_user
from wakedock.database.models import User

# Import v1.0.0 API modules
from wakedock.api.v1.services import router as services_router
from wakedock.api.v1.containers import router as containers_router
from wakedock.api.v1.routes.stacks import router as stacks_router

# Create main API router
api_router = APIRouter()

# Include v1.0.0 routers
api_router.include_router(
    services_router,
    dependencies=[Depends(get_current_user)]
)

api_router.include_router(
    containers_router,
    dependencies=[Depends(get_current_user)]
)

api_router.include_router(
    stacks_router,
    dependencies=[Depends(get_current_user)]
)

# Health check endpoint for v1.0.0
@api_router.get("/health")
async def health_check():
    """Health check endpoint for WakeDock v1.0.0"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "features": [
            "Service Creation Wizard",
            "Docker Compose Editor", 
            "GitHub Integration",
            "Advanced Container Orchestration",
            "Real-time Monitoring",
            "Network Management",
            "Volume Management",
            "Stack Detection & Categorization"
        ]
    }

# Version info endpoint
@api_router.get("/version")
async def get_version_info():
    """Get detailed version information"""
    return {
        "version": "1.0.0",
        "build_date": "2025-07-18",
        "features": {
            "service_management": {
                "version": "1.0.0",
                "description": "Advanced service creation and management with templates",
                "endpoints": [
                    "/api/v1/services/templates",
                    "/api/v1/services/create",
                    "/api/v1/services/compose/validate",
                    "/api/v1/services/compose/deploy"
                ]
            },
            "github_integration": {
                "version": "1.0.0",
                "description": "Import and deploy containerized projects from GitHub",
                "endpoints": [
                    "/api/v1/services/github/repositories",
                    "/api/v1/services/github/import"
                ]
            },
            "container_orchestration": {
                "version": "1.0.0",
                "description": "Advanced container management and monitoring",
                "endpoints": [
                    "/api/v1/containers/",
                    "/api/v1/containers/{container_id}/control",
                    "/api/v1/containers/{container_id}/logs",
                    "/api/v1/containers/{container_id}/metrics",
                    "/api/v1/containers/networks",
                    "/api/v1/containers/volumes",
                    "/api/v1/containers/ws/monitor"
                ]
            }
        },
        "changelog": [
            "Added Service Creation Wizard with pre-configured templates",
            "Implemented Docker Compose Editor with real-time validation",
            "Added GitHub Integration for direct repository deployment",
            "Enhanced Container Orchestration with granular controls",
            "Added Real-time Monitoring with WebSocket support",
            "Implemented Advanced Network Management",
            "Added Volume Management with cleanup capabilities",
            "Enhanced Health Checks and Auto-recovery",
            "Added One-click Deployment from GitHub repositories",
            "Implemented CI/CD Integration with webhooks"
        ]
    }
