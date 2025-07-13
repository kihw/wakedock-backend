#!/usr/bin/env python3
"""
Health check script for WakeDock container.
Validates that the FastAPI server is running and responsive.
"""

import sys
import os
import asyncio
import httpx
import logging
from typing import Dict, Any


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
HOST = os.getenv('WAKEDOCK_HOST', '127.0.0.1')
PORT = int(os.getenv('WAKEDOCK_PORT', '5000'))
TIMEOUT = int(os.getenv('HEALTH_CHECK_TIMEOUT', '10'))
MAX_RETRIES = int(os.getenv('HEALTH_CHECK_RETRIES', '3'))


async def check_health() -> Dict[str, Any]:
    """
    Perform health check on the WakeDock API server.
    
    Returns:
        Dict with health status information
    """
    url = f"http://{HOST}:{PORT}/api/v1/health"
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            
            health_data = response.json()
            return {
                "status": "healthy",
                "response_time": response.elapsed.total_seconds(),
                "status_code": response.status_code,
                "data": health_data
            }
            
        except httpx.TimeoutException:
            return {
                "status": "unhealthy",
                "error": "Request timeout",
                "timeout": TIMEOUT
            }
        except httpx.HTTPStatusError as e:
            return {
                "status": "unhealthy", 
                "error": f"HTTP error: {e.response.status_code}",
                "status_code": e.response.status_code
            }
        except httpx.RequestError as e:
            return {
                "status": "unhealthy",
                "error": f"Connection error: {str(e)}"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": f"Unexpected error: {str(e)}"
            }


async def main():
    """Main health check function with retry logic."""
    logger.info(f"Starting health check for WakeDock at {HOST}:{PORT}")
    
    for attempt in range(1, MAX_RETRIES + 1):
        logger.info(f"Health check attempt {attempt}/{MAX_RETRIES}")
        
        try:
            result = await check_health()
            
            if result["status"] == "healthy":
                logger.info("✅ Health check passed")
                logger.info(f"Response time: {result.get('response_time', 'N/A')}s")
                sys.exit(0)
            else:
                logger.warning(f"❌ Health check failed: {result['error']}")
                
        except Exception as e:
            logger.error(f"❌ Health check error: {str(e)}")
        
        if attempt < MAX_RETRIES:
            await asyncio.sleep(2)  # Wait 2 seconds before retry
    
    logger.error(f"❌ Health check failed after {MAX_RETRIES} attempts")
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())