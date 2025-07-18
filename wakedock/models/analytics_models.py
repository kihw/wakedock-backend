"""
Analytics Models - SQLAlchemy models for analytics data
"""

from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean, ForeignKey, Index, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from uuid import uuid4

from wakedock.core.database import Base
from wakedock.models.base import BaseModel, TimestampMixin, UUIDMixin

import logging
logger = logging.getLogger(__name__)


class Metric(BaseModel, UUIDMixin):
    """Metric model for storing metric definitions"""
    
    __tablename__ = 'metrics'
    __table_args__ = {'extend_existing': True}
    
    # Basic metric information
    name = Column(String(100), nullable=False, unique=True, index=True)
    type = Column(String(50), nullable=False)  # counter, gauge, histogram, summary
    description = Column(Text)
    unit = Column(String(50))
    
    # Metadata and labels
    labels = Column(JSONB, default=dict)
    metric_metadata = Column(JSONB, default=dict)
    
    # Configuration
    retention_days = Column(Integer, default=90)
    sampling_rate = Column(Float, default=1.0)
    active = Column(Boolean, default=True)
    
    # Relationships
    data_points = relationship("MetricData", back_populates="metric", cascade="all, delete-orphan")
    statistics = relationship("MetricStatistics", back_populates="metric", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_metric_name_type', 'name', 'type'),
        Index('idx_metric_active', 'active'),
        Index('idx_metric_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Metric(id={self.id}, name={self.name}, type={self.type})>"


class MetricData(BaseModel, UUIDMixin):
    """Metric data model for storing time-series data points"""
    
    __tablename__ = 'metric_data'
    __table_args__ = {'extend_existing': True}
    __table_args__ = {'extend_existing': True}
    
    # Foreign key to metric
    metric_id = Column(UUID(as_uuid=True), ForeignKey('metrics.id'), nullable=False)
    
    # Data point information
    timestamp = Column(DateTime, nullable=False, index=True)
    value = Column(Float, nullable=False)
    
    # Additional metadata
    labels = Column(JSONB, default=dict)
    quality = Column(String(20), default='good')  # good, poor, interpolated
    source = Column(String(100))
    
    # Relationships
    metric = relationship("Metric", back_populates="data_points")
    
    # Indexes for time-series queries
    __table_args__ = (
        Index('idx_metric_data_metric_timestamp', 'metric_id', 'timestamp'),
        Index('idx_metric_data_timestamp', 'timestamp'),
        Index('idx_metric_data_metric_id', 'metric_id'),
        Index('idx_metric_data_value', 'value'),
    )
    
    def __repr__(self):
        return f"<MetricData(id={self.id}, metric_id={self.metric_id}, timestamp={self.timestamp}, value={self.value})>"


class MetricStatistics(BaseModel, UUIDMixin):
    """Metric statistics model for storing aggregated statistics"""
    
    __tablename__ = 'metric_statistics'
    __table_args__ = {'extend_existing': True}
    
    # Foreign key to metric
    metric_id = Column(UUID(as_uuid=True), ForeignKey('metrics.id'), nullable=False)
    
    # Time period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    granularity = Column(String(20), nullable=False)  # minute, hour, day, week, month
    
    # Statistical values
    count = Column(Integer, default=0)
    sum = Column(Float, default=0.0)
    mean = Column(Float, default=0.0)
    median = Column(Float, default=0.0)
    min = Column(Float, default=0.0)
    max = Column(Float, default=0.0)
    stddev = Column(Float, default=0.0)
    variance = Column(Float, default=0.0)
    
    # Percentiles
    percentile_25 = Column(Float, default=0.0)
    percentile_50 = Column(Float, default=0.0)
    percentile_75 = Column(Float, default=0.0)
    percentile_90 = Column(Float, default=0.0)
    percentile_95 = Column(Float, default=0.0)
    percentile_99 = Column(Float, default=0.0)
    
    # Additional metadata
    data_points = Column(Integer, default=0)
    quality_score = Column(Float, default=1.0)
    
    # Relationships
    metric = relationship("Metric", back_populates="statistics")
    
    # Indexes for aggregation queries
    __table_args__ = (
        Index('idx_metric_stats_metric_period', 'metric_id', 'period_start', 'period_end'),
        Index('idx_metric_stats_granularity', 'granularity'),
        Index('idx_metric_stats_period_start', 'period_start'),
    )
    
    def __repr__(self):
        return f"<MetricStatistics(id={self.id}, metric_id={self.metric_id}, period={self.period_start}-{self.period_end})>"


class Dashboard(BaseModel, UUIDMixin):
    """Dashboard model for storing dashboard configurations"""
    
    __tablename__ = 'analytics_dashboards'
    __table_args__ = {'extend_existing': True}
    
    # Basic dashboard information
    name = Column(String(100), nullable=False)
    description = Column(Text)
    
    # Configuration
    config = Column(JSONB, default=dict)
    layout = Column(JSONB, default=dict)
    filters = Column(JSONB, default=dict)
    
    # Settings
    refresh_interval = Column(Integer, default=300)  # seconds
    public = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    
    # Access tracking
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime)
    
    # Relationships
    widgets = relationship("Widget", back_populates="dashboard", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_dashboard_name', 'name'),
        Index('idx_dashboard_public', 'public'),
        Index('idx_dashboard_active', 'active'),
    )
    
    def __repr__(self):
        return f"<Dashboard(id={self.id}, name={self.name})>"


class Widget(BaseModel, UUIDMixin):
    """Widget model for storing dashboard widgets"""
    
    __tablename__ = 'analytics_widgets'
    __table_args__ = {'extend_existing': True}
    
    # Foreign key to dashboard
    dashboard_id = Column(UUID(as_uuid=True), ForeignKey('analytics_dashboards.id'), nullable=False)
    
    # Widget information
    title = Column(String(100))
    type = Column(String(50), nullable=False)  # line_chart, bar_chart, pie_chart, gauge, counter, table
    
    # Configuration
    config = Column(JSONB, default=dict)
    position = Column(JSONB, default=dict)  # x, y coordinates
    size = Column(JSONB, default=dict)      # width, height
    
    # Data source
    metric_id = Column(UUID(as_uuid=True), ForeignKey('metrics.id'))
    query = Column(Text)
    
    # Settings
    refresh_interval = Column(Integer, default=300)
    active = Column(Boolean, default=True)
    
    # Relationships
    dashboard = relationship("Dashboard", back_populates="widgets")
    metric = relationship("Metric")
    
    # Indexes
    __table_args__ = (
        Index('idx_widget_dashboard_id', 'dashboard_id'),
        Index('idx_widget_metric_id', 'metric_id'),
        Index('idx_widget_type', 'type'),
    )
    
    def __repr__(self):
        return f"<Widget(id={self.id}, title={self.title}, type={self.type})>"


class Report(BaseModel, UUIDMixin):
    """Report model for storing generated reports"""
    
    __tablename__ = 'analytics_reports'
    __table_args__ = {'extend_existing': True}
    
    # Basic report information
    name = Column(String(100), nullable=False)
    description = Column(Text)
    report_type = Column(String(50), nullable=False)  # summary, detailed, comparison, trend
    
    # Configuration and data
    config = Column(JSONB, default=dict)
    data = Column(JSONB, default=dict)
    
    # Metadata
    metrics_count = Column(Integer, default=0)
    data_points_count = Column(Integer, default=0)
    generation_time = Column(Float)  # seconds
    
    # Time range
    time_range_start = Column(DateTime)
    time_range_end = Column(DateTime)
    
    # File information
    file_path = Column(String(500))
    file_size = Column(Integer)
    format = Column(String(20), default='json')
    
    # Status
    status = Column(String(20), default='completed')  # pending, completed, failed
    error_message = Column(Text)
    
    # Indexes
    __table_args__ = (
        Index('idx_report_name', 'name'),
        Index('idx_report_type', 'report_type'),
        Index('idx_report_status', 'status'),
        Index('idx_report_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Report(id={self.id}, name={self.name}, type={self.report_type})>"


class Alert(BaseModel, UUIDMixin):
    """Alert model for storing metric alerts"""
    
    __tablename__ = 'analytics_alerts'
    __table_args__ = {'extend_existing': True}
    
    # Foreign key to metric
    metric_id = Column(UUID(as_uuid=True), ForeignKey('metrics.id'), nullable=False)
    
    # Alert information
    name = Column(String(100), nullable=False)
    description = Column(Text)
    alert_type = Column(String(50), nullable=False)  # threshold, anomaly, trend
    
    # Configuration
    config = Column(JSONB, default=dict)
    conditions = Column(JSONB, default=dict)
    
    # Thresholds
    threshold_value = Column(Float)
    threshold_operator = Column(String(20))  # gt, lt, eq, ne, gte, lte
    
    # Settings
    severity = Column(String(20), default='medium')  # low, medium, high, critical
    active = Column(Boolean, default=True)
    
    # Notification settings
    notification_channels = Column(JSONB, default=list)
    notification_interval = Column(Integer, default=300)  # seconds
    
    # Status
    last_triggered = Column(DateTime)
    trigger_count = Column(Integer, default=0)
    
    # Relationships
    metric = relationship("Metric")
    incidents = relationship("AlertIncident", back_populates="alert", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_alert_metric_id', 'metric_id'),
        Index('idx_alert_active', 'active'),
        Index('idx_alert_severity', 'severity'),
    )
    
    def __repr__(self):
        return f"<Alert(id={self.id}, name={self.name}, metric_id={self.metric_id})>"


class AlertIncident(BaseModel, UUIDMixin):
    """Alert incident model for storing alert occurrences"""
    
    __tablename__ = 'analytics_alert_incidents'
    __table_args__ = {'extend_existing': True}
    
    # Foreign key to alert
    alert_id = Column(UUID(as_uuid=True), ForeignKey('analytics_alerts.id'), nullable=False)
    
    # Incident information
    triggered_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime)
    duration = Column(Integer)  # seconds
    
    # Trigger details
    trigger_value = Column(Float)
    threshold_value = Column(Float)
    deviation = Column(Float)
    
    # Status
    status = Column(String(20), default='active')  # active, resolved, acknowledged
    severity = Column(String(20), default='medium')
    
    # Metadata
    context = Column(JSONB, default=dict)
    notes = Column(Text)
    
    # Relationships
    alert = relationship("Alert", back_populates="incidents")
    
    # Indexes
    __table_args__ = (
        Index('idx_alert_incident_alert_id', 'alert_id'),
        Index('idx_alert_incident_triggered_at', 'triggered_at'),
        Index('idx_alert_incident_status', 'status'),
    )
    
    def __repr__(self):
        return f"<AlertIncident(id={self.id}, alert_id={self.alert_id}, triggered_at={self.triggered_at})>"


class Correlation(BaseModel, UUIDMixin):
    """Correlation model for storing metric correlations"""
    
    __tablename__ = 'analytics_correlations'
    __table_args__ = {'extend_existing': True}
    
    # Metric pairs
    metric_1_id = Column(UUID(as_uuid=True), ForeignKey('metrics.id'), nullable=False)
    metric_2_id = Column(UUID(as_uuid=True), ForeignKey('metrics.id'), nullable=False)
    
    # Correlation data
    correlation_coefficient = Column(Float, nullable=False)
    p_value = Column(Float)
    correlation_type = Column(String(20), default='pearson')  # pearson, spearman, kendall
    
    # Time period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Metadata
    data_points = Column(Integer, default=0)
    significance = Column(String(20))  # significant, not_significant
    strength = Column(String(20))      # very_weak, weak, moderate, strong, very_strong
    
    # Relationships
    metric_1 = relationship("Metric", foreign_keys=[metric_1_id])
    metric_2 = relationship("Metric", foreign_keys=[metric_2_id])
    
    # Indexes
    __table_args__ = (
        Index('idx_correlation_metrics', 'metric_1_id', 'metric_2_id'),
        Index('idx_correlation_period', 'period_start', 'period_end'),
        Index('idx_correlation_coefficient', 'correlation_coefficient'),
    )
    
    def __repr__(self):
        return f"<Correlation(id={self.id}, metric_1={self.metric_1_id}, metric_2={self.metric_2_id}, coeff={self.correlation_coefficient})>"


class Anomaly(BaseModel, UUIDMixin):
    """Anomaly model for storing detected anomalies"""
    
    __tablename__ = 'analytics_anomalies'
    __table_args__ = {'extend_existing': True}
    
    # Foreign key to metric
    metric_id = Column(UUID(as_uuid=True), ForeignKey('metrics.id'), nullable=False)
    
    # Anomaly data
    timestamp = Column(DateTime, nullable=False)
    value = Column(Float, nullable=False)
    expected_value = Column(Float)
    deviation = Column(Float)
    
    # Detection details
    algorithm = Column(String(50))  # zscore, isolation_forest, one_class_svm
    confidence = Column(Float, default=0.0)
    severity = Column(String(20), default='medium')  # low, medium, high, critical
    
    # Context
    context = Column(JSONB, default=dict)
    labels = Column(JSONB, default=dict)
    
    # Status
    status = Column(String(20), default='detected')  # detected, investigating, resolved, false_positive
    resolution_notes = Column(Text)
    resolved_at = Column(DateTime)
    
    # Relationships
    metric = relationship("Metric")
    
    # Indexes
    __table_args__ = (
        Index('idx_anomaly_metric_timestamp', 'metric_id', 'timestamp'),
        Index('idx_anomaly_severity', 'severity'),
        Index('idx_anomaly_status', 'status'),
    )
    
    def __repr__(self):
        return f"<Anomaly(id={self.id}, metric_id={self.metric_id}, timestamp={self.timestamp}, value={self.value})>"


class Forecast(BaseModel, UUIDMixin):
    """Forecast model for storing forecasting data"""
    
    __tablename__ = 'analytics_forecasts'
    __table_args__ = {'extend_existing': True}
    
    # Foreign key to metric
    metric_id = Column(UUID(as_uuid=True), ForeignKey('metrics.id'), nullable=False)
    
    # Forecast parameters
    forecast_horizon = Column(Integer, nullable=False)  # hours
    model_type = Column(String(50), nullable=False)     # linear, arima, prophet, lstm
    
    # Training data
    training_start = Column(DateTime, nullable=False)
    training_end = Column(DateTime, nullable=False)
    training_data_points = Column(Integer, default=0)
    
    # Forecast data
    forecast_data = Column(JSONB, default=dict)
    confidence_intervals = Column(JSONB, default=dict)
    
    # Quality metrics
    accuracy_score = Column(Float, default=0.0)
    mae = Column(Float, default=0.0)    # Mean Absolute Error
    rmse = Column(Float, default=0.0)   # Root Mean Square Error
    mape = Column(Float, default=0.0)   # Mean Absolute Percentage Error
    
    # Metadata
    model_version = Column(String(20), default='1.0')
    parameters = Column(JSONB, default=dict)
    
    # Status
    status = Column(String(20), default='completed')  # pending, completed, failed
    error_message = Column(Text)
    
    # Relationships
    metric = relationship("Metric")
    
    # Indexes
    __table_args__ = (
        Index('idx_forecast_metric_id', 'metric_id'),
        Index('idx_forecast_status', 'status'),
        Index('idx_forecast_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Forecast(id={self.id}, metric_id={self.metric_id}, horizon={self.forecast_horizon}h)>"


class Export(BaseModel, UUIDMixin):
    """Export model for storing data export information"""
    
    __tablename__ = 'analytics_exports'
    __table_args__ = {'extend_existing': True}
    
    # Export configuration
    name = Column(String(100))
    format = Column(String(20), nullable=False)  # json, csv, xlsx, parquet
    compression = Column(String(20), default='none')  # none, gzip, bzip2, xz
    
    # Data selection
    metrics = Column(JSONB, default=list)
    time_range_start = Column(DateTime)
    time_range_end = Column(DateTime)
    filters = Column(JSONB, default=dict)
    
    # File information
    file_path = Column(String(500))
    file_size = Column(Integer)
    download_url = Column(String(500))
    
    # Settings
    encryption = Column(Boolean, default=False)
    email_notification = Column(Boolean, default=False)
    expires_at = Column(DateTime)
    
    # Status
    status = Column(String(20), default='pending')  # pending, processing, completed, failed
    progress = Column(Float, default=0.0)
    error_message = Column(Text)
    
    # Metadata
    records_count = Column(Integer, default=0)
    generation_time = Column(Float)  # seconds
    
    # Indexes
    __table_args__ = (
        Index('idx_export_status', 'status'),
        Index('idx_export_created_at', 'created_at'),
        Index('idx_export_expires_at', 'expires_at'),
    )
    
    def __repr__(self):
        return f"<Export(id={self.id}, format={self.format}, status={self.status})>"


# Utility functions for model operations

def create_metric_with_defaults(name: str, metric_type: str, **kwargs) -> Metric:
    """Create a metric with default values"""
    metric = Metric(
        name=name,
        type=metric_type,
        description=kwargs.get('description', ''),
        unit=kwargs.get('unit', ''),
        labels=kwargs.get('labels', {}),
        metric_metadata=kwargs.get('metadata', {}),
        retention_days=kwargs.get('retention_days', 90),
        sampling_rate=kwargs.get('sampling_rate', 1.0),
        active=kwargs.get('active', True)
    )
    
    return metric


def create_metric_data_point(metric_id: str, timestamp: datetime, value: float, **kwargs) -> MetricData:
    """Create a metric data point"""
    data_point = MetricData(
        metric_id=metric_id,
        timestamp=timestamp,
        value=value,
        labels=kwargs.get('labels', {}),
        quality=kwargs.get('quality', 'good'),
        source=kwargs.get('source', '')
    )
    
    return data_point


def create_dashboard_with_defaults(name: str, **kwargs) -> Dashboard:
    """Create a dashboard with default values"""
    dashboard = Dashboard(
        name=name,
        description=kwargs.get('description', ''),
        config=kwargs.get('config', {}),
        layout=kwargs.get('layout', {}),
        filters=kwargs.get('filters', {}),
        refresh_interval=kwargs.get('refresh_interval', 300),
        public=kwargs.get('public', False),
        active=kwargs.get('active', True)
    )
    
    return dashboard


def create_widget_with_defaults(dashboard_id: str, widget_type: str, **kwargs) -> Widget:
    """Create a widget with default values"""
    widget = Widget(
        dashboard_id=dashboard_id,
        title=kwargs.get('title', ''),
        type=widget_type,
        config=kwargs.get('config', {}),
        position=kwargs.get('position', {}),
        size=kwargs.get('size', {}),
        metric_id=kwargs.get('metric_id'),
        query=kwargs.get('query', ''),
        refresh_interval=kwargs.get('refresh_interval', 300),
        active=kwargs.get('active', True)
    )
    
    return widget


def create_alert_with_defaults(metric_id: str, name: str, alert_type: str, **kwargs) -> Alert:
    """Create an alert with default values"""
    alert = Alert(
        metric_id=metric_id,
        name=name,
        description=kwargs.get('description', ''),
        alert_type=alert_type,
        config=kwargs.get('config', {}),
        conditions=kwargs.get('conditions', {}),
        threshold_value=kwargs.get('threshold_value'),
        threshold_operator=kwargs.get('threshold_operator', 'gt'),
        severity=kwargs.get('severity', 'medium'),
        active=kwargs.get('active', True),
        notification_channels=kwargs.get('notification_channels', []),
        notification_interval=kwargs.get('notification_interval', 300)
    )
    
    return alert


# Model relationship helpers

def get_metric_with_statistics(session, metric_id: str) -> Optional[Metric]:
    """Get metric with its statistics"""
    return session.query(Metric).filter(Metric.id == metric_id).first()


def get_dashboard_with_widgets(session, dashboard_id: str) -> Optional[Dashboard]:
    """Get dashboard with its widgets"""
    return session.query(Dashboard).filter(Dashboard.id == dashboard_id).first()


def get_alert_with_incidents(session, alert_id: str) -> Optional[Alert]:
    """Get alert with its incidents"""
    return session.query(Alert).filter(Alert.id == alert_id).first()
