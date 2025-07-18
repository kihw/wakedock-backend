"""
Dashboard Repository - Data access layer for dashboard operations
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, asc, update, delete
from sqlalchemy.orm import joinedload, selectinload
from datetime import datetime, timedelta
from uuid import uuid4

from wakedock.models.analytics_models import Dashboard, Widget, Metric, MetricData
from wakedock.core.exceptions import DatabaseError, NotFoundError

import logging
logger = logging.getLogger(__name__)


class DashboardRepository:
    """Repository for dashboard data access"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_dashboard(self, dashboard_data: Dict[str, Any]) -> Dashboard:
        """Create a new dashboard"""
        try:
            dashboard = Dashboard(
                id=dashboard_data.get('id', str(uuid4())),
                name=dashboard_data['name'],
                description=dashboard_data.get('description', ''),
                config=dashboard_data.get('config', {}),
                layout=dashboard_data.get('layout', {}),
                filters=dashboard_data.get('filters', {}),
                refresh_interval=dashboard_data.get('refresh_interval', 300),
                public=dashboard_data.get('public', False),
                active=dashboard_data.get('active', True),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            self.session.add(dashboard)
            await self.session.commit()
            await self.session.refresh(dashboard)
            
            logger.info(f"Created dashboard: {dashboard.name}")
            return dashboard
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating dashboard: {str(e)}")
            raise DatabaseError(f"Failed to create dashboard: {str(e)}")
    
    async def get_dashboard_by_id(self, dashboard_id: str) -> Optional[Dashboard]:
        """Get dashboard by ID with widgets"""
        try:
            query = (
                select(Dashboard)
                .options(selectinload(Dashboard.widgets))
                .where(Dashboard.id == dashboard_id)
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error getting dashboard by ID: {str(e)}")
            raise DatabaseError(f"Failed to get dashboard: {str(e)}")
    
    async def get_dashboard_by_name(self, name: str) -> Optional[Dashboard]:
        """Get dashboard by name"""
        try:
            query = select(Dashboard).where(Dashboard.name == name)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error getting dashboard by name: {str(e)}")
            raise DatabaseError(f"Failed to get dashboard: {str(e)}")
    
    async def get_dashboards(self, filters: Dict[str, Any] = None, 
                           page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """Get dashboards with filtering and pagination"""
        try:
            query = select(Dashboard).options(selectinload(Dashboard.widgets))
            
            # Apply filters
            if filters:
                if 'search' in filters and filters['search']:
                    search_term = filters['search']
                    query = query.where(or_(
                        Dashboard.name.ilike(f"%{search_term}%"),
                        Dashboard.description.ilike(f"%{search_term}%")
                    ))
                
                if 'public' in filters and filters['public'] is not None:
                    query = query.where(Dashboard.public == filters['public'])
                
                if 'active' in filters and filters['active'] is not None:
                    query = query.where(Dashboard.active == filters['active'])
            
            # Get total count
            count_query = select(func.count(Dashboard.id))
            if filters:
                if 'search' in filters and filters['search']:
                    search_term = filters['search']
                    count_query = count_query.where(or_(
                        Dashboard.name.ilike(f"%{search_term}%"),
                        Dashboard.description.ilike(f"%{search_term}%")
                    ))
                
                if 'public' in filters and filters['public'] is not None:
                    count_query = count_query.where(Dashboard.public == filters['public'])
                
                if 'active' in filters and filters['active'] is not None:
                    count_query = count_query.where(Dashboard.active == filters['active'])
            
            total_count_result = await self.session.execute(count_query)
            total_count = total_count_result.scalar()
            
            # Apply pagination
            offset = (page - 1) * per_page
            query = query.order_by(desc(Dashboard.created_at)).offset(offset).limit(per_page)
            
            result = await self.session.execute(query)
            dashboards = result.scalars().all()
            
            return {
                'dashboards': dashboards,
                'total_count': total_count,
                'page': page,
                'per_page': per_page,
                'total_pages': (total_count + per_page - 1) // per_page
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboards: {str(e)}")
            raise DatabaseError(f"Failed to get dashboards: {str(e)}")
    
    async def update_dashboard(self, dashboard_id: str, update_data: Dict[str, Any]) -> Dashboard:
        """Update dashboard"""
        try:
            dashboard = await self.get_dashboard_by_id(dashboard_id)
            if not dashboard:
                raise NotFoundError(f"Dashboard {dashboard_id} not found")
            
            # Update fields
            for field, value in update_data.items():
                if hasattr(dashboard, field):
                    setattr(dashboard, field, value)
            
            dashboard.updated_at = datetime.utcnow()
            
            await self.session.commit()
            await self.session.refresh(dashboard)
            
            logger.info(f"Updated dashboard: {dashboard_id}")
            return dashboard
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating dashboard: {str(e)}")
            raise DatabaseError(f"Failed to update dashboard: {str(e)}")
    
    async def delete_dashboard(self, dashboard_id: str) -> bool:
        """Delete dashboard"""
        try:
            dashboard = await self.get_dashboard_by_id(dashboard_id)
            if not dashboard:
                raise NotFoundError(f"Dashboard {dashboard_id} not found")
            
            await self.session.delete(dashboard)
            await self.session.commit()
            
            logger.info(f"Deleted dashboard: {dashboard_id}")
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting dashboard: {str(e)}")
            raise DatabaseError(f"Failed to delete dashboard: {str(e)}")
    
    async def create_widget(self, widget_data: Dict[str, Any]) -> Widget:
        """Create a new widget"""
        try:
            widget = Widget(
                id=widget_data.get('id', str(uuid4())),
                dashboard_id=widget_data['dashboard_id'],
                title=widget_data.get('title', ''),
                type=widget_data['type'],
                config=widget_data.get('config', {}),
                position=widget_data.get('position', {}),
                size=widget_data.get('size', {}),
                metric_id=widget_data.get('metric_id'),
                query=widget_data.get('query', ''),
                refresh_interval=widget_data.get('refresh_interval', 300),
                active=widget_data.get('active', True),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            self.session.add(widget)
            await self.session.commit()
            await self.session.refresh(widget)
            
            logger.info(f"Created widget: {widget.title}")
            return widget
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating widget: {str(e)}")
            raise DatabaseError(f"Failed to create widget: {str(e)}")
    
    async def get_widget_by_id(self, widget_id: str) -> Optional[Widget]:
        """Get widget by ID"""
        try:
            query = (
                select(Widget)
                .options(joinedload(Widget.metric))
                .where(Widget.id == widget_id)
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error getting widget by ID: {str(e)}")
            raise DatabaseError(f"Failed to get widget: {str(e)}")
    
    async def get_widgets_by_dashboard(self, dashboard_id: str) -> List[Widget]:
        """Get all widgets for a dashboard"""
        try:
            query = (
                select(Widget)
                .options(joinedload(Widget.metric))
                .where(Widget.dashboard_id == dashboard_id)
                .order_by(Widget.created_at)
            )
            result = await self.session.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting widgets by dashboard: {str(e)}")
            raise DatabaseError(f"Failed to get widgets: {str(e)}")
    
    async def update_widget(self, widget_id: str, update_data: Dict[str, Any]) -> Widget:
        """Update widget"""
        try:
            widget = await self.get_widget_by_id(widget_id)
            if not widget:
                raise NotFoundError(f"Widget {widget_id} not found")
            
            # Update fields
            for field, value in update_data.items():
                if hasattr(widget, field):
                    setattr(widget, field, value)
            
            widget.updated_at = datetime.utcnow()
            
            await self.session.commit()
            await self.session.refresh(widget)
            
            logger.info(f"Updated widget: {widget_id}")
            return widget
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating widget: {str(e)}")
            raise DatabaseError(f"Failed to update widget: {str(e)}")
    
    async def delete_widget(self, widget_id: str) -> bool:
        """Delete widget"""
        try:
            widget = await self.get_widget_by_id(widget_id)
            if not widget:
                raise NotFoundError(f"Widget {widget_id} not found")
            
            await self.session.delete(widget)
            await self.session.commit()
            
            logger.info(f"Deleted widget: {widget_id}")
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting widget: {str(e)}")
            raise DatabaseError(f"Failed to delete widget: {str(e)}")
    
    async def get_dashboard_metrics(self, dashboard_id: str) -> List[Dict[str, Any]]:
        """Get all metrics used in a dashboard"""
        try:
            query = (
                select(Metric, Widget.title.label('widget_title'))
                .select_from(Widget)
                .join(Metric, Widget.metric_id == Metric.id)
                .where(Widget.dashboard_id == dashboard_id)
                .where(Widget.active == True)
            )
            
            result = await self.session.execute(query)
            
            metrics = []
            for row in result.fetchall():
                metrics.append({
                    'metric': row.Metric,
                    'widget_title': row.widget_title
                })
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error getting dashboard metrics: {str(e)}")
            raise DatabaseError(f"Failed to get dashboard metrics: {str(e)}")
    
    async def get_dashboard_data(self, dashboard_id: str, time_range: Dict[str, datetime] = None) -> Dict[str, Any]:
        """Get dashboard data with widget values"""
        try:
            dashboard = await self.get_dashboard_by_id(dashboard_id)
            if not dashboard:
                raise NotFoundError(f"Dashboard {dashboard_id} not found")
            
            # Get all widgets with their metrics
            widgets = await self.get_widgets_by_dashboard(dashboard_id)
            
            # Get data for each widget
            widget_data = []
            for widget in widgets:
                if not widget.active:
                    continue
                
                widget_info = {
                    'widget_id': widget.id,
                    'title': widget.title,
                    'type': widget.type,
                    'config': widget.config,
                    'position': widget.position,
                    'size': widget.size,
                    'data': None,
                    'metric_info': None
                }
                
                # Get metric data if widget has a metric
                if widget.metric_id and widget.metric:
                    widget_info['metric_info'] = {
                        'metric_id': widget.metric.id,
                        'name': widget.metric.name,
                        'type': widget.metric.type,
                        'unit': widget.metric.unit,
                        'description': widget.metric.description
                    }
                    
                    # Get latest metric value or time range data
                    if time_range:
                        # Get time series data
                        from wakedock.repositories.analytics_repository import AnalyticsRepository
                        analytics_repo = AnalyticsRepository(self.session)
                        metric_data = await analytics_repo.get_metric_data(
                            widget.metric_id,
                            time_range.get('start', datetime.utcnow() - timedelta(hours=24)),
                            time_range.get('end', datetime.utcnow())
                        )
                        widget_info['data'] = [
                            {
                                'timestamp': point.timestamp,
                                'value': point.value,
                                'labels': point.labels
                            }
                            for point in metric_data
                        ]
                    else:
                        # Get latest value
                        latest_query = (
                            select(func.max(MetricData.timestamp), MetricData.value)
                            .select_from(MetricData)
                            .where(MetricData.metric_id == widget.metric_id)
                            .group_by(MetricData.value)
                            .order_by(desc(func.max(MetricData.timestamp)))
                            .limit(1)
                        )
                        latest_result = await self.session.execute(latest_query)
                        latest_row = latest_result.fetchone()
                        
                        if latest_row:
                            widget_info['data'] = {
                                'timestamp': latest_row[0],
                                'value': latest_row[1],
                                'type': 'latest'
                            }
                
                widget_data.append(widget_info)
            
            return {
                'dashboard': {
                    'id': dashboard.id,
                    'name': dashboard.name,
                    'description': dashboard.description,
                    'config': dashboard.config,
                    'layout': dashboard.layout,
                    'filters': dashboard.filters,
                    'refresh_interval': dashboard.refresh_interval,
                    'public': dashboard.public,
                    'created_at': dashboard.created_at,
                    'updated_at': dashboard.updated_at,
                    'last_accessed': dashboard.last_accessed,
                    'access_count': dashboard.access_count
                },
                'widgets': widget_data,
                'metadata': {
                    'total_widgets': len(widget_data),
                    'active_widgets': len([w for w in widgets if w.active]),
                    'generated_at': datetime.utcnow()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard data: {str(e)}")
            raise DatabaseError(f"Failed to get dashboard data: {str(e)}")
    
    async def update_dashboard_access(self, dashboard_id: str) -> bool:
        """Update dashboard access tracking"""
        try:
            query = (
                update(Dashboard)
                .where(Dashboard.id == dashboard_id)
                .values(
                    access_count=Dashboard.access_count + 1,
                    last_accessed=datetime.utcnow()
                )
            )
            await self.session.execute(query)
            await self.session.commit()
            
            return True
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating dashboard access: {str(e)}")
            return False
    
    async def clone_dashboard(self, dashboard_id: str, new_name: str) -> Dashboard:
        """Clone a dashboard with all its widgets"""
        try:
            original = await self.get_dashboard_by_id(dashboard_id)
            if not original:
                raise NotFoundError(f"Dashboard {dashboard_id} not found")
            
            # Create new dashboard
            new_dashboard = Dashboard(
                id=str(uuid4()),
                name=new_name,
                description=f"Clone of {original.name}",
                config=original.config.copy(),
                layout=original.layout.copy(),
                filters=original.filters.copy(),
                refresh_interval=original.refresh_interval,
                public=False,  # Clones are private by default
                active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            self.session.add(new_dashboard)
            await self.session.flush()  # Get the ID
            
            # Clone all widgets
            for widget in original.widgets:
                new_widget = Widget(
                    id=str(uuid4()),
                    dashboard_id=new_dashboard.id,
                    title=widget.title,
                    type=widget.type,
                    config=widget.config.copy(),
                    position=widget.position.copy(),
                    size=widget.size.copy(),
                    metric_id=widget.metric_id,
                    query=widget.query,
                    refresh_interval=widget.refresh_interval,
                    active=widget.active,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                self.session.add(new_widget)
            
            await self.session.commit()
            await self.session.refresh(new_dashboard)
            
            logger.info(f"Cloned dashboard {dashboard_id} to {new_dashboard.id}")
            return new_dashboard
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error cloning dashboard: {str(e)}")
            raise DatabaseError(f"Failed to clone dashboard: {str(e)}")
    
    async def get_dashboard_statistics(self) -> Dict[str, Any]:
        """Get dashboard statistics"""
        try:
            # Total dashboards
            total_dashboards_query = select(func.count(Dashboard.id))
            total_dashboards_result = await self.session.execute(total_dashboards_query)
            total_dashboards = total_dashboards_result.scalar()
            
            # Active dashboards
            active_dashboards_query = select(func.count(Dashboard.id)).where(Dashboard.active == True)
            active_dashboards_result = await self.session.execute(active_dashboards_query)
            active_dashboards = active_dashboards_result.scalar()
            
            # Public dashboards
            public_dashboards_query = select(func.count(Dashboard.id)).where(Dashboard.public == True)
            public_dashboards_result = await self.session.execute(public_dashboards_query)
            public_dashboards = public_dashboards_result.scalar()
            
            # Total widgets
            total_widgets_query = select(func.count(Widget.id))
            total_widgets_result = await self.session.execute(total_widgets_query)
            total_widgets = total_widgets_result.scalar()
            
            # Widgets by type
            widgets_by_type_query = select(
                Widget.type,
                func.count(Widget.id).label('count')
            ).group_by(Widget.type)
            widgets_by_type_result = await self.session.execute(widgets_by_type_query)
            widgets_by_type = {row.type: row.count for row in widgets_by_type_result.fetchall()}
            
            # Most accessed dashboards
            most_accessed_query = (
                select(Dashboard.name, Dashboard.access_count)
                .where(Dashboard.access_count > 0)
                .order_by(desc(Dashboard.access_count))
                .limit(10)
            )
            most_accessed_result = await self.session.execute(most_accessed_query)
            most_accessed = [
                {'name': row.name, 'access_count': row.access_count}
                for row in most_accessed_result.fetchall()
            ]
            
            return {
                'total_dashboards': total_dashboards,
                'active_dashboards': active_dashboards,
                'public_dashboards': public_dashboards,
                'total_widgets': total_widgets,
                'widgets_by_type': widgets_by_type,
                'most_accessed_dashboards': most_accessed,
                'average_widgets_per_dashboard': total_widgets / total_dashboards if total_dashboards > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting dashboard statistics: {str(e)}")
            raise DatabaseError(f"Failed to get dashboard statistics: {str(e)}")
    
    async def search_dashboards(self, query: str, limit: int = 50) -> List[Dashboard]:
        """Search dashboards by name or description"""
        try:
            search_query = (
                select(Dashboard)
                .where(or_(
                    Dashboard.name.ilike(f"%{query}%"),
                    Dashboard.description.ilike(f"%{query}%")
                ))
                .where(Dashboard.active == True)
                .order_by(Dashboard.name)
                .limit(limit)
            )
            
            result = await self.session.execute(search_query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error searching dashboards: {str(e)}")
            raise DatabaseError(f"Failed to search dashboards: {str(e)}")
    
    async def get_popular_dashboards(self, limit: int = 10) -> List[Dashboard]:
        """Get most popular dashboards by access count"""
        try:
            query = (
                select(Dashboard)
                .where(Dashboard.access_count > 0)
                .where(Dashboard.active == True)
                .order_by(desc(Dashboard.access_count))
                .limit(limit)
            )
            
            result = await self.session.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting popular dashboards: {str(e)}")
            raise DatabaseError(f"Failed to get popular dashboards: {str(e)}")
    
    async def get_recent_dashboards(self, limit: int = 10) -> List[Dashboard]:
        """Get recently created dashboards"""
        try:
            query = (
                select(Dashboard)
                .where(Dashboard.active == True)
                .order_by(desc(Dashboard.created_at))
                .limit(limit)
            )
            
            result = await self.session.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Error getting recent dashboards: {str(e)}")
            raise DatabaseError(f"Failed to get recent dashboards: {str(e)}")
    
    async def bulk_update_widgets(self, dashboard_id: str, widgets_data: List[Dict[str, Any]]) -> List[Widget]:
        """Bulk update widgets for a dashboard"""
        try:
            # Get existing widgets
            existing_widgets = await self.get_widgets_by_dashboard(dashboard_id)
            existing_widget_ids = {w.id for w in existing_widgets}
            
            updated_widgets = []
            
            for widget_data in widgets_data:
                widget_id = widget_data.get('id')
                
                if widget_id and widget_id in existing_widget_ids:
                    # Update existing widget
                    widget = await self.update_widget(widget_id, widget_data)
                    updated_widgets.append(widget)
                else:
                    # Create new widget
                    widget_data['dashboard_id'] = dashboard_id
                    widget = await self.create_widget(widget_data)
                    updated_widgets.append(widget)
            
            return updated_widgets
            
        except Exception as e:
            logger.error(f"Error bulk updating widgets: {str(e)}")
            raise DatabaseError(f"Failed to bulk update widgets: {str(e)}")
    
    async def export_dashboard(self, dashboard_id: str) -> Dict[str, Any]:
        """Export dashboard configuration"""
        try:
            dashboard_data = await self.get_dashboard_data(dashboard_id)
            
            # Remove runtime data and keep only configuration
            export_data = {
                'dashboard': {
                    'name': dashboard_data['dashboard']['name'],
                    'description': dashboard_data['dashboard']['description'],
                    'config': dashboard_data['dashboard']['config'],
                    'layout': dashboard_data['dashboard']['layout'],
                    'filters': dashboard_data['dashboard']['filters'],
                    'refresh_interval': dashboard_data['dashboard']['refresh_interval']
                },
                'widgets': [
                    {
                        'title': widget['title'],
                        'type': widget['type'],
                        'config': widget['config'],
                        'position': widget['position'],
                        'size': widget['size'],
                        'metric_id': widget.get('metric_info', {}).get('metric_id'),
                        'query': widget.get('query', ''),
                        'refresh_interval': widget.get('refresh_interval', 300)
                    }
                    for widget in dashboard_data['widgets']
                ],
                'export_metadata': {
                    'exported_at': datetime.utcnow(),
                    'version': '1.0',
                    'total_widgets': len(dashboard_data['widgets'])
                }
            }
            
            return export_data
            
        except Exception as e:
            logger.error(f"Error exporting dashboard: {str(e)}")
            raise DatabaseError(f"Failed to export dashboard: {str(e)}")
    
    async def import_dashboard(self, import_data: Dict[str, Any], new_name: str = None) -> Dashboard:
        """Import dashboard from configuration"""
        try:
            dashboard_config = import_data['dashboard']
            widgets_config = import_data.get('widgets', [])
            
            # Create dashboard
            dashboard_data = {
                'name': new_name or dashboard_config['name'],
                'description': dashboard_config.get('description', ''),
                'config': dashboard_config.get('config', {}),
                'layout': dashboard_config.get('layout', {}),
                'filters': dashboard_config.get('filters', {}),
                'refresh_interval': dashboard_config.get('refresh_interval', 300),
                'public': False,  # Imported dashboards are private by default
                'active': True
            }
            
            dashboard = await self.create_dashboard(dashboard_data)
            
            # Create widgets
            for widget_config in widgets_config:
                widget_data = {
                    'dashboard_id': dashboard.id,
                    'title': widget_config.get('title', ''),
                    'type': widget_config['type'],
                    'config': widget_config.get('config', {}),
                    'position': widget_config.get('position', {}),
                    'size': widget_config.get('size', {}),
                    'metric_id': widget_config.get('metric_id'),
                    'query': widget_config.get('query', ''),
                    'refresh_interval': widget_config.get('refresh_interval', 300),
                    'active': True
                }
                
                await self.create_widget(widget_data)
            
            logger.info(f"Imported dashboard: {dashboard.name}")
            return dashboard
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error importing dashboard: {str(e)}")
            raise DatabaseError(f"Failed to import dashboard: {str(e)}")
