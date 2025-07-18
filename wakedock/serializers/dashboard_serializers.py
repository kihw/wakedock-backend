"""
Dashboard Serializers - Pydantic models for dashboard data validation
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum


class WidgetType(str, Enum):
    """Widget types enum"""
    CHART = "chart"
    METRIC = "metric"
    TABLE = "table"
    TEXT = "text"
    IMAGE = "image"
    GAUGE = "gauge"
    HEATMAP = "heatmap"
    MAP = "map"
    PROGRESS = "progress"
    ALERT = "alert"
    LOG = "log"
    IFRAME = "iframe"
    CUSTOM = "custom"


class ChartType(str, Enum):
    """Chart types enum"""
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    DOUGHNUT = "doughnut"
    RADAR = "radar"
    SCATTER = "scatter"
    BUBBLE = "bubble"
    AREA = "area"
    COLUMN = "column"
    HISTOGRAM = "histogram"
    CANDLESTICK = "candlestick"


class AggregationType(str, Enum):
    """Aggregation types enum"""
    AVG = "avg"
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    MEDIAN = "median"
    MODE = "mode"
    STD = "std"
    VAR = "var"


class LayoutType(str, Enum):
    """Layout types enum"""
    GRID = "grid"
    FLOW = "flow"
    FIXED = "fixed"


class ThemeMode(str, Enum):
    """Theme modes enum"""
    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


class FilterType(str, Enum):
    """Filter types enum"""
    TEXT = "text"
    SELECT = "select"
    DATE = "date"
    NUMBER = "number"
    BOOLEAN = "boolean"


class PositionModel(BaseModel):
    """Widget position model"""
    x: Optional[int] = Field(None, ge=0, description="X coordinate")
    y: Optional[int] = Field(None, ge=0, description="Y coordinate")
    row: Optional[int] = Field(None, ge=0, description="Row number")
    col: Optional[int] = Field(None, ge=0, description="Column number")


class SizeModel(BaseModel):
    """Widget size model"""
    width: Optional[int] = Field(None, ge=1, le=12, description="Widget width")
    height: Optional[int] = Field(None, ge=1, le=20, description="Widget height")
    min_width: Optional[int] = Field(None, ge=1, description="Minimum width")
    min_height: Optional[int] = Field(None, ge=1, description="Minimum height")


class LayoutModel(BaseModel):
    """Dashboard layout model"""
    type: LayoutType = Field(LayoutType.GRID, description="Layout type")
    columns: Optional[int] = Field(None, ge=1, le=12, description="Number of columns")
    rows: Optional[int] = Field(None, ge=1, le=20, description="Number of rows")
    gap: Optional[int] = Field(None, ge=0, le=50, description="Gap between widgets")


class ThemeModel(BaseModel):
    """Dashboard theme model"""
    mode: ThemeMode = Field(ThemeMode.LIGHT, description="Theme mode")
    colors: Optional[Dict[str, str]] = Field(None, description="Custom colors")
    
    @validator('colors')
    def validate_colors(cls, v):
        if v is not None:
            import re
            color_pattern = re.compile(r'^#[0-9A-Fa-f]{6}$')
            for color_name, color_value in v.items():
                if not color_pattern.match(color_value):
                    raise ValueError(f"Invalid color format for {color_name}: {color_value}")
        return v


class FilterModel(BaseModel):
    """Dashboard filter model"""
    name: str = Field(..., description="Filter name")
    type: FilterType = Field(..., description="Filter type")
    options: Optional[List[str]] = Field(None, description="Filter options")
    default_value: Optional[Any] = Field(None, description="Default value")


class ChartConfigModel(BaseModel):
    """Chart widget configuration model"""
    chart_type: ChartType = Field(ChartType.LINE, description="Chart type")
    aggregation: AggregationType = Field(AggregationType.AVG, description="Aggregation type")
    time_period: str = Field("1h", description="Time period")
    colors: Optional[List[str]] = Field(None, description="Chart colors")
    show_legend: bool = Field(True, description="Show legend")
    show_grid: bool = Field(True, description="Show grid")
    
    @validator('colors')
    def validate_colors(cls, v):
        if v is not None:
            import re
            color_pattern = re.compile(r'^#[0-9A-Fa-f]{6}$')
            for color in v:
                if not color_pattern.match(color):
                    raise ValueError(f"Invalid color format: {color}")
        return v


class MetricConfigModel(BaseModel):
    """Metric widget configuration model"""
    format: str = Field("number", description="Value format")
    unit: Optional[str] = Field(None, description="Value unit")
    threshold: Optional[float] = Field(None, description="Threshold value")
    show_trend: bool = Field(True, description="Show trend")
    show_change: bool = Field(True, description="Show change")


class TableConfigModel(BaseModel):
    """Table widget configuration model"""
    columns: List[Dict[str, Any]] = Field(..., description="Table columns")
    pagination: bool = Field(True, description="Enable pagination")
    page_size: int = Field(10, ge=1, le=100, description="Page size")
    sortable: bool = Field(True, description="Enable sorting")
    searchable: bool = Field(True, description="Enable searching")


class GaugeConfigModel(BaseModel):
    """Gauge widget configuration model"""
    min_value: float = Field(0, description="Minimum value")
    max_value: float = Field(100, description="Maximum value")
    thresholds: Optional[List[Dict[str, Any]]] = Field(None, description="Thresholds")
    show_value: bool = Field(True, description="Show value")
    show_percentage: bool = Field(True, description="Show percentage")
    
    @validator('max_value')
    def validate_max_value(cls, v, values):
        if 'min_value' in values and v <= values['min_value']:
            raise ValueError("Maximum value must be greater than minimum value")
        return v


class TextConfigModel(BaseModel):
    """Text widget configuration model"""
    content: str = Field(..., max_length=10000, description="Text content")
    format: str = Field("plain", description="Text format")
    font_size: Optional[int] = Field(None, ge=8, le=72, description="Font size")
    alignment: str = Field("left", description="Text alignment")


class ImageConfigModel(BaseModel):
    """Image widget configuration model"""
    url: str = Field(..., description="Image URL")
    alt_text: Optional[str] = Field(None, description="Alt text")
    fit: str = Field("contain", description="Image fit")
    
    @validator('url')
    def validate_url(cls, v):
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError("Image URL must be a valid HTTP(S) URL")
        return v


class AlertConfigModel(BaseModel):
    """Alert widget configuration model"""
    severity: str = Field("medium", description="Alert severity")
    conditions: List[Dict[str, Any]] = Field(..., description="Alert conditions")
    auto_dismiss: bool = Field(False, description="Auto dismiss")
    sound_enabled: bool = Field(True, description="Sound enabled")


class IframeConfigModel(BaseModel):
    """Iframe widget configuration model"""
    url: str = Field(..., description="Iframe URL")
    sandbox: bool = Field(True, description="Enable sandbox")
    
    @validator('url')
    def validate_url(cls, v):
        if not (v.startswith('http://') or v.startswith('https://')):
            raise ValueError("Iframe URL must be a valid HTTP(S) URL")
        return v


class QueryModel(BaseModel):
    """Widget query model"""
    metric: Optional[str] = Field(None, description="Metric name")
    aggregation: AggregationType = Field(AggregationType.AVG, description="Aggregation type")
    time_range: str = Field("1h", description="Time range")
    filters: Optional[Dict[str, Any]] = Field(None, description="Query filters")
    group_by: Optional[List[str]] = Field(None, description="Group by fields")


class CreateWidgetRequest(BaseModel):
    """Create widget request model"""
    title: str = Field(..., min_length=1, max_length=100, description="Widget title")
    type: WidgetType = Field(..., description="Widget type")
    dashboard_id: str = Field(..., description="Dashboard ID")
    position: Optional[PositionModel] = Field(None, description="Widget position")
    size: Optional[SizeModel] = Field(None, description="Widget size")
    config: Optional[Dict[str, Any]] = Field(None, description="Widget configuration")
    metric_id: Optional[str] = Field(None, description="Metric ID")
    query: Optional[QueryModel] = Field(None, description="Widget query")
    refresh_interval: int = Field(60, ge=10, le=3600, description="Refresh interval in seconds")
    active: bool = Field(True, description="Widget active status")


class UpdateWidgetRequest(BaseModel):
    """Update widget request model"""
    title: Optional[str] = Field(None, min_length=1, max_length=100, description="Widget title")
    type: Optional[WidgetType] = Field(None, description="Widget type")
    position: Optional[PositionModel] = Field(None, description="Widget position")
    size: Optional[SizeModel] = Field(None, description="Widget size")
    config: Optional[Dict[str, Any]] = Field(None, description="Widget configuration")
    metric_id: Optional[str] = Field(None, description="Metric ID")
    query: Optional[QueryModel] = Field(None, description="Widget query")
    refresh_interval: Optional[int] = Field(None, ge=10, le=3600, description="Refresh interval in seconds")
    active: Optional[bool] = Field(None, description="Widget active status")


class CreateDashboardRequest(BaseModel):
    """Create dashboard request model"""
    name: str = Field(..., min_length=1, max_length=100, description="Dashboard name")
    description: Optional[str] = Field(None, max_length=500, description="Dashboard description")
    layout: Optional[LayoutModel] = Field(None, description="Dashboard layout")
    theme: Optional[ThemeModel] = Field(None, description="Dashboard theme")
    refresh_interval: int = Field(60, ge=10, le=86400, description="Refresh interval in seconds")
    auto_refresh: bool = Field(True, description="Auto refresh enabled")
    public: bool = Field(False, description="Public dashboard")
    filters: Optional[List[FilterModel]] = Field(None, description="Dashboard filters")
    widgets: Optional[List[CreateWidgetRequest]] = Field(None, description="Dashboard widgets")


class UpdateDashboardRequest(BaseModel):
    """Update dashboard request model"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Dashboard name")
    description: Optional[str] = Field(None, max_length=500, description="Dashboard description")
    layout: Optional[LayoutModel] = Field(None, description="Dashboard layout")
    theme: Optional[ThemeModel] = Field(None, description="Dashboard theme")
    refresh_interval: Optional[int] = Field(None, ge=10, le=86400, description="Refresh interval in seconds")
    auto_refresh: Optional[bool] = Field(None, description="Auto refresh enabled")
    public: Optional[bool] = Field(None, description="Public dashboard")
    filters: Optional[List[FilterModel]] = Field(None, description="Dashboard filters")
    widgets: Optional[List[UpdateWidgetRequest]] = Field(None, description="Dashboard widgets")


class DashboardSearchRequest(BaseModel):
    """Dashboard search request model"""
    query: Optional[str] = Field(None, description="Search query")
    filters: Optional[Dict[str, Any]] = Field(None, description="Search filters")
    sort: Optional[Dict[str, str]] = Field(None, description="Sort configuration")
    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(20, ge=1, le=100, description="Items per page")


class TimeRangeRequest(BaseModel):
    """Time range request model"""
    start: datetime = Field(..., description="Start time")
    end: datetime = Field(..., description="End time")
    
    @validator('end')
    def validate_end_time(cls, v, values):
        if 'start' in values and v <= values['start']:
            raise ValueError("End time must be after start time")
        return v


class DashboardExportRequest(BaseModel):
    """Dashboard export request model"""
    format: str = Field("json", description="Export format")
    include_data: bool = Field(False, description="Include widget data")
    include_metadata: bool = Field(True, description="Include metadata")


class DashboardImportRequest(BaseModel):
    """Dashboard import request model"""
    data: Dict[str, Any] = Field(..., description="Import data")
    new_name: Optional[str] = Field(None, description="New dashboard name")
    overwrite: bool = Field(False, description="Overwrite existing dashboard")


class BulkWidgetRequest(BaseModel):
    """Bulk widget operation request model"""
    operation: str = Field(..., description="Operation type")
    widgets: List[Dict[str, Any]] = Field(..., description="Widget data")


class RealTimeRequest(BaseModel):
    """Real-time data request model"""
    dashboard_id: str = Field(..., description="Dashboard ID")
    websocket_id: str = Field(..., description="WebSocket ID")


class ScheduleConfigModel(BaseModel):
    """Schedule configuration model"""
    frequency: str = Field(..., description="Schedule frequency")
    time: Optional[str] = Field(None, description="Schedule time")
    days: Optional[List[str]] = Field(None, description="Schedule days")
    timezone: str = Field("UTC", description="Timezone")
    enabled: bool = Field(True, description="Schedule enabled")


class DashboardReportRequest(BaseModel):
    """Dashboard report request model"""
    dashboard_id: str = Field(..., description="Dashboard ID")
    schedule: ScheduleConfigModel = Field(..., description="Schedule configuration")
    recipients: List[str] = Field(..., description="Report recipients")
    format: str = Field("pdf", description="Report format")


class DashboardTemplateRequest(BaseModel):
    """Dashboard template request model"""
    name: str = Field(..., description="Template name")
    description: Optional[str] = Field(None, description="Template description")
    category: Optional[str] = Field(None, description="Template category")
    tags: Optional[List[str]] = Field(None, description="Template tags")


class DashboardBackupRequest(BaseModel):
    """Dashboard backup request model"""
    dashboard_id: str = Field(..., description="Dashboard ID")
    name: Optional[str] = Field(None, description="Backup name")
    description: Optional[str] = Field(None, description="Backup description")


class DashboardRestoreRequest(BaseModel):
    """Dashboard restore request model"""
    backup_id: str = Field(..., description="Backup ID")
    new_name: Optional[str] = Field(None, description="New dashboard name")
    overwrite: bool = Field(False, description="Overwrite existing dashboard")


class DashboardAnalyticsRequest(BaseModel):
    """Dashboard analytics request model"""
    dashboard_id: str = Field(..., description="Dashboard ID")
    time_range: TimeRangeRequest = Field(..., description="Time range")
    metrics: Optional[List[str]] = Field(None, description="Specific metrics")
    include_trends: bool = Field(True, description="Include trends")
    include_forecasts: bool = Field(False, description="Include forecasts")


class DashboardInsightsRequest(BaseModel):
    """Dashboard insights request model"""
    dashboard_id: str = Field(..., description="Dashboard ID")
    time_range: TimeRangeRequest = Field(..., description="Time range")
    insight_types: Optional[List[str]] = Field(None, description="Insight types")
    confidence_threshold: float = Field(0.8, ge=0, le=1, description="Confidence threshold")


class DashboardOptimizationRequest(BaseModel):
    """Dashboard optimization request model"""
    dashboard_id: str = Field(..., description="Dashboard ID")
    optimization_types: Optional[List[str]] = Field(None, description="Optimization types")
    apply_changes: bool = Field(False, description="Apply optimization changes")


class DashboardResponse(BaseModel):
    """Dashboard response model"""
    id: str = Field(..., description="Dashboard ID")
    name: str = Field(..., description="Dashboard name")
    description: Optional[str] = Field(None, description="Dashboard description")
    layout: Optional[LayoutModel] = Field(None, description="Dashboard layout")
    theme: Optional[ThemeModel] = Field(None, description="Dashboard theme")
    refresh_interval: int = Field(..., description="Refresh interval")
    auto_refresh: bool = Field(..., description="Auto refresh enabled")
    public: bool = Field(..., description="Public dashboard")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Update timestamp")
    last_accessed: Optional[datetime] = Field(None, description="Last access timestamp")
    access_count: int = Field(..., description="Access count")
    widgets: List[Dict[str, Any]] = Field(..., description="Dashboard widgets")
    filters: List[FilterModel] = Field(..., description="Dashboard filters")


class WidgetResponse(BaseModel):
    """Widget response model"""
    id: str = Field(..., description="Widget ID")
    dashboard_id: str = Field(..., description="Dashboard ID")
    title: str = Field(..., description="Widget title")
    type: WidgetType = Field(..., description="Widget type")
    config: Dict[str, Any] = Field(..., description="Widget configuration")
    position: Optional[PositionModel] = Field(None, description="Widget position")
    size: Optional[SizeModel] = Field(None, description="Widget size")
    metric_id: Optional[str] = Field(None, description="Metric ID")
    query: Optional[QueryModel] = Field(None, description="Widget query")
    refresh_interval: int = Field(..., description="Refresh interval")
    active: bool = Field(..., description="Widget active status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Update timestamp")
    data: Optional[Any] = Field(None, description="Widget data")
    status: str = Field(..., description="Widget status")


class DashboardListResponse(BaseModel):
    """Dashboard list response model"""
    dashboards: List[DashboardResponse] = Field(..., description="Dashboard list")
    total_count: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total pages")


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")
    timestamp: datetime = Field(..., description="Error timestamp")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")
