"""
Health check endpoints
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Dict, Any
import psutil
import time
from datetime import datetime

from wakedock.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    version: str
    uptime: float
    system: Dict[str, Any]


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    settings = get_settings()
    
    # System metrics
    system_info = {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory": {
            "total": psutil.virtual_memory().total,
            "available": psutil.virtual_memory().available,
            "percent": psutil.virtual_memory().percent
        },
        "disk": {
            "total": psutil.disk_usage('/').total,
            "free": psutil.disk_usage('/').free,
            "percent": psutil.disk_usage('/').percent
        }
    }
    
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        version="1.0.0",
        uptime=time.time() - psutil.boot_time(),
        system=system_info
    )


@router.get("/metrics")
async def metrics():
    """Prometheus-style metrics endpoint"""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    metrics = [
        f"# HELP wakedock_cpu_percent CPU usage percentage",
        f"# TYPE wakedock_cpu_percent gauge",
        f"wakedock_cpu_percent {cpu_percent}",
        f"",
        f"# HELP wakedock_memory_usage_bytes Memory usage in bytes",
        f"# TYPE wakedock_memory_usage_bytes gauge",
        f"wakedock_memory_usage_bytes {memory.used}",
        f"",
        f"# HELP wakedock_memory_total_bytes Total memory in bytes",
        f"# TYPE wakedock_memory_total_bytes gauge",
        f"wakedock_memory_total_bytes {memory.total}",
        f"",
        f"# HELP wakedock_disk_usage_bytes Disk usage in bytes",
        f"# TYPE wakedock_disk_usage_bytes gauge",
        f"wakedock_disk_usage_bytes {disk.used}",
        f"",
        f"# HELP wakedock_disk_total_bytes Total disk space in bytes",
        f"# TYPE wakedock_disk_total_bytes gauge",
        f"wakedock_disk_total_bytes {disk.total}",
    ]
    
    return "\n".join(metrics)
