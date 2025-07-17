"""
Middleware utilities for WakeDock
"""
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """Middleware for logging requests"""
    
    def __init__(self):
        self.enabled = True
    
    async def __call__(self, request: Any, call_next: Callable) -> Any:
        """Process request"""
        if self.enabled:
            logger.info(f"Processing request: {request}")
        
        response = await call_next(request)
        
        if self.enabled:
            logger.info(f"Response status: {response}")
        
        return response


logging_middleware = RequestLoggingMiddleware()
