"""
Analytics Routes - API endpoints for analytics operations
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Body, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from wakedock.core.database import get_async_session
from wakedock.core.dependencies import get_current_user
from wakedock.core.exceptions import ValidationError, NotFoundError, ServiceError
from wakedock.controllers.analytics_controller import AnalyticsController
from wakedock.serializers.analytics_serializers import (
    MetricCreateRequest, MetricUpdateRequest, MetricValueRequest,
    MetricAggregationRequest, ContainerAnalyticsRequest, ServiceAnalyticsRequest,
    CustomReportRequest, CorrelationRequest, AnomalyDetectionRequest,
    ForecastRequest, ExportRequest, BulkOperationRequest,
    DashboardRequest, SearchRequest, TimeRangeRequest,
    MetricResponse, AggregationResponse, AnalyticsResponse,
    ReportResponse, CorrelationResponse, AnomalyResponse,
    ForecastResponse, ExportResponse, HealthResponse,
    BulkOperationResponse, DashboardResponse, PaginatedResponse,
    ErrorResponse, SuccessResponse, AnalyticsSerializer
)
from wakedock.views.analytics_view import AnalyticsView
from wakedock.core.logging import get_logger

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/metrics", response_model=MetricResponse)
async def create_metric(
    request: MetricCreateRequest,
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Create a new metric"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Create metric
        metric_data = await controller.create_metric(request.dict())
        
        # Format response
        response_data = view.format_metric_response(metric_data)
        
        logger.info(f"Created metric: {request.name}")
        return response_data
        
    except ValidationError as e:
        logger.error(f"Validation error creating metric: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error creating metric: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating metric: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/metrics", response_model=PaginatedResponse)
async def get_metrics(
    search: Optional[str] = Query(None, description="Search metrics by name"),
    metric_type: Optional[str] = Query(None, description="Filter by metric type"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Sort by field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Get list of metrics with filtering and pagination"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Build search parameters
        search_params = {
            'search': search,
            'metric_type': metric_type,
            'active': active,
            'page': page,
            'per_page': per_page,
            'sort_by': sort_by,
            'sort_order': sort_order
        }
        
        # Get metrics
        metrics_data = await controller.get_metrics(search_params)
        
        # Format response
        response_data = view.format_metrics_list_response(
            metrics_data['metrics'],
            metrics_data['total_count'],
            page,
            per_page
        )
        
        return response_data
        
    except Exception as e:
        logger.error(f"Error getting metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/metrics/{metric_id}", response_model=MetricResponse)
async def get_metric(
    metric_id: str = Path(..., description="Metric ID"),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Get a specific metric by ID"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Get metric
        metric_data = await controller.get_metric(metric_id)
        
        # Format response
        response_data = view.format_metric_response(metric_data)
        
        return response_data
        
    except NotFoundError as e:
        logger.error(f"Metric not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting metric: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/metrics/{metric_id}", response_model=MetricResponse)
async def update_metric(
    metric_id: str = Path(..., description="Metric ID"),
    request: MetricUpdateRequest = Body(...),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Update a metric"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Update metric
        metric_data = await controller.update_metric(metric_id, request.dict(exclude_unset=True))
        
        # Format response
        response_data = view.format_metric_response(metric_data)
        
        logger.info(f"Updated metric: {metric_id}")
        return response_data
        
    except NotFoundError as e:
        logger.error(f"Metric not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error updating metric: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating metric: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/metrics/{metric_id}", response_model=SuccessResponse)
async def delete_metric(
    metric_id: str = Path(..., description="Metric ID"),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Delete a metric"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Delete metric
        await controller.delete_metric(metric_id)
        
        logger.info(f"Deleted metric: {metric_id}")
        return view.format_success_response(f"Metric {metric_id} deleted successfully")
        
    except NotFoundError as e:
        logger.error(f"Metric not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting metric: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/metrics/{metric_id}/values", response_model=SuccessResponse)
async def record_metric_value(
    metric_id: str = Path(..., description="Metric ID"),
    request: MetricValueRequest = Body(...),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Record a metric value"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Record value
        result = await controller.record_metric_value(
            metric_id,
            request.value,
            request.timestamp,
            request.labels
        )
        
        return view.format_success_response(
            "Metric value recorded successfully",
            result
        )
        
    except NotFoundError as e:
        logger.error(f"Metric not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error recording value: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error recording metric value: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/metrics/{metric_id}/aggregation", response_model=AggregationResponse)
async def get_metric_aggregation(
    metric_id: str = Path(..., description="Metric ID"),
    request: MetricAggregationRequest = Body(...),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Get metric aggregation data"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Get aggregation
        aggregation_data = await controller.get_aggregated_metrics(
            metric_id,
            request.aggregation_type,
            request.time_range.start,
            request.time_range.end,
            request.granularity
        )
        
        # Format response
        response_data = view.format_aggregation_response(aggregation_data)
        
        return response_data
        
    except NotFoundError as e:
        logger.error(f"Metric not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error getting aggregation: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting metric aggregation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/containers/analytics", response_model=AnalyticsResponse)
async def get_container_analytics(
    request: ContainerAnalyticsRequest = Body(...),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Get container analytics"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Get analytics
        analytics_data = await controller.get_container_analytics(
            request.container_id,
            request.time_range.start,
            request.time_range.end
        )
        
        # Format response
        response_data = view.format_container_analytics_response(analytics_data)
        
        return response_data
        
    except ValidationError as e:
        logger.error(f"Validation error getting container analytics: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting container analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/services/analytics", response_model=AnalyticsResponse)
async def get_service_analytics(
    request: ServiceAnalyticsRequest = Body(...),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Get service analytics"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Get analytics
        analytics_data = await controller.get_service_analytics(
            request.service_id,
            request.time_range.start,
            request.time_range.end
        )
        
        # Format response
        response_data = view.format_service_analytics_response(analytics_data)
        
        return response_data
        
    except ValidationError as e:
        logger.error(f"Validation error getting service analytics: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting service analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/reports", response_model=ReportResponse)
async def create_custom_report(
    request: CustomReportRequest = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Create a custom analytics report"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Create report
        report_data = await controller.create_custom_report(request.dict())
        
        # Format response
        response_data = view.format_report_response(report_data)
        
        logger.info(f"Created report: {report_data['report_id']}")
        return response_data
        
    except ValidationError as e:
        logger.error(f"Validation error creating report: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating report: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/correlations", response_model=CorrelationResponse)
async def get_metric_correlations(
    request: CorrelationRequest = Body(...),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Get metric correlations"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Get correlations
        correlation_data = await controller.get_metric_correlations(
            request.metric_ids,
            request.time_range.start,
            request.time_range.end
        )
        
        # Format response
        response_data = view.format_correlation_response(correlation_data)
        
        return response_data
        
    except ValidationError as e:
        logger.error(f"Validation error getting correlations: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting correlations: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/anomalies", response_model=AnomalyResponse)
async def detect_anomalies(
    request: AnomalyDetectionRequest = Body(...),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Detect anomalies in metric data"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Detect anomalies
        anomaly_data = await controller.get_anomaly_detection(
            request.metric_id,
            request.time_range.start,
            request.time_range.end,
            request.sensitivity
        )
        
        # Format response
        response_data = view.format_anomaly_response(anomaly_data)
        
        return response_data
        
    except ValidationError as e:
        logger.error(f"Validation error detecting anomalies: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error detecting anomalies: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/forecasts", response_model=ForecastResponse)
async def generate_forecast(
    request: ForecastRequest = Body(...),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Generate forecasting for a metric"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Generate forecast
        forecast_data = await controller.get_forecasting(
            request.metric_id,
            request.forecast_hours
        )
        
        # Format response
        response_data = view.format_forecast_response(forecast_data)
        
        return response_data
        
    except ValidationError as e:
        logger.error(f"Validation error generating forecast: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating forecast: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/export", response_model=ExportResponse)
async def export_metrics_data(
    request: ExportRequest = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Export metrics data"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Export data
        export_data = await controller.export_metrics_data(request.config.dict())
        
        # Format response
        response_data = view.format_export_response(export_data)
        
        logger.info(f"Exported data: {export_data['export_id']}")
        return response_data
        
    except ValidationError as e:
        logger.error(f"Validation error exporting data: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error exporting data: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health", response_model=HealthResponse)
async def get_system_health(
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Get system health metrics"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Get health metrics
        health_data = await controller.get_system_health_metrics()
        
        # Format response
        response_data = view.format_health_metrics_response(health_data)
        
        return response_data
        
    except Exception as e:
        logger.error(f"Error getting system health: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/bulk-operations", response_model=BulkOperationResponse)
async def bulk_metric_operation(
    request: BulkOperationRequest = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Perform bulk operations on metrics"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Perform bulk operation
        operation_data = await controller.bulk_metric_operation(request.dict())
        
        # Format response
        response_data = view.format_bulk_operation_response(operation_data)
        
        logger.info(f"Performed bulk {request.operation} on {len(request.metric_ids)} metrics")
        return response_data
        
    except ValidationError as e:
        logger.error(f"Validation error in bulk operation: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in bulk operation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/cleanup", response_model=SuccessResponse)
async def cleanup_old_metrics(
    retention_days: int = Query(90, ge=1, le=365, description="Retention period in days"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Clean up old metric data"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Cleanup old data
        cleanup_result = await controller.cleanup_old_metrics(retention_days)
        
        logger.info(f"Cleaned up metrics older than {retention_days} days")
        return view.format_success_response(
            f"Cleaned up {cleanup_result.get('deleted_count', 0)} old metric records",
            cleanup_result
        )
        
    except Exception as e:
        logger.error(f"Error cleaning up old metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Dashboard routes

@router.post("/dashboards", response_model=DashboardResponse)
async def create_dashboard(
    request: DashboardRequest = Body(...),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Create a new dashboard"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Create dashboard
        dashboard_data = await controller.create_dashboard(request.dict())
        
        # Format response
        response_data = view.format_dashboard_response(dashboard_data)
        
        logger.info(f"Created dashboard: {dashboard_data['dashboard_id']}")
        return response_data
        
    except ValidationError as e:
        logger.error(f"Validation error creating dashboard: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/dashboards", response_model=PaginatedResponse)
async def get_dashboards(
    search: Optional[str] = Query(None, description="Search dashboards by name"),
    public: Optional[bool] = Query(None, description="Filter by public status"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Get list of dashboards"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Build search parameters
        search_params = {
            'search': search,
            'public': public,
            'page': page,
            'per_page': per_page
        }
        
        # Get dashboards
        dashboards_data = await controller.get_dashboards(search_params)
        
        # Format response
        formatted_dashboards = [
            view.format_dashboard_response(dashboard)
            for dashboard in dashboards_data['dashboards']
        ]
        
        return view.create_paginated_response(
            formatted_dashboards,
            dashboards_data['total_count'],
            page,
            per_page
        )
        
    except Exception as e:
        logger.error(f"Error getting dashboards: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/dashboards/{dashboard_id}", response_model=DashboardResponse)
async def get_dashboard(
    dashboard_id: str = Path(..., description="Dashboard ID"),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Get a specific dashboard"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Get dashboard
        dashboard_data = await controller.get_dashboard(dashboard_id)
        
        # Format response
        response_data = view.format_dashboard_response(dashboard_data)
        
        return response_data
        
    except NotFoundError as e:
        logger.error(f"Dashboard not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/dashboards/{dashboard_id}", response_model=DashboardResponse)
async def update_dashboard(
    dashboard_id: str = Path(..., description="Dashboard ID"),
    request: DashboardRequest = Body(...),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Update a dashboard"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Update dashboard
        dashboard_data = await controller.update_dashboard(dashboard_id, request.dict())
        
        # Format response
        response_data = view.format_dashboard_response(dashboard_data)
        
        logger.info(f"Updated dashboard: {dashboard_id}")
        return response_data
        
    except NotFoundError as e:
        logger.error(f"Dashboard not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error updating dashboard: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/dashboards/{dashboard_id}", response_model=SuccessResponse)
async def delete_dashboard(
    dashboard_id: str = Path(..., description="Dashboard ID"),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Delete a dashboard"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        # Delete dashboard
        await controller.delete_dashboard(dashboard_id)
        
        logger.info(f"Deleted dashboard: {dashboard_id}")
        return view.format_success_response(f"Dashboard {dashboard_id} deleted successfully")
        
    except NotFoundError as e:
        logger.error(f"Dashboard not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Streaming endpoints

@router.get("/metrics/{metric_id}/stream")
async def stream_metric_data(
    metric_id: str = Path(..., description="Metric ID"),
    interval: int = Query(5, ge=1, le=60, description="Update interval in seconds"),
    db: AsyncSession = Depends(get_async_session),
    current_user: dict = Depends(get_current_user)
):
    """Stream real-time metric data"""
    try:
        controller = AnalyticsController(db)
        view = AnalyticsView()
        
        async def generate_stream():
            while True:
                try:
                    # Get latest metric data
                    metric_data = await controller.get_metric_realtime_data(metric_id)
                    
                    # Format for streaming
                    response_data = view.create_streaming_response(metric_data)
                    
                    yield f"data: {response_data}\n\n"
                    
                    # Wait for next interval
                    await asyncio.sleep(interval)
                    
                except Exception as e:
                    logger.error(f"Error in metric stream: {str(e)}")
                    break
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*"
            }
        )
        
    except NotFoundError as e:
        logger.error(f"Metric not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error streaming metric data: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


# WebSocket endpoints would go here for real-time updates

# Error handlers

@router.exception_handler(ValidationError)
async def validation_error_handler(request, exc):
    """Handle validation errors"""
    view = AnalyticsView()
    return JSONResponse(
        status_code=400,
        content=view.format_error_response(str(exc), "VALIDATION_ERROR")
    )


@router.exception_handler(NotFoundError)
async def not_found_error_handler(request, exc):
    """Handle not found errors"""
    view = AnalyticsView()
    return JSONResponse(
        status_code=404,
        content=view.format_error_response(str(exc), "NOT_FOUND")
    )


@router.exception_handler(ServiceError)
async def service_error_handler(request, exc):
    """Handle service errors"""
    view = AnalyticsView()
    return JSONResponse(
        status_code=500,
        content=view.format_error_response(str(exc), "SERVICE_ERROR")
    )


# Health check endpoint
@router.get("/ping")
async def ping():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
