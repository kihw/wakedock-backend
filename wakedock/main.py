"""
Main application entry point for WakeDock Backend.
FastAPI application with Docker management capabilities.
"""

import asyncio
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configuration and settings
from wakedock.config import get_settings

# Core application setup
from wakedock.core.app_configurator import prepare_application, create_fastapi_app
from wakedock.core.service_initializer import initialize_all_services

# Infrastructure services
from wakedock.infrastructure.cache.service import shutdown_cache_service
from wakedock.security.manager import shutdown_security
from wakedock.performance.integration import shutdown_performance


async def start_application_services(app, services):
    """Start all application services and connect them."""
    logger = logging.getLogger(__name__)
    settings = get_settings()
    
    # Start monitoring service
    monitoring_service = services.get("monitoring_service")
    if settings.monitoring.enabled and monitoring_service:
        await monitoring_service.start()
        logger.info("Monitoring service started")
    
    # Start WebSocket event handlers
    await start_websocket_handlers(services)
    
    # Send startup notification
    await send_startup_notification(services)


async def start_websocket_handlers(services):
    """Start WebSocket event handlers for real-time updates."""
    logger = logging.getLogger(__name__)
    
    # Start Docker events monitoring
    docker_events_handler = services.get("docker_events_handler")
    if docker_events_handler:
        from wakedock.api.websocket import handle_docker_event
        docker_events_handler.subscribe(handle_docker_event)
        await docker_events_handler.start_monitoring()
        logger.info("Docker events monitoring started")


async def send_startup_notification(services):
    """Send startup notification to configured channels."""
    logger = logging.getLogger(__name__)
    notification_service = services.get("notification_service")
    
    if notification_service:
        try:
            await notification_service.send_startup_notification()
            logger.info("Startup notification sent")
        except Exception as e:
            logger.warning(f"Failed to send startup notification: {e}")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # Get settings
    settings = get_settings()
    
    # Create FastAPI app
    app = create_fastapi_app()
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Initialize services and middleware
    prepare_application(app)
    
    return app


# Create the FastAPI application instance
app = create_app()


@app.on_event("startup")
async def startup_event():
    """Handle application startup."""
    logger = logging.getLogger(__name__)
    logger.info("🚀 Starting WakeDock Backend...")
    
    try:
        # Initialize all services
        services = await initialize_all_services()
        app.state.services = services
        
        # Start application services
        await start_application_services(app, services)
        
        logger.info("✅ WakeDock Backend started successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to start WakeDock Backend: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Handle application shutdown."""
    logger = logging.getLogger(__name__)
    logger.info("🛑 Shutting down WakeDock Backend...")
    
    try:
        # Shutdown services gracefully
        await shutdown_cache_service()
        await shutdown_security()
        await shutdown_performance()
        
        # Stop monitoring if enabled
        services = getattr(app.state, 'services', {})
        monitoring_service = services.get("monitoring_service")
        if monitoring_service:
            await monitoring_service.stop()
            
        logger.info("✅ WakeDock Backend shutdown completed")
        
    except Exception as e:
        logger.error(f"❌ Error during shutdown: {e}")


if __name__ == "__main__":
    # Development server
    settings = get_settings()
    
    uvicorn.run(
        "wakedock.main:app",
        host="0.0.0.0",
        port=5000,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug",
        access_log=True,
    )