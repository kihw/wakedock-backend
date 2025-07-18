"""
Dashboard Service - Business logic for dashboard operations
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
import json
import asyncio

from wakedock.controllers.dashboard_controller import DashboardController
from wakedock.repositories.dashboard_repository import DashboardRepository
from wakedock.repositories.analytics_repository import AnalyticsRepository
from wakedock.validators.dashboard_validator import DashboardValidator
from wakedock.core.exceptions import ValidationError, NotFoundError, ServiceError
from wakedock.core.logging import get_logger
from wakedock.core.cache import cache_service
from wakedock.core.websocket import websocket_manager

logger = get_logger(__name__)


class DashboardService:
    """Service for dashboard operations with business logic"""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.controller = DashboardController(db_session)
        self.repository = DashboardRepository(db_session)
        self.analytics_repository = AnalyticsRepository(db_session)
        self.validator = DashboardValidator()
        self.cache_ttl = 300  # 5 minutes
    
    async def process_dashboard_request(self, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process dashboard request with business logic"""
        try:
            if action == 'create':
                return await self._process_create_dashboard(data)
            elif action == 'update':
                return await self._process_update_dashboard(data)
            elif action == 'delete':
                return await self._process_delete_dashboard(data)
            elif action == 'get':
                return await self._process_get_dashboard(data)
            elif action == 'list':
                return await self._process_list_dashboards(data)
            elif action == 'clone':
                return await self._process_clone_dashboard(data)
            elif action == 'export':
                return await self._process_export_dashboard(data)
            elif action == 'import':
                return await self._process_import_dashboard(data)
            else:
                raise ValidationError(f"Unknown dashboard action: {action}")
            
        except Exception as e:
            logger.error(f"Error processing dashboard request: {str(e)}")
            if isinstance(e, (ValidationError, NotFoundError, ServiceError)):
                raise
            raise ServiceError(f"Failed to process dashboard request: {str(e)}")
    
    async def process_widget_request(self, action: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process widget request with business logic"""
        try:
            if action == 'create':
                return await self._process_create_widget(data)
            elif action == 'update':
                return await self._process_update_widget(data)
            elif action == 'delete':
                return await self._process_delete_widget(data)
            elif action == 'bulk_create':
                return await self._process_bulk_create_widgets(data)
            elif action == 'bulk_update':
                return await self._process_bulk_update_widgets(data)
            elif action == 'bulk_delete':
                return await self._process_bulk_delete_widgets(data)
            else:
                raise ValidationError(f"Unknown widget action: {action}")
            
        except Exception as e:
            logger.error(f"Error processing widget request: {str(e)}")
            if isinstance(e, (ValidationError, NotFoundError, ServiceError)):
                raise
            raise ServiceError(f"Failed to process widget request: {str(e)}")
    
    async def start_real_time_updates(self, dashboard_id: str, websocket_id: str) -> bool:
        """Start real-time updates for dashboard"""
        try:
            # Validate dashboard exists
            dashboard = await self.repository.get_dashboard_by_id(dashboard_id)
            if not dashboard:
                raise NotFoundError(f"Dashboard {dashboard_id} not found")
            
            # Start real-time data streaming
            await self._start_dashboard_streaming(dashboard_id, websocket_id)
            
            logger.info(f"Started real-time updates for dashboard {dashboard_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting real-time updates: {str(e)}")
            return False
    
    async def stop_real_time_updates(self, dashboard_id: str, websocket_id: str) -> bool:
        """Stop real-time updates for dashboard"""
        try:
            # Stop real-time data streaming
            await self._stop_dashboard_streaming(dashboard_id, websocket_id)
            
            logger.info(f"Stopped real-time updates for dashboard {dashboard_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping real-time updates: {str(e)}")
            return False
    
    async def optimize_dashboard_performance(self, dashboard_id: str) -> Dict[str, Any]:
        """Optimize dashboard performance"""
        try:
            # Get dashboard data
            dashboard = await self.repository.get_dashboard_by_id(dashboard_id)
            if not dashboard:
                raise NotFoundError(f"Dashboard {dashboard_id} not found")
            
            # Analyze performance
            performance_analysis = await self._analyze_dashboard_performance(dashboard)
            
            # Apply optimizations
            optimizations = await self._apply_dashboard_optimizations(dashboard, performance_analysis)
            
            return {
                'dashboard_id': dashboard_id,
                'performance_analysis': performance_analysis,
                'optimizations_applied': optimizations,
                'timestamp': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error optimizing dashboard: {str(e)}")
            if isinstance(e, NotFoundError):
                raise
            raise ServiceError(f"Failed to optimize dashboard: {str(e)}")
    
    async def generate_dashboard_insights(self, dashboard_id: str, time_range: Dict[str, datetime]) -> Dict[str, Any]:
        """Generate insights for dashboard"""
        try:
            # Get dashboard analytics
            analytics = await self.controller.get_dashboard_analytics(dashboard_id, time_range)
            
            # Generate insights
            insights = await self._generate_dashboard_insights(analytics)
            
            return {
                'dashboard_id': dashboard_id,
                'time_range': time_range,
                'insights': insights,
                'generated_at': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error generating dashboard insights: {str(e)}")
            if isinstance(e, NotFoundError):
                raise
            raise ServiceError(f"Failed to generate dashboard insights: {str(e)}")
    
    async def create_dashboard_template(self, dashboard_id: str, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create dashboard template"""
        try:
            # Export dashboard
            export_data = await self.controller.export_dashboard(dashboard_id)
            
            # Create template
            template = await self._create_dashboard_template(export_data, template_data)
            
            return template
            
        except Exception as e:
            logger.error(f"Error creating dashboard template: {str(e)}")
            if isinstance(e, NotFoundError):
                raise
            raise ServiceError(f"Failed to create dashboard template: {str(e)}")
    
    async def schedule_dashboard_report(self, dashboard_id: str, schedule_config: Dict[str, Any]) -> Dict[str, Any]:
        """Schedule dashboard report"""
        try:
            # Validate schedule configuration
            await self._validate_schedule_config(schedule_config)
            
            # Create scheduled report
            report = await self._create_scheduled_report(dashboard_id, schedule_config)
            
            return report
            
        except Exception as e:
            logger.error(f"Error scheduling dashboard report: {str(e)}")
            if isinstance(e, ValidationError):
                raise
            raise ServiceError(f"Failed to schedule dashboard report: {str(e)}")
    
    async def process_dashboard_alerts(self, dashboard_id: str) -> Dict[str, Any]:
        """Process dashboard alerts"""
        try:
            # Get dashboard alerts
            alerts = await self._get_dashboard_alerts(dashboard_id)
            
            # Process each alert
            processed_alerts = []
            for alert in alerts:
                processed_alert = await self._process_alert(alert)
                processed_alerts.append(processed_alert)
            
            return {
                'dashboard_id': dashboard_id,
                'alerts_processed': len(processed_alerts),
                'alerts': processed_alerts,
                'timestamp': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error processing dashboard alerts: {str(e)}")
            raise ServiceError(f"Failed to process dashboard alerts: {str(e)}")
    
    async def calculate_dashboard_metrics(self, dashboard_id: str) -> Dict[str, Any]:
        """Calculate dashboard metrics"""
        try:
            # Get dashboard data
            dashboard = await self.repository.get_dashboard_by_id(dashboard_id)
            if not dashboard:
                raise NotFoundError(f"Dashboard {dashboard_id} not found")
            
            # Calculate metrics
            metrics = await self._calculate_dashboard_metrics(dashboard)
            
            return {
                'dashboard_id': dashboard_id,
                'metrics': metrics,
                'calculated_at': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error calculating dashboard metrics: {str(e)}")
            if isinstance(e, NotFoundError):
                raise
            raise ServiceError(f"Failed to calculate dashboard metrics: {str(e)}")
    
    async def backup_dashboard(self, dashboard_id: str) -> Dict[str, Any]:
        """Backup dashboard"""
        try:
            # Export dashboard
            export_data = await self.controller.export_dashboard(dashboard_id)
            
            # Create backup
            backup = await self._create_dashboard_backup(export_data)
            
            return backup
            
        except Exception as e:
            logger.error(f"Error backing up dashboard: {str(e)}")
            if isinstance(e, NotFoundError):
                raise
            raise ServiceError(f"Failed to backup dashboard: {str(e)}")
    
    async def restore_dashboard(self, backup_id: str) -> Dict[str, Any]:
        """Restore dashboard from backup"""
        try:
            # Get backup data
            backup_data = await self._get_dashboard_backup(backup_id)
            
            # Restore dashboard
            restored_dashboard = await self.controller.import_dashboard(backup_data['data'])
            
            return restored_dashboard
            
        except Exception as e:
            logger.error(f"Error restoring dashboard: {str(e)}")
            if isinstance(e, NotFoundError):
                raise
            raise ServiceError(f"Failed to restore dashboard: {str(e)}")
    
    # Private methods for dashboard operations
    
    async def _process_create_dashboard(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process create dashboard request"""
        # Validate data
        await self.validator.validate_dashboard_config(data)
        
        # Apply business rules
        data = await self._apply_dashboard_business_rules(data)
        
        # Create dashboard
        dashboard = await self.controller.create_dashboard(data)
        
        # Post-creation processing
        await self._post_dashboard_creation(dashboard)
        
        return dashboard
    
    async def _process_update_dashboard(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process update dashboard request"""
        dashboard_id = data.get('id')
        if not dashboard_id:
            raise ValidationError("Dashboard ID is required for update")
        
        update_data = {k: v for k, v in data.items() if k != 'id'}
        
        # Apply business rules
        update_data = await self._apply_dashboard_business_rules(update_data)
        
        # Update dashboard
        dashboard = await self.controller.update_dashboard(dashboard_id, update_data)
        
        # Post-update processing
        await self._post_dashboard_update(dashboard)
        
        return dashboard
    
    async def _process_delete_dashboard(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process delete dashboard request"""
        dashboard_id = data.get('id')
        if not dashboard_id:
            raise ValidationError("Dashboard ID is required for delete")
        
        # Check dependencies
        await self._check_dashboard_dependencies(dashboard_id)
        
        # Delete dashboard
        success = await self.controller.delete_dashboard(dashboard_id)
        
        # Post-deletion processing
        await self._post_dashboard_deletion(dashboard_id)
        
        return {'success': success, 'dashboard_id': dashboard_id}
    
    async def _process_get_dashboard(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process get dashboard request"""
        dashboard_id = data.get('id')
        if not dashboard_id:
            raise ValidationError("Dashboard ID is required")
        
        time_range = data.get('time_range')
        
        # Get dashboard
        dashboard = await self.controller.get_dashboard(dashboard_id, time_range)
        
        # Apply business logic
        dashboard = await self._enhance_dashboard_response(dashboard)
        
        return dashboard
    
    async def _process_list_dashboards(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process list dashboards request"""
        # Validate search parameters
        await self.validator.validate_search_params(data)
        
        # Get dashboards
        dashboards = await self.controller.get_dashboards(data)
        
        # Apply business logic
        dashboards = await self._enhance_dashboards_response(dashboards)
        
        return dashboards
    
    async def _process_clone_dashboard(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process clone dashboard request"""
        dashboard_id = data.get('id')
        new_name = data.get('new_name')
        
        if not dashboard_id or not new_name:
            raise ValidationError("Dashboard ID and new name are required for cloning")
        
        # Clone dashboard
        dashboard = await self.controller.clone_dashboard(dashboard_id, new_name)
        
        # Post-cloning processing
        await self._post_dashboard_cloning(dashboard)
        
        return dashboard
    
    async def _process_export_dashboard(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process export dashboard request"""
        dashboard_id = data.get('id')
        if not dashboard_id:
            raise ValidationError("Dashboard ID is required for export")
        
        # Export dashboard
        export_data = await self.controller.export_dashboard(dashboard_id)
        
        # Apply business logic
        export_data = await self._enhance_export_data(export_data)
        
        return export_data
    
    async def _process_import_dashboard(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process import dashboard request"""
        import_data = data.get('import_data')
        if not import_data:
            raise ValidationError("Import data is required")
        
        # Validate import data
        await self.validator.validate_dashboard_import(import_data)
        
        new_name = data.get('new_name')
        
        # Import dashboard
        dashboard = await self.controller.import_dashboard(import_data, new_name)
        
        # Post-import processing
        await self._post_dashboard_import(dashboard)
        
        return dashboard
    
    async def _process_create_widget(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process create widget request"""
        # Validate data
        await self.validator.validate_widget_config(data)
        
        # Apply business rules
        data = await self._apply_widget_business_rules(data)
        
        # Create widget
        widget = await self.controller.create_widget(data)
        
        # Post-creation processing
        await self._post_widget_creation(widget)
        
        return widget
    
    async def _process_update_widget(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process update widget request"""
        widget_id = data.get('id')
        if not widget_id:
            raise ValidationError("Widget ID is required for update")
        
        update_data = {k: v for k, v in data.items() if k != 'id'}
        
        # Apply business rules
        update_data = await self._apply_widget_business_rules(update_data)
        
        # Update widget
        widget = await self.controller.update_widget(widget_id, update_data)
        
        # Post-update processing
        await self._post_widget_update(widget)
        
        return widget
    
    async def _process_delete_widget(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process delete widget request"""
        widget_id = data.get('id')
        if not widget_id:
            raise ValidationError("Widget ID is required for delete")
        
        # Delete widget
        success = await self.controller.delete_widget(widget_id)
        
        # Post-deletion processing
        await self._post_widget_deletion(widget_id)
        
        return {'success': success, 'widget_id': widget_id}
    
    async def _process_bulk_create_widgets(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process bulk create widgets request"""
        widgets_data = data.get('widgets', [])
        
        # Validate bulk operation
        await self.validator.validate_bulk_operation('create', widgets_data)
        
        # Create widgets
        results = []
        for widget_data in widgets_data:
            try:
                widget = await self.controller.create_widget(widget_data)
                results.append({'success': True, 'widget': widget})
            except Exception as e:
                results.append({'success': False, 'error': str(e)})
        
        return {'results': results}
    
    async def _process_bulk_update_widgets(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process bulk update widgets request"""
        widgets_data = data.get('widgets', [])
        
        # Validate bulk operation
        await self.validator.validate_bulk_operation('update', widgets_data)
        
        # Update widgets
        results = []
        for widget_data in widgets_data:
            try:
                widget_id = widget_data.pop('id')
                widget = await self.controller.update_widget(widget_id, widget_data)
                results.append({'success': True, 'widget': widget})
            except Exception as e:
                results.append({'success': False, 'error': str(e)})
        
        return {'results': results}
    
    async def _process_bulk_delete_widgets(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process bulk delete widgets request"""
        widgets_data = data.get('widgets', [])
        
        # Validate bulk operation
        await self.validator.validate_bulk_operation('delete', widgets_data)
        
        # Delete widgets
        results = []
        for widget_data in widgets_data:
            try:
                widget_id = widget_data['id']
                success = await self.controller.delete_widget(widget_id)
                results.append({'success': success, 'widget_id': widget_id})
            except Exception as e:
                results.append({'success': False, 'error': str(e)})
        
        return {'results': results}
    
    # Private helper methods
    
    async def _apply_dashboard_business_rules(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply business rules to dashboard data"""
        # Set default values
        if 'refresh_interval' not in data:
            data['refresh_interval'] = 60  # 1 minute default
        
        if 'auto_refresh' not in data:
            data['auto_refresh'] = True
        
        if 'public' not in data:
            data['public'] = False
        
        # Apply naming conventions
        if 'name' in data:
            data['name'] = data['name'].strip()
        
        return data
    
    async def _apply_widget_business_rules(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply business rules to widget data"""
        # Set default values
        if 'refresh_interval' not in data:
            data['refresh_interval'] = 60  # 1 minute default
        
        if 'active' not in data:
            data['active'] = True
        
        # Apply naming conventions
        if 'title' in data:
            data['title'] = data['title'].strip()
        
        return data
    
    async def _start_dashboard_streaming(self, dashboard_id: str, websocket_id: str):
        """Start dashboard streaming"""
        # Implementation would connect to websocket manager
        # and start streaming dashboard updates
        pass
    
    async def _stop_dashboard_streaming(self, dashboard_id: str, websocket_id: str):
        """Stop dashboard streaming"""
        # Implementation would disconnect from websocket manager
        # and stop streaming dashboard updates
        pass
    
    async def _analyze_dashboard_performance(self, dashboard) -> Dict[str, Any]:
        """Analyze dashboard performance"""
        return {
            'widget_count': len(dashboard.widgets),
            'active_widgets': len([w for w in dashboard.widgets if w.active]),
            'slow_widgets': [],  # Would analyze widget performance
            'optimization_opportunities': []
        }
    
    async def _apply_dashboard_optimizations(self, dashboard, analysis: Dict[str, Any]) -> List[str]:
        """Apply dashboard optimizations"""
        optimizations = []
        
        # Example optimizations based on analysis
        if analysis['widget_count'] > 20:
            optimizations.append('Consider splitting dashboard into multiple pages')
        
        return optimizations
    
    async def _generate_dashboard_insights(self, analytics: Dict[str, Any]) -> Dict[str, Any]:
        """Generate dashboard insights"""
        insights = {
            'usage_patterns': {},
            'performance_trends': {},
            'recommendations': []
        }
        
        # Generate insights based on analytics
        # This would analyze the analytics data and provide insights
        
        return insights
    
    async def _create_dashboard_template(self, export_data: Dict[str, Any], template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create dashboard template"""
        return {
            'id': f"template_{datetime.utcnow().isoformat()}",
            'name': template_data.get('name', 'Dashboard Template'),
            'description': template_data.get('description', 'Generated dashboard template'),
            'template_data': export_data,
            'created_at': datetime.utcnow()
        }
    
    async def _validate_schedule_config(self, config: Dict[str, Any]):
        """Validate schedule configuration"""
        if 'frequency' not in config:
            raise ValidationError("Schedule frequency is required")
        
        if config['frequency'] not in ['hourly', 'daily', 'weekly', 'monthly']:
            raise ValidationError("Invalid schedule frequency")
    
    async def _create_scheduled_report(self, dashboard_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create scheduled report"""
        return {
            'id': f"report_{datetime.utcnow().isoformat()}",
            'dashboard_id': dashboard_id,
            'schedule': config,
            'created_at': datetime.utcnow(),
            'next_run': datetime.utcnow() + timedelta(hours=1)  # Example
        }
    
    async def _get_dashboard_alerts(self, dashboard_id: str) -> List[Dict[str, Any]]:
        """Get dashboard alerts"""
        # Implementation would query alert system
        return []
    
    async def _process_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Process single alert"""
        return {
            'alert_id': alert.get('id'),
            'status': 'processed',
            'processed_at': datetime.utcnow()
        }
    
    async def _calculate_dashboard_metrics(self, dashboard) -> Dict[str, Any]:
        """Calculate dashboard metrics"""
        return {
            'total_widgets': len(dashboard.widgets),
            'active_widgets': len([w for w in dashboard.widgets if w.active]),
            'access_count': dashboard.access_count,
            'last_accessed': dashboard.last_accessed
        }
    
    async def _create_dashboard_backup(self, export_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create dashboard backup"""
        return {
            'id': f"backup_{datetime.utcnow().isoformat()}",
            'data': export_data,
            'created_at': datetime.utcnow()
        }
    
    async def _get_dashboard_backup(self, backup_id: str) -> Dict[str, Any]:
        """Get dashboard backup"""
        # Implementation would retrieve backup from storage
        return {
            'id': backup_id,
            'data': {},
            'created_at': datetime.utcnow()
        }
    
    async def _post_dashboard_creation(self, dashboard: Dict[str, Any]):
        """Post-dashboard creation processing"""
        # Send notifications, update cache, etc.
        pass
    
    async def _post_dashboard_update(self, dashboard: Dict[str, Any]):
        """Post-dashboard update processing"""
        # Send notifications, update cache, etc.
        pass
    
    async def _post_dashboard_deletion(self, dashboard_id: str):
        """Post-dashboard deletion processing"""
        # Clean up resources, send notifications, etc.
        pass
    
    async def _post_dashboard_cloning(self, dashboard: Dict[str, Any]):
        """Post-dashboard cloning processing"""
        # Send notifications, update cache, etc.
        pass
    
    async def _post_dashboard_import(self, dashboard: Dict[str, Any]):
        """Post-dashboard import processing"""
        # Send notifications, update cache, etc.
        pass
    
    async def _post_widget_creation(self, widget: Dict[str, Any]):
        """Post-widget creation processing"""
        # Send notifications, update cache, etc.
        pass
    
    async def _post_widget_update(self, widget: Dict[str, Any]):
        """Post-widget update processing"""
        # Send notifications, update cache, etc.
        pass
    
    async def _post_widget_deletion(self, widget_id: str):
        """Post-widget deletion processing"""
        # Clean up resources, send notifications, etc.
        pass
    
    async def _check_dashboard_dependencies(self, dashboard_id: str):
        """Check dashboard dependencies before deletion"""
        # Check if dashboard is used in reports, alerts, etc.
        pass
    
    async def _enhance_dashboard_response(self, dashboard: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance dashboard response with business logic"""
        # Add computed fields, format data, etc.
        return dashboard
    
    async def _enhance_dashboards_response(self, dashboards: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance dashboards response with business logic"""
        # Add computed fields, format data, etc.
        return dashboards
    
    async def _enhance_export_data(self, export_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance export data with business logic"""
        # Add metadata, format data, etc.
        export_data['exported_at'] = datetime.utcnow()
        return export_data
