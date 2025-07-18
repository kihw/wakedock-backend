"""
Dashboard Controller - Business logic for dashboard operations
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from wakedock.repositories.dashboard_repository import DashboardRepository
from wakedock.repositories.analytics_repository import AnalyticsRepository
from wakedock.validators.analytics_validator import AnalyticsValidator
from wakedock.core.exceptions import ValidationError, NotFoundError, ServiceError
from wakedock.core.logging import get_logger
from wakedock.core.cache import cache_service

logger = get_logger(__name__)


class DashboardController:
    """Controller for dashboard operations"""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.repository = DashboardRepository(db_session)
        self.analytics_repository = AnalyticsRepository(db_session)
        self.validator = AnalyticsValidator()
        self.cache_ttl = 300  # 5 minutes
    
    async def create_dashboard(self, dashboard_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new dashboard"""
        try:
            # Validate dashboard configuration
            await self.validator.validate_dashboard_config(dashboard_data)
            
            # Check if dashboard name already exists
            existing_dashboard = await self.repository.get_dashboard_by_name(dashboard_data['name'])
            if existing_dashboard:
                raise ValidationError(f"Dashboard with name '{dashboard_data['name']}' already exists")
            
            # Create dashboard
            dashboard = await self.repository.create_dashboard(dashboard_data)
            
            # Create widgets if provided
            if 'widgets' in dashboard_data:
                for widget_data in dashboard_data['widgets']:
                    widget_data['dashboard_id'] = dashboard.id
                    await self.repository.create_widget(widget_data)
            
            # Get complete dashboard data
            dashboard_data = await self.repository.get_dashboard_data(dashboard.id)
            
            # Clear cache
            await self._clear_dashboard_cache()
            
            logger.info(f"Created dashboard: {dashboard.name}")
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Error creating dashboard: {str(e)}")
            if isinstance(e, (ValidationError, ServiceError)):
                raise
            raise ServiceError(f"Failed to create dashboard: {str(e)}")
    
    async def get_dashboard(self, dashboard_id: str, time_range: Dict[str, datetime] = None) -> Dict[str, Any]:
        """Get dashboard with data"""
        try:
            # Check cache first
            cache_key = f"dashboard:{dashboard_id}"
            if time_range:
                cache_key += f":{time_range['start'].isoformat()}:{time_range['end'].isoformat()}"
            
            cached_result = await cache_service.get(cache_key)
            if cached_result:
                return cached_result
            
            # Get dashboard data
            dashboard_data = await self.repository.get_dashboard_data(dashboard_id, time_range)
            
            # Update access tracking
            await self.repository.update_dashboard_access(dashboard_id)
            
            # Enhance with analytics
            enhanced_data = await self._enhance_dashboard_data(dashboard_data)
            
            # Cache result
            await cache_service.set(cache_key, enhanced_data, self.cache_ttl)
            
            return enhanced_data
            
        except Exception as e:
            logger.error(f"Error getting dashboard: {str(e)}")
            if isinstance(e, NotFoundError):
                raise
            raise ServiceError(f"Failed to get dashboard: {str(e)}")
    
    async def get_dashboards(self, search_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get dashboards with filtering and pagination"""
        try:
            # Get dashboards from repository
            dashboards_data = await self.repository.get_dashboards(
                filters=search_params,
                page=search_params.get('page', 1),
                per_page=search_params.get('per_page', 20)
            )
            
            # Enhance dashboard list with summary data
            enhanced_dashboards = []
            for dashboard in dashboards_data['dashboards']:
                enhanced_dashboard = await self._enhance_dashboard_summary(dashboard)
                enhanced_dashboards.append(enhanced_dashboard)
            
            return {
                'dashboards': enhanced_dashboards,
                'total_count': dashboards_data['total_count'],
                'page': dashboards_data['page'],
                'per_page': dashboards_data['per_page'],
                'total_pages': dashboards_data['total_pages']
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboards: {str(e)}")
            raise ServiceError(f"Failed to get dashboards: {str(e)}")
    
    async def update_dashboard(self, dashboard_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update dashboard"""
        try:
            # Validate update data
            if 'name' in update_data:
                # Check if new name already exists
                existing_dashboard = await self.repository.get_dashboard_by_name(update_data['name'])
                if existing_dashboard and existing_dashboard.id != dashboard_id:
                    raise ValidationError(f"Dashboard with name '{update_data['name']}' already exists")
            
            # Update dashboard
            dashboard = await self.repository.update_dashboard(dashboard_id, update_data)
            
            # Update widgets if provided
            if 'widgets' in update_data:
                await self.repository.bulk_update_widgets(dashboard_id, update_data['widgets'])
            
            # Get updated dashboard data
            dashboard_data = await self.repository.get_dashboard_data(dashboard_id)
            
            # Clear cache
            await self._clear_dashboard_cache(dashboard_id)
            
            logger.info(f"Updated dashboard: {dashboard_id}")
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Error updating dashboard: {str(e)}")
            if isinstance(e, (ValidationError, NotFoundError)):
                raise
            raise ServiceError(f"Failed to update dashboard: {str(e)}")
    
    async def delete_dashboard(self, dashboard_id: str) -> bool:
        """Delete dashboard"""
        try:
            # Delete dashboard
            success = await self.repository.delete_dashboard(dashboard_id)
            
            # Clear cache
            await self._clear_dashboard_cache(dashboard_id)
            
            logger.info(f"Deleted dashboard: {dashboard_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error deleting dashboard: {str(e)}")
            if isinstance(e, NotFoundError):
                raise
            raise ServiceError(f"Failed to delete dashboard: {str(e)}")
    
    async def clone_dashboard(self, dashboard_id: str, new_name: str) -> Dict[str, Any]:
        """Clone dashboard"""
        try:
            # Check if new name already exists
            existing_dashboard = await self.repository.get_dashboard_by_name(new_name)
            if existing_dashboard:
                raise ValidationError(f"Dashboard with name '{new_name}' already exists")
            
            # Clone dashboard
            cloned_dashboard = await self.repository.clone_dashboard(dashboard_id, new_name)
            
            # Get complete dashboard data
            dashboard_data = await self.repository.get_dashboard_data(cloned_dashboard.id)
            
            # Clear cache
            await self._clear_dashboard_cache()
            
            logger.info(f"Cloned dashboard {dashboard_id} to {cloned_dashboard.id}")
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Error cloning dashboard: {str(e)}")
            if isinstance(e, (ValidationError, NotFoundError)):
                raise
            raise ServiceError(f"Failed to clone dashboard: {str(e)}")
    
    async def create_widget(self, widget_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new widget"""
        try:
            # Validate widget configuration
            await self.validator.validate_widget_config(widget_data)
            
            # Validate metric exists if specified
            if widget_data.get('metric_id'):
                metric = await self.analytics_repository.get_metric_by_id(widget_data['metric_id'])
                if not metric:
                    raise ValidationError(f"Metric {widget_data['metric_id']} not found")
            
            # Create widget
            widget = await self.repository.create_widget(widget_data)
            
            # Clear dashboard cache
            await self._clear_dashboard_cache(widget_data['dashboard_id'])
            
            logger.info(f"Created widget: {widget.title}")
            return {
                'widget_id': widget.id,
                'dashboard_id': widget.dashboard_id,
                'title': widget.title,
                'type': widget.type,
                'config': widget.config,
                'position': widget.position,
                'size': widget.size,
                'metric_id': widget.metric_id,
                'created_at': widget.created_at
            }
            
        except Exception as e:
            logger.error(f"Error creating widget: {str(e)}")
            if isinstance(e, ValidationError):
                raise
            raise ServiceError(f"Failed to create widget: {str(e)}")
    
    async def update_widget(self, widget_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update widget"""
        try:
            # Validate widget configuration if provided
            if any(key in update_data for key in ['type', 'metric_id', 'config']):
                await self.validator.validate_widget_config(update_data)
            
            # Validate metric exists if specified
            if update_data.get('metric_id'):
                metric = await self.analytics_repository.get_metric_by_id(update_data['metric_id'])
                if not metric:
                    raise ValidationError(f"Metric {update_data['metric_id']} not found")
            
            # Update widget
            widget = await self.repository.update_widget(widget_id, update_data)
            
            # Clear dashboard cache
            await self._clear_dashboard_cache(widget.dashboard_id)
            
            logger.info(f"Updated widget: {widget_id}")
            return {
                'widget_id': widget.id,
                'dashboard_id': widget.dashboard_id,
                'title': widget.title,
                'type': widget.type,
                'config': widget.config,
                'position': widget.position,
                'size': widget.size,
                'metric_id': widget.metric_id,
                'updated_at': widget.updated_at
            }
            
        except Exception as e:
            logger.error(f"Error updating widget: {str(e)}")
            if isinstance(e, (ValidationError, NotFoundError)):
                raise
            raise ServiceError(f"Failed to update widget: {str(e)}")
    
    async def delete_widget(self, widget_id: str) -> bool:
        """Delete widget"""
        try:
            # Get widget to find dashboard_id
            widget = await self.repository.get_widget_by_id(widget_id)
            if not widget:
                raise NotFoundError(f"Widget {widget_id} not found")
            
            dashboard_id = widget.dashboard_id
            
            # Delete widget
            success = await self.repository.delete_widget(widget_id)
            
            # Clear dashboard cache
            await self._clear_dashboard_cache(dashboard_id)
            
            logger.info(f"Deleted widget: {widget_id}")
            return success
            
        except Exception as e:
            logger.error(f"Error deleting widget: {str(e)}")
            if isinstance(e, NotFoundError):
                raise
            raise ServiceError(f"Failed to delete widget: {str(e)}")
    
    async def get_dashboard_real_time_data(self, dashboard_id: str) -> Dict[str, Any]:
        """Get real-time data for dashboard"""
        try:
            # Get dashboard
            dashboard = await self.repository.get_dashboard_by_id(dashboard_id)
            if not dashboard:
                raise NotFoundError(f"Dashboard {dashboard_id} not found")
            
            # Get widgets
            widgets = await self.repository.get_widgets_by_dashboard(dashboard_id)
            
            # Get real-time data for each widget
            real_time_data = []
            for widget in widgets:
                if not widget.active or not widget.metric_id:
                    continue
                
                # Get latest metric value
                latest_data = await self.analytics_repository.get_metric_data(
                    widget.metric_id,
                    datetime.utcnow() - timedelta(minutes=5),
                    datetime.utcnow(),
                    limit=1
                )
                
                widget_data = {
                    'widget_id': widget.id,
                    'title': widget.title,
                    'type': widget.type,
                    'latest_value': latest_data[-1].value if latest_data else None,
                    'latest_timestamp': latest_data[-1].timestamp if latest_data else None,
                    'status': 'active' if latest_data else 'no_data'
                }
                
                real_time_data.append(widget_data)
            
            return {
                'dashboard_id': dashboard_id,
                'widgets': real_time_data,
                'timestamp': datetime.utcnow(),
                'refresh_interval': dashboard.refresh_interval
            }
            
        except Exception as e:
            logger.error(f"Error getting real-time data: {str(e)}")
            if isinstance(e, NotFoundError):
                raise
            raise ServiceError(f"Failed to get real-time data: {str(e)}")
    
    async def get_dashboard_analytics(self, dashboard_id: str, time_range: Dict[str, datetime]) -> Dict[str, Any]:
        """Get analytics for dashboard usage"""
        try:
            dashboard = await self.repository.get_dashboard_by_id(dashboard_id)
            if not dashboard:
                raise NotFoundError(f"Dashboard {dashboard_id} not found")
            
            # Get dashboard metrics
            metrics = await self.repository.get_dashboard_metrics(dashboard_id)
            
            # Get analytics for each metric
            metrics_analytics = []
            for metric_info in metrics:
                metric = metric_info['metric']
                
                # Get metric statistics
                stats = await self.analytics_repository.get_metric_statistics(
                    metric.id,
                    time_range['start'],
                    time_range['end']
                )
                
                # Get metric trends
                trends = await self.analytics_repository.get_metric_trends(
                    metric.id,
                    (time_range['end'] - time_range['start']).days
                )
                
                metrics_analytics.append({
                    'metric_id': metric.id,
                    'metric_name': metric.name,
                    'widget_title': metric_info['widget_title'],
                    'statistics': stats,
                    'trends': trends
                })
            
            return {
                'dashboard_id': dashboard_id,
                'dashboard_name': dashboard.name,
                'time_range': time_range,
                'metrics_analytics': metrics_analytics,
                'dashboard_stats': {
                    'total_widgets': len(dashboard.widgets),
                    'active_widgets': len([w for w in dashboard.widgets if w.active]),
                    'total_metrics': len(metrics),
                    'access_count': dashboard.access_count,
                    'last_accessed': dashboard.last_accessed
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard analytics: {str(e)}")
            if isinstance(e, NotFoundError):
                raise
            raise ServiceError(f"Failed to get dashboard analytics: {str(e)}")
    
    async def export_dashboard(self, dashboard_id: str) -> Dict[str, Any]:
        """Export dashboard configuration"""
        try:
            export_data = await self.repository.export_dashboard(dashboard_id)
            
            logger.info(f"Exported dashboard: {dashboard_id}")
            return export_data
            
        except Exception as e:
            logger.error(f"Error exporting dashboard: {str(e)}")
            if isinstance(e, NotFoundError):
                raise
            raise ServiceError(f"Failed to export dashboard: {str(e)}")
    
    async def import_dashboard(self, import_data: Dict[str, Any], new_name: str = None) -> Dict[str, Any]:
        """Import dashboard from configuration"""
        try:
            # Validate import data structure
            if 'dashboard' not in import_data:
                raise ValidationError("Invalid import data: missing dashboard configuration")
            
            # Check if name already exists
            dashboard_name = new_name or import_data['dashboard']['name']
            existing_dashboard = await self.repository.get_dashboard_by_name(dashboard_name)
            if existing_dashboard:
                raise ValidationError(f"Dashboard with name '{dashboard_name}' already exists")
            
            # Import dashboard
            dashboard = await self.repository.import_dashboard(import_data, new_name)
            
            # Get complete dashboard data
            dashboard_data = await self.repository.get_dashboard_data(dashboard.id)
            
            # Clear cache
            await self._clear_dashboard_cache()
            
            logger.info(f"Imported dashboard: {dashboard.name}")
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Error importing dashboard: {str(e)}")
            if isinstance(e, ValidationError):
                raise
            raise ServiceError(f"Failed to import dashboard: {str(e)}")
    
    async def get_dashboard_templates(self) -> List[Dict[str, Any]]:
        """Get dashboard templates"""
        try:
            # Get popular dashboards as templates
            popular_dashboards = await self.repository.get_popular_dashboards(5)
            
            templates = []
            for dashboard in popular_dashboards:
                export_data = await self.repository.export_dashboard(dashboard.id)
                template = {
                    'id': dashboard.id,
                    'name': dashboard.name,
                    'description': dashboard.description,
                    'access_count': dashboard.access_count,
                    'widget_count': len(dashboard.widgets),
                    'template_data': export_data
                }
                templates.append(template)
            
            return templates
            
        except Exception as e:
            logger.error(f"Error getting dashboard templates: {str(e)}")
            raise ServiceError(f"Failed to get dashboard templates: {str(e)}")
    
    async def get_dashboard_statistics(self) -> Dict[str, Any]:
        """Get dashboard statistics"""
        try:
            # Get basic statistics
            stats = await self.repository.get_dashboard_statistics()
            
            # Get popular dashboards
            popular_dashboards = await self.repository.get_popular_dashboards(5)
            
            # Get recent dashboards
            recent_dashboards = await self.repository.get_recent_dashboards(5)
            
            return {
                'overview': stats,
                'popular_dashboards': [
                    {
                        'id': d.id,
                        'name': d.name,
                        'access_count': d.access_count,
                        'widget_count': len(d.widgets)
                    }
                    for d in popular_dashboards
                ],
                'recent_dashboards': [
                    {
                        'id': d.id,
                        'name': d.name,
                        'created_at': d.created_at,
                        'widget_count': len(d.widgets)
                    }
                    for d in recent_dashboards
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard statistics: {str(e)}")
            raise ServiceError(f"Failed to get dashboard statistics: {str(e)}")
    
    async def search_dashboards(self, query: str) -> List[Dict[str, Any]]:
        """Search dashboards"""
        try:
            # Search dashboards
            dashboards = await self.repository.search_dashboards(query)
            
            # Format results
            results = []
            for dashboard in dashboards:
                results.append({
                    'id': dashboard.id,
                    'name': dashboard.name,
                    'description': dashboard.description,
                    'widget_count': len(dashboard.widgets),
                    'access_count': dashboard.access_count,
                    'created_at': dashboard.created_at,
                    'last_accessed': dashboard.last_accessed
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching dashboards: {str(e)}")
            raise ServiceError(f"Failed to search dashboards: {str(e)}")
    
    # Private helper methods
    
    async def _enhance_dashboard_data(self, dashboard_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance dashboard data with additional insights"""
        enhanced_data = dashboard_data.copy()
        
        # Add performance metrics
        enhanced_data['performance'] = {
            'load_time': 0.5,  # Simulated
            'data_freshness': 'recent',
            'widget_health': await self._calculate_widget_health(dashboard_data['widgets'])
        }
        
        # Add usage insights
        enhanced_data['insights'] = {
            'most_viewed_widgets': await self._get_most_viewed_widgets(dashboard_data['widgets']),
            'data_coverage': await self._calculate_data_coverage(dashboard_data['widgets']),
            'recommendations': await self._generate_dashboard_recommendations(dashboard_data)
        }
        
        return enhanced_data
    
    async def _enhance_dashboard_summary(self, dashboard) -> Dict[str, Any]:
        """Enhance dashboard summary with additional info"""
        return {
            'id': dashboard.id,
            'name': dashboard.name,
            'description': dashboard.description,
            'widget_count': len(dashboard.widgets),
            'active_widgets': len([w for w in dashboard.widgets if w.active]),
            'access_count': dashboard.access_count,
            'last_accessed': dashboard.last_accessed,
            'created_at': dashboard.created_at,
            'updated_at': dashboard.updated_at,
            'public': dashboard.public,
            'refresh_interval': dashboard.refresh_interval
        }
    
    async def _calculate_widget_health(self, widgets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate widget health score"""
        if not widgets:
            return {'score': 0, 'status': 'no_widgets'}
        
        healthy_widgets = 0
        for widget in widgets:
            if widget.get('data') and widget.get('metric_info'):
                healthy_widgets += 1
        
        health_score = (healthy_widgets / len(widgets)) * 100
        
        if health_score >= 80:
            status = 'healthy'
        elif health_score >= 60:
            status = 'degraded'
        else:
            status = 'unhealthy'
        
        return {
            'score': health_score,
            'status': status,
            'healthy_widgets': healthy_widgets,
            'total_widgets': len(widgets)
        }
    
    async def _get_most_viewed_widgets(self, widgets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Get most viewed widgets (simulated for now)"""
        return [
            {
                'widget_id': widget['widget_id'],
                'title': widget['title'],
                'views': 100  # Simulated
            }
            for widget in widgets[:3]  # Top 3
        ]
    
    async def _calculate_data_coverage(self, widgets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate data coverage for widgets"""
        if not widgets:
            return {'coverage': 0, 'status': 'no_data'}
        
        widgets_with_data = len([w for w in widgets if w.get('data')])
        coverage = (widgets_with_data / len(widgets)) * 100
        
        return {
            'coverage': coverage,
            'widgets_with_data': widgets_with_data,
            'total_widgets': len(widgets)
        }
    
    async def _generate_dashboard_recommendations(self, dashboard_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate dashboard recommendations"""
        recommendations = []
        
        # Check for widgets without data
        widgets_without_data = [w for w in dashboard_data['widgets'] if not w.get('data')]
        if widgets_without_data:
            recommendations.append({
                'type': 'data_missing',
                'message': f"{len(widgets_without_data)} widgets have no data",
                'action': 'Check metric configurations'
            })
        
        # Check for outdated refresh intervals
        slow_widgets = [w for w in dashboard_data['widgets'] if w.get('refresh_interval', 300) > 600]
        if slow_widgets:
            recommendations.append({
                'type': 'performance',
                'message': f"{len(slow_widgets)} widgets have slow refresh intervals",
                'action': 'Consider reducing refresh intervals'
            })
        
        return recommendations
    
    async def _clear_dashboard_cache(self, dashboard_id: str = None):
        """Clear dashboard cache"""
        if dashboard_id:
            await cache_service.delete_pattern(f"dashboard:{dashboard_id}:*")
        else:
            await cache_service.delete_pattern("dashboard:*")
