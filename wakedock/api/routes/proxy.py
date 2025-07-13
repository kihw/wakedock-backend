"""
Proxy endpoints for handling service requests
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{subdomain:path}", include_in_schema=False)
async def proxy_request(request: Request, subdomain: str):
    """Handle proxy requests to services"""
    # This will be handled by the ProxyMiddleware
    # This endpoint is just a fallback
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>WakeDock</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
            .container { max-width: 600px; margin: 0 auto; }
            .logo { font-size: 2em; margin-bottom: 20px; }
            .message { font-size: 1.2em; color: #666; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">🐳 WakeDock</div>
            <div class="message">
                Service not found or not configured.
            </div>
        </div>
    </body>
    </html>
    """)


@router.api_route("/{subdomain:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"], include_in_schema=False)
async def proxy_request_all_methods(request: Request, subdomain: str):
    """Handle all HTTP methods for proxy requests"""
    return await proxy_request(request, subdomain)
