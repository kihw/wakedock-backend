"""
Dashboard Validator - Validation logic for dashboard operations
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import re
from pydantic import BaseModel, Field, validator

from wakedock.core.exceptions import ValidationError
from wakedock.core.logging import get_logger

logger = get_logger(__name__)


class DashboardValidator:
    """Validator for dashboard operations"""
    
    VALID_WIDGET_TYPES = {
        'chart', 'metric', 'table', 'text', 'image', 'gauge', 'heatmap', 
        'map', 'progress', 'alert', 'log', 'iframe', 'custom'
    }
    
    VALID_CHART_TYPES = {
        'line', 'bar', 'pie', 'doughnut', 'radar', 'scatter', 'bubble', 
        'area', 'column', 'histogram', 'candlestick'
    }
    
    VALID_AGGREGATION_TYPES = {
        'avg', 'sum', 'min', 'max', 'count', 'median', 'mode', 'std', 'var'
    }
    
    VALID_TIME_PERIODS = {
        '1m', '5m', '15m', '30m', '1h', '3h', '6h', '12h', '1d', '7d', '30d'
    }
    
    def __init__(self):
        self.name_pattern = re.compile(r'^[a-zA-Z0-9_\-\s]{1,100}$')
        self.color_pattern = re.compile(r'^#[0-9A-Fa-f]{6}$')
    
    async def validate_dashboard_config(self, dashboard_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate dashboard configuration"""
        try:
            # Validate required fields
            if 'name' not in dashboard_data:
                raise ValidationError("Dashboard name is required")
            
            # Validate name
            if not self.name_pattern.match(dashboard_data['name']):
                raise ValidationError(
                    "Dashboard name must contain only alphanumeric characters, spaces, hyphens, and underscores (1-100 characters)"
                )
            
            # Validate description
            if 'description' in dashboard_data and len(dashboard_data['description']) > 500:
                raise ValidationError("Dashboard description must be less than 500 characters")
            
            # Validate layout
            if 'layout' in dashboard_data:
                await self._validate_layout(dashboard_data['layout'])
            
            # Validate refresh interval
            if 'refresh_interval' in dashboard_data:
                refresh_interval = dashboard_data['refresh_interval']
                if not isinstance(refresh_interval, int) or refresh_interval < 10:
                    raise ValidationError("Refresh interval must be at least 10 seconds")
                if refresh_interval > 86400:  # 24 hours
                    raise ValidationError("Refresh interval cannot exceed 24 hours")
            
            # Validate public flag
            if 'public' in dashboard_data and not isinstance(dashboard_data['public'], bool):
                raise ValidationError("Public flag must be a boolean")
            
            # Validate auto_refresh flag
            if 'auto_refresh' in dashboard_data and not isinstance(dashboard_data['auto_refresh'], bool):
                raise ValidationError("Auto refresh flag must be a boolean")
            
            # Validate theme
            if 'theme' in dashboard_data:
                await self._validate_theme(dashboard_data['theme'])
            
            # Validate filters
            if 'filters' in dashboard_data:
                await self._validate_filters(dashboard_data['filters'])
            
            return dashboard_data
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating dashboard config: {str(e)}")
            raise ValidationError(f"Invalid dashboard configuration: {str(e)}")
    
    async def validate_widget_config(self, widget_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate widget configuration"""
        try:
            # Validate required fields
            if 'title' not in widget_data:
                raise ValidationError("Widget title is required")
            
            if 'type' not in widget_data:
                raise ValidationError("Widget type is required")
            
            # Validate title
            if not self.name_pattern.match(widget_data['title']):
                raise ValidationError(
                    "Widget title must contain only alphanumeric characters, spaces, hyphens, and underscores (1-100 characters)"
                )
            
            # Validate type
            if widget_data['type'] not in self.VALID_WIDGET_TYPES:
                raise ValidationError(f"Invalid widget type: {widget_data['type']}")
            
            # Validate position
            if 'position' in widget_data:
                await self._validate_position(widget_data['position'])
            
            # Validate size
            if 'size' in widget_data:
                await self._validate_size(widget_data['size'])
            
            # Validate config based on widget type
            if 'config' in widget_data:
                await self._validate_widget_type_config(widget_data['type'], widget_data['config'])
            
            # Validate metric_id if provided
            if 'metric_id' in widget_data:
                if not isinstance(widget_data['metric_id'], str):
                    raise ValidationError("Metric ID must be a string")
            
            # Validate query if provided
            if 'query' in widget_data:
                await self._validate_query(widget_data['query'])
            
            # Validate refresh_interval
            if 'refresh_interval' in widget_data:
                refresh_interval = widget_data['refresh_interval']
                if not isinstance(refresh_interval, int) or refresh_interval < 10:
                    raise ValidationError("Widget refresh interval must be at least 10 seconds")
                if refresh_interval > 3600:  # 1 hour
                    raise ValidationError("Widget refresh interval cannot exceed 1 hour")
            
            # Validate active flag
            if 'active' in widget_data and not isinstance(widget_data['active'], bool):
                raise ValidationError("Active flag must be a boolean")
            
            return widget_data
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating widget config: {str(e)}")
            raise ValidationError(f"Invalid widget configuration: {str(e)}")
    
    async def validate_dashboard_import(self, import_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate dashboard import data"""
        try:
            # Validate structure
            if 'dashboard' not in import_data:
                raise ValidationError("Import data must contain dashboard configuration")
            
            # Validate dashboard
            dashboard_data = import_data['dashboard']
            await self.validate_dashboard_config(dashboard_data)
            
            # Validate widgets
            if 'widgets' in import_data:
                if not isinstance(import_data['widgets'], list):
                    raise ValidationError("Widgets must be a list")
                
                for widget in import_data['widgets']:
                    await self.validate_widget_config(widget)
            
            # Validate version
            if 'version' in import_data:
                if not isinstance(import_data['version'], str):
                    raise ValidationError("Version must be a string")
            
            # Validate metadata
            if 'metadata' in import_data:
                await self._validate_metadata(import_data['metadata'])
            
            return import_data
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating dashboard import: {str(e)}")
            raise ValidationError(f"Invalid dashboard import data: {str(e)}")
    
    async def validate_time_range(self, start_time: datetime, end_time: datetime) -> bool:
        """Validate time range"""
        try:
            if start_time >= end_time:
                raise ValidationError("Start time must be before end time")
            
            # Check for reasonable time range (not more than 1 year)
            time_diff = end_time - start_time
            if time_diff.days > 365:
                raise ValidationError("Time range cannot exceed 1 year")
            
            # Check for minimum time range (at least 1 minute)
            if time_diff.total_seconds() < 60:
                raise ValidationError("Time range must be at least 1 minute")
            
            return True
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating time range: {str(e)}")
            raise ValidationError(f"Invalid time range: {str(e)}")
    
    async def validate_search_params(self, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate search parameters"""
        try:
            # Validate page
            if 'page' in search_params:
                page = search_params['page']
                if not isinstance(page, int) or page < 1:
                    raise ValidationError("Page must be a positive integer")
            
            # Validate per_page
            if 'per_page' in search_params:
                per_page = search_params['per_page']
                if not isinstance(per_page, int) or per_page < 1 or per_page > 100:
                    raise ValidationError("Per page must be between 1 and 100")
            
            # Validate filters
            if 'filters' in search_params:
                await self._validate_search_filters(search_params['filters'])
            
            # Validate sort
            if 'sort' in search_params:
                await self._validate_sort(search_params['sort'])
            
            return search_params
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating search params: {str(e)}")
            raise ValidationError(f"Invalid search parameters: {str(e)}")
    
    async def validate_bulk_operation(self, operation: str, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate bulk operation"""
        try:
            if operation not in ['create', 'update', 'delete']:
                raise ValidationError(f"Invalid bulk operation: {operation}")
            
            if not isinstance(data, list):
                raise ValidationError("Bulk operation data must be a list")
            
            if len(data) == 0:
                raise ValidationError("Bulk operation data cannot be empty")
            
            if len(data) > 100:
                raise ValidationError("Bulk operation cannot exceed 100 items")
            
            # Validate each item
            for i, item in enumerate(data):
                if not isinstance(item, dict):
                    raise ValidationError(f"Item {i} must be a dictionary")
                
                if operation == 'create':
                    await self.validate_widget_config(item)
                elif operation == 'update':
                    if 'id' not in item:
                        raise ValidationError(f"Item {i} must contain an ID for update operation")
                    # Validate update data
                    update_data = {k: v for k, v in item.items() if k != 'id'}
                    if update_data:
                        await self.validate_widget_config(update_data)
                elif operation == 'delete':
                    if 'id' not in item:
                        raise ValidationError(f"Item {i} must contain an ID for delete operation")
            
            return data
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error validating bulk operation: {str(e)}")
            raise ValidationError(f"Invalid bulk operation: {str(e)}")
    
    # Private validation methods
    
    async def _validate_layout(self, layout: Dict[str, Any]):
        """Validate layout configuration"""
        if 'type' in layout:
            if layout['type'] not in ['grid', 'flow', 'fixed']:
                raise ValidationError(f"Invalid layout type: {layout['type']}")
        
        if 'columns' in layout:
            columns = layout['columns']
            if not isinstance(columns, int) or columns < 1 or columns > 12:
                raise ValidationError("Layout columns must be between 1 and 12")
        
        if 'rows' in layout:
            rows = layout['rows']
            if not isinstance(rows, int) or rows < 1 or rows > 20:
                raise ValidationError("Layout rows must be between 1 and 20")
        
        if 'gap' in layout:
            gap = layout['gap']
            if not isinstance(gap, int) or gap < 0 or gap > 50:
                raise ValidationError("Layout gap must be between 0 and 50")
    
    async def _validate_position(self, position: Dict[str, Any]):
        """Validate widget position"""
        if 'x' in position:
            if not isinstance(position['x'], int) or position['x'] < 0:
                raise ValidationError("Position x must be a non-negative integer")
        
        if 'y' in position:
            if not isinstance(position['y'], int) or position['y'] < 0:
                raise ValidationError("Position y must be a non-negative integer")
        
        if 'row' in position:
            if not isinstance(position['row'], int) or position['row'] < 0:
                raise ValidationError("Position row must be a non-negative integer")
        
        if 'col' in position:
            if not isinstance(position['col'], int) or position['col'] < 0:
                raise ValidationError("Position col must be a non-negative integer")
    
    async def _validate_size(self, size: Dict[str, Any]):
        """Validate widget size"""
        if 'width' in size:
            width = size['width']
            if not isinstance(width, int) or width < 1 or width > 12:
                raise ValidationError("Widget width must be between 1 and 12")
        
        if 'height' in size:
            height = size['height']
            if not isinstance(height, int) or height < 1 or height > 20:
                raise ValidationError("Widget height must be between 1 and 20")
        
        if 'min_width' in size:
            min_width = size['min_width']
            if not isinstance(min_width, int) or min_width < 1:
                raise ValidationError("Widget minimum width must be at least 1")
        
        if 'min_height' in size:
            min_height = size['min_height']
            if not isinstance(min_height, int) or min_height < 1:
                raise ValidationError("Widget minimum height must be at least 1")
    
    async def _validate_widget_type_config(self, widget_type: str, config: Dict[str, Any]):
        """Validate widget configuration based on type"""
        if widget_type == 'chart':
            await self._validate_chart_config(config)
        elif widget_type == 'metric':
            await self._validate_metric_config(config)
        elif widget_type == 'table':
            await self._validate_table_config(config)
        elif widget_type == 'gauge':
            await self._validate_gauge_config(config)
        elif widget_type == 'text':
            await self._validate_text_config(config)
        elif widget_type == 'image':
            await self._validate_image_config(config)
        elif widget_type == 'alert':
            await self._validate_alert_config(config)
        elif widget_type == 'iframe':
            await self._validate_iframe_config(config)
    
    async def _validate_chart_config(self, config: Dict[str, Any]):
        """Validate chart widget configuration"""
        if 'chart_type' in config:
            if config['chart_type'] not in self.VALID_CHART_TYPES:
                raise ValidationError(f"Invalid chart type: {config['chart_type']}")
        
        if 'aggregation' in config:
            if config['aggregation'] not in self.VALID_AGGREGATION_TYPES:
                raise ValidationError(f"Invalid aggregation type: {config['aggregation']}")
        
        if 'time_period' in config:
            if config['time_period'] not in self.VALID_TIME_PERIODS:
                raise ValidationError(f"Invalid time period: {config['time_period']}")
        
        if 'colors' in config:
            if not isinstance(config['colors'], list):
                raise ValidationError("Colors must be a list")
            for color in config['colors']:
                if not self.color_pattern.match(color):
                    raise ValidationError(f"Invalid color format: {color}")
    
    async def _validate_metric_config(self, config: Dict[str, Any]):
        """Validate metric widget configuration"""
        if 'format' in config:
            if config['format'] not in ['number', 'percentage', 'currency', 'bytes', 'duration']:
                raise ValidationError(f"Invalid metric format: {config['format']}")
        
        if 'threshold' in config:
            threshold = config['threshold']
            if not isinstance(threshold, (int, float)):
                raise ValidationError("Threshold must be a number")
        
        if 'unit' in config:
            if not isinstance(config['unit'], str):
                raise ValidationError("Unit must be a string")
    
    async def _validate_table_config(self, config: Dict[str, Any]):
        """Validate table widget configuration"""
        if 'columns' in config:
            if not isinstance(config['columns'], list):
                raise ValidationError("Table columns must be a list")
            for column in config['columns']:
                if not isinstance(column, dict):
                    raise ValidationError("Table column must be a dictionary")
                if 'name' not in column:
                    raise ValidationError("Table column must have a name")
        
        if 'pagination' in config:
            if not isinstance(config['pagination'], bool):
                raise ValidationError("Pagination must be a boolean")
        
        if 'page_size' in config:
            page_size = config['page_size']
            if not isinstance(page_size, int) or page_size < 1 or page_size > 100:
                raise ValidationError("Page size must be between 1 and 100")
    
    async def _validate_gauge_config(self, config: Dict[str, Any]):
        """Validate gauge widget configuration"""
        if 'min_value' in config:
            if not isinstance(config['min_value'], (int, float)):
                raise ValidationError("Minimum value must be a number")
        
        if 'max_value' in config:
            if not isinstance(config['max_value'], (int, float)):
                raise ValidationError("Maximum value must be a number")
        
        if 'min_value' in config and 'max_value' in config:
            if config['min_value'] >= config['max_value']:
                raise ValidationError("Minimum value must be less than maximum value")
        
        if 'thresholds' in config:
            if not isinstance(config['thresholds'], list):
                raise ValidationError("Thresholds must be a list")
            for threshold in config['thresholds']:
                if not isinstance(threshold, dict):
                    raise ValidationError("Threshold must be a dictionary")
                if 'value' not in threshold or 'color' not in threshold:
                    raise ValidationError("Threshold must have value and color")
    
    async def _validate_text_config(self, config: Dict[str, Any]):
        """Validate text widget configuration"""
        if 'content' in config:
            if not isinstance(config['content'], str):
                raise ValidationError("Text content must be a string")
            if len(config['content']) > 10000:
                raise ValidationError("Text content cannot exceed 10,000 characters")
        
        if 'format' in config:
            if config['format'] not in ['plain', 'markdown', 'html']:
                raise ValidationError(f"Invalid text format: {config['format']}")
    
    async def _validate_image_config(self, config: Dict[str, Any]):
        """Validate image widget configuration"""
        if 'url' in config:
            if not isinstance(config['url'], str):
                raise ValidationError("Image URL must be a string")
            # Basic URL validation
            if not (config['url'].startswith('http://') or config['url'].startswith('https://')):
                raise ValidationError("Image URL must be a valid HTTP(S) URL")
        
        if 'alt_text' in config:
            if not isinstance(config['alt_text'], str):
                raise ValidationError("Alt text must be a string")
    
    async def _validate_alert_config(self, config: Dict[str, Any]):
        """Validate alert widget configuration"""
        if 'severity' in config:
            if config['severity'] not in ['low', 'medium', 'high', 'critical']:
                raise ValidationError(f"Invalid alert severity: {config['severity']}")
        
        if 'conditions' in config:
            if not isinstance(config['conditions'], list):
                raise ValidationError("Alert conditions must be a list")
    
    async def _validate_iframe_config(self, config: Dict[str, Any]):
        """Validate iframe widget configuration"""
        if 'url' in config:
            if not isinstance(config['url'], str):
                raise ValidationError("Iframe URL must be a string")
            # Basic URL validation
            if not (config['url'].startswith('http://') or config['url'].startswith('https://')):
                raise ValidationError("Iframe URL must be a valid HTTP(S) URL")
        
        if 'sandbox' in config:
            if not isinstance(config['sandbox'], bool):
                raise ValidationError("Sandbox must be a boolean")
    
    async def _validate_theme(self, theme: Dict[str, Any]):
        """Validate theme configuration"""
        if 'mode' in theme:
            if theme['mode'] not in ['light', 'dark', 'auto']:
                raise ValidationError(f"Invalid theme mode: {theme['mode']}")
        
        if 'colors' in theme:
            if not isinstance(theme['colors'], dict):
                raise ValidationError("Theme colors must be a dictionary")
            for color_name, color_value in theme['colors'].items():
                if not self.color_pattern.match(color_value):
                    raise ValidationError(f"Invalid color format for {color_name}: {color_value}")
    
    async def _validate_filters(self, filters: List[Dict[str, Any]]):
        """Validate dashboard filters"""
        if not isinstance(filters, list):
            raise ValidationError("Filters must be a list")
        
        for filter_config in filters:
            if 'name' not in filter_config:
                raise ValidationError("Filter must have a name")
            if 'type' not in filter_config:
                raise ValidationError("Filter must have a type")
            if filter_config['type'] not in ['text', 'select', 'date', 'number', 'boolean']:
                raise ValidationError(f"Invalid filter type: {filter_config['type']}")
    
    async def _validate_query(self, query: Dict[str, Any]):
        """Validate widget query configuration"""
        if 'metric' in query:
            if not isinstance(query['metric'], str):
                raise ValidationError("Query metric must be a string")
        
        if 'aggregation' in query:
            if query['aggregation'] not in self.VALID_AGGREGATION_TYPES:
                raise ValidationError(f"Invalid query aggregation: {query['aggregation']}")
        
        if 'time_range' in query:
            if query['time_range'] not in self.VALID_TIME_PERIODS:
                raise ValidationError(f"Invalid query time range: {query['time_range']}")
    
    async def _validate_metadata(self, metadata: Dict[str, Any]):
        """Validate import metadata"""
        if 'exported_at' in metadata:
            if not isinstance(metadata['exported_at'], str):
                raise ValidationError("Exported at must be a string")
        
        if 'exported_by' in metadata:
            if not isinstance(metadata['exported_by'], str):
                raise ValidationError("Exported by must be a string")
    
    async def _validate_search_filters(self, filters: Dict[str, Any]):
        """Validate search filters"""
        if 'name' in filters:
            if not isinstance(filters['name'], str):
                raise ValidationError("Name filter must be a string")
        
        if 'public' in filters:
            if not isinstance(filters['public'], bool):
                raise ValidationError("Public filter must be a boolean")
        
        if 'created_after' in filters:
            if not isinstance(filters['created_after'], str):
                raise ValidationError("Created after filter must be a string")
        
        if 'created_before' in filters:
            if not isinstance(filters['created_before'], str):
                raise ValidationError("Created before filter must be a string")
    
    async def _validate_sort(self, sort: Dict[str, Any]):
        """Validate sort configuration"""
        if 'field' in sort:
            if sort['field'] not in ['name', 'created_at', 'updated_at', 'access_count']:
                raise ValidationError(f"Invalid sort field: {sort['field']}")
        
        if 'direction' in sort:
            if sort['direction'] not in ['asc', 'desc']:
                raise ValidationError(f"Invalid sort direction: {sort['direction']}")
