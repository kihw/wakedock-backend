"""
Analytics Serializers - Data serialization and deserialization for analytics
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum

from wakedock.repositories.analytics_repository import MetricType, AggregationType, TimeGranularity


class MetricTypeEnum(str, Enum):
    """Metric type enumeration"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class AggregationTypeEnum(str, Enum):
    """Aggregation type enumeration"""
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    PERCENTILE = "percentile"


class TimeGranularityEnum(str, Enum):
    """Time granularity enumeration"""
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class MetricLabels(BaseModel):
    """Metric labels model"""
    labels: Dict[str, Union[str, int, float, bool]] = Field(default_factory=dict)
    
    @validator('labels')
    def validate_labels(cls, v):
        if not isinstance(v, dict):
            raise ValueError("Labels must be a dictionary")
        
        if len(v) > 50:
            raise ValueError("Too many labels (max 50)")
        
        for key, value in v.items():
            if not isinstance(key, str):
                raise ValueError("Label keys must be strings")
            
            if len(key) > 100:
                raise ValueError("Label key too long (max 100 characters)")
            
            if isinstance(value, str) and len(value) > 200:
                raise ValueError("Label value too long (max 200 characters)")
        
        return v


class MetricMetadata(BaseModel):
    """Metric metadata model"""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('metadata')
    def validate_metadata(cls, v):
        if not isinstance(v, dict):
            raise ValueError("Metadata must be a dictionary")
        
        # Check size (simplified)
        if len(str(v)) > 10000:
            raise ValueError("Metadata too large (max 10000 characters)")
        
        return v


class MetricCreateRequest(BaseModel):
    """Request model for creating a metric"""
    name: str = Field(..., min_length=1, max_length=100)
    type: MetricTypeEnum = Field(...)
    description: Optional[str] = Field(None, max_length=500)
    unit: Optional[str] = Field(None, max_length=50)
    labels: Optional[Dict[str, Union[str, int, float, bool]]] = Field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @validator('name')
    def validate_name(cls, v):
        import re
        if not re.match(r'^[a-zA-Z0-9_\.\-]+$', v):
            raise ValueError("Name must contain only alphanumeric characters, underscores, dots, and hyphens")
        return v


class MetricUpdateRequest(BaseModel):
    """Request model for updating a metric"""
    description: Optional[str] = Field(None, max_length=500)
    unit: Optional[str] = Field(None, max_length=50)
    labels: Optional[Dict[str, Union[str, int, float, bool]]] = None
    metadata: Optional[Dict[str, Any]] = None


class MetricValueRequest(BaseModel):
    """Request model for recording a metric value"""
    value: Union[int, float] = Field(...)
    timestamp: Optional[datetime] = None
    labels: Optional[Dict[str, Union[str, int, float, bool]]] = Field(default_factory=dict)
    
    @validator('value')
    def validate_value(cls, v):
        if not isinstance(v, (int, float)):
            raise ValueError("Value must be numeric")
        
        if abs(v) > 1e15:
            raise ValueError("Value out of reasonable bounds")
        
        # Check for NaN or infinity
        if v != v:  # NaN check
            raise ValueError("Value cannot be NaN")
        
        if v == float('inf') or v == float('-inf'):
            raise ValueError("Value cannot be infinite")
        
        return v
    
    @validator('timestamp')
    def validate_timestamp(cls, v):
        if v is None:
            return datetime.utcnow()
        
        now = datetime.utcnow()
        if v > now + timedelta(hours=1):
            raise ValueError("Timestamp cannot be more than 1 hour in the future")
        
        if v < now - timedelta(days=365):
            raise ValueError("Timestamp cannot be more than 1 year in the past")
        
        return v


class TimeRangeRequest(BaseModel):
    """Request model for time range"""
    start: datetime = Field(...)
    end: datetime = Field(...)
    
    @validator('end')
    def validate_end_time(cls, v, values):
        if 'start' in values and v <= values['start']:
            raise ValueError("End time must be after start time")
        return v
    
    @validator('start')
    def validate_start_time(cls, v):
        now = datetime.utcnow()
        if v < now - timedelta(days=365):
            raise ValueError("Start time cannot be more than 1 year in the past")
        return v


class MetricAggregationRequest(BaseModel):
    """Request model for metric aggregation"""
    metric_id: str = Field(..., min_length=1)
    aggregation_type: AggregationTypeEnum = Field(...)
    time_range: TimeRangeRequest = Field(...)
    granularity: Optional[TimeGranularityEnum] = None
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @validator('metric_id')
    def validate_metric_id(cls, v):
        from uuid import UUID
        try:
            UUID(v)
        except ValueError:
            raise ValueError("Invalid metric ID format")
        return v


class ContainerAnalyticsRequest(BaseModel):
    """Request model for container analytics"""
    container_id: str = Field(..., min_length=1)
    time_range: TimeRangeRequest = Field(...)
    metrics: Optional[List[str]] = Field(default_factory=list)
    
    @validator('container_id')
    def validate_container_id(cls, v):
        import re
        # Docker container ID validation
        if not re.match(r'^[a-f0-9]{64}$', v) and not re.match(r'^[a-f0-9]{12}$', v):
            raise ValueError("Invalid container ID format")
        return v


class ServiceAnalyticsRequest(BaseModel):
    """Request model for service analytics"""
    service_id: str = Field(..., min_length=1)
    time_range: TimeRangeRequest = Field(...)
    metrics: Optional[List[str]] = Field(default_factory=list)
    
    @validator('service_id')
    def validate_service_id(cls, v):
        from uuid import UUID
        try:
            UUID(v)
        except ValueError:
            raise ValueError("Invalid service ID format")
        return v


class ReportConfig(BaseModel):
    """Report configuration model"""
    report_type: str = Field(..., regex=r'^(summary|detailed|comparison|trend)$')
    metrics: List[str] = Field(..., min_items=1, max_items=20)
    time_range: TimeRangeRequest = Field(...)
    aggregation: Optional[AggregationTypeEnum] = Field(default=AggregationTypeEnum.AVG)
    granularity: Optional[TimeGranularityEnum] = Field(default=TimeGranularityEnum.HOUR)
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @validator('metrics')
    def validate_metrics(cls, v):
        from uuid import UUID
        for metric_id in v:
            try:
                UUID(metric_id)
            except ValueError:
                raise ValueError(f"Invalid metric ID format: {metric_id}")
        return v


class CustomReportRequest(BaseModel):
    """Request model for custom report"""
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    config: ReportConfig = Field(...)


class CorrelationRequest(BaseModel):
    """Request model for correlation analysis"""
    metric_ids: List[str] = Field(..., min_items=2, max_items=10)
    time_range: TimeRangeRequest = Field(...)
    correlation_type: Optional[str] = Field(default="pearson", regex=r'^(pearson|spearman|kendall)$')
    
    @validator('metric_ids')
    def validate_metric_ids(cls, v):
        from uuid import UUID
        
        # Check for duplicates
        if len(set(v)) != len(v):
            raise ValueError("Duplicate metric IDs not allowed")
        
        # Validate format
        for metric_id in v:
            try:
                UUID(metric_id)
            except ValueError:
                raise ValueError(f"Invalid metric ID format: {metric_id}")
        
        return v


class AnomalyDetectionRequest(BaseModel):
    """Request model for anomaly detection"""
    metric_id: str = Field(..., min_length=1)
    time_range: TimeRangeRequest = Field(...)
    sensitivity: Optional[float] = Field(default=2.0, ge=0.1, le=10.0)
    algorithm: Optional[str] = Field(default="zscore", regex=r'^(zscore|isolation_forest|one_class_svm)$')
    
    @validator('metric_id')
    def validate_metric_id(cls, v):
        from uuid import UUID
        try:
            UUID(v)
        except ValueError:
            raise ValueError("Invalid metric ID format")
        return v


class ForecastRequest(BaseModel):
    """Request model for forecasting"""
    metric_id: str = Field(..., min_length=1)
    forecast_hours: int = Field(default=24, ge=1, le=168)  # Max 1 week
    model_type: Optional[str] = Field(default="linear", regex=r'^(linear|arima|prophet|lstm)$')
    confidence_level: Optional[float] = Field(default=0.95, ge=0.5, le=0.99)
    
    @validator('metric_id')
    def validate_metric_id(cls, v):
        from uuid import UUID
        try:
            UUID(v)
        except ValueError:
            raise ValueError("Invalid metric ID format")
        return v


class ExportConfig(BaseModel):
    """Export configuration model"""
    format: str = Field(..., regex=r'^(json|csv|xlsx|parquet)$')
    metrics: List[str] = Field(..., min_items=1, max_items=50)
    time_range: Optional[TimeRangeRequest] = None
    compression: Optional[str] = Field(default="none", regex=r'^(none|gzip|bzip2|xz)$')
    
    @validator('metrics')
    def validate_metrics(cls, v):
        from uuid import UUID
        for metric_id in v:
            try:
                UUID(metric_id)
            except ValueError:
                raise ValueError(f"Invalid metric ID format: {metric_id}")
        return v


class ExportRequest(BaseModel):
    """Request model for data export"""
    config: ExportConfig = Field(...)
    email_notification: Optional[bool] = Field(default=False)
    encryption: Optional[bool] = Field(default=False)


class BulkOperationRequest(BaseModel):
    """Request model for bulk operations"""
    metric_ids: List[str] = Field(..., min_items=1, max_items=100)
    operation: str = Field(..., regex=r'^(delete|update_metadata|update_labels|aggregate)$')
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    labels: Optional[Dict[str, Union[str, int, float, bool]]] = Field(default_factory=dict)
    aggregation_config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @validator('metric_ids')
    def validate_metric_ids(cls, v):
        from uuid import UUID
        for metric_id in v:
            try:
                UUID(metric_id)
            except ValueError:
                raise ValueError(f"Invalid metric ID format: {metric_id}")
        return v


class WidgetConfig(BaseModel):
    """Widget configuration model"""
    type: str = Field(..., regex=r'^(line_chart|bar_chart|pie_chart|gauge|counter|table)$')
    metric_id: str = Field(..., min_length=1)
    title: Optional[str] = Field(None, max_length=100)
    size: Optional[Dict[str, int]] = Field(default_factory=dict)
    position: Optional[Dict[str, int]] = Field(default_factory=dict)
    config: Optional[Dict[str, Any]] = Field(default_factory=dict)
    
    @validator('metric_id')
    def validate_metric_id(cls, v):
        from uuid import UUID
        try:
            UUID(v)
        except ValueError:
            raise ValueError("Invalid metric ID format")
        return v


class DashboardConfig(BaseModel):
    """Dashboard configuration model"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    widgets: List[WidgetConfig] = Field(..., min_items=1, max_items=50)
    layout: Optional[Dict[str, Any]] = Field(default_factory=dict)
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    refresh_interval: Optional[int] = Field(default=300, ge=30, le=3600)  # 30 seconds to 1 hour


class DashboardRequest(BaseModel):
    """Request model for dashboard operations"""
    config: DashboardConfig = Field(...)
    public: Optional[bool] = Field(default=False)
    shared_with: Optional[List[str]] = Field(default_factory=list)


class SearchRequest(BaseModel):
    """Request model for search operations"""
    query: Optional[str] = Field(None, max_length=200)
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    sort_by: Optional[str] = Field(default="created_at")
    sort_order: Optional[str] = Field(default="desc", regex=r'^(asc|desc)$')
    page: Optional[int] = Field(default=1, ge=1)
    per_page: Optional[int] = Field(default=20, ge=1, le=100)
    
    @validator('query')
    def validate_query(cls, v):
        if v is None:
            return v
        
        # Check for SQL injection attempts
        dangerous_patterns = [
            r'(union|select|insert|update|delete|drop|create|alter)\s+',
            r'(\-\-|\#|\/\*|\*\/)',
            r'(script|javascript|vbscript)',
            r'(onload|onerror|onclick)'
        ]
        
        query_lower = v.lower()
        for pattern in dangerous_patterns:
            import re
            if re.search(pattern, query_lower):
                raise ValueError("Search query contains invalid characters")
        
        return v


# Response models

class MetricResponse(BaseModel):
    """Response model for metric data"""
    metric_id: str
    name: str
    type: str
    description: Optional[str] = None
    unit: Optional[str] = None
    labels: Dict[str, Union[str, int, float, bool]] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: Optional[datetime] = None
    statistics: Optional[Dict[str, Any]] = Field(default_factory=dict)


class DataPoint(BaseModel):
    """Data point model"""
    timestamp: datetime
    value: Union[int, float]
    labels: Dict[str, Union[str, int, float, bool]] = Field(default_factory=dict)
    quality: Optional[str] = "good"


class MetricDataResponse(BaseModel):
    """Response model for metric data points"""
    metric_id: str
    metric_name: str
    metric_type: str
    unit: Optional[str] = None
    time_range: Dict[str, Any] = Field(default_factory=dict)
    data_points: List[DataPoint] = Field(default_factory=list)
    statistics: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AggregationResponse(BaseModel):
    """Response model for aggregation data"""
    metric_id: str
    aggregation_type: str
    granularity: str
    time_range: Dict[str, Any] = Field(default_factory=dict)
    data_points: List[DataPoint] = Field(default_factory=list)
    statistics: Dict[str, Any] = Field(default_factory=dict)
    trend: Dict[str, Any] = Field(default_factory=dict)
    insights: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AnalyticsResponse(BaseModel):
    """Response model for analytics data"""
    entity_id: str
    entity_type: str
    time_range: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    performance_score: Optional[float] = None
    health_score: Optional[float] = None
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    trends: Dict[str, Any] = Field(default_factory=dict)
    alerts: List[Dict[str, Any]] = Field(default_factory=list)


class ReportResponse(BaseModel):
    """Response model for report data"""
    report_id: str
    name: str
    description: Optional[str] = None
    report_type: str
    created_at: datetime
    time_range: Dict[str, Any] = Field(default_factory=dict)
    metrics: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    visualizations: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CorrelationResponse(BaseModel):
    """Response model for correlation data"""
    metric_ids: List[str]
    time_range: Dict[str, Any] = Field(default_factory=dict)
    correlations: List[Dict[str, Any]] = Field(default_factory=list)
    insights: List[Dict[str, Any]] = Field(default_factory=list)
    matrix: List[List[float]] = Field(default_factory=list)
    statistics: Dict[str, Any] = Field(default_factory=dict)
    visualization_data: Dict[str, Any] = Field(default_factory=dict)


class AnomalyResponse(BaseModel):
    """Response model for anomaly data"""
    metric_id: str
    metric_name: str
    time_range: Dict[str, Any] = Field(default_factory=dict)
    sensitivity: float
    anomalies: List[Dict[str, Any]] = Field(default_factory=list)
    statistics: Dict[str, Any] = Field(default_factory=dict)
    baseline: Dict[str, Any] = Field(default_factory=dict)
    threshold: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    visualization_data: Dict[str, Any] = Field(default_factory=dict)


class ForecastResponse(BaseModel):
    """Response model for forecast data"""
    metric_id: str
    metric_name: str
    forecast_horizon: int
    model_type: str
    forecast_points: List[DataPoint] = Field(default_factory=list)
    confidence_intervals: Dict[str, Any] = Field(default_factory=dict)
    accuracy_metrics: Dict[str, Any] = Field(default_factory=dict)
    quality_score: float
    trends: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExportResponse(BaseModel):
    """Response model for export data"""
    export_id: str
    format: str
    metrics: List[str]
    time_range: Dict[str, Any] = Field(default_factory=dict)
    download_url: str
    file_size: int
    expires_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)
    status: str


class HealthResponse(BaseModel):
    """Response model for health data"""
    timestamp: datetime
    overall_health_score: float
    components: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    alerts: List[Dict[str, Any]] = Field(default_factory=list)
    trends: Dict[str, Any] = Field(default_factory=dict)
    thresholds: Dict[str, Any] = Field(default_factory=dict)
    last_updated: datetime


class BulkOperationResponse(BaseModel):
    """Response model for bulk operations"""
    operation: str
    total_requested: int
    successful: int
    failed: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    execution_time: Optional[float] = None
    summary: Dict[str, Any] = Field(default_factory=dict)


class DashboardResponse(BaseModel):
    """Response model for dashboard data"""
    dashboard_id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    widgets: List[Dict[str, Any]] = Field(default_factory=list)
    layout: Dict[str, Any] = Field(default_factory=dict)
    filters: Dict[str, Any] = Field(default_factory=dict)
    refresh_interval: int
    permissions: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PaginatedResponse(BaseModel):
    """Generic paginated response model"""
    data: List[Dict[str, Any]]
    pagination: Dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Error response model"""
    error: Dict[str, Any]


class SuccessResponse(BaseModel):
    """Success response model"""
    success: bool = True
    message: str
    timestamp: datetime
    data: Optional[Dict[str, Any]] = None


# Serializer utilities

class AnalyticsSerializer:
    """Utility class for analytics serialization"""
    
    @staticmethod
    def serialize_metric(metric_data: Dict[str, Any]) -> MetricResponse:
        """Serialize metric data to response model"""
        return MetricResponse(**metric_data)
    
    @staticmethod
    def serialize_aggregation(aggregation_data: Dict[str, Any]) -> AggregationResponse:
        """Serialize aggregation data to response model"""
        return AggregationResponse(**aggregation_data)
    
    @staticmethod
    def serialize_analytics(analytics_data: Dict[str, Any]) -> AnalyticsResponse:
        """Serialize analytics data to response model"""
        return AnalyticsResponse(**analytics_data)
    
    @staticmethod
    def serialize_report(report_data: Dict[str, Any]) -> ReportResponse:
        """Serialize report data to response model"""
        return ReportResponse(**report_data)
    
    @staticmethod
    def serialize_correlation(correlation_data: Dict[str, Any]) -> CorrelationResponse:
        """Serialize correlation data to response model"""
        return CorrelationResponse(**correlation_data)
    
    @staticmethod
    def serialize_anomaly(anomaly_data: Dict[str, Any]) -> AnomalyResponse:
        """Serialize anomaly data to response model"""
        return AnomalyResponse(**anomaly_data)
    
    @staticmethod
    def serialize_forecast(forecast_data: Dict[str, Any]) -> ForecastResponse:
        """Serialize forecast data to response model"""
        return ForecastResponse(**forecast_data)
    
    @staticmethod
    def serialize_export(export_data: Dict[str, Any]) -> ExportResponse:
        """Serialize export data to response model"""
        return ExportResponse(**export_data)
    
    @staticmethod
    def serialize_health(health_data: Dict[str, Any]) -> HealthResponse:
        """Serialize health data to response model"""
        return HealthResponse(**health_data)
    
    @staticmethod
    def serialize_bulk_operation(operation_data: Dict[str, Any]) -> BulkOperationResponse:
        """Serialize bulk operation data to response model"""
        return BulkOperationResponse(**operation_data)
    
    @staticmethod
    def serialize_dashboard(dashboard_data: Dict[str, Any]) -> DashboardResponse:
        """Serialize dashboard data to response model"""
        return DashboardResponse(**dashboard_data)
    
    @staticmethod
    def serialize_error(error_message: str, error_code: str = None, 
                       details: Dict[str, Any] = None) -> ErrorResponse:
        """Serialize error to response model"""
        error_data = {
            'message': error_message,
            'timestamp': datetime.utcnow()
        }
        
        if error_code:
            error_data['code'] = error_code
        
        if details:
            error_data['details'] = details
        
        return ErrorResponse(error=error_data)
    
    @staticmethod
    def serialize_success(message: str, data: Dict[str, Any] = None) -> SuccessResponse:
        """Serialize success to response model"""
        return SuccessResponse(
            message=message,
            timestamp=datetime.utcnow(),
            data=data
        )
    
    @staticmethod
    def create_paginated_response(data: List[Dict[str, Any]], 
                                 total_count: int, 
                                 page: int, 
                                 per_page: int) -> PaginatedResponse:
        """Create paginated response"""
        pagination = {
            'page': page,
            'per_page': per_page,
            'total_count': total_count,
            'total_pages': (total_count + per_page - 1) // per_page,
            'has_next': page * per_page < total_count,
            'has_previous': page > 1
        }
        
        return PaginatedResponse(data=data, pagination=pagination)
