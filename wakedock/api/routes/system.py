"""
System management endpoints
"""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime

from wakedock.core.monitoring import MonitoringService

router = APIRouter()


class SystemOverviewResponse(BaseModel):
    total_services: int
    running_services: int
    stopped_services: int
    total_cpu_usage: float
    total_memory_usage: int
    timestamp: datetime


def get_monitoring_service(request: Request) -> MonitoringService:
    """Dependency to get monitoring service from app state"""
    return request.app.state.monitoring


@router.get("/overview", response_model=SystemOverviewResponse)
async def get_system_overview(monitoring: MonitoringService = Depends(get_monitoring_service)):
    """Get system overview metrics"""
    overview = await monitoring.get_system_overview()
    return SystemOverviewResponse(**overview)


@router.get("/health")
async def get_system_health():
    """Get detailed system health status"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "components": {
            "api": "healthy",
            "database": "healthy",
            "docker": "healthy",
            "caddy": "healthy"
        }
    }


@router.get("/metrics")
async def get_system_metrics(monitoring: MonitoringService = Depends(get_monitoring_service)):
    """Get detailed system metrics"""
    # This would return more detailed metrics for monitoring systems
    return {
        "timestamp": datetime.now(),
        "metrics": {
            "requests_total": 0,
            "requests_per_second": 0,
            "error_rate": 0,
            "response_time": 0
        }
    }
