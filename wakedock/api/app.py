"""
FastAPI application factory
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wakedock.api.auth.routes import router as auth_router
from wakedock.api.middleware import ProxyMiddleware
from wakedock.api.routes import (
    centralized_logs,
    compose_stacks,
    container_lifecycle,
    container_logs,
    containers,
    env_files,
    environment,
    health,
    images,
    logs,
    proxy,
    services,
    system,
    user_preferences,
)
from wakedock.api.v1.routes import (
    services as services_v1,
    containers as containers_v1,
)
from wakedock.config import get_settings
from wakedock.core.advanced_analytics import AdvancedAnalyticsService
from wakedock.core.alerts_service import AlertsService
from wakedock.core.monitoring import MonitoringService
from wakedock.core.orchestrator import DockerOrchestrator

logger = logging.getLogger(__name__)


def create_app(orchestrator: DockerOrchestrator, monitoring: MonitoringService, analytics: AdvancedAnalyticsService = None, alerts: AlertsService = None) -> FastAPI:
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
    
    # Container management routes
    app.include_router(
        containers.router,
        prefix="/api/v1",
        tags=["containers"]
    )
    
    app.include_router(
        container_lifecycle.router,
        prefix="/api/v1",
        tags=["container-lifecycle"]
    )
    
    app.include_router(
        images.router,
        prefix="/api/v1",
        tags=["images"]
    )
    
    app.include_router(
        container_logs.router,
        prefix="/api/v1",
        tags=["container-logs"]
    )
    
    # Docker Compose routes
    app.include_router(
        compose_stacks.router,
        prefix="/api/v1",
        tags=["compose-stacks"]
    )
    
    # Environment files routes
    app.include_router(
        env_files.router,
        prefix="/api/v1",
        tags=["environment"]
    )
    
    # Logs routes
    app.include_router(
        logs.router,
        prefix="/api/v1",
        tags=["logs"]
    )
    
    # Centralized logs routes
    app.include_router(
        centralized_logs.router,
        tags=["centralized-logs"]
    )
    
    # Real-time monitoring routes
    app.include_router(
        monitoring.router,
        tags=["monitoring"]
    )
    
    # Advanced analytics routes
    if analytics:
        app.include_router(
            analytics.router,
            tags=["analytics"]
        )
     # Alerts routes
    if alerts:
        app.include_router(
            alerts.router,
            tags=["alerts"]
        )

    # Environment management routes
    app.include_router(
        environment.router,
        tags=["environments"]
    )

    # User preferences routes
    app.include_router(
        user_preferences.router,
        tags=["user-preferences"]
    )

    # Version 1.0.0 API routes
    app.include_router(
        services_v1.router,
        prefix="/api/v1",
        tags=["services-v1"]
    )
    
    app.include_router(
        containers_v1.router,
        prefix="/api/v1",
        tags=["containers-v1"]
    )

    app.include_router(
        proxy.router,
        prefix="",
        tags=["proxy"]
    )
    
    # Store dependencies in app state
    app.state.orchestrator = orchestrator
    app.state.monitoring = monitoring
    app.state.analytics = analytics
    app.state.alerts = alerts
    app.state.settings = settings
    
    @app.on_event("startup")
    async def startup_event():
        logger.info("WakeDock API started")
        
        # Initialize analytics service if provided
        if analytics:
            try:
                await analytics.start()
                logger.info("Advanced Analytics service started")
            except Exception as e:
                logger.error(f"Failed to start Analytics service: {e}")
        
        # Initialize alerts service if provided
        if alerts:
            try:
                await alerts.start()
                logger.info("Alerts service started")
            except Exception as e:
                logger.error(f"Failed to start Alerts service: {e}")
        
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("WakeDock API shutting down")
        
        # Stop analytics service if running
        if analytics:
            try:
                await analytics.stop()
                logger.info("Advanced Analytics service stopped")
            except Exception as e:
                logger.error(f"Error stopping Analytics service: {e}")
        
        # Stop alerts service if running
        if alerts:
            try:
                await alerts.stop()
                logger.info("Alerts service stopped")
            except Exception as e:
                logger.error(f"Error stopping Alerts service: {e}")
    
    return app
