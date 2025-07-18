"""
Analytics Validator - Validation logic for analytics, metrics and reports
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import re
from uuid import UUID

from wakedock.repositories.analytics_repository import MetricType, AggregationType, TimeGranularity
from wakedock.core.exceptions import ValidationError

import logging
logger = logging.getLogger(__name__)


class AnalyticsValidator:
    """Validator for analytics data and operations"""
    
    def __init__(self):
        self.metric_types = [t.value for t in MetricType]
        self.aggregation_types = [a.value for a in AggregationType]
        self.time_granularities = [g.value for g in TimeGranularity]
        self.max_metric_name_length = 100
        self.max_description_length = 500
        self.max_labels_count = 50
        self.max_time_range_days = 365
        self.max_forecast_hours = 168  # 1 week
        self.valid_export_formats = ['json', 'csv', 'xlsx', 'parquet']
        self.valid_report_types = ['summary', 'detailed', 'comparison', 'trend']
    
    async def validate_metric_id(self, metric_id: str) -> bool:
        """Validate metric ID format"""
        if not metric_id:
            raise ValidationError("Metric ID is required")
        
        try:
            UUID(metric_id)
        except ValueError:
            raise ValidationError("Invalid metric ID format")
        
        return True
    
    async def validate_container_id(self, container_id: str) -> bool:
        """Validate container ID format"""
        if not container_id:
            raise ValidationError("Container ID is required")
        
        # Docker container ID validation (64 character hex string or 12 character short form)
        if not re.match(r'^[a-f0-9]{64}$', container_id):
            if not re.match(r'^[a-f0-9]{12}$', container_id):
                raise ValidationError("Invalid container ID format")
        
        return True
    
    async def validate_service_id(self, service_id: str) -> bool:
        """Validate service ID format"""
        if not service_id:
            raise ValidationError("Service ID is required")
        
        try:
            UUID(service_id)
        except ValueError:
            raise ValidationError("Invalid service ID format")
        
        return True
    
    async def validate_metric_type(self, metric_type: str) -> bool:
        """Validate metric type"""
        if not metric_type:
            raise ValidationError("Metric type is required")
        
        if metric_type not in self.metric_types:
            raise ValidationError(f"Invalid metric type. Must be one of: {', '.join(self.metric_types)}")
        
        return True
    
    async def validate_aggregation_type(self, aggregation_type: str) -> bool:
        """Validate aggregation type"""
        if not aggregation_type:
            raise ValidationError("Aggregation type is required")
        
        if aggregation_type not in self.aggregation_types:
            raise ValidationError(f"Invalid aggregation type. Must be one of: {', '.join(self.aggregation_types)}")
        
        return True
    
    async def validate_granularity(self, granularity: str) -> bool:
        """Validate time granularity"""
        if not granularity:
            raise ValidationError("Time granularity is required")
        
        if granularity not in self.time_granularities:
            raise ValidationError(f"Invalid granularity. Must be one of: {', '.join(self.time_granularities)}")
        
        return True
    
    async def validate_metric_name(self, metric_name: str) -> bool:
        """Validate metric name"""
        if not metric_name:
            raise ValidationError("Metric name is required")
        
        if not metric_name.strip():
            raise ValidationError("Metric name cannot be empty")
        
        if len(metric_name) > self.max_metric_name_length:
            raise ValidationError(f"Metric name too long (max {self.max_metric_name_length} characters)")
        
        # Must be alphanumeric with underscores, dots, and hyphens
        if not re.match(r'^[a-zA-Z0-9_\.\-]+$', metric_name):
            raise ValidationError("Metric name must contain only alphanumeric characters, underscores, dots, and hyphens")
        
        return True
    
    async def validate_metric_description(self, description: str) -> bool:
        """Validate metric description"""
        if description is None:
            return True  # Description is optional
        
        if len(description) > self.max_description_length:
            raise ValidationError(f"Description too long (max {self.max_description_length} characters)")
        
        return True
    
    async def validate_metric_unit(self, unit: str) -> bool:
        """Validate metric unit"""
        if unit is None:
            return True  # Unit is optional
        
        if len(unit) > 50:
            raise ValidationError("Unit too long (max 50 characters)")
        
        # Common units validation
        valid_units = [
            'bytes', 'kb', 'mb', 'gb', 'tb',
            'percent', '%', 'ratio',
            'seconds', 'ms', 'ns', 'minutes', 'hours',
            'count', 'requests', 'errors',
            'cpu', 'memory', 'disk', 'network'
        ]
        
        if unit.lower() not in valid_units:
            logger.warning(f"Uncommon unit used: {unit}")
        
        return True
    
    async def validate_metric_value(self, value: Any) -> bool:
        """Validate metric value"""
        if value is None:
            raise ValidationError("Metric value is required")
        
        # Must be numeric
        if not isinstance(value, (int, float)):
            try:
                float(value)
            except (ValueError, TypeError):
                raise ValidationError("Metric value must be numeric")
        
        # Check for reasonable bounds
        numeric_value = float(value)
        if numeric_value < -1e15 or numeric_value > 1e15:
            raise ValidationError("Metric value out of reasonable bounds")
        
        # Check for NaN or infinity
        if not (numeric_value == numeric_value):  # NaN check
            raise ValidationError("Metric value cannot be NaN")
        
        if numeric_value == float('inf') or numeric_value == float('-inf'):
            raise ValidationError("Metric value cannot be infinite")
        
        return True
    
    async def validate_labels(self, labels: Dict[str, Any]) -> bool:
        """Validate metric labels"""
        if not isinstance(labels, dict):
            raise ValidationError("Labels must be a dictionary")
        
        if len(labels) > self.max_labels_count:
            raise ValidationError(f"Too many labels (max {self.max_labels_count})")
        
        for key, value in labels.items():
            # Validate label key
            if not isinstance(key, str):
                raise ValidationError("Label keys must be strings")
            
            if len(key) > 100:
                raise ValidationError("Label key too long (max 100 characters)")
            
            if not re.match(r'^[a-zA-Z0-9_\-\.]+$', key):
                raise ValidationError("Label key contains invalid characters")
            
            # Validate label value
            if value is not None:
                if isinstance(value, str) and len(value) > 200:
                    raise ValidationError("Label value too long (max 200 characters)")
                
                if not isinstance(value, (str, int, float, bool)):
                    raise ValidationError("Label value must be string, number, or boolean")
        
        return True
    
    async def validate_timestamp(self, timestamp: datetime) -> bool:
        """Validate timestamp"""
        if not isinstance(timestamp, datetime):
            raise ValidationError("Timestamp must be a datetime object")
        
        # Check if timestamp is too far in the future
        now = datetime.utcnow()
        if timestamp > now + timedelta(hours=1):
            raise ValidationError("Timestamp cannot be more than 1 hour in the future")
        
        # Check if timestamp is too far in the past
        if timestamp < now - timedelta(days=365):
            raise ValidationError("Timestamp cannot be more than 1 year in the past")
        
        return True
    
    async def validate_time_range(self, start_time: datetime, end_time: datetime) -> bool:
        """Validate time range"""
        if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
            raise ValidationError("Start and end times must be datetime objects")
        
        if start_time >= end_time:
            raise ValidationError("Start time must be before end time")
        
        # Check maximum time range
        time_diff = end_time - start_time
        if time_diff.days > self.max_time_range_days:
            raise ValidationError(f"Time range too large (max {self.max_time_range_days} days)")
        
        # Check if time range is reasonable
        if time_diff.total_seconds() < 60:
            raise ValidationError("Time range must be at least 1 minute")
        
        return True
    
    async def validate_search_query(self, query: str) -> bool:
        """Validate search query"""
        if not query:
            return True  # Empty query is allowed
        
        if len(query) > 200:
            raise ValidationError("Search query too long (max 200 characters)")
        
        # Check for SQL injection attempts
        dangerous_patterns = [
            r'(union|select|insert|update|delete|drop|create|alter)\s+',
            r'(\-\-|\#|\/\*|\*\/)',
            r'(script|javascript|vbscript)',
            r'(onload|onerror|onclick)'
        ]
        
        query_lower = query.lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, query_lower):
                raise ValidationError("Search query contains invalid characters")
        
        return True
    
    async def validate_metric_creation(self, metric_data: Dict[str, Any]) -> bool:
        """Validate metric creation data"""
        required_fields = ['name', 'type']
        
        # Check required fields
        for field in required_fields:
            if field not in metric_data:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate individual fields
        await self.validate_metric_name(metric_data['name'])
        await self.validate_metric_type(metric_data['type'])
        
        # Validate optional fields
        if 'description' in metric_data:
            await self.validate_metric_description(metric_data['description'])
        
        if 'unit' in metric_data:
            await self.validate_metric_unit(metric_data['unit'])
        
        if 'labels' in metric_data:
            await self.validate_labels(metric_data['labels'])
        
        if 'metadata' in metric_data:
            await self.validate_metadata(metric_data['metadata'])
        
        return True
    
    async def validate_metadata(self, metadata: Dict[str, Any]) -> bool:
        """Validate metadata"""
        if not isinstance(metadata, dict):
            raise ValidationError("Metadata must be a dictionary")
        
        # Estimate metadata size
        metadata_str = str(metadata)
        if len(metadata_str) > 10000:
            raise ValidationError("Metadata too large (max 10000 characters)")
        
        return True
    
    async def validate_report_config(self, report_config: Dict[str, Any]) -> bool:
        """Validate report configuration"""
        required_fields = ['report_type', 'metrics', 'time_range']
        
        # Check required fields
        for field in required_fields:
            if field not in report_config:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate report type
        if report_config['report_type'] not in self.valid_report_types:
            raise ValidationError(f"Invalid report type. Must be one of: {', '.join(self.valid_report_types)}")
        
        # Validate metrics list
        metrics = report_config['metrics']
        if not isinstance(metrics, list):
            raise ValidationError("Metrics must be a list")
        
        if len(metrics) == 0:
            raise ValidationError("At least one metric is required")
        
        if len(metrics) > 20:
            raise ValidationError("Too many metrics (max 20)")
        
        for metric_id in metrics:
            await self.validate_metric_id(metric_id)
        
        # Validate time range
        time_range = report_config['time_range']
        if not isinstance(time_range, dict):
            raise ValidationError("Time range must be a dictionary")
        
        if 'start' not in time_range or 'end' not in time_range:
            raise ValidationError("Time range must include start and end")
        
        # Validate optional fields
        if 'aggregation' in report_config:
            await self.validate_aggregation_type(report_config['aggregation'])
        
        if 'granularity' in report_config:
            await self.validate_granularity(report_config['granularity'])
        
        return True
    
    async def validate_export_config(self, export_config: Dict[str, Any]) -> bool:
        """Validate export configuration"""
        required_fields = ['format', 'metrics']
        
        # Check required fields
        for field in required_fields:
            if field not in export_config:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate format
        if export_config['format'] not in self.valid_export_formats:
            raise ValidationError(f"Invalid export format. Must be one of: {', '.join(self.valid_export_formats)}")
        
        # Validate metrics
        metrics = export_config['metrics']
        if not isinstance(metrics, list):
            raise ValidationError("Metrics must be a list")
        
        if len(metrics) == 0:
            raise ValidationError("At least one metric is required")
        
        if len(metrics) > 50:
            raise ValidationError("Too many metrics for export (max 50)")
        
        for metric_id in metrics:
            await self.validate_metric_id(metric_id)
        
        # Validate optional fields
        if 'time_range' in export_config:
            time_range = export_config['time_range']
            if isinstance(time_range, dict) and 'start' in time_range and 'end' in time_range:
                start_time = datetime.fromisoformat(time_range['start'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(time_range['end'].replace('Z', '+00:00'))
                await self.validate_time_range(start_time, end_time)
        
        return True
    
    async def validate_correlation_request(self, metric_ids: List[str]) -> bool:
        """Validate correlation request"""
        if not isinstance(metric_ids, list):
            raise ValidationError("Metric IDs must be a list")
        
        if len(metric_ids) < 2:
            raise ValidationError("At least 2 metrics required for correlation")
        
        if len(metric_ids) > 10:
            raise ValidationError("Maximum 10 metrics allowed for correlation")
        
        # Check for duplicates
        if len(set(metric_ids)) != len(metric_ids):
            raise ValidationError("Duplicate metric IDs not allowed")
        
        # Validate each metric ID
        for metric_id in metric_ids:
            await self.validate_metric_id(metric_id)
        
        return True
    
    async def validate_forecast_request(self, metric_id: str, forecast_hours: int) -> bool:
        """Validate forecast request"""
        await self.validate_metric_id(metric_id)
        
        if not isinstance(forecast_hours, int):
            raise ValidationError("Forecast hours must be an integer")
        
        if forecast_hours <= 0:
            raise ValidationError("Forecast hours must be positive")
        
        if forecast_hours > self.max_forecast_hours:
            raise ValidationError(f"Forecast hours too large (max {self.max_forecast_hours})")
        
        return True
    
    async def validate_anomaly_detection_request(self, metric_id: str, sensitivity: float = None) -> bool:
        """Validate anomaly detection request"""
        await self.validate_metric_id(metric_id)
        
        if sensitivity is not None:
            if not isinstance(sensitivity, (int, float)):
                raise ValidationError("Sensitivity must be numeric")
            
            if sensitivity < 0.1 or sensitivity > 10.0:
                raise ValidationError("Sensitivity must be between 0.1 and 10.0")
        
        return True
    
    async def validate_dashboard_config(self, dashboard_config: Dict[str, Any]) -> bool:
        """Validate dashboard configuration"""
        required_fields = ['name', 'widgets']
        
        # Check required fields
        for field in required_fields:
            if field not in dashboard_config:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate dashboard name
        name = dashboard_config['name']
        if not isinstance(name, str) or not name.strip():
            raise ValidationError("Dashboard name must be a non-empty string")
        
        if len(name) > 100:
            raise ValidationError("Dashboard name too long (max 100 characters)")
        
        # Validate widgets
        widgets = dashboard_config['widgets']
        if not isinstance(widgets, list):
            raise ValidationError("Widgets must be a list")
        
        if len(widgets) == 0:
            raise ValidationError("At least one widget is required")
        
        if len(widgets) > 50:
            raise ValidationError("Too many widgets (max 50)")
        
        for widget in widgets:
            await self.validate_widget_config(widget)
        
        return True
    
    async def validate_widget_config(self, widget_config: Dict[str, Any]) -> bool:
        """Validate widget configuration"""
        required_fields = ['type', 'metric_id']
        
        # Check required fields
        for field in required_fields:
            if field not in widget_config:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate widget type
        valid_widget_types = ['line_chart', 'bar_chart', 'pie_chart', 'gauge', 'counter', 'table']
        if widget_config['type'] not in valid_widget_types:
            raise ValidationError(f"Invalid widget type. Must be one of: {', '.join(valid_widget_types)}")
        
        # Validate metric ID
        await self.validate_metric_id(widget_config['metric_id'])
        
        # Validate optional fields
        if 'title' in widget_config:
            title = widget_config['title']
            if not isinstance(title, str) or len(title) > 100:
                raise ValidationError("Widget title must be a string with max 100 characters")
        
        if 'size' in widget_config:
            size = widget_config['size']
            if not isinstance(size, dict) or 'width' not in size or 'height' not in size:
                raise ValidationError("Widget size must be a dictionary with width and height")
        
        return True
    
    async def validate_bulk_metric_operation(self, operation_data: Dict[str, Any]) -> bool:
        """Validate bulk metric operation"""
        required_fields = ['metric_ids', 'operation']
        
        for field in required_fields:
            if field not in operation_data:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate metric IDs
        metric_ids = operation_data['metric_ids']
        if not isinstance(metric_ids, list):
            raise ValidationError("Metric IDs must be a list")
        
        if len(metric_ids) == 0:
            raise ValidationError("At least one metric ID is required")
        
        if len(metric_ids) > 100:
            raise ValidationError("Too many metric IDs (max 100)")
        
        for metric_id in metric_ids:
            await self.validate_metric_id(metric_id)
        
        # Validate operation
        valid_operations = ['delete', 'update_metadata', 'update_labels', 'aggregate']
        if operation_data['operation'] not in valid_operations:
            raise ValidationError(f"Invalid operation. Must be one of: {', '.join(valid_operations)}")
        
        return True
