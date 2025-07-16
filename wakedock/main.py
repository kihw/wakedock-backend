"""
Main application entry point
"""

import asyncio
import logging
import uvicorn
from pathlib import Path

from wakedock.config import get_settings
from wakedock.api.app import create_app
from wakedock.core.monitoring import MonitoringService
from wakedock.core.orchestrator import DockerOrchestrator
from wakedock.core.advanced_analytics import AdvancedAnalyticsService
from wakedock.core.alerts_service import AlertsService
from wakedock.core.metrics_collector import MetricsCollector
from wakedock.core.log_optimization_service import LogOptimizationService
from wakedock.database.database import init_database

# Create app instance for uvicorn
def create_application():
    """Create and configure the FastAPI application"""
    settings = get_settings()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, settings.logging.level),
        format=settings.logging.format,
        handlers=[
            logging.FileHandler(settings.logging.file),
            logging.StreamHandler()
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Creating WakeDock application...")
    
    # Create data directories
    Path(settings.wakedock.data_path).mkdir(parents=True, exist_ok=True)
    Path(settings.logging.file).parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize database
    try:
        init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # Don't raise in production, let the app start and handle gracefully
    
    # Initialize services
    orchestrator = DockerOrchestrator()
    monitoring_service = MonitoringService()
    
    # Initialize analytics if monitoring is enabled
    analytics_service = None
    alerts_service = None
    log_optimization_service = None
    if settings.monitoring.enabled:
        try:
            # Create metrics collector
            metrics_collector = MetricsCollector()
            
            # Create analytics service
            analytics_service = AdvancedAnalyticsService(
                metrics_collector=metrics_collector,
                storage_path=str(Path(settings.wakedock.data_path) / "analytics")
            )
            
            # Create alerts service
            alerts_service = AlertsService(
                metrics_collector=metrics_collector,
                storage_path=str(Path(settings.wakedock.data_path) / "alerts")
            )
            
            # Create log optimization service
            log_optimization_service = LogOptimizationService(
                storage_path=str(Path(settings.wakedock.data_path) / "logs_optimization")
            )
            
            logger.info("Advanced Analytics, Alerts, and Log Optimization services initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Analytics/Alerts/LogOptimization services: {e}")
            analytics_service = None
            alerts_service = None
            log_optimization_service = None
    
    # Connect monitoring service to orchestrator
    monitoring_service.set_orchestrator(orchestrator)
    
    # Create FastAPI app
    app = create_app(orchestrator, monitoring_service, analytics_service, alerts_service)
    
    return app

# Create the app instance for uvicorn
try:
    app = create_application()
except Exception as e:
    # Fallback: create a minimal app for startup debugging
    from fastapi import FastAPI
    app = FastAPI(title="WakeDock (Minimal)", description="Fallback app for debugging")
    
    @app.get("/health")
    def health():
        return {"status": "ok", "message": "Minimal app running"}
    
    print(f"⚠️ Failed to create full application, using minimal app: {e}")


async def main():
    """Main application entry point for direct execution"""
    settings = get_settings()
    logger = logging.getLogger(__name__)
    
    # Start monitoring service if enabled
    if settings.monitoring.enabled:
        # Get the monitoring service from the app
        monitoring_service = getattr(app, 'monitoring_service', None)
        if monitoring_service:
            await monitoring_service.start()
    
    # Start the server
    config = uvicorn.Config(
        app,
        host=settings.wakedock.host,
        port=settings.wakedock.port,
        log_level=settings.logging.level.lower(),
        access_log=True
    )
    
    server = uvicorn.Server(config)
    logger.info(f"WakeDock started on {settings.wakedock.host}:{settings.wakedock.port}")
    
    try:
        await server.serve()
    except KeyboardInterrupt:
        logger.info("Shutting down WakeDock...")
    finally:
        if settings.monitoring.enabled:
            monitoring_service = getattr(app, 'monitoring_service', None)
            if monitoring_service:
                await monitoring_service.stop()


if __name__ == "__main__":
    asyncio.run(main())
