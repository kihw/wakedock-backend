"""
Dashboard View - Response formatting for dashboard operations
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from decimal import Decimal
import json

from wakedock.core.logging import get_logger

logger = get_logger(__name__)


class DashboardView:
    """View for dashboard response formatting"""
    
    def __init__(self):
        self.date_format = "%Y-%m-%d %H:%M:%S"
    
    def format_dashboard_response(self, dashboard_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format dashboard response"""
        try:
            return {
                'dashboard': {
                    'id': dashboard_data.get('id'),
                    'name': dashboard_data.get('name'),
                    'description': dashboard_data.get('description'),
                    'layout': dashboard_data.get('layout', {}),
                    'theme': dashboard_data.get('theme', {}),
                    'refresh_interval': dashboard_data.get('refresh_interval', 60),
                    'auto_refresh': dashboard_data.get('auto_refresh', True),
                    'public': dashboard_data.get('public', False),
                    'created_at': self._format_datetime(dashboard_data.get('created_at')),
                    'updated_at': self._format_datetime(dashboard_data.get('updated_at')),
                    'last_accessed': self._format_datetime(dashboard_data.get('last_accessed')),
                    'access_count': dashboard_data.get('access_count', 0),
                    'widgets': self._format_widgets(dashboard_data.get('widgets', [])),
                    'filters': dashboard_data.get('filters', []),
                    'performance': self._format_performance(dashboard_data.get('performance', {})),
                    'insights': self._format_insights(dashboard_data.get('insights', {}))
                },
                'metadata': {
                    'total_widgets': len(dashboard_data.get('widgets', [])),
                    'active_widgets': len([w for w in dashboard_data.get('widgets', []) if w.get('active', True)]),
                    'widget_types': self._get_widget_types(dashboard_data.get('widgets', [])),
                    'last_updated': self._format_datetime(dashboard_data.get('updated_at')),
                    'response_time': self._calculate_response_time()
                }
            }
            
        except Exception as e:
            logger.error(f"Error formatting dashboard response: {str(e)}")
            return self._format_error_response(str(e))
    
    def format_dashboards_list_response(self, dashboards_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format dashboards list response"""
        try:
            return {
                'dashboards': [
                    self._format_dashboard_summary(dashboard)
                    for dashboard in dashboards_data.get('dashboards', [])
                ],
                'pagination': {
                    'page': dashboards_data.get('page', 1),
                    'per_page': dashboards_data.get('per_page', 20),
                    'total_count': dashboards_data.get('total_count', 0),
                    'total_pages': dashboards_data.get('total_pages', 0)
                },
                'metadata': {
                    'total_dashboards': dashboards_data.get('total_count', 0),
                    'response_time': self._calculate_response_time()
                }
            }
            
        except Exception as e:
            logger.error(f"Error formatting dashboards list response: {str(e)}")
            return self._format_error_response(str(e))
    
    def format_widget_response(self, widget_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format widget response"""
        try:
            return {
                'widget': {
                    'id': widget_data.get('widget_id'),
                    'dashboard_id': widget_data.get('dashboard_id'),
                    'title': widget_data.get('title'),
                    'type': widget_data.get('type'),
                    'config': widget_data.get('config', {}),
                    'position': widget_data.get('position', {}),
                    'size': widget_data.get('size', {}),
                    'metric_id': widget_data.get('metric_id'),
                    'query': widget_data.get('query', {}),
                    'refresh_interval': widget_data.get('refresh_interval', 60),
                    'active': widget_data.get('active', True),
                    'created_at': self._format_datetime(widget_data.get('created_at')),
                    'updated_at': self._format_datetime(widget_data.get('updated_at')),
                    'data': self._format_widget_data(widget_data.get('data')),
                    'status': widget_data.get('status', 'active')
                },
                'metadata': {
                    'data_points': len(widget_data.get('data', [])) if widget_data.get('data') else 0,
                    'last_updated': self._format_datetime(widget_data.get('updated_at')),
                    'response_time': self._calculate_response_time()
                }
            }
            
        except Exception as e:
            logger.error(f"Error formatting widget response: {str(e)}")
            return self._format_error_response(str(e))
    
    def format_real_time_response(self, real_time_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format real-time data response"""
        try:
            return {
                'dashboard_id': real_time_data.get('dashboard_id'),
                'widgets': [
                    {
                        'widget_id': widget.get('widget_id'),
                        'title': widget.get('title'),
                        'type': widget.get('type'),
                        'latest_value': self._format_value(widget.get('latest_value')),
                        'latest_timestamp': self._format_datetime(widget.get('latest_timestamp')),
                        'status': widget.get('status'),
                        'trend': self._calculate_trend(widget.get('latest_value')),
                        'change': self._calculate_change(widget.get('latest_value'))
                    }
                    for widget in real_time_data.get('widgets', [])
                ],
                'metadata': {
                    'timestamp': self._format_datetime(real_time_data.get('timestamp')),
                    'refresh_interval': real_time_data.get('refresh_interval', 60),
                    'active_widgets': len([w for w in real_time_data.get('widgets', []) if w.get('status') == 'active']),
                    'response_time': self._calculate_response_time()
                }
            }
            
        except Exception as e:
            logger.error(f"Error formatting real-time response: {str(e)}")
            return self._format_error_response(str(e))
    
    def format_analytics_response(self, analytics_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format analytics response"""
        try:
            return {
                'dashboard_id': analytics_data.get('dashboard_id'),
                'dashboard_name': analytics_data.get('dashboard_name'),
                'time_range': {
                    'start': self._format_datetime(analytics_data.get('time_range', {}).get('start')),
                    'end': self._format_datetime(analytics_data.get('time_range', {}).get('end'))
                },
                'metrics': [
                    {
                        'metric_id': metric.get('metric_id'),
                        'metric_name': metric.get('metric_name'),
                        'widget_title': metric.get('widget_title'),
                        'statistics': self._format_statistics(metric.get('statistics', {})),
                        'trends': self._format_trends(metric.get('trends', {}))
                    }
                    for metric in analytics_data.get('metrics_analytics', [])
                ],
                'dashboard_stats': {
                    'total_widgets': analytics_data.get('dashboard_stats', {}).get('total_widgets', 0),
                    'active_widgets': analytics_data.get('dashboard_stats', {}).get('active_widgets', 0),
                    'total_metrics': analytics_data.get('dashboard_stats', {}).get('total_metrics', 0),
                    'access_count': analytics_data.get('dashboard_stats', {}).get('access_count', 0),
                    'last_accessed': self._format_datetime(analytics_data.get('dashboard_stats', {}).get('last_accessed'))
                },
                'metadata': {
                    'generated_at': self._format_datetime(datetime.utcnow()),
                    'response_time': self._calculate_response_time()
                }
            }
            
        except Exception as e:
            logger.error(f"Error formatting analytics response: {str(e)}")
            return self._format_error_response(str(e))
    
    def format_insights_response(self, insights_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format insights response"""
        try:
            return {
                'dashboard_id': insights_data.get('dashboard_id'),
                'time_range': {
                    'start': self._format_datetime(insights_data.get('time_range', {}).get('start')),
                    'end': self._format_datetime(insights_data.get('time_range', {}).get('end'))
                },
                'insights': {
                    'usage_patterns': self._format_usage_patterns(insights_data.get('insights', {}).get('usage_patterns', {})),
                    'performance_trends': self._format_performance_trends(insights_data.get('insights', {}).get('performance_trends', {})),
                    'recommendations': self._format_recommendations(insights_data.get('insights', {}).get('recommendations', []))
                },
                'metadata': {
                    'generated_at': self._format_datetime(insights_data.get('generated_at')),
                    'response_time': self._calculate_response_time()
                }
            }
            
        except Exception as e:
            logger.error(f"Error formatting insights response: {str(e)}")
            return self._format_error_response(str(e))
    
    def format_export_response(self, export_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format export response"""
        try:
            return {
                'export': {
                    'dashboard': export_data.get('dashboard', {}),
                    'widgets': export_data.get('widgets', []),
                    'version': export_data.get('version', '1.0'),
                    'metadata': {
                        'exported_at': self._format_datetime(export_data.get('exported_at')),
                        'exported_by': export_data.get('exported_by'),
                        'export_format': 'json',
                        'dashboard_id': export_data.get('dashboard', {}).get('id')
                    }
                },
                'metadata': {
                    'export_size': self._calculate_export_size(export_data),
                    'widget_count': len(export_data.get('widgets', [])),
                    'response_time': self._calculate_response_time()
                }
            }
            
        except Exception as e:
            logger.error(f"Error formatting export response: {str(e)}")
            return self._format_error_response(str(e))
    
    def format_import_response(self, import_result: Dict[str, Any]) -> Dict[str, Any]:
        """Format import response"""
        try:
            return {
                'import_result': {
                    'dashboard': self._format_dashboard_summary(import_result),
                    'status': 'success',
                    'imported_at': self._format_datetime(datetime.utcnow())
                },
                'metadata': {
                    'widgets_imported': len(import_result.get('widgets', [])),
                    'response_time': self._calculate_response_time()
                }
            }
            
        except Exception as e:
            logger.error(f"Error formatting import response: {str(e)}")
            return self._format_error_response(str(e))
    
    def format_templates_response(self, templates_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Format templates response"""
        try:
            return {
                'templates': [
                    {
                        'id': template.get('id'),
                        'name': template.get('name'),
                        'description': template.get('description'),
                        'access_count': template.get('access_count', 0),
                        'widget_count': template.get('widget_count', 0),
                        'preview': self._generate_template_preview(template)
                    }
                    for template in templates_data
                ],
                'metadata': {
                    'total_templates': len(templates_data),
                    'response_time': self._calculate_response_time()
                }
            }
            
        except Exception as e:
            logger.error(f"Error formatting templates response: {str(e)}")
            return self._format_error_response(str(e))
    
    def format_statistics_response(self, statistics_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format statistics response"""
        try:
            return {
                'statistics': {
                    'overview': statistics_data.get('overview', {}),
                    'popular_dashboards': [
                        {
                            'id': dashboard.get('id'),
                            'name': dashboard.get('name'),
                            'access_count': dashboard.get('access_count', 0),
                            'widget_count': dashboard.get('widget_count', 0)
                        }
                        for dashboard in statistics_data.get('popular_dashboards', [])
                    ],
                    'recent_dashboards': [
                        {
                            'id': dashboard.get('id'),
                            'name': dashboard.get('name'),
                            'created_at': self._format_datetime(dashboard.get('created_at')),
                            'widget_count': dashboard.get('widget_count', 0)
                        }
                        for dashboard in statistics_data.get('recent_dashboards', [])
                    ]
                },
                'metadata': {
                    'generated_at': self._format_datetime(datetime.utcnow()),
                    'response_time': self._calculate_response_time()
                }
            }
            
        except Exception as e:
            logger.error(f"Error formatting statistics response: {str(e)}")
            return self._format_error_response(str(e))
    
    def format_search_response(self, search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Format search response"""
        try:
            return {
                'results': [
                    {
                        'id': result.get('id'),
                        'name': result.get('name'),
                        'description': result.get('description'),
                        'widget_count': result.get('widget_count', 0),
                        'access_count': result.get('access_count', 0),
                        'created_at': self._format_datetime(result.get('created_at')),
                        'last_accessed': self._format_datetime(result.get('last_accessed')),
                        'relevance_score': self._calculate_relevance_score(result)
                    }
                    for result in search_results
                ],
                'metadata': {
                    'total_results': len(search_results),
                    'response_time': self._calculate_response_time()
                }
            }
            
        except Exception as e:
            logger.error(f"Error formatting search response: {str(e)}")
            return self._format_error_response(str(e))
    
    def format_bulk_operation_response(self, bulk_result: Dict[str, Any]) -> Dict[str, Any]:
        """Format bulk operation response"""
        try:
            results = bulk_result.get('results', [])
            successful_operations = len([r for r in results if r.get('success')])
            failed_operations = len([r for r in results if not r.get('success')])
            
            return {
                'bulk_operation': {
                    'total_operations': len(results),
                    'successful': successful_operations,
                    'failed': failed_operations,
                    'success_rate': (successful_operations / len(results)) * 100 if results else 0
                },
                'results': [
                    {
                        'success': result.get('success'),
                        'data': result.get('widget') if result.get('success') else None,
                        'error': result.get('error') if not result.get('success') else None
                    }
                    for result in results
                ],
                'metadata': {
                    'processed_at': self._format_datetime(datetime.utcnow()),
                    'response_time': self._calculate_response_time()
                }
            }
            
        except Exception as e:
            logger.error(f"Error formatting bulk operation response: {str(e)}")
            return self._format_error_response(str(e))
    
    def format_streaming_response(self, streaming_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format streaming response"""
        try:
            return {
                'stream': {
                    'dashboard_id': streaming_data.get('dashboard_id'),
                    'event_type': streaming_data.get('event_type', 'update'),
                    'data': streaming_data.get('data', {}),
                    'timestamp': self._format_datetime(streaming_data.get('timestamp')),
                    'sequence_number': streaming_data.get('sequence_number', 0)
                },
                'metadata': {
                    'stream_id': streaming_data.get('stream_id'),
                    'client_id': streaming_data.get('client_id'),
                    'response_time': self._calculate_response_time()
                }
            }
            
        except Exception as e:
            logger.error(f"Error formatting streaming response: {str(e)}")
            return self._format_error_response(str(e))
    
    # Private helper methods
    
    def _format_dashboard_summary(self, dashboard: Dict[str, Any]) -> Dict[str, Any]:
        """Format dashboard summary"""
        return {
            'id': dashboard.get('id'),
            'name': dashboard.get('name'),
            'description': dashboard.get('description'),
            'widget_count': dashboard.get('widget_count', 0),
            'active_widgets': dashboard.get('active_widgets', 0),
            'access_count': dashboard.get('access_count', 0),
            'last_accessed': self._format_datetime(dashboard.get('last_accessed')),
            'created_at': self._format_datetime(dashboard.get('created_at')),
            'updated_at': self._format_datetime(dashboard.get('updated_at')),
            'public': dashboard.get('public', False),
            'refresh_interval': dashboard.get('refresh_interval', 60)
        }
    
    def _format_widgets(self, widgets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format widgets list"""
        return [
            {
                'widget_id': widget.get('widget_id'),
                'title': widget.get('title'),
                'type': widget.get('type'),
                'config': widget.get('config', {}),
                'position': widget.get('position', {}),
                'size': widget.get('size', {}),
                'metric_id': widget.get('metric_id'),
                'active': widget.get('active', True),
                'data': self._format_widget_data(widget.get('data')),
                'metric_info': widget.get('metric_info', {}),
                'status': widget.get('status', 'active')
            }
            for widget in widgets
        ]
    
    def _format_widget_data(self, data: Any) -> Any:
        """Format widget data"""
        if isinstance(data, list):
            return [self._format_data_point(point) for point in data]
        elif isinstance(data, dict):
            return {k: self._format_value(v) for k, v in data.items()}
        else:
            return self._format_value(data)
    
    def _format_data_point(self, point: Dict[str, Any]) -> Dict[str, Any]:
        """Format single data point"""
        return {
            'timestamp': self._format_datetime(point.get('timestamp')),
            'value': self._format_value(point.get('value')),
            'metadata': point.get('metadata', {})
        }
    
    def _format_value(self, value: Any) -> Any:
        """Format value based on type"""
        if isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, datetime):
            return self._format_datetime(value)
        else:
            return value
    
    def _format_datetime(self, dt: datetime) -> str:
        """Format datetime to string"""
        if dt is None:
            return None
        return dt.strftime(self.date_format)
    
    def _format_performance(self, performance: Dict[str, Any]) -> Dict[str, Any]:
        """Format performance data"""
        return {
            'load_time': performance.get('load_time', 0),
            'data_freshness': performance.get('data_freshness', 'unknown'),
            'widget_health': performance.get('widget_health', {})
        }
    
    def _format_insights(self, insights: Dict[str, Any]) -> Dict[str, Any]:
        """Format insights data"""
        return {
            'most_viewed_widgets': insights.get('most_viewed_widgets', []),
            'data_coverage': insights.get('data_coverage', {}),
            'recommendations': insights.get('recommendations', [])
        }
    
    def _format_statistics(self, statistics: Dict[str, Any]) -> Dict[str, Any]:
        """Format statistics data"""
        return {
            'avg': self._format_value(statistics.get('avg')),
            'min': self._format_value(statistics.get('min')),
            'max': self._format_value(statistics.get('max')),
            'sum': self._format_value(statistics.get('sum')),
            'count': statistics.get('count', 0),
            'std': self._format_value(statistics.get('std')),
            'median': self._format_value(statistics.get('median'))
        }
    
    def _format_trends(self, trends: Dict[str, Any]) -> Dict[str, Any]:
        """Format trends data"""
        return {
            'direction': trends.get('direction', 'stable'),
            'change_rate': self._format_value(trends.get('change_rate')),
            'trend_score': self._format_value(trends.get('trend_score')),
            'period': trends.get('period', 'daily')
        }
    
    def _format_usage_patterns(self, patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Format usage patterns"""
        return {
            'peak_hours': patterns.get('peak_hours', []),
            'usage_frequency': patterns.get('usage_frequency', 'daily'),
            'popular_widgets': patterns.get('popular_widgets', [])
        }
    
    def _format_performance_trends(self, trends: Dict[str, Any]) -> Dict[str, Any]:
        """Format performance trends"""
        return {
            'load_time_trend': trends.get('load_time_trend', 'stable'),
            'data_freshness_trend': trends.get('data_freshness_trend', 'stable'),
            'error_rate_trend': trends.get('error_rate_trend', 'stable')
        }
    
    def _format_recommendations(self, recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format recommendations"""
        return [
            {
                'type': rec.get('type'),
                'message': rec.get('message'),
                'action': rec.get('action'),
                'priority': rec.get('priority', 'medium'),
                'impact': rec.get('impact', 'low')
            }
            for rec in recommendations
        ]
    
    def _get_widget_types(self, widgets: List[Dict[str, Any]]) -> List[str]:
        """Get unique widget types"""
        types = set()
        for widget in widgets:
            if widget.get('type'):
                types.add(widget['type'])
        return list(types)
    
    def _calculate_response_time(self) -> float:
        """Calculate response time (simulated)"""
        return 0.1  # Simulated response time
    
    def _calculate_trend(self, value: Any) -> str:
        """Calculate trend (simulated)"""
        return 'stable'  # Simulated trend
    
    def _calculate_change(self, value: Any) -> float:
        """Calculate change (simulated)"""
        return 0.0  # Simulated change
    
    def _calculate_export_size(self, export_data: Dict[str, Any]) -> int:
        """Calculate export size"""
        return len(json.dumps(export_data))
    
    def _generate_template_preview(self, template: Dict[str, Any]) -> Dict[str, Any]:
        """Generate template preview"""
        return {
            'thumbnail': None,  # Would generate thumbnail
            'widget_types': [],  # Would extract widget types
            'layout_type': 'grid'  # Would extract layout type
        }
    
    def _calculate_relevance_score(self, result: Dict[str, Any]) -> float:
        """Calculate relevance score for search results"""
        return 1.0  # Simulated relevance score
    
    def _format_error_response(self, error_message: str) -> Dict[str, Any]:
        """Format error response"""
        return {
            'error': {
                'message': error_message,
                'timestamp': self._format_datetime(datetime.utcnow()),
                'code': 'DASHBOARD_ERROR'
            }
        }
