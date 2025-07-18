"""
Dashboard Routes - API endpoints for dashboard operations
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, List, Optional
from datetime import datetime

from wakedock.core.database import get_db
from wakedock.services.dashboard_service import DashboardService
from wakedock.views.dashboard_view import DashboardView
from wakedock.serializers.dashboard_serializers import (
    CreateDashboardRequest,
    UpdateDashboardRequest,
    CreateWidgetRequest,
    UpdateWidgetRequest,
    DashboardSearchRequest,
    TimeRangeRequest,
    DashboardExportRequest,
    DashboardImportRequest,
    BulkWidgetRequest,
    RealTimeRequest,
    DashboardReportRequest,
    DashboardTemplateRequest,
    DashboardBackupRequest,
    DashboardRestoreRequest,
    DashboardAnalyticsRequest,
    DashboardInsightsRequest,
    DashboardOptimizationRequest,
    DashboardResponse,
    WidgetResponse,
    DashboardListResponse,
    ErrorResponse
)
from wakedock.core.exceptions import ValidationError, NotFoundError, ServiceError
from wakedock.core.logging import get_logger
from wakedock.core.auth import get_current_user

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/dashboards", tags=["dashboards"])


@router.post("/", response_model=DashboardResponse)
async def create_dashboard(
    request: CreateDashboardRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new dashboard"""
    try:
        service = DashboardService(db)
        view = DashboardView()
        
        # Add user context
        dashboard_data = request.dict()
        dashboard_data['created_by'] = current_user['user_id']
        
        # Process request
        result = await service.process_dashboard_request('create', dashboard_data)
        
        # Format response
        response = view.format_dashboard_response(result)
        
        return response['dashboard']
        
    except ValidationError as e:
        logger.error(f"Validation error creating dashboard: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error creating dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{dashboard_id}", response_model=DashboardResponse)
async def get_dashboard(
    dashboard_id: str = Path(..., description="Dashboard ID"),
    start_time: Optional[datetime] = Query(None, description="Start time for data"),
    end_time: Optional[datetime] = Query(None, description="End time for data"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get dashboard by ID"""
    try:
        service = DashboardService(db)
        view = DashboardView()
        
        # Prepare request data
        request_data = {'id': dashboard_id}
        if start_time and end_time:
            request_data['time_range'] = {
                'start': start_time,
                'end': end_time
            }
        
        # Process request
        result = await service.process_dashboard_request('get', request_data)
        
        # Format response
        response = view.format_dashboard_response(result)
        
        return response['dashboard']
        
    except NotFoundError as e:
        logger.error(f"Dashboard not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error getting dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=DashboardListResponse)
async def get_dashboards(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search query"),
    public: Optional[bool] = Query(None, description="Filter by public dashboards"),
    sort_by: Optional[str] = Query("created_at", description="Sort field"),
    sort_order: Optional[str] = Query("desc", description="Sort order"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get dashboards with filtering and pagination"""
    try:
        service = DashboardService(db)
        view = DashboardView()
        
        # Prepare search parameters
        search_params = {
            'page': page,
            'per_page': per_page,
            'search': search,
            'filters': {'public': public} if public is not None else None,
            'sort': {'field': sort_by, 'direction': sort_order}
        }
        
        # Process request
        result = await service.process_dashboard_request('list', search_params)
        
        # Format response
        response = view.format_dashboards_list_response(result)
        
        return response
        
    except ServiceError as e:
        logger.error(f"Service error getting dashboards: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting dashboards: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/{dashboard_id}", response_model=DashboardResponse)
async def update_dashboard(
    dashboard_id: str = Path(..., description="Dashboard ID"),
    request: UpdateDashboardRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update dashboard"""
    try:
        service = DashboardService(db)
        view = DashboardView()
        
        # Prepare request data
        update_data = request.dict(exclude_unset=True)
        update_data['id'] = dashboard_id
        update_data['updated_by'] = current_user['user_id']
        
        # Process request
        result = await service.process_dashboard_request('update', update_data)
        
        # Format response
        response = view.format_dashboard_response(result)
        
        return response['dashboard']
        
    except NotFoundError as e:
        logger.error(f"Dashboard not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error updating dashboard: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error updating dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error updating dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{dashboard_id}")
async def delete_dashboard(
    dashboard_id: str = Path(..., description="Dashboard ID"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete dashboard"""
    try:
        service = DashboardService(db)
        
        # Process request
        result = await service.process_dashboard_request('delete', {'id': dashboard_id})
        
        return {"message": "Dashboard deleted successfully"}
        
    except NotFoundError as e:
        logger.error(f"Dashboard not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error deleting dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error deleting dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{dashboard_id}/clone", response_model=DashboardResponse)
async def clone_dashboard(
    dashboard_id: str = Path(..., description="Dashboard ID"),
    new_name: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Clone dashboard"""
    try:
        service = DashboardService(db)
        view = DashboardView()
        
        # Process request
        result = await service.process_dashboard_request('clone', {
            'id': dashboard_id,
            'new_name': new_name
        })
        
        # Format response
        response = view.format_dashboard_response(result)
        
        return response['dashboard']
        
    except NotFoundError as e:
        logger.error(f"Dashboard not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error cloning dashboard: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error cloning dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error cloning dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{dashboard_id}/export")
async def export_dashboard(
    dashboard_id: str = Path(..., description="Dashboard ID"),
    request: DashboardExportRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Export dashboard"""
    try:
        service = DashboardService(db)
        view = DashboardView()
        
        # Process request
        result = await service.process_dashboard_request('export', {
            'id': dashboard_id,
            'format': request.format,
            'include_data': request.include_data,
            'include_metadata': request.include_metadata
        })
        
        # Format response
        response = view.format_export_response(result)
        
        return response
        
    except NotFoundError as e:
        logger.error(f"Dashboard not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error exporting dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error exporting dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/import", response_model=DashboardResponse)
async def import_dashboard(
    request: DashboardImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Import dashboard"""
    try:
        service = DashboardService(db)
        view = DashboardView()
        
        # Process request
        result = await service.process_dashboard_request('import', {
            'import_data': request.data,
            'new_name': request.new_name,
            'overwrite': request.overwrite
        })
        
        # Format response
        response = view.format_import_response(result)
        
        return response['import_result']['dashboard']
        
    except ValidationError as e:
        logger.error(f"Validation error importing dashboard: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error importing dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error importing dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{dashboard_id}/widgets", response_model=WidgetResponse)
async def create_widget(
    dashboard_id: str = Path(..., description="Dashboard ID"),
    request: CreateWidgetRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create widget"""
    try:
        service = DashboardService(db)
        view = DashboardView()
        
        # Prepare request data
        widget_data = request.dict()
        widget_data['dashboard_id'] = dashboard_id
        widget_data['created_by'] = current_user['user_id']
        
        # Process request
        result = await service.process_widget_request('create', widget_data)
        
        # Format response
        response = view.format_widget_response(result)
        
        return response['widget']
        
    except ValidationError as e:
        logger.error(f"Validation error creating widget: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error creating widget: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error creating widget: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put("/widgets/{widget_id}", response_model=WidgetResponse)
async def update_widget(
    widget_id: str = Path(..., description="Widget ID"),
    request: UpdateWidgetRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update widget"""
    try:
        service = DashboardService(db)
        view = DashboardView()
        
        # Prepare request data
        update_data = request.dict(exclude_unset=True)
        update_data['id'] = widget_id
        update_data['updated_by'] = current_user['user_id']
        
        # Process request
        result = await service.process_widget_request('update', update_data)
        
        # Format response
        response = view.format_widget_response(result)
        
        return response['widget']
        
    except NotFoundError as e:
        logger.error(f"Widget not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error updating widget: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error updating widget: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error updating widget: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/widgets/{widget_id}")
async def delete_widget(
    widget_id: str = Path(..., description="Widget ID"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete widget"""
    try:
        service = DashboardService(db)
        
        # Process request
        result = await service.process_widget_request('delete', {'id': widget_id})
        
        return {"message": "Widget deleted successfully"}
        
    except NotFoundError as e:
        logger.error(f"Widget not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error deleting widget: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error deleting widget: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/widgets/bulk")
async def bulk_widget_operations(
    request: BulkWidgetRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Bulk widget operations"""
    try:
        service = DashboardService(db)
        view = DashboardView()
        
        # Process request
        if request.operation == 'create':
            result = await service.process_widget_request('bulk_create', request.dict())
        elif request.operation == 'update':
            result = await service.process_widget_request('bulk_update', request.dict())
        elif request.operation == 'delete':
            result = await service.process_widget_request('bulk_delete', request.dict())
        else:
            raise ValidationError(f"Unknown bulk operation: {request.operation}")
        
        # Format response
        response = view.format_bulk_operation_response(result)
        
        return response
        
    except ValidationError as e:
        logger.error(f"Validation error in bulk widget operations: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error in bulk widget operations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in bulk widget operations: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{dashboard_id}/realtime")
async def get_dashboard_realtime(
    dashboard_id: str = Path(..., description="Dashboard ID"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get real-time dashboard data"""
    try:
        service = DashboardService(db)
        view = DashboardView()
        
        # Get real-time data
        result = await service.controller.get_dashboard_real_time_data(dashboard_id)
        
        # Format response
        response = view.format_real_time_response(result)
        
        return response
        
    except NotFoundError as e:
        logger.error(f"Dashboard not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error getting real-time data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting real-time data: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{dashboard_id}/analytics")
async def get_dashboard_analytics(
    dashboard_id: str = Path(..., description="Dashboard ID"),
    start_time: datetime = Query(..., description="Start time"),
    end_time: datetime = Query(..., description="End time"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get dashboard analytics"""
    try:
        service = DashboardService(db)
        view = DashboardView()
        
        # Get analytics
        result = await service.controller.get_dashboard_analytics(
            dashboard_id, 
            {'start': start_time, 'end': end_time}
        )
        
        # Format response
        response = view.format_analytics_response(result)
        
        return response
        
    except NotFoundError as e:
        logger.error(f"Dashboard not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error getting analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting analytics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{dashboard_id}/insights")
async def get_dashboard_insights(
    dashboard_id: str = Path(..., description="Dashboard ID"),
    start_time: datetime = Query(..., description="Start time"),
    end_time: datetime = Query(..., description="End time"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get dashboard insights"""
    try:
        service = DashboardService(db)
        view = DashboardView()
        
        # Generate insights
        result = await service.generate_dashboard_insights(
            dashboard_id, 
            {'start': start_time, 'end': end_time}
        )
        
        # Format response
        response = view.format_insights_response(result)
        
        return response
        
    except NotFoundError as e:
        logger.error(f"Dashboard not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error generating insights: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error generating insights: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{dashboard_id}/optimize")
async def optimize_dashboard(
    dashboard_id: str = Path(..., description="Dashboard ID"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Optimize dashboard performance"""
    try:
        service = DashboardService(db)
        
        # Optimize dashboard
        result = await service.optimize_dashboard_performance(dashboard_id)
        
        return result
        
    except NotFoundError as e:
        logger.error(f"Dashboard not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error optimizing dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error optimizing dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/templates")
async def get_dashboard_templates(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get dashboard templates"""
    try:
        service = DashboardService(db)
        view = DashboardView()
        
        # Get templates
        result = await service.controller.get_dashboard_templates()
        
        # Format response
        response = view.format_templates_response(result)
        
        return response
        
    except ServiceError as e:
        logger.error(f"Service error getting templates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting templates: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/statistics")
async def get_dashboard_statistics(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get dashboard statistics"""
    try:
        service = DashboardService(db)
        view = DashboardView()
        
        # Get statistics
        result = await service.controller.get_dashboard_statistics()
        
        # Format response
        response = view.format_statistics_response(result)
        
        return response
        
    except ServiceError as e:
        logger.error(f"Service error getting statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/search")
async def search_dashboards(
    q: str = Query(..., description="Search query"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Search dashboards"""
    try:
        service = DashboardService(db)
        view = DashboardView()
        
        # Search dashboards
        result = await service.controller.search_dashboards(q)
        
        # Format response
        response = view.format_search_response(result)
        
        return response
        
    except ServiceError as e:
        logger.error(f"Service error searching dashboards: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error searching dashboards: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{dashboard_id}/backup")
async def backup_dashboard(
    dashboard_id: str = Path(..., description="Dashboard ID"),
    request: DashboardBackupRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Backup dashboard"""
    try:
        service = DashboardService(db)
        
        # Backup dashboard
        result = await service.backup_dashboard(dashboard_id)
        
        return result
        
    except NotFoundError as e:
        logger.error(f"Dashboard not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error backing up dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error backing up dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/restore")
async def restore_dashboard(
    request: DashboardRestoreRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Restore dashboard from backup"""
    try:
        service = DashboardService(db)
        
        # Restore dashboard
        result = await service.restore_dashboard(request.backup_id)
        
        return result
        
    except NotFoundError as e:
        logger.error(f"Backup not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error restoring dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error restoring dashboard: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{dashboard_id}/reports")
async def schedule_dashboard_report(
    dashboard_id: str = Path(..., description="Dashboard ID"),
    request: DashboardReportRequest = Body(...),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Schedule dashboard report"""
    try:
        service = DashboardService(db)
        
        # Schedule report
        result = await service.schedule_dashboard_report(dashboard_id, request.dict())
        
        return result
        
    except NotFoundError as e:
        logger.error(f"Dashboard not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        logger.error(f"Validation error scheduling report: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error scheduling report: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error scheduling report: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{dashboard_id}/alerts")
async def get_dashboard_alerts(
    dashboard_id: str = Path(..., description="Dashboard ID"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get dashboard alerts"""
    try:
        service = DashboardService(db)
        
        # Process alerts
        result = await service.process_dashboard_alerts(dashboard_id)
        
        return result
        
    except NotFoundError as e:
        logger.error(f"Dashboard not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error processing alerts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error processing alerts: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{dashboard_id}/metrics")
async def get_dashboard_metrics(
    dashboard_id: str = Path(..., description="Dashboard ID"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get dashboard metrics"""
    try:
        service = DashboardService(db)
        
        # Calculate metrics
        result = await service.calculate_dashboard_metrics(dashboard_id)
        
        return result
        
    except NotFoundError as e:
        logger.error(f"Dashboard not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceError as e:
        logger.error(f"Service error calculating metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error calculating metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
