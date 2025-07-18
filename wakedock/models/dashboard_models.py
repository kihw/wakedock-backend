"""
Dashboard Models - SQLAlchemy models for dashboard data
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey, Index, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

from wakedock.core.database import Base


class Dashboard(Base):
    """Dashboard model"""
    __tablename__ = "dashboards"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text)
    layout = Column(JSON)
    theme = Column(JSON)
    refresh_interval = Column(Integer, default=60)
    auto_refresh = Column(Boolean, default=True)
    public = Column(Boolean, default=False)
    filters = Column(JSON)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    last_accessed = Column(DateTime)
    access_count = Column(Integer, default=0)
    
    # Relationships
    widgets = relationship("Widget", back_populates="dashboard", cascade="all, delete-orphan")
    reports = relationship("DashboardReport", back_populates="dashboard", cascade="all, delete-orphan")
    backups = relationship("DashboardBackup", back_populates="dashboard", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_dashboard_name', 'name'),
        Index('idx_dashboard_public', 'public'),
        Index('idx_dashboard_created_at', 'created_at'),
        Index('idx_dashboard_updated_at', 'updated_at'),
        Index('idx_dashboard_access_count', 'access_count'),
    )


class Widget(Base):
    """Widget model"""
    __tablename__ = "widgets"
    
    id = Column(String(36), primary_key=True, index=True)
    dashboard_id = Column(String(36), ForeignKey("dashboards.id"), nullable=False)
    title = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)
    config = Column(JSON)
    position = Column(JSON)
    size = Column(JSON)
    metric_id = Column(String(36), ForeignKey("metrics.id"))
    query = Column(JSON)
    refresh_interval = Column(Integer, default=60)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    dashboard = relationship("Dashboard", back_populates="widgets")
    metric = relationship("Metric", back_populates="widgets")
    
    # Indexes
    __table_args__ = (
        Index('idx_widget_dashboard_id', 'dashboard_id'),
        Index('idx_widget_type', 'type'),
        Index('idx_widget_metric_id', 'metric_id'),
        Index('idx_widget_active', 'active'),
        Index('idx_widget_created_at', 'created_at'),
    )


class DashboardTemplate(Base):
    """Dashboard template model"""
    __tablename__ = "dashboard_templates"
    
    id = Column(String(36), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    category = Column(String(50))
    tags = Column(JSON)
    template_data = Column(JSON)
    usage_count = Column(Integer, default=0)
    public = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Indexes
    __table_args__ = (
        Index('idx_template_name', 'name'),
        Index('idx_template_category', 'category'),
        Index('idx_template_public', 'public'),
        Index('idx_template_usage_count', 'usage_count'),
    )


class DashboardReport(Base):
    """Dashboard report model"""
    __tablename__ = "dashboard_reports"
    
    id = Column(String(36), primary_key=True, index=True)
    dashboard_id = Column(String(36), ForeignKey("dashboards.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    schedule = Column(JSON)
    recipients = Column(JSON)
    format = Column(String(10), default="pdf")
    enabled = Column(Boolean, default=True)
    last_run = Column(DateTime)
    next_run = Column(DateTime)
    run_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    dashboard = relationship("Dashboard", back_populates="reports")
    executions = relationship("ReportExecution", back_populates="report", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_report_dashboard_id', 'dashboard_id'),
        Index('idx_report_enabled', 'enabled'),
        Index('idx_report_next_run', 'next_run'),
        Index('idx_report_last_run', 'last_run'),
    )


class ReportExecution(Base):
    """Report execution model"""
    __tablename__ = "report_executions"
    
    id = Column(String(36), primary_key=True, index=True)
    report_id = Column(String(36), ForeignKey("dashboard_reports.id"), nullable=False)
    status = Column(String(20), default="pending")
    started_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime)
    duration = Column(Float)
    file_path = Column(String(255))
    file_size = Column(Integer)
    error_message = Column(Text)
    execution_metadata = Column(JSON)
    
    # Relationships
    report = relationship("DashboardReport", back_populates="executions")
    
    # Indexes
    __table_args__ = (
        Index('idx_execution_report_id', 'report_id'),
        Index('idx_execution_status', 'status'),
        Index('idx_execution_started_at', 'started_at'),
        Index('idx_execution_completed_at', 'completed_at'),
    )


class DashboardBackup(Base):
    """Dashboard backup model"""
    __tablename__ = "dashboard_backups"
    
    id = Column(String(36), primary_key=True, index=True)
    dashboard_id = Column(String(36), ForeignKey("dashboards.id"), nullable=False)
    name = Column(String(100))
    description = Column(Text)
    backup_data = Column(JSON)
    file_path = Column(String(255))
    file_size = Column(Integer)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    dashboard = relationship("Dashboard", back_populates="backups")
    
    # Indexes
    __table_args__ = (
        Index('idx_backup_dashboard_id', 'dashboard_id'),
        Index('idx_backup_created_at', 'created_at'),
    )


class DashboardShare(Base):
    """Dashboard share model"""
    __tablename__ = "dashboard_shares"
    
    id = Column(String(36), primary_key=True, index=True)
    dashboard_id = Column(String(36), ForeignKey("dashboards.id"), nullable=False)
    share_token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime)
    password = Column(String(255))
    view_count = Column(Integer, default=0)
    max_views = Column(Integer)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    last_accessed = Column(DateTime)
    
    # Relationships
    dashboard = relationship("Dashboard")
    
    # Indexes
    __table_args__ = (
        Index('idx_share_dashboard_id', 'dashboard_id'),
        Index('idx_share_token', 'share_token'),
        Index('idx_share_enabled', 'enabled'),
        Index('idx_share_expires_at', 'expires_at'),
    )


class DashboardAccess(Base):
    """Dashboard access log model"""
    __tablename__ = "dashboard_access"
    
    id = Column(String(36), primary_key=True, index=True)
    dashboard_id = Column(String(36), ForeignKey("dashboards.id"), nullable=False)
    user_id = Column(String(36))
    ip_address = Column(String(45))
    user_agent = Column(String(255))
    session_id = Column(String(255))
    accessed_at = Column(DateTime, default=func.now())
    duration = Column(Integer)
    
    # Relationships
    dashboard = relationship("Dashboard")
    
    # Indexes
    __table_args__ = (
        Index('idx_access_dashboard_id', 'dashboard_id'),
        Index('idx_access_user_id', 'user_id'),
        Index('idx_access_accessed_at', 'accessed_at'),
        Index('idx_access_session_id', 'session_id'),
    )


class DashboardAlert(Base):
    """Dashboard alert model"""
    __tablename__ = "dashboard_alerts"
    
    id = Column(String(36), primary_key=True, index=True)
    dashboard_id = Column(String(36), ForeignKey("dashboards.id"), nullable=False)
    widget_id = Column(String(36), ForeignKey("widgets.id"))
    name = Column(String(100), nullable=False)
    description = Column(Text)
    conditions = Column(JSON)
    severity = Column(String(20), default="medium")
    enabled = Column(Boolean, default=True)
    last_triggered = Column(DateTime)
    trigger_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    dashboard = relationship("Dashboard")
    widget = relationship("Widget")
    notifications = relationship("AlertNotification", back_populates="alert", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_alert_dashboard_id', 'dashboard_id'),
        Index('idx_alert_widget_id', 'widget_id'),
        Index('idx_alert_enabled', 'enabled'),
        Index('idx_alert_severity', 'severity'),
        Index('idx_alert_last_triggered', 'last_triggered'),
    )


class AlertNotification(Base):
    """Alert notification model"""
    __tablename__ = "alert_notifications"
    
    id = Column(String(36), primary_key=True, index=True)
    alert_id = Column(String(36), ForeignKey("dashboard_alerts.id"), nullable=False)
    type = Column(String(20), nullable=False)
    recipient = Column(String(255), nullable=False)
    message = Column(Text)
    status = Column(String(20), default="pending")
    sent_at = Column(DateTime)
    error_message = Column(Text)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    alert = relationship("DashboardAlert", back_populates="notifications")
    
    # Indexes
    __table_args__ = (
        Index('idx_notification_alert_id', 'alert_id'),
        Index('idx_notification_type', 'type'),
        Index('idx_notification_status', 'status'),
        Index('idx_notification_sent_at', 'sent_at'),
    )


class DashboardMetric(Base):
    """Dashboard metric model"""
    __tablename__ = "dashboard_metrics"
    
    id = Column(String(36), primary_key=True, index=True)
    dashboard_id = Column(String(36), ForeignKey("dashboards.id"), nullable=False)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float)
    metric_type = Column(String(50))
    timestamp = Column(DateTime, default=func.now())
    metric_metadata = Column(JSON)
    
    # Relationships
    dashboard = relationship("Dashboard")
    
    # Indexes
    __table_args__ = (
        Index('idx_dashboard_metric_dashboard_id', 'dashboard_id'),
        Index('idx_dashboard_metric_name', 'metric_name'),
        Index('idx_dashboard_metric_timestamp', 'timestamp'),
        Index('idx_dashboard_metric_type', 'metric_type'),
    )


class DashboardTag(Base):
    """Dashboard tag model"""
    __tablename__ = "dashboard_tags"
    
    id = Column(String(36), primary_key=True, index=True)
    dashboard_id = Column(String(36), ForeignKey("dashboards.id"), nullable=False)
    tag_name = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    dashboard = relationship("Dashboard")
    
    # Indexes
    __table_args__ = (
        Index('idx_tag_dashboard_id', 'dashboard_id'),
        Index('idx_tag_name', 'tag_name'),
        Index('idx_tag_dashboard_tag', 'dashboard_id', 'tag_name', unique=True),
    )


class DashboardComment(Base):
    """Dashboard comment model"""
    __tablename__ = "dashboard_comments"
    
    id = Column(String(36), primary_key=True, index=True)
    dashboard_id = Column(String(36), ForeignKey("dashboards.id"), nullable=False)
    user_id = Column(String(36))
    comment = Column(Text, nullable=False)
    parent_id = Column(String(36), ForeignKey("dashboard_comments.id"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    dashboard = relationship("Dashboard")
    parent = relationship("DashboardComment", remote_side=[id])
    children = relationship("DashboardComment")
    
    # Indexes
    __table_args__ = (
        Index('idx_comment_dashboard_id', 'dashboard_id'),
        Index('idx_comment_user_id', 'user_id'),
        Index('idx_comment_parent_id', 'parent_id'),
        Index('idx_comment_created_at', 'created_at'),
    )


class DashboardFavorite(Base):
    """Dashboard favorite model"""
    __tablename__ = "dashboard_favorites"
    
    id = Column(String(36), primary_key=True, index=True)
    dashboard_id = Column(String(36), ForeignKey("dashboards.id"), nullable=False)
    user_id = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    dashboard = relationship("Dashboard")
    
    # Indexes
    __table_args__ = (
        Index('idx_favorite_dashboard_id', 'dashboard_id'),
        Index('idx_favorite_user_id', 'user_id'),
        Index('idx_favorite_user_dashboard', 'user_id', 'dashboard_id', unique=True),
    )


class DashboardVersion(Base):
    """Dashboard version model"""
    __tablename__ = "dashboard_versions"
    
    id = Column(String(36), primary_key=True, index=True)
    dashboard_id = Column(String(36), ForeignKey("dashboards.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    name = Column(String(100))
    description = Column(Text)
    changes = Column(Text)
    dashboard_data = Column(JSON)
    created_at = Column(DateTime, default=func.now())
    created_by = Column(String(36))
    
    # Relationships
    dashboard = relationship("Dashboard")
    
    # Indexes
    __table_args__ = (
        Index('idx_version_dashboard_id', 'dashboard_id'),
        Index('idx_version_number', 'version_number'),
        Index('idx_version_created_at', 'created_at'),
        Index('idx_version_dashboard_version', 'dashboard_id', 'version_number', unique=True),
    )


class DashboardPermission(Base):
    """Dashboard permission model"""
    __tablename__ = "dashboard_permissions"
    
    id = Column(String(36), primary_key=True, index=True)
    dashboard_id = Column(String(36), ForeignKey("dashboards.id"), nullable=False)
    user_id = Column(String(36))
    role = Column(String(50), nullable=False)
    permission = Column(String(50), nullable=False)
    granted_at = Column(DateTime, default=func.now())
    granted_by = Column(String(36))
    
    # Relationships
    dashboard = relationship("Dashboard")
    
    # Indexes
    __table_args__ = (
        Index('idx_permission_dashboard_id', 'dashboard_id'),
        Index('idx_permission_user_id', 'user_id'),
        Index('idx_permission_role', 'role'),
        Index('idx_permission_permission', 'permission'),
        Index('idx_permission_user_dashboard', 'user_id', 'dashboard_id', 'permission', unique=True),
    )


class DashboardAuditLog(Base):
    """Dashboard audit log model"""
    __tablename__ = "dashboard_audit_logs"
    
    id = Column(String(36), primary_key=True, index=True)
    dashboard_id = Column(String(36), ForeignKey("dashboards.id"), nullable=False)
    user_id = Column(String(36))
    action = Column(String(50), nullable=False)
    resource_type = Column(String(50))
    resource_id = Column(String(36))
    details = Column(JSON)
    ip_address = Column(String(45))
    user_agent = Column(String(255))
    timestamp = Column(DateTime, default=func.now())
    
    # Relationships
    dashboard = relationship("Dashboard")
    
    # Indexes
    __table_args__ = (
        Index('idx_audit_dashboard_id', 'dashboard_id'),
        Index('idx_audit_user_id', 'user_id'),
        Index('idx_audit_action', 'action'),
        Index('idx_audit_resource_type', 'resource_type'),
        Index('idx_audit_timestamp', 'timestamp'),
    )


class DashboardSubscription(Base):
    """Dashboard subscription model"""
    __tablename__ = "dashboard_subscriptions"
    
    id = Column(String(36), primary_key=True, index=True)
    dashboard_id = Column(String(36), ForeignKey("dashboards.id"), nullable=False)
    user_id = Column(String(36), nullable=False)
    subscription_type = Column(String(50), nullable=False)
    frequency = Column(String(20), default="daily")
    enabled = Column(Boolean, default=True)
    last_sent = Column(DateTime)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    dashboard = relationship("Dashboard")
    
    # Indexes
    __table_args__ = (
        Index('idx_subscription_dashboard_id', 'dashboard_id'),
        Index('idx_subscription_user_id', 'user_id'),
        Index('idx_subscription_type', 'subscription_type'),
        Index('idx_subscription_enabled', 'enabled'),
        Index('idx_subscription_user_dashboard', 'user_id', 'dashboard_id', unique=True),
    )


# Add Widget relationship to Metric model
from wakedock.models.analytics_models import Metric
Metric.widgets = relationship("Widget", back_populates="metric")
