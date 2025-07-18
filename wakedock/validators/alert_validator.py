"""
Alert Validator - Validation logic for alerts and notifications
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import re
from uuid import UUID

from wakedock.repositories.alert_repository import AlertSeverity, AlertStatus
from wakedock.core.exceptions import ValidationError

import logging
logger = logging.getLogger(__name__)


class AlertValidator:
    """Validator for alert data and operations"""
    
    def __init__(self):
        self.severity_levels = [s.value for s in AlertSeverity]
        self.status_types = [s.value for s in AlertStatus]
        self.metric_operators = ['gt', 'lt', 'gte', 'lte', 'eq', 'ne']
        self.max_title_length = 200
        self.max_description_length = 1000
        self.max_tags_count = 20
        self.max_metadata_size = 5000
    
    async def validate_alert_id(self, alert_id: str) -> bool:
        """Validate alert ID format"""
        if not alert_id:
            raise ValidationError("Alert ID is required")
        
        try:
            UUID(alert_id)
        except ValueError:
            raise ValidationError("Invalid alert ID format")
        
        return True
    
    async def validate_container_id(self, container_id: str) -> bool:
        """Validate container ID format"""
        if not container_id:
            raise ValidationError("Container ID is required")
        
        # Docker container ID validation (64 character hex string)
        if not re.match(r'^[a-f0-9]{64}$', container_id):
            # Also accept short form (12 characters)
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
    
    async def validate_severity(self, severity: str) -> bool:
        """Validate alert severity"""
        if not severity:
            raise ValidationError("Severity is required")
        
        if severity not in self.severity_levels:
            raise ValidationError(f"Invalid severity. Must be one of: {', '.join(self.severity_levels)}")
        
        return True
    
    async def validate_status(self, status: str) -> bool:
        """Validate alert status"""
        if not status:
            raise ValidationError("Status is required")
        
        if status not in self.status_types:
            raise ValidationError(f"Invalid status. Must be one of: {', '.join(self.status_types)}")
        
        return True
    
    async def validate_metric_operator(self, operator: str) -> bool:
        """Validate metric operator"""
        if not operator:
            raise ValidationError("Metric operator is required")
        
        if operator not in self.metric_operators:
            raise ValidationError(f"Invalid operator. Must be one of: {', '.join(self.metric_operators)}")
        
        return True
    
    async def validate_alert_title(self, title: str) -> bool:
        """Validate alert title"""
        if not title:
            raise ValidationError("Alert title is required")
        
        if not title.strip():
            raise ValidationError("Alert title cannot be empty")
        
        if len(title) > self.max_title_length:
            raise ValidationError(f"Alert title too long (max {self.max_title_length} characters)")
        
        # Check for invalid characters
        if re.search(r'[<>"\'\&]', title):
            raise ValidationError("Alert title contains invalid characters")
        
        return True
    
    async def validate_alert_description(self, description: str) -> bool:
        """Validate alert description"""
        if not description:
            raise ValidationError("Alert description is required")
        
        if not description.strip():
            raise ValidationError("Alert description cannot be empty")
        
        if len(description) > self.max_description_length:
            raise ValidationError(f"Alert description too long (max {self.max_description_length} characters)")
        
        return True
    
    async def validate_metric_name(self, metric_name: str) -> bool:
        """Validate metric name"""
        if not metric_name:
            raise ValidationError("Metric name is required")
        
        # Must be alphanumeric with underscores and dots
        if not re.match(r'^[a-zA-Z0-9_\.]+$', metric_name):
            raise ValidationError("Metric name must contain only alphanumeric characters, underscores, and dots")
        
        if len(metric_name) > 100:
            raise ValidationError("Metric name too long (max 100 characters)")
        
        return True
    
    async def validate_metric_value(self, metric_value: Any) -> bool:
        """Validate metric value"""
        if metric_value is None:
            raise ValidationError("Metric value is required")
        
        # Must be numeric
        if not isinstance(metric_value, (int, float)):
            try:
                float(metric_value)
            except (ValueError, TypeError):
                raise ValidationError("Metric value must be numeric")
        
        return True
    
    async def validate_threshold(self, threshold: Any) -> bool:
        """Validate threshold value"""
        if threshold is None:
            raise ValidationError("Threshold is required")
        
        # Must be numeric
        if not isinstance(threshold, (int, float)):
            try:
                float(threshold)
            except (ValueError, TypeError):
                raise ValidationError("Threshold must be numeric")
        
        return True
    
    async def validate_tags(self, tags: Dict[str, Any]) -> bool:
        """Validate alert tags"""
        if not isinstance(tags, dict):
            raise ValidationError("Tags must be a dictionary")
        
        if len(tags) > self.max_tags_count:
            raise ValidationError(f"Too many tags (max {self.max_tags_count})")
        
        for key, value in tags.items():
            # Validate tag key
            if not isinstance(key, str):
                raise ValidationError("Tag keys must be strings")
            
            if len(key) > 50:
                raise ValidationError("Tag key too long (max 50 characters)")
            
            if not re.match(r'^[a-zA-Z0-9_\-]+$', key):
                raise ValidationError("Tag key contains invalid characters")
            
            # Validate tag value
            if value is not None:
                if isinstance(value, str) and len(value) > 100:
                    raise ValidationError("Tag value too long (max 100 characters)")
                
                if not isinstance(value, (str, int, float, bool)):
                    raise ValidationError("Tag value must be string, number, or boolean")
        
        return True
    
    async def validate_metadata(self, metadata: Dict[str, Any]) -> bool:
        """Validate alert metadata"""
        if not isinstance(metadata, dict):
            raise ValidationError("Metadata must be a dictionary")
        
        # Estimate metadata size
        metadata_str = str(metadata)
        if len(metadata_str) > self.max_metadata_size:
            raise ValidationError(f"Metadata too large (max {self.max_metadata_size} characters)")
        
        return True
    
    async def validate_alert_creation(self, alert_data: Dict[str, Any]) -> bool:
        """Validate alert creation data"""
        required_fields = ['title', 'description', 'severity', 'metric_name', 'metric_value', 'threshold']
        
        # Check required fields
        for field in required_fields:
            if field not in alert_data:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate individual fields
        await self.validate_alert_title(alert_data['title'])
        await self.validate_alert_description(alert_data['description'])
        await self.validate_severity(alert_data['severity'])
        await self.validate_metric_name(alert_data['metric_name'])
        await self.validate_metric_value(alert_data['metric_value'])
        await self.validate_threshold(alert_data['threshold'])
        
        # Validate optional fields
        if 'operator' in alert_data:
            await self.validate_metric_operator(alert_data['operator'])
        
        if 'container_id' in alert_data and alert_data['container_id']:
            await self.validate_container_id(alert_data['container_id'])
        
        if 'service_id' in alert_data and alert_data['service_id']:
            await self.validate_service_id(alert_data['service_id'])
        
        if 'tags' in alert_data:
            await self.validate_tags(alert_data['tags'])
        
        if 'metadata' in alert_data:
            await self.validate_metadata(alert_data['metadata'])
        
        return True
    
    async def validate_alert_update(self, update_data: Dict[str, Any]) -> bool:
        """Validate alert update data"""
        if not update_data:
            raise ValidationError("Update data is required")
        
        # Validate allowed update fields
        allowed_fields = ['status', 'severity', 'description', 'metadata', 'resolved_at', 'acknowledged_at']
        
        for field in update_data:
            if field not in allowed_fields:
                raise ValidationError(f"Field '{field}' cannot be updated")
        
        # Validate individual fields
        if 'status' in update_data:
            await self.validate_status(update_data['status'])
        
        if 'severity' in update_data:
            await self.validate_severity(update_data['severity'])
        
        if 'description' in update_data:
            await self.validate_alert_description(update_data['description'])
        
        if 'metadata' in update_data:
            await self.validate_metadata(update_data['metadata'])
        
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
    
    async def validate_search_filters(self, filters: Dict[str, Any]) -> bool:
        """Validate search filters"""
        if not isinstance(filters, dict):
            raise ValidationError("Filters must be a dictionary")
        
        allowed_filters = ['severity', 'status', 'container_id', 'service_id', 'created_after', 'created_before']
        
        for filter_key in filters:
            if filter_key not in allowed_filters:
                raise ValidationError(f"Invalid filter: {filter_key}")
        
        # Validate individual filters
        if 'severity' in filters:
            await self.validate_severity(filters['severity'])
        
        if 'status' in filters:
            await self.validate_status(filters['status'])
        
        if 'container_id' in filters:
            await self.validate_container_id(filters['container_id'])
        
        if 'service_id' in filters:
            await self.validate_service_id(filters['service_id'])
        
        if 'created_after' in filters:
            await self.validate_datetime(filters['created_after'])
        
        if 'created_before' in filters:
            await self.validate_datetime(filters['created_before'])
        
        return True
    
    async def validate_datetime(self, datetime_str: str) -> bool:
        """Validate datetime string"""
        if not datetime_str:
            raise ValidationError("Datetime is required")
        
        try:
            # Try to parse ISO format
            datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        except ValueError:
            raise ValidationError("Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")
        
        return True
    
    async def validate_metric_data(self, metric_data: Dict[str, Any]) -> bool:
        """Validate metric data for alert processing"""
        required_fields = ['metric_name', 'metric_value', 'timestamp']
        
        for field in required_fields:
            if field not in metric_data:
                raise ValidationError(f"Missing required field: {field}")
        
        await self.validate_metric_name(metric_data['metric_name'])
        await self.validate_metric_value(metric_data['metric_value'])
        
        if 'timestamp' in metric_data:
            await self.validate_datetime(metric_data['timestamp'])
        
        # Validate optional fields
        if 'container_id' in metric_data and metric_data['container_id']:
            await self.validate_container_id(metric_data['container_id'])
        
        if 'service_id' in metric_data and metric_data['service_id']:
            await self.validate_service_id(metric_data['service_id'])
        
        if 'tags' in metric_data:
            await self.validate_tags(metric_data['tags'])
        
        return True
    
    async def validate_alert_rule(self, rule_data: Dict[str, Any]) -> bool:
        """Validate alert rule data"""
        required_fields = ['name', 'metric_name', 'operator', 'threshold', 'severity']
        
        for field in required_fields:
            if field not in rule_data:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate rule name
        if not rule_data['name'].strip():
            raise ValidationError("Rule name cannot be empty")
        
        if len(rule_data['name']) > 100:
            raise ValidationError("Rule name too long (max 100 characters)")
        
        await self.validate_metric_name(rule_data['metric_name'])
        await self.validate_metric_operator(rule_data['operator'])
        await self.validate_threshold(rule_data['threshold'])
        await self.validate_severity(rule_data['severity'])
        
        # Validate optional fields
        if 'description' in rule_data:
            if len(rule_data['description']) > 500:
                raise ValidationError("Rule description too long (max 500 characters)")
        
        if 'tags' in rule_data:
            await self.validate_tags(rule_data['tags'])
        
        if 'cooldown_period' in rule_data:
            cooldown = rule_data['cooldown_period']
            if not isinstance(cooldown, int) or cooldown < 0:
                raise ValidationError("Cooldown period must be a non-negative integer")
        
        return True
    
    async def validate_notification_channel(self, channel_data: Dict[str, Any]) -> bool:
        """Validate notification channel data"""
        required_fields = ['name', 'type', 'config']
        
        for field in required_fields:
            if field not in channel_data:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate channel name
        if not channel_data['name'].strip():
            raise ValidationError("Channel name cannot be empty")
        
        if len(channel_data['name']) > 100:
            raise ValidationError("Channel name too long (max 100 characters)")
        
        # Validate channel type
        valid_types = ['email', 'slack', 'webhook', 'sms', 'discord']
        if channel_data['type'] not in valid_types:
            raise ValidationError(f"Invalid channel type. Must be one of: {', '.join(valid_types)}")
        
        # Validate channel config
        if not isinstance(channel_data['config'], dict):
            raise ValidationError("Channel config must be a dictionary")
        
        # Type-specific validation
        channel_type = channel_data['type']
        config = channel_data['config']
        
        if channel_type == 'email':
            if 'recipient' not in config:
                raise ValidationError("Email channel requires 'recipient' in config")
            
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, config['recipient']):
                raise ValidationError("Invalid email address")
        
        elif channel_type == 'webhook':
            if 'url' not in config:
                raise ValidationError("Webhook channel requires 'url' in config")
            
            url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
            if not re.match(url_pattern, config['url']):
                raise ValidationError("Invalid webhook URL")
        
        elif channel_type == 'slack':
            if 'webhook_url' not in config:
                raise ValidationError("Slack channel requires 'webhook_url' in config")
        
        return True
    
    async def validate_bulk_operation(self, operation_data: Dict[str, Any]) -> bool:
        """Validate bulk operation data"""
        required_fields = ['alert_ids', 'operation']
        
        for field in required_fields:
            if field not in operation_data:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate alert IDs
        alert_ids = operation_data['alert_ids']
        if not isinstance(alert_ids, list):
            raise ValidationError("Alert IDs must be a list")
        
        if len(alert_ids) == 0:
            raise ValidationError("At least one alert ID is required")
        
        if len(alert_ids) > 100:
            raise ValidationError("Too many alert IDs (max 100)")
        
        for alert_id in alert_ids:
            await self.validate_alert_id(alert_id)
        
        # Validate operation
        valid_operations = ['acknowledge', 'resolve', 'delete', 'update_severity']
        if operation_data['operation'] not in valid_operations:
            raise ValidationError(f"Invalid operation. Must be one of: {', '.join(valid_operations)}")
        
        return True
