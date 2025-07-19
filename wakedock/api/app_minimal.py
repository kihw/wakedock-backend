"""
Minimal FastAPI application for WakeDock - bypasses complex dependencies
"""

import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import datetime

logger = logging.getLogger(__name__)

# Response models
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    message: str = "WakeDock Backend (Minimal) is running"

class ServiceResponse(BaseModel):
    id: str
    name: str
    status: str
    image: str
    created_at: str
    updated_at: str

class SystemOverviewResponse(BaseModel):
    total_services: int
    running_services: int
    stopped_services: int
    total_containers: int
    system_uptime: str

def create_minimal_app() -> FastAPI:
    """Create minimal FastAPI application without complex dependencies"""
    
    app = FastAPI(
        title="WakeDock API (Minimal)",
        description="Minimal WakeDock API for debugging and development",
        version="0.1.0",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json"
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Health endpoint
    @app.get("/api/v1/health", response_model=HealthResponse)
    async def health():
        return HealthResponse(
            status="healthy",
            timestamp=datetime.datetime.utcnow().isoformat()
        )
    
    # System overview endpoint
    @app.get("/api/v1/system/overview", response_model=SystemOverviewResponse)
    async def system_overview():
        return SystemOverviewResponse(
            total_services=5,
            running_services=3,
            stopped_services=2,
            total_containers=5,
            system_uptime="2 days, 4:30:15"
        )
    
    # Services endpoints (mock data)
    @app.get("/api/v1/services", response_model=List[ServiceResponse])
    async def get_services():
        mock_services = [
            {
                "id": "1",
                "name": "nginx-proxy",
                "status": "running",
                "image": "nginx:latest",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00"
            },
            {
                "id": "2",
                "name": "redis-cache",
                "status": "running",
                "image": "redis:alpine",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00"
            },
            {
                "id": "3",
                "name": "postgres-db",
                "status": "stopped",
                "image": "postgres:15",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00"
            }
        ]
        return [ServiceResponse(**service) for service in mock_services]
    
    @app.get("/api/v1/services/{service_id}", response_model=ServiceResponse)
    async def get_service(service_id: str):
        if service_id == "1":
            return ServiceResponse(
                id="1",
                name="nginx-proxy",
                status="running",
                image="nginx:latest",
                created_at="2024-01-01T00:00:00",
                updated_at="2024-01-01T00:00:00"
            )
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Auth endpoints (mock)
    @app.post("/api/v1/auth/login")
    async def login(username: str, password: str):
        # Mock authentication - always succeed for testing
        return {
            "access_token": "mock-jwt-token",
            "token_type": "bearer",
            "user": {
                "id": 1,
                "username": username,
                "email": f"{username}@example.com",
                "role": "admin"
            }
        }
    
    @app.get("/api/v1/auth/me")
    async def get_current_user():
        return {
            "id": 1,
            "username": "admin",
            "email": "admin@example.com",
            "role": "admin"
        }
    
    # Containers endpoint
    @app.get("/api/v1/containers")
    async def get_containers():
        return []
    
    # Stacks endpoint
    @app.get("/api/v1/stacks")
    async def get_stacks():
        return []
    
    logger.info("Minimal WakeDock API created successfully")
    return app

# Create the app instance
app = create_minimal_app()