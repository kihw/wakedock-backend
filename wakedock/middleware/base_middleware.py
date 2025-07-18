"""
Base middleware classes for WakeDock MVC architecture
"""

from typing import Any, Dict, List, Optional, Callable, Awaitable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
import time
import logging
import uuid
from datetime import datetime


class BaseMiddleware(BaseHTTPMiddleware):
    """Base middleware class with common functionality"""
    
    def __init__(self, app: ASGIApp, name: str = None):
        super().__init__(app)
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(f"wakedock.middleware.{self.name}")
        self.enabled = True
        self.config = {}
    
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Dispatch the request through the middleware"""
        if not self.enabled:
            return await call_next(request)
        
        # Pre-processing
        start_time = time.time()
        request_id = str(uuid.uuid4())
        
        # Add request ID to headers
        request.state.request_id = request_id
        
        try:
            # Call pre-processing hook
            await self.pre_process(request)
            
            # Process the request
            response = await call_next(request)
            
            # Call post-processing hook
            await self.post_process(request, response)
            
            # Add common headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Processed-By"] = self.name
            
            # Log request
            process_time = time.time() - start_time
            self.log_request(request, response, process_time)
            
            return response
            
        except Exception as e:
            # Handle errors
            response = await self.handle_error(request, e)
            process_time = time.time() - start_time
            self.log_error(request, e, process_time)
            return response
    
    async def pre_process(self, request: Request) -> None:
        """Pre-processing hook - override in subclasses"""
        pass
    
    async def post_process(self, request: Request, response: Response) -> None:
        """Post-processing hook - override in subclasses"""
        pass
    
    async def handle_error(self, request: Request, exc: Exception) -> Response:
        """Error handling hook - override in subclasses"""
        from fastapi import HTTPException
        from starlette.responses import JSONResponse
        
        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "success": False,
                    "error": {
                        "message": exc.detail,
                        "status_code": exc.status_code,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
            )
        
        # Generic error response
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "message": "Internal server error",
                    "status_code": 500,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
        )
    
    def log_request(self, request: Request, response: Response, process_time: float) -> None:
        """Log request details"""
        self.logger.info(
            f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "process_time": process_time,
                "request_id": getattr(request.state, 'request_id', None),
                "user_agent": request.headers.get("user-agent"),
                "ip": request.client.host if request.client else None
            }
        )
    
    def log_error(self, request: Request, exc: Exception, process_time: float) -> None:
        """Log error details"""
        self.logger.error(
            f"Error processing {request.method} {request.url.path}: {str(exc)}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "error": str(exc),
                "error_type": type(exc).__name__,
                "process_time": process_time,
                "request_id": getattr(request.state, 'request_id', None),
                "user_agent": request.headers.get("user-agent"),
                "ip": request.client.host if request.client else None
            },
            exc_info=True
        )
    
    def configure(self, config: Dict[str, Any]) -> None:
        """Configure the middleware"""
        self.config.update(config)
        self.enabled = config.get('enabled', True)
        
        # Apply configuration
        self.apply_config()
    
    def apply_config(self) -> None:
        """Apply configuration - override in subclasses"""
        pass
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)
    
    def set_config(self, key: str, value: Any) -> None:
        """Set configuration value"""
        self.config[key] = value
    
    def enable(self) -> None:
        """Enable the middleware"""
        self.enabled = True
    
    def disable(self) -> None:
        """Disable the middleware"""
        self.enabled = False
    
    def is_enabled(self) -> bool:
        """Check if middleware is enabled"""
        return self.enabled
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get middleware metrics"""
        return {
            "name": self.name,
            "enabled": self.enabled,
            "config": self.config,
            "timestamp": datetime.utcnow().isoformat()
        }


class RequestLoggingMiddleware(BaseMiddleware):
    """Middleware for detailed request logging"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app, "RequestLogging")
    
    async def pre_process(self, request: Request) -> None:
        """Log incoming request details"""
        self.logger.info(
            f"Incoming request: {request.method} {request.url}",
            extra={
                "method": request.method,
                "url": str(request.url),
                "headers": dict(request.headers),
                "query_params": dict(request.query_params),
                "request_id": request.state.request_id
            }
        )
    
    async def post_process(self, request: Request, response: Response) -> None:
        """Log response details"""
        self.logger.info(
            f"Response: {response.status_code}",
            extra={
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "request_id": request.state.request_id
            }
        )


class SecurityHeadersMiddleware(BaseMiddleware):
    """Middleware for adding security headers"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app, "SecurityHeaders")
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": "default-src 'self'",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        }
    
    async def post_process(self, request: Request, response: Response) -> None:
        """Add security headers to response"""
        for header, value in self.security_headers.items():
            response.headers[header] = value
    
    def apply_config(self) -> None:
        """Apply security headers configuration"""
        custom_headers = self.get_config('headers', {})
        self.security_headers.update(custom_headers)


class CORSMiddleware(BaseMiddleware):
    """Middleware for handling CORS"""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app, "CORS")
        self.allowed_origins = ["*"]
        self.allowed_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        self.allowed_headers = ["*"]
        self.allow_credentials = True
    
    async def pre_process(self, request: Request) -> None:
        """Handle CORS preflight requests"""
        if request.method == "OPTIONS":
            request.state.is_preflight = True
        else:
            request.state.is_preflight = False
    
    async def post_process(self, request: Request, response: Response) -> None:
        """Add CORS headers to response"""
        origin = request.headers.get("origin")
        
        if origin and (origin in self.allowed_origins or "*" in self.allowed_origins):
            response.headers["Access-Control-Allow-Origin"] = origin
        
        response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allowed_methods)
        response.headers["Access-Control-Allow-Headers"] = ", ".join(self.allowed_headers)
        
        if self.allow_credentials:
            response.headers["Access-Control-Allow-Credentials"] = "true"
    
    def apply_config(self) -> None:
        """Apply CORS configuration"""
        self.allowed_origins = self.get_config('allowed_origins', ["*"])
        self.allowed_methods = self.get_config('allowed_methods', ["GET", "POST", "PUT", "DELETE", "OPTIONS"])
        self.allowed_headers = self.get_config('allowed_headers', ["*"])
        self.allow_credentials = self.get_config('allow_credentials', True)
