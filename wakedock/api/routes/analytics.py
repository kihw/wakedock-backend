"""
Analytics API routes for WakeDock
"""

import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from datetime import datetime
import time

from wakedock.core.auth import get_current_user
from wakedock.core.analytics import analytics_service, Event, EventType, PerformanceMetrics, MetricType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


class EventRequest(BaseModel):
    type: str
    name: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None


class MetricRequest(BaseModel):
    name: str
    value: float
    metric_type: str = "gauge"
    labels: Optional[Dict[str, str]] = None


class PerformanceRequest(BaseModel):
    response_time: float
    cpu_usage: float
    memory_usage: float
    disk_io: float = 0.0
    network_io: float = 0.0
    error_rate: float = 0.0
    throughput: float = 0.0
    availability: float = 100.0


@router.get("/metrics")
async def get_metrics(
    name: Optional[str] = Query(None, description="Metric name to filter by"),
    start_time: Optional[float] = Query(None, description="Start time (Unix timestamp)"),
    end_time: Optional[float] = Query(None, description="End time (Unix timestamp)"),
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get metrics data"""
    try:
        metrics = await analytics_service.get_metrics(name, start_time, end_time)
        return {
            "success": True,
            "data": metrics
        }
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get metrics")


@router.post("/metrics")
async def record_metric(
    request: MetricRequest,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Record a metric"""
    try:
        metric_type = MetricType(request.metric_type)
        await analytics_service.record_metric(
            request.name,
            request.value,
            metric_type,
            request.labels
        )
        return {
            "success": True,
            "message": f"Metric {request.name} recorded successfully"
        }
    except Exception as e:
        logger.error(f"Failed to record metric: {e}")
        raise HTTPException(status_code=500, detail="Failed to record metric")


@router.get("/performance")
async def get_performance_metrics(
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get performance metrics summary"""
    try:
        performance = await analytics_service.get_performance_summary()
        return {
            "success": True,
            "data": performance
        }
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance metrics")


@router.post("/performance")
async def record_performance_metrics(
    request: PerformanceRequest,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Record performance metrics"""
    try:
        metrics = PerformanceMetrics(
            response_time=request.response_time,
            cpu_usage=request.cpu_usage,
            memory_usage=request.memory_usage,
            disk_io=request.disk_io,
            network_io=request.network_io,
            error_rate=request.error_rate,
            throughput=request.throughput,
            availability=request.availability
        )
        await analytics_service.record_performance_metrics(metrics)
        return {
            "success": True,
            "message": "Performance metrics recorded successfully"
        }
    except Exception as e:
        logger.error(f"Failed to record performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to record performance metrics")


@router.get("/users")
async def get_user_analytics(
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get user analytics"""
    try:
        user_analytics = await analytics_service.get_user_analytics()
        return {
            "success": True,
            "data": user_analytics
        }
    except Exception as e:
        logger.error(f"Failed to get user analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user analytics")


@router.get("/api")
async def get_api_analytics(
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get API analytics"""
    try:
        api_analytics = await analytics_service.get_api_analytics()
        return {
            "success": True,
            "data": api_analytics
        }
    except Exception as e:
        logger.error(f"Failed to get API analytics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get API analytics")


@router.post("/events")
async def record_event(
    request: EventRequest,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Record an analytics event"""
    try:
        event = Event(
            id=f"event_{int(time.time() * 1000)}",
            type=EventType(request.type),
            name=request.name,
            timestamp=time.time(),
            user_id=request.user_id or user.get("id"),
            session_id=request.session_id,
            properties=request.properties or {}
        )
        await analytics_service.record_event(event)
        return {
            "success": True,
            "message": "Event recorded successfully"
        }
    except Exception as e:
        logger.error(f"Failed to record event: {e}")
        raise HTTPException(status_code=500, detail="Failed to record event")


@router.get("/realtime")
async def get_realtime_metrics(
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get real-time metrics"""
    try:
        realtime = await analytics_service.get_real_time_metrics()
        return {
            "success": True,
            "data": realtime
        }
    except Exception as e:
        logger.error(f"Failed to get real-time metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get real-time metrics")


@router.get("/dashboard")
async def get_dashboard_data(
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get analytics dashboard data"""
    try:
        # Get all dashboard data in parallel
        dashboard_data = {
            "performance": await analytics_service.get_performance_summary(),
            "users": await analytics_service.get_user_analytics(),
            "api": await analytics_service.get_api_analytics(),
            "realtime": await analytics_service.get_real_time_metrics(),
            "health": await analytics_service.get_system_health(),
            "alerts": await analytics_service.get_alerts(acknowledged=False)
        }
        
        return {
            "success": True,
            "data": dashboard_data,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Failed to get dashboard data: {e}")
        raise HTTPException(status_code=500, detail="Failed to get dashboard data")


@router.post("/export")
async def export_analytics_data(
    start_time: Optional[float] = Query(None, description="Start time (Unix timestamp)"),
    end_time: Optional[float] = Query(None, description="End time (Unix timestamp)"),
    format: str = Query("json", description="Export format"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Export analytics data"""
    try:
        export_data = await analytics_service.export_analytics_data(
            start_time, end_time, format
        )
        
        return {
            "success": True,
            "data": export_data,
            "message": "Analytics data exported successfully"
        }
    except Exception as e:
        logger.error(f"Failed to export analytics data: {e}")
        raise HTTPException(status_code=500, detail="Failed to export analytics data")


# Initialize analytics service on startup
@router.on_event("startup")
async def startup_event():
    """Initialize analytics service"""
    await analytics_service.initialize()
    logger.info("Analytics service initialized")