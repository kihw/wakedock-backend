"""
Analytics View - Response formatting and data presentation for analytics
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from wakedock.core.logging import get_logger

logger = get_logger(__name__)


class AnalyticsView:
    """View for formatting analytics responses"""
    
    def __init__(self):
        self.default_date_format = "%Y-%m-%dT%H:%M:%S.%fZ"
        self.compact_date_format = "%Y-%m-%d %H:%M:%S"
        self.max_data_points = 1000
    
    def format_metric_response(self, metric_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format metric data for API response"""
        return {
            'metric_id': metric_data.get('metric_id'),
            'name': metric_data.get('name'),
            'type': metric_data.get('type'),
            'description': metric_data.get('description'),
            'unit': metric_data.get('unit'),
            'labels': metric_data.get('labels', {}),
            'metadata': metric_data.get('metadata', {}),
            'created_at': self._format_datetime(metric_data.get('created_at')),
            'updated_at': self._format_datetime(metric_data.get('updated_at')),
            'statistics': self._format_statistics(metric_data.get('statistics', {}))
        }
    
    def format_metrics_list_response(self, metrics: List[Dict[str, Any]], 
                                   total_count: int = None, 
                                   page: int = None, 
                                   per_page: int = None) -> Dict[str, Any]:
        """Format metrics list for API response"""
        formatted_metrics = [self.format_metric_response(metric) for metric in metrics]
        
        response = {
            'metrics': formatted_metrics,
            'count': len(formatted_metrics)
        }
        
        # Add pagination info if provided
        if total_count is not None:
            response['total_count'] = total_count
        
        if page is not None and per_page is not None:
            response['pagination'] = {
                'page': page,
                'per_page': per_page,
                'total_pages': (total_count + per_page - 1) // per_page if total_count else 1
            }
        
        return response
    
    def format_metric_data_response(self, metric_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format metric data points for API response"""
        return {
            'metric_id': metric_data.get('metric_id'),
            'metric_name': metric_data.get('metric_name'),
            'metric_type': metric_data.get('metric_type'),
            'unit': metric_data.get('unit'),
            'time_range': self._format_time_range(metric_data.get('time_range', {})),
            'data_points': self._format_data_points(metric_data.get('data_points', [])),
            'statistics': self._format_statistics(metric_data.get('statistics', {})),
            'metadata': {
                'total_points': len(metric_data.get('data_points', [])),
                'granularity': metric_data.get('granularity'),
                'aggregation': metric_data.get('aggregation')
            }
        }
    
    def format_aggregation_response(self, aggregation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format aggregation data for API response"""
        return {
            'metric_id': aggregation_data.get('metric_id'),
            'aggregation_type': aggregation_data.get('aggregation_type'),
            'granularity': aggregation_data.get('granularity'),
            'time_range': self._format_time_range(aggregation_data.get('time_range', {})),
            'data_points': self._format_data_points(aggregation_data.get('data_points', [])),
            'statistics': self._format_statistics(aggregation_data.get('statistics', {})),
            'trend': self._format_trend(aggregation_data.get('trend', {})),
            'insights': aggregation_data.get('insights', []),
            'metadata': {
                'total_points': len(aggregation_data.get('data_points', [])),
                'calculation_time': aggregation_data.get('calculation_time'),
                'data_quality': aggregation_data.get('data_quality', 'good')
            }
        }
    
    def format_container_analytics_response(self, analytics_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format container analytics for API response"""
        return {
            'container_id': analytics_data.get('container_id'),
            'container_name': analytics_data.get('container_name'),
            'time_range': self._format_time_range(analytics_data.get('time_range', {})),
            'metrics': {
                'cpu': self._format_resource_metrics(analytics_data.get('cpu_metrics', {})),
                'memory': self._format_resource_metrics(analytics_data.get('memory_metrics', {})),
                'network': self._format_network_metrics(analytics_data.get('network_metrics', {})),
                'disk': self._format_disk_metrics(analytics_data.get('disk_metrics', {}))
            },
            'performance_score': analytics_data.get('performance_score', 0),
            'resource_efficiency': analytics_data.get('resource_efficiency', {}),
            'recommendations': analytics_data.get('recommendations', []),
            'health_status': self._format_health_status(analytics_data.get('health_status', {})),
            'trends': self._format_trends(analytics_data.get('trends', {})),
            'alerts': analytics_data.get('alerts', [])
        }
    
    def format_service_analytics_response(self, analytics_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format service analytics for API response"""
        return {
            'service_id': analytics_data.get('service_id'),
            'service_name': analytics_data.get('service_name'),
            'time_range': self._format_time_range(analytics_data.get('time_range', {})),
            'metrics': {
                'performance': self._format_performance_metrics(analytics_data.get('performance_metrics', {})),
                'availability': self._format_availability_metrics(analytics_data.get('availability_metrics', {})),
                'reliability': self._format_reliability_metrics(analytics_data.get('reliability_metrics', {})),
                'scalability': self._format_scalability_metrics(analytics_data.get('scalability_metrics', {}))
            },
            'health_score': analytics_data.get('health_score', 0),
            'scaling_recommendations': analytics_data.get('scaling_recommendations', []),
            'cost_analysis': analytics_data.get('cost_analysis', {}),
            'sla_compliance': analytics_data.get('sla_compliance', {}),
            'trends': self._format_trends(analytics_data.get('trends', {})),
            'incidents': analytics_data.get('incidents', [])
        }
    
    def format_report_response(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format report data for API response"""
        return {
            'report_id': report_data.get('report_id'),
            'name': report_data.get('name'),
            'description': report_data.get('description'),
            'report_type': report_data.get('report_type'),
            'created_at': self._format_datetime(report_data.get('created_at')),
            'time_range': self._format_time_range(report_data.get('time_range', {})),
            'metrics': self._format_report_metrics(report_data.get('metrics', [])),
            'summary': report_data.get('summary', {}),
            'visualizations': self._format_visualizations(report_data.get('visualizations', [])),
            'metadata': {
                'total_metrics': len(report_data.get('metrics', [])),
                'data_points': report_data.get('total_data_points', 0),
                'generation_time': report_data.get('generation_time'),
                'format': report_data.get('format', 'json')
            }
        }
    
    def format_correlation_response(self, correlation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format correlation data for API response"""
        return {
            'metric_ids': correlation_data.get('metric_ids', []),
            'time_range': self._format_time_range(correlation_data.get('time_range', {})),
            'correlations': self._format_correlations(correlation_data.get('correlations', [])),
            'insights': correlation_data.get('insights', []),
            'matrix': correlation_data.get('correlation_matrix', []),
            'statistics': {
                'total_correlations': len(correlation_data.get('correlations', [])),
                'strong_correlations': len([c for c in correlation_data.get('correlations', []) 
                                          if abs(c.get('coefficient', 0)) > 0.7]),
                'weak_correlations': len([c for c in correlation_data.get('correlations', []) 
                                        if abs(c.get('coefficient', 0)) < 0.3])
            },
            'visualization_data': self._format_correlation_visualization(correlation_data)
        }
    
    def format_anomaly_response(self, anomaly_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format anomaly detection data for API response"""
        return {
            'metric_id': anomaly_data.get('metric_id'),
            'metric_name': anomaly_data.get('metric_name'),
            'time_range': self._format_time_range(anomaly_data.get('time_range', {})),
            'sensitivity': anomaly_data.get('sensitivity', 2.0),
            'anomalies': self._format_anomalies(anomaly_data.get('anomalies', [])),
            'statistics': {
                'total_points': anomaly_data.get('total_points', 0),
                'anomaly_count': len(anomaly_data.get('anomalies', [])),
                'anomaly_rate': anomaly_data.get('anomaly_rate', 0.0)
            },
            'baseline': anomaly_data.get('baseline', {}),
            'threshold': anomaly_data.get('threshold', {}),
            'recommendations': anomaly_data.get('recommendations', []),
            'visualization_data': self._format_anomaly_visualization(anomaly_data)
        }
    
    def format_forecast_response(self, forecast_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format forecast data for API response"""
        return {
            'metric_id': forecast_data.get('metric_id'),
            'metric_name': forecast_data.get('metric_name'),
            'forecast_horizon': forecast_data.get('forecast_hours', 24),
            'model_type': forecast_data.get('model_type', 'linear'),
            'forecast_points': self._format_data_points(forecast_data.get('forecast_points', [])),
            'confidence_intervals': forecast_data.get('confidence_intervals', {}),
            'accuracy_metrics': forecast_data.get('accuracy_metrics', {}),
            'quality_score': forecast_data.get('quality_score', 0.0),
            'trends': self._format_forecast_trends(forecast_data.get('trends', {})),
            'recommendations': forecast_data.get('recommendations', []),
            'metadata': {
                'generated_at': self._format_datetime(forecast_data.get('generated_at')),
                'training_data_points': forecast_data.get('training_data_points', 0),
                'model_version': forecast_data.get('model_version', '1.0')
            }
        }
    
    def format_export_response(self, export_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format export data for API response"""
        return {
            'export_id': export_data.get('export_id'),
            'format': export_data.get('format'),
            'metrics': export_data.get('metrics', []),
            'time_range': self._format_time_range(export_data.get('time_range', {})),
            'download_url': export_data.get('download_url'),
            'file_size': export_data.get('file_size'),
            'expires_at': self._format_datetime(export_data.get('expires_at')),
            'metadata': export_data.get('metadata', {}),
            'status': export_data.get('status', 'completed')
        }
    
    def format_health_metrics_response(self, health_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format system health metrics for API response"""
        return {
            'timestamp': self._format_datetime(health_data.get('timestamp')),
            'overall_health_score': health_data.get('overall_health_score', 0),
            'components': {
                'cpu': self._format_health_component(health_data.get('cpu_health', {})),
                'memory': self._format_health_component(health_data.get('memory_health', {})),
                'disk': self._format_health_component(health_data.get('disk_health', {})),
                'network': self._format_health_component(health_data.get('network_health', {})),
                'database': self._format_health_component(health_data.get('database_health', {}))
            },
            'recommendations': health_data.get('recommendations', []),
            'alerts': health_data.get('alerts', []),
            'trends': self._format_health_trends(health_data.get('trends', {})),
            'thresholds': health_data.get('thresholds', {}),
            'last_updated': self._format_datetime(health_data.get('last_updated'))
        }
    
    def format_bulk_operation_response(self, operation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format bulk operation results for API response"""
        return {
            'operation': operation_data.get('operation'),
            'total_requested': operation_data.get('total_requested', 0),
            'successful': operation_data.get('updated_count', 0) + operation_data.get('deleted_count', 0),
            'failed': len(operation_data.get('errors', [])),
            'errors': operation_data.get('errors', []),
            'execution_time': operation_data.get('execution_time'),
            'summary': self._format_bulk_summary(operation_data)
        }
    
    def format_dashboard_response(self, dashboard_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format dashboard data for API response"""
        return {
            'dashboard_id': dashboard_data.get('dashboard_id'),
            'name': dashboard_data.get('name'),
            'description': dashboard_data.get('description'),
            'created_at': self._format_datetime(dashboard_data.get('created_at')),
            'updated_at': self._format_datetime(dashboard_data.get('updated_at')),
            'widgets': self._format_widgets(dashboard_data.get('widgets', [])),
            'layout': dashboard_data.get('layout', {}),
            'filters': dashboard_data.get('filters', {}),
            'refresh_interval': dashboard_data.get('refresh_interval', 300),
            'permissions': dashboard_data.get('permissions', {}),
            'metadata': {
                'widget_count': len(dashboard_data.get('widgets', [])),
                'last_accessed': self._format_datetime(dashboard_data.get('last_accessed')),
                'access_count': dashboard_data.get('access_count', 0)
            }
        }
    
    def format_error_response(self, error_message: str, error_code: str = None, 
                             details: Dict[str, Any] = None) -> Dict[str, Any]:
        """Format error response"""
        response = {
            'error': {
                'message': error_message,
                'timestamp': self._format_datetime(datetime.utcnow())
            }
        }
        
        if error_code:
            response['error']['code'] = error_code
        
        if details:
            response['error']['details'] = details
        
        return response
    
    def format_success_response(self, message: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Format success response"""
        response = {
            'success': True,
            'message': message,
            'timestamp': self._format_datetime(datetime.utcnow())
        }
        
        if data:
            response['data'] = data
        
        return response
    
    # Private helper methods
    
    def _format_datetime(self, dt: datetime) -> str:
        """Format datetime for API response"""
        if dt is None:
            return None
        
        if isinstance(dt, str):
            return dt
        
        return dt.strftime(self.default_date_format)
    
    def _format_compact_datetime(self, dt: datetime) -> str:
        """Format datetime in compact format"""
        if dt is None:
            return None
        
        if isinstance(dt, str):
            return dt
        
        return dt.strftime(self.compact_date_format)
    
    def _format_time_range(self, time_range: Dict[str, Any]) -> Dict[str, Any]:
        """Format time range for API response"""
        if not time_range:
            return {}
        
        return {
            'start': self._format_datetime(time_range.get('start')),
            'end': self._format_datetime(time_range.get('end')),
            'duration': time_range.get('duration'),
            'granularity': time_range.get('granularity')
        }
    
    def _format_data_points(self, data_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format data points for API response"""
        if not data_points:
            return []
        
        # Limit data points to prevent large responses
        if len(data_points) > self.max_data_points:
            # Sample data points evenly
            step = len(data_points) // self.max_data_points
            data_points = data_points[::step]
        
        return [
            {
                'timestamp': self._format_datetime(point.get('timestamp')),
                'value': point.get('value'),
                'labels': point.get('labels', {}),
                'quality': point.get('quality', 'good')
            }
            for point in data_points
        ]
    
    def _format_statistics(self, statistics: Dict[str, Any]) -> Dict[str, Any]:
        """Format statistics for API response"""
        if not statistics:
            return {}
        
        return {
            'count': statistics.get('count', 0),
            'sum': statistics.get('sum', 0),
            'mean': statistics.get('mean', 0),
            'median': statistics.get('median', 0),
            'min': statistics.get('min', 0),
            'max': statistics.get('max', 0),
            'stddev': statistics.get('stddev', 0),
            'variance': statistics.get('variance', 0),
            'percentiles': statistics.get('percentiles', {}),
            'distribution': statistics.get('distribution', {})
        }
    
    def _format_trend(self, trend: Dict[str, Any]) -> Dict[str, Any]:
        """Format trend data for API response"""
        if not trend:
            return {}
        
        return {
            'direction': trend.get('direction', 'stable'),
            'strength': trend.get('strength', 0.0),
            'correlation': trend.get('correlation', 0.0),
            'change_rate': trend.get('change_rate', 0.0),
            'confidence': trend.get('confidence', 0.0)
        }
    
    def _format_trends(self, trends: Dict[str, Any]) -> Dict[str, Any]:
        """Format multiple trends for API response"""
        if not trends:
            return {}
        
        return {
            metric: self._format_trend(trend)
            for metric, trend in trends.items()
        }
    
    def _format_resource_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Format resource metrics for API response"""
        if not metrics:
            return {}
        
        return {
            'current': metrics.get('current', 0),
            'average': metrics.get('average', 0),
            'peak': metrics.get('peak', 0),
            'limit': metrics.get('limit', 0),
            'utilization': metrics.get('utilization', 0),
            'trend': self._format_trend(metrics.get('trend', {})),
            'history': self._format_data_points(metrics.get('history', []))
        }
    
    def _format_network_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Format network metrics for API response"""
        if not metrics:
            return {}
        
        return {
            'bytes_sent': metrics.get('bytes_sent', 0),
            'bytes_received': metrics.get('bytes_received', 0),
            'packets_sent': metrics.get('packets_sent', 0),
            'packets_received': metrics.get('packets_received', 0),
            'errors': metrics.get('errors', 0),
            'dropped': metrics.get('dropped', 0),
            'bandwidth_usage': metrics.get('bandwidth_usage', 0)
        }
    
    def _format_disk_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Format disk metrics for API response"""
        if not metrics:
            return {}
        
        return {
            'read_bytes': metrics.get('read_bytes', 0),
            'write_bytes': metrics.get('write_bytes', 0),
            'read_ops': metrics.get('read_ops', 0),
            'write_ops': metrics.get('write_ops', 0),
            'usage': metrics.get('usage', 0),
            'available': metrics.get('available', 0),
            'io_utilization': metrics.get('io_utilization', 0)
        }
    
    def _format_health_status(self, health_status: Dict[str, Any]) -> Dict[str, Any]:
        """Format health status for API response"""
        if not health_status:
            return {}
        
        return {
            'status': health_status.get('status', 'unknown'),
            'score': health_status.get('score', 0),
            'issues': health_status.get('issues', []),
            'last_check': self._format_datetime(health_status.get('last_check'))
        }
    
    def _format_performance_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Format performance metrics for API response"""
        if not metrics:
            return {}
        
        return {
            'response_time': metrics.get('response_time', {}),
            'throughput': metrics.get('throughput', {}),
            'error_rate': metrics.get('error_rate', 0),
            'success_rate': metrics.get('success_rate', 100),
            'concurrent_users': metrics.get('concurrent_users', 0)
        }
    
    def _format_availability_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Format availability metrics for API response"""
        if not metrics:
            return {}
        
        return {
            'uptime': metrics.get('uptime', 100),
            'downtime': metrics.get('downtime', 0),
            'incidents': metrics.get('incidents', 0),
            'mttr': metrics.get('mttr', 0),
            'mtbf': metrics.get('mtbf', 0)
        }
    
    def _format_reliability_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Format reliability metrics for API response"""
        if not metrics:
            return {}
        
        return {
            'error_rate': metrics.get('error_rate', 0),
            'timeout_rate': metrics.get('timeout_rate', 0),
            'retry_rate': metrics.get('retry_rate', 0),
            'failure_rate': metrics.get('failure_rate', 0)
        }
    
    def _format_scalability_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Format scalability metrics for API response"""
        if not metrics:
            return {}
        
        return {
            'instances': metrics.get('instances', 1),
            'auto_scaling': metrics.get('auto_scaling', {}),
            'load_distribution': metrics.get('load_distribution', {}),
            'capacity_usage': metrics.get('capacity_usage', 0)
        }
    
    def _format_report_metrics(self, metrics: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format report metrics for API response"""
        return [
            {
                'metric_id': metric.get('metric_id'),
                'metric_name': metric.get('metric_name'),
                'data_summary': metric.get('data_summary', {}),
                'insights': metric.get('insights', [])
            }
            for metric in metrics
        ]
    
    def _format_visualizations(self, visualizations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format visualizations for API response"""
        return [
            {
                'type': viz.get('type'),
                'title': viz.get('title'),
                'data': viz.get('data', []),
                'config': viz.get('config', {})
            }
            for viz in visualizations
        ]
    
    def _format_correlations(self, correlations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format correlations for API response"""
        return [
            {
                'metric_1': corr.get('metric_1'),
                'metric_2': corr.get('metric_2'),
                'coefficient': corr.get('coefficient', 0.0),
                'p_value': corr.get('p_value', 1.0),
                'strength': self._get_correlation_strength(corr.get('coefficient', 0.0)),
                'significance': corr.get('significance', 'not_significant')
            }
            for corr in correlations
        ]
    
    def _format_correlation_visualization(self, correlation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format correlation visualization data"""
        return {
            'heatmap_data': correlation_data.get('correlation_matrix', []),
            'scatter_plots': correlation_data.get('scatter_plots', []),
            'network_graph': correlation_data.get('network_graph', {})
        }
    
    def _format_anomalies(self, anomalies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format anomalies for API response"""
        return [
            {
                'timestamp': self._format_datetime(anomaly.get('timestamp')),
                'value': anomaly.get('value'),
                'expected_value': anomaly.get('expected_value'),
                'deviation': anomaly.get('deviation'),
                'severity': anomaly.get('severity', 'low'),
                'confidence': anomaly.get('confidence', 0.0),
                'context': anomaly.get('context', {})
            }
            for anomaly in anomalies
        ]
    
    def _format_anomaly_visualization(self, anomaly_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format anomaly visualization data"""
        return {
            'timeline': anomaly_data.get('timeline', []),
            'distribution': anomaly_data.get('distribution', {}),
            'patterns': anomaly_data.get('patterns', [])
        }
    
    def _format_forecast_trends(self, trends: Dict[str, Any]) -> Dict[str, Any]:
        """Format forecast trends for API response"""
        if not trends:
            return {}
        
        return {
            'overall_trend': trends.get('overall_trend', 'stable'),
            'seasonal_patterns': trends.get('seasonal_patterns', []),
            'trend_changes': trends.get('trend_changes', [])
        }
    
    def _format_health_component(self, component: Dict[str, Any]) -> Dict[str, Any]:
        """Format health component for API response"""
        if not component:
            return {}
        
        return {
            'status': component.get('status', 'unknown'),
            'score': component.get('score', 0),
            'value': component.get('value', 0),
            'threshold': component.get('threshold', {}),
            'message': component.get('message', ''),
            'last_updated': self._format_datetime(component.get('last_updated'))
        }
    
    def _format_health_trends(self, trends: Dict[str, Any]) -> Dict[str, Any]:
        """Format health trends for API response"""
        if not trends:
            return {}
        
        return {
            'overall': self._format_trend(trends.get('overall', {})),
            'components': {
                component: self._format_trend(trend)
                for component, trend in trends.get('components', {}).items()
            }
        }
    
    def _format_widgets(self, widgets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format widgets for API response"""
        return [
            {
                'widget_id': widget.get('widget_id'),
                'type': widget.get('type'),
                'title': widget.get('title'),
                'metric_id': widget.get('metric_id'),
                'config': widget.get('config', {}),
                'position': widget.get('position', {}),
                'size': widget.get('size', {}),
                'data': widget.get('data', {}),
                'last_updated': self._format_datetime(widget.get('last_updated'))
            }
            for widget in widgets
        ]
    
    def _format_bulk_summary(self, operation_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format bulk operation summary"""
        return {
            'success_rate': (operation_data.get('successful', 0) / 
                           max(1, operation_data.get('total_requested', 1))) * 100,
            'error_rate': (len(operation_data.get('errors', [])) / 
                         max(1, operation_data.get('total_requested', 1))) * 100,
            'most_common_error': self._get_most_common_error(operation_data.get('errors', []))
        }
    
    def _get_correlation_strength(self, coefficient: float) -> str:
        """Get correlation strength description"""
        abs_coeff = abs(coefficient)
        
        if abs_coeff >= 0.9:
            return 'very_strong'
        elif abs_coeff >= 0.7:
            return 'strong'
        elif abs_coeff >= 0.5:
            return 'moderate'
        elif abs_coeff >= 0.3:
            return 'weak'
        else:
            return 'very_weak'
    
    def _get_most_common_error(self, errors: List[Dict[str, Any]]) -> str:
        """Get most common error message"""
        if not errors:
            return None
        
        error_counts = {}
        for error in errors:
            error_msg = error.get('error', 'Unknown error')
            error_counts[error_msg] = error_counts.get(error_msg, 0) + 1
        
        return max(error_counts, key=error_counts.get) if error_counts else None
    
    def create_paginated_response(self, data: List[Dict[str, Any]], 
                                 total_count: int, 
                                 page: int, 
                                 per_page: int) -> Dict[str, Any]:
        """Create paginated response"""
        return {
            'data': data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_count': total_count,
                'total_pages': (total_count + per_page - 1) // per_page,
                'has_next': page * per_page < total_count,
                'has_previous': page > 1
            }
        }
    
    def create_streaming_response(self, data: Dict[str, Any], 
                                 chunk_id: str = None) -> Dict[str, Any]:
        """Create streaming response format"""
        response = {
            'timestamp': self._format_datetime(datetime.utcnow()),
            'data': data
        }
        
        if chunk_id:
            response['chunk_id'] = chunk_id
        
        return response
