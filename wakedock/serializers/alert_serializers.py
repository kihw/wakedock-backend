"""
Alert Serializers - Pydantic models for alert data validation and serialization
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum


class AlertSeverityEnum(str, Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatusEnum(str, Enum):
    """Alert status types"""
    ACTIVE = "active"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SUPPRESSED = "suppressed"


class MetricOperatorEnum(str, Enum):
    """Metric operators"""
    GT = "gt"
    LT = "lt"
    GTE = "gte"
    LTE = "lte"
    EQ = "eq"
    NE = "ne"


class AlertCreateSerializer(BaseModel):
    """Serializer for alert creation"""
    title: str = Field(..., min_length=1, max_length=200, description="Alert title")
    description: str = Field(..., min_length=1, max_length=1000, description="Alert description")
    severity: AlertSeverityEnum = Field(..., description="Alert severity level")
    metric_name: str = Field(..., min_length=1, max_length=100, description="Metric name")
    metric_value: float = Field(..., description="Current metric value")
    threshold: float = Field(..., description="Alert threshold value")
    operator: MetricOperatorEnum = Field(MetricOperatorEnum.GT, description="Comparison operator")
    container_id: Optional[str] = Field(None, description="Associated container ID")
    service_id: Optional[str] = Field(None, description="Associated service ID")
    node_id: Optional[str] = Field(None, description="Associated node ID")
    tags: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Alert tags")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Alert metadata")
    
    @validator('title')
    def validate_title(cls, v):
        if not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()
    
    @validator('description')
    def validate_description(cls, v):
        if not v.strip():
            raise ValueError('Description cannot be empty')
        return v.strip()
    
    @validator('metric_name')
    def validate_metric_name(cls, v):
        import re
        if not re.match(r'^[a-zA-Z0-9_\.]+$', v):
            raise ValueError('Metric name must contain only alphanumeric characters, underscores, and dots')
        return v
    
    @validator('tags')
    def validate_tags(cls, v):
        if v and len(v) > 20:
            raise ValueError('Too many tags (maximum 20)')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "title": "High CPU Usage",
                "description": "Container CPU usage exceeded threshold",
                "severity": "high",
                "metric_name": "cpu_usage",
                "metric_value": 95.5,
                "threshold": 80.0,
                "operator": "gt",
                "container_id": "abc123def456",
                "service_id": "service-uuid",
                "tags": {
                    "environment": "production",
                    "team": "infrastructure"
                },
                "metadata": {
                    "source": "monitoring_system",
                    "check_interval": 60
                }
            }
        }


class AlertUpdateSerializer(BaseModel):
    """Serializer for alert updates"""
    status: Optional[AlertStatusEnum] = Field(None, description="Alert status")
    severity: Optional[AlertSeverityEnum] = Field(None, description="Alert severity")
    description: Optional[str] = Field(None, min_length=1, max_length=1000, description="Alert description")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Alert metadata")
    
    @validator('description')
    def validate_description(cls, v):
        if v is not None and not v.strip():
            raise ValueError('Description cannot be empty')
        return v.strip() if v else v
    
    class Config:
        schema_extra = {
            "example": {
                "status": "acknowledged",
                "severity": "medium",
                "description": "Updated alert description",
                "metadata": {
                    "updated_by": "admin",
                    "reason": "threshold_adjusted"
                }
            }
        }


class AlertSearchSerializer(BaseModel):
    """Serializer for alert search"""
    query: str = Field(..., min_length=2, max_length=200, description="Search query")
    severity: Optional[AlertSeverityEnum] = Field(None, description="Filter by severity")
    status: Optional[AlertStatusEnum] = Field(None, description="Filter by status")
    container_id: Optional[str] = Field(None, description="Filter by container ID")
    service_id: Optional[str] = Field(None, description="Filter by service ID")
    created_after: Optional[datetime] = Field(None, description="Filter by creation date (after)")
    created_before: Optional[datetime] = Field(None, description="Filter by creation date (before)")
    limit: int = Field(50, ge=1, le=100, description="Maximum results to return")
    offset: int = Field(0, ge=0, description="Number of results to skip")
    
    class Config:
        schema_extra = {
            "example": {
                "query": "cpu usage",
                "severity": "high",
                "status": "active",
                "container_id": "abc123def456",
                "limit": 20,
                "offset": 0
            }
        }


class AlertAcknowledgeSerializer(BaseModel):
    """Serializer for alert acknowledgment"""
    user_id: str = Field(..., description="User acknowledging the alert")
    note: Optional[str] = Field(None, max_length=500, description="Acknowledgment note")
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "user-123",
                "note": "Investigating the issue"
            }
        }


class AlertResolveSerializer(BaseModel):
    """Serializer for alert resolution"""
    user_id: str = Field(..., description="User resolving the alert")
    resolution_note: Optional[str] = Field(None, max_length=1000, description="Resolution note")
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "user-123",
                "resolution_note": "Issue resolved by restarting container"
            }
        }


class AlertMetricSerializer(BaseModel):
    """Serializer for metric data processing"""
    metric_name: str = Field(..., min_length=1, max_length=100, description="Metric name")
    metric_value: float = Field(..., description="Metric value")
    timestamp: datetime = Field(..., description="Metric timestamp")
    container_id: Optional[str] = Field(None, description="Associated container ID")
    service_id: Optional[str] = Field(None, description="Associated service ID")
    node_id: Optional[str] = Field(None, description="Associated node ID")
    tags: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Metric tags")
    
    @validator('metric_name')
    def validate_metric_name(cls, v):
        import re
        if not re.match(r'^[a-zA-Z0-9_\.]+$', v):
            raise ValueError('Metric name must contain only alphanumeric characters, underscores, and dots')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "metric_name": "cpu_usage",
                "metric_value": 85.2,
                "timestamp": "2023-01-01T12:00:00Z",
                "container_id": "abc123def456",
                "service_id": "service-uuid",
                "tags": {
                    "environment": "production",
                    "datacenter": "us-west-1"
                }
            }
        }


class AlertRuleSerializer(BaseModel):
    """Serializer for alert rule creation"""
    name: str = Field(..., min_length=1, max_length=100, description="Rule name")
    description: Optional[str] = Field(None, max_length=500, description="Rule description")
    metric_name: str = Field(..., min_length=1, max_length=100, description="Metric name")
    operator: MetricOperatorEnum = Field(..., description="Comparison operator")
    threshold: float = Field(..., description="Alert threshold")
    severity: AlertSeverityEnum = Field(..., description="Alert severity")
    enabled: bool = Field(True, description="Whether rule is enabled")
    cooldown_period: int = Field(300, ge=0, description="Cooldown period in seconds")
    tags: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Rule tags")
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()
    
    @validator('metric_name')
    def validate_metric_name(cls, v):
        import re
        if not re.match(r'^[a-zA-Z0-9_\.]+$', v):
            raise ValueError('Metric name must contain only alphanumeric characters, underscores, and dots')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "name": "High CPU Usage Rule",
                "description": "Trigger alert when CPU usage exceeds 80%",
                "metric_name": "cpu_usage",
                "operator": "gt",
                "threshold": 80.0,
                "severity": "high",
                "enabled": True,
                "cooldown_period": 300,
                "tags": {
                    "category": "performance",
                    "team": "infrastructure"
                }
            }
        }


class NotificationChannelEnum(str, Enum):
    """Notification channel types"""
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    SMS = "sms"
    DISCORD = "discord"


class AlertNotificationChannelSerializer(BaseModel):
    """Serializer for notification channel configuration"""
    name: str = Field(..., min_length=1, max_length=100, description="Channel name")
    type: NotificationChannelEnum = Field(..., description="Channel type")
    enabled: bool = Field(True, description="Whether channel is enabled")
    config: Dict[str, Any] = Field(..., description="Channel configuration")
    severity_filter: Optional[List[AlertSeverityEnum]] = Field(None, description="Severity levels to notify")
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Name cannot be empty')
        return v.strip()
    
    @validator('config')
    def validate_config(cls, v, values):
        channel_type = values.get('type')
        
        if channel_type == NotificationChannelEnum.EMAIL:
            if 'recipient' not in v:
                raise ValueError('Email channel requires recipient in config')
            
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, v['recipient']):
                raise ValueError('Invalid email address')
        
        elif channel_type == NotificationChannelEnum.WEBHOOK:
            if 'url' not in v:
                raise ValueError('Webhook channel requires url in config')
            
            import re
            url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
            if not re.match(url_pattern, v['url']):
                raise ValueError('Invalid webhook URL')
        
        elif channel_type == NotificationChannelEnum.SLACK:
            if 'webhook_url' not in v:
                raise ValueError('Slack channel requires webhook_url in config')
        
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Production Alerts Email",
                "type": "email",
                "enabled": True,
                "config": {
                    "recipient": "alerts@company.com",
                    "subject_prefix": "[PROD]"
                },
                "severity_filter": ["high", "critical"]
            }
        }


class AlertBulkOperationSerializer(BaseModel):
    """Serializer for bulk alert operations"""
    alert_ids: List[str] = Field(..., min_items=1, max_items=100, description="List of alert IDs")
    operation: str = Field(..., description="Operation to perform")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Operation parameters")
    
    @validator('operation')
    def validate_operation(cls, v):
        valid_operations = ['acknowledge', 'resolve', 'delete', 'update_severity', 'suppress']
        if v not in valid_operations:
            raise ValueError(f'Invalid operation. Must be one of: {", ".join(valid_operations)}')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "alert_ids": ["alert-1", "alert-2", "alert-3"],
                "operation": "acknowledge",
                "parameters": {
                    "user_id": "user-123",
                    "note": "Bulk acknowledgment"
                }
            }
        }


class AlertStatisticsRequestSerializer(BaseModel):
    """Serializer for alert statistics request"""
    days: int = Field(30, ge=1, le=365, description="Number of days to include in statistics")
    include_trends: bool = Field(True, description="Whether to include trend analysis")
    include_critical: bool = Field(True, description="Whether to include critical alerts")
    
    class Config:
        schema_extra = {
            "example": {
                "days": 30,
                "include_trends": True,
                "include_critical": True
            }
        }


class AlertFilterSerializer(BaseModel):
    """Serializer for alert filtering"""
    severity: Optional[List[AlertSeverityEnum]] = Field(None, description="Filter by severity levels")
    status: Optional[List[AlertStatusEnum]] = Field(None, description="Filter by status types")
    container_ids: Optional[List[str]] = Field(None, description="Filter by container IDs")
    service_ids: Optional[List[str]] = Field(None, description="Filter by service IDs")
    metric_names: Optional[List[str]] = Field(None, description="Filter by metric names")
    date_range: Optional[Dict[str, datetime]] = Field(None, description="Date range filter")
    tags: Optional[Dict[str, Any]] = Field(None, description="Filter by tags")
    
    @validator('date_range')
    def validate_date_range(cls, v):
        if v and 'start' in v and 'end' in v:
            if v['start'] >= v['end']:
                raise ValueError('Start date must be before end date')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "severity": ["high", "critical"],
                "status": ["active"],
                "container_ids": ["container-1", "container-2"],
                "date_range": {
                    "start": "2023-01-01T00:00:00Z",
                    "end": "2023-01-31T23:59:59Z"
                },
                "tags": {
                    "environment": "production"
                }
            }
        }


class AlertExportSerializer(BaseModel):
    """Serializer for alert export"""
    format: str = Field("json", description="Export format")
    filters: Optional[AlertFilterSerializer] = Field(None, description="Export filters")
    include_history: bool = Field(False, description="Whether to include alert history")
    include_metadata: bool = Field(True, description="Whether to include metadata")
    
    @validator('format')
    def validate_format(cls, v):
        valid_formats = ['json', 'csv', 'xlsx']
        if v not in valid_formats:
            raise ValueError(f'Invalid format. Must be one of: {", ".join(valid_formats)}')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "format": "json",
                "filters": {
                    "severity": ["high", "critical"],
                    "status": ["active"]
                },
                "include_history": True,
                "include_metadata": True
            }
        }


class AlertWebhookSerializer(BaseModel):
    """Serializer for alert webhook payload"""
    alert_id: str = Field(..., description="Alert ID")
    event_type: str = Field(..., description="Event type")
    timestamp: datetime = Field(..., description="Event timestamp")
    alert_data: Dict[str, Any] = Field(..., description="Alert data")
    
    @validator('event_type')
    def validate_event_type(cls, v):
        valid_events = ['created', 'updated', 'acknowledged', 'resolved', 'deleted']
        if v not in valid_events:
            raise ValueError(f'Invalid event type. Must be one of: {", ".join(valid_events)}')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "alert_id": "alert-123",
                "event_type": "created",
                "timestamp": "2023-01-01T12:00:00Z",
                "alert_data": {
                    "title": "High CPU Usage",
                    "severity": "high",
                    "status": "active",
                    "metric_name": "cpu_usage",
                    "metric_value": 95.5,
                    "threshold": 80.0
                }
            }
        }
