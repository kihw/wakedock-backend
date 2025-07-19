"""
FastAPI application with real authentication for WakeDock.
"""

import logging
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

from sqlalchemy.orm import Session

from wakedock.database.database import get_db_session
from wakedock.core.auth.auth_service import AuthService
from wakedock.models.auth_models import User

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()

# Response models
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: Dict[str, Any]

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: datetime

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    message: str = "WakeDock Backend is running"

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


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db_session)
) -> User:
    """Get current user from JWT token."""
    token = credentials.credentials
    auth_service = AuthService(db)
    
    user = await auth_service.get_current_user(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


def create_app() -> FastAPI:
    """Create FastAPI application with authentication."""
    
    app = FastAPI(
        title="WakeDock API",
        description="WakeDock API with Authentication",
        version="0.2.0",
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
    
    # Health endpoint (no auth required)
    @app.get("/api/v1/health", response_model=HealthResponse)
    async def health():
        return HealthResponse(
            status="healthy",
            timestamp=datetime.utcnow().isoformat()
        )
    
    # Auth endpoints
    @app.post("/api/v1/auth/login", response_model=LoginResponse)
    async def login(
        credentials: LoginRequest,
        db: Session = Depends(get_db_session)
    ):
        """Login endpoint."""
        auth_service = AuthService(db)
        
        # Authenticate user
        user = await auth_service.authenticate_user(
            credentials.username,
            credentials.password
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password"
            )
        
        # Create tokens
        tokens = await auth_service.create_tokens(user)
        
        return LoginResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            token_type=tokens["token_type"],
            user={
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role.value,
                "full_name": user.full_name
            }
        )
    
    @app.get("/api/v1/auth/me", response_model=UserResponse)
    async def get_current_user_info(
        current_user: User = Depends(get_current_user)
    ):
        """Get current user information."""
        return UserResponse(
            id=current_user.id,
            username=current_user.username,
            email=current_user.email,
            full_name=current_user.full_name,
            role=current_user.role.value,
            is_active=current_user.is_active,
            created_at=current_user.created_at
        )
    
    @app.post("/api/v1/auth/logout")
    async def logout(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db_session)
    ):
        """Logout endpoint."""
        # In a real implementation, you might want to revoke the token
        return {"message": "Logged out successfully"}
    
    # Protected endpoints
    @app.get("/api/v1/system/overview", response_model=SystemOverviewResponse)
    async def system_overview(
        current_user: User = Depends(get_current_user)
    ):
        """Get system overview (protected)."""
        return SystemOverviewResponse(
            total_services=5,
            running_services=3,
            stopped_services=2,
            total_containers=5,
            system_uptime="2 days, 4:30:15"
        )
    
    @app.get("/api/v1/services", response_model=List[ServiceResponse])
    async def get_services(
        current_user: User = Depends(get_current_user)
    ):
        """Get services list (protected)."""
        # Mock data for now
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
    async def get_service(
        service_id: str,
        current_user: User = Depends(get_current_user)
    ):
        """Get service details (protected)."""
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
    
    # Containers endpoint
    @app.get("/api/v1/containers")
    async def get_containers(
        current_user: User = Depends(get_current_user)
    ):
        """Get containers list (protected)."""
        return []
    
    # Stacks endpoint
    @app.get("/api/v1/stacks")
    async def get_stacks(
        current_user: User = Depends(get_current_user)
    ):
        """Get stacks list (protected)."""
        return []
    
    logger.info("WakeDock API with authentication created successfully")
    return app

# Create the app instance
app = create_app()