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
from wakedock.database.database import init_database


async def main():
    """Main application entry point"""
    # Load configuration
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
    logger.info("Starting WakeDock...")
    
    # Create data directories
    Path(settings.wakedock.data_path).mkdir(parents=True, exist_ok=True)
    Path(settings.logging.file).parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize database
    try:
        init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    # Initialize services
    orchestrator = DockerOrchestrator()
    monitoring_service = MonitoringService()
    
    # Connect monitoring service to orchestrator
    monitoring_service.set_orchestrator(orchestrator)
    
    # Create FastAPI app
    app = create_app(orchestrator, monitoring_service)
    
    # Start monitoring service
    if settings.monitoring.enabled:
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
            await monitoring_service.stop()


if __name__ == "__main__":
    asyncio.run(main())
