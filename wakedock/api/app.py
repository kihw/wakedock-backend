"""
FastAPI application factory
"""

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import logging

from wakedock.api.routes import services, health, proxy, system
from wakedock.api.auth.routes import router as auth_router
from wakedock.api.middleware import ProxyMiddleware
from wakedock.core.orchestrator import DockerOrchestrator
from wakedock.core.monitoring import MonitoringService
from wakedock.config import get_settings

logger = logging.getLogger(__name__)


def create_app(orchestrator: DockerOrchestrator, monitoring: MonitoringService) -> FastAPI:
    """Create and configure FastAPI application"""
    settings = get_settings()
    
    app = FastAPI(
        title="WakeDock API",
        description="Intelligent Docker orchestration with Caddy reverse proxy",
        version="1.0.0",
        docs_url="/api/docs" if settings.wakedock.debug else None,
        redoc_url="/api/redoc" if settings.wakedock.debug else None,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add proxy middleware
    app.add_middleware(ProxyMiddleware, orchestrator=orchestrator)
    
    # Include routers
    app.include_router(
        health.router,
        prefix="/api/v1",
        tags=["health"]
    )
    
    app.include_router(
        services.router,
        prefix="/api/v1/services",
        tags=["services"]
    )
    
    app.include_router(
        system.router,
        prefix="/api/v1/system",
        tags=["system"]
    )
    
    app.include_router(
        auth_router,
        prefix="/api/v1",
        tags=["authentication"]
    )
    
    app.include_router(
        proxy.router,
        prefix="",
        tags=["proxy"]
    )
    
    # Store dependencies in app state
    app.state.orchestrator = orchestrator
    app.state.monitoring = monitoring
    app.state.settings = settings
    
    @app.on_event("startup")
    async def startup_event():
        logger.info("WakeDock API started")
        
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("WakeDock API shutting down")
    
    return app
