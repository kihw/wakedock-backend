"""
Proxy middleware for handling service wake-up and routing
"""

import asyncio
import logging
from typing import Callable
from urllib.parse import urlparse

from fastapi import Request, Response
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import StreamingResponse
import httpx

from wakedock.core.orchestrator import DockerOrchestrator
from wakedock.templates.loading import get_loading_page

logger = logging.getLogger(__name__)


class ProxyMiddleware(BaseHTTPMiddleware):
    """Middleware to handle service wake-up and proxy requests"""
    
    def __init__(self, app, orchestrator: DockerOrchestrator):
        super().__init__(app)
        self.orchestrator = orchestrator
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process incoming requests"""
        host = request.headers.get("host", "")
        
        # Skip admin and API requests
        if host.startswith("admin.") or request.url.path.startswith("/api/"):
            return await call_next(request)
        
        # Extract subdomain
        subdomain = self._extract_subdomain(host)
        if not subdomain:
            return await call_next(request)
        
        # Find service by subdomain
        service = await self.orchestrator.get_service_by_subdomain(subdomain)
        if not service:
            logger.warning(f"No service found for subdomain: {subdomain}")
            return await call_next(request)
        
        # Check if service is running
        is_running = await self.orchestrator.is_service_running(service["id"])
        
        if not is_running:
            # Start the service
            logger.info(f"Waking up service: {service['name']}")
            await self.orchestrator.wake_service(service["id"])
            
            # Return loading page
            loading_html = get_loading_page(service)
            return HTMLResponse(content=loading_html, status_code=202)
        
        # Service is running, proxy the request
        try:
            service_url = await self.orchestrator.get_service_url(service["id"])
            if not service_url:
                logger.error(f"Could not get URL for service: {service['name']}")
                return await call_next(request)
            
            # Proxy the request
            return await self._proxy_request(request, service_url)
        
        except Exception as e:
            logger.error(f"Error proxying request to {service['name']}: {str(e)}")
            return await call_next(request)
    
    def _extract_subdomain(self, host: str) -> str:
        """Extract subdomain from host header"""
        parts = host.split(".")
        if len(parts) >= 2:
            return parts[0]
        return ""
    
    async def _proxy_request(self, request: Request, target_url: str) -> Response:
        """Proxy request to target service"""
        try:
            # Build target URL
            url = f"{target_url.rstrip('/')}{request.url.path}"
            if request.url.query:
                url += f"?{request.url.query}"
            
            # Prepare headers (remove host header to avoid conflicts)
            headers = dict(request.headers)
            headers.pop("host", None)
            
            # Make request to target service
            response = await self.client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=await request.body(),
                follow_redirects=False
            )
            
            # Stream response back
            async def generate():
                async for chunk in response.aiter_bytes():
                    yield chunk
            
            return StreamingResponse(
                generate(),
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type")
            )
        
        except httpx.TimeoutException:
            logger.error(f"Timeout when proxying to {target_url}")
            return HTMLResponse(
                content="<h1>Service Timeout</h1><p>The service is taking too long to respond.</p>",
                status_code=504
            )
        except Exception as e:
            logger.error(f"Proxy error: {str(e)}")
            return HTMLResponse(
                content=f"<h1>Proxy Error</h1><p>{str(e)}</p>",
                status_code=502
            )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
