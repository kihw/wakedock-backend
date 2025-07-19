"""
FastAPI application factory - Version complète mais simplifiée
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# from wakedock.api.auth.routes import router as auth_router  # Skip auth for now
from wakedock.api.middleware import ProxyMiddleware
from wakedock.api.routes import (
    health,
    monitoring,
    services,
    system,
    containers,
    logs,
)
from wakedock.config import get_settings
from wakedock.core.advanced_analytics import AdvancedAnalyticsService
from wakedock.core.alerts_service import AlertsService
from wakedock.core.monitoring import MonitoringService
from wakedock.core.orchestrator import DockerOrchestrator

logger = logging.getLogger(__name__)


def create_app(orchestrator: DockerOrchestrator, monitoring_service: MonitoringService, analytics_service: AdvancedAnalyticsService = None, alerts_service: AlertsService = None) -> FastAPI:
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
    
    # Include essential routers
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
    
    # Skip auth router for now
    # app.include_router(
    #     auth_router,
    #     prefix="/api/v1",
    #     tags=["authentication"]
    # )
    
    # Container management routes
    app.include_router(
        containers.router,
        prefix="/api/v1",
        tags=["containers"]
    )
    
    # Logs routes
    app.include_router(
        logs.router,
        prefix="/api/v1",
        tags=["logs"]
    )
    
    # Real-time monitoring routes
    app.include_router(
        monitoring.router,
        tags=["monitoring"]
    )
    
    # Store dependencies in app state
    app.state.orchestrator = orchestrator
    app.state.monitoring = monitoring_service
    app.state.analytics = analytics_service
    app.state.alerts = alerts_service
    app.state.settings = settings
    
    @app.on_event("startup")
    async def startup_event():
        logger.info("WakeDock API (Full) started")
        
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("WakeDock API (Full) shutting down")
    
    return app