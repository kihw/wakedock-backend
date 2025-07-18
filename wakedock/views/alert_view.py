"""
Alert View - Response formatting and presentation logic for alerts
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from wakedock.models.alert import Alert, AlertHistory
from wakedock.repositories.alert_repository import AlertSeverity, AlertStatus

import logging
logger = logging.getLogger(__name__)


class AlertView:
    """View layer for alert response formatting"""
    
    def __init__(self):
        self.severity_colors = {
            AlertSeverity.CRITICAL.value: '#FF0000',
            AlertSeverity.HIGH.value: '#FF8000',
            AlertSeverity.MEDIUM.value: '#FFFF00',
            AlertSeverity.LOW.value: '#00FF00'
        }
        
        self.status_icons = {
            AlertStatus.ACTIVE.value: '🔴',
            AlertStatus.ACKNOWLEDGED.value: '🟡',
            AlertStatus.RESOLVED.value: '🟢',
            AlertStatus.SUPPRESSED.value: '🔵'
        }
    
    async def alert_response(self, alert: Alert, history: List[AlertHistory] = None) -> Dict[str, Any]:
        """Format single alert response"""
        try:
            # Calculate alert age
            age_seconds = (datetime.utcnow() - alert.created_at).total_seconds()
            age_human = self._format_duration(age_seconds)
            
            # Format base response
            response = {
                'id': alert.id,
                'rule_id': alert.rule_id,
                'title': alert.title,
                'description': alert.description,
                'severity': alert.severity,
                'status': alert.status,
                'metric_name': alert.metric_name,
                'metric_value': alert.metric_value,
                'threshold': alert.threshold,
                'operator': alert.operator,
                'container_id': alert.container_id,
                'service_id': alert.service_id,
                'node_id': alert.node_id,
                'tags': alert.tags or {},
                'metadata': alert.metadata or {},
                'created_at': alert.created_at.isoformat(),
                'updated_at': alert.updated_at.isoformat(),
                'age': {
                    'seconds': int(age_seconds),
                    'human': age_human
                },
                'ui': {
                    'color': self.severity_colors.get(alert.severity, '#808080'),
                    'icon': self.status_icons.get(alert.status, '❓'),
                    'severity_label': alert.severity.upper(),
                    'status_label': alert.status.replace('_', ' ').title()
                }
            }
            
            # Add resolution information if resolved
            if alert.status == AlertStatus.RESOLVED.value and alert.resolved_at:
                response['resolved_at'] = alert.resolved_at.isoformat()
                response['resolved_by'] = alert.resolved_by
                response['resolution_note'] = alert.resolution_note
                
                # Calculate resolution time
                resolution_time = (alert.resolved_at - alert.created_at).total_seconds()
                response['resolution_time'] = {
                    'seconds': int(resolution_time),
                    'human': self._format_duration(resolution_time)
                }
            
            # Add acknowledgment information if acknowledged
            if alert.status == AlertStatus.ACKNOWLEDGED.value and alert.acknowledged_at:
                response['acknowledged_at'] = alert.acknowledged_at.isoformat()
                response['acknowledged_by'] = alert.acknowledged_by
                
                # Calculate acknowledgment time
                ack_time = (alert.acknowledged_at - alert.created_at).total_seconds()
                response['acknowledgment_time'] = {
                    'seconds': int(ack_time),
                    'human': self._format_duration(ack_time)
                }
            
            # Add history if provided
            if history:
                response['history'] = [
                    await self._format_history_entry(entry) for entry in history
                ]
                response['history_count'] = len(history)
            
            return response
            
        except Exception as e:
            logger.error(f"Error formatting alert response: {str(e)}")
            return {'error': 'Failed to format alert response'}
    
    async def alerts_list_response(self, alerts: List[Alert], total_count: int, limit: int, offset: int, has_more: bool, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Format alerts list response"""
        try:
            # Format individual alerts
            formatted_alerts = []
            for alert in alerts:
                formatted_alert = await self.alert_response(alert)
                formatted_alerts.append(formatted_alert)
            
            # Calculate summary statistics
            summary = await self._calculate_alerts_summary(alerts)
            
            return {
                'alerts': formatted_alerts,
                'pagination': {
                    'total_count': total_count,
                    'limit': limit,
                    'offset': offset,
                    'has_more': has_more,
                    'current_page': (offset // limit) + 1 if limit > 0 else 1,
                    'total_pages': (total_count + limit - 1) // limit if limit > 0 else 1
                },
                'summary': summary,
                'filters': filters or {},
                'retrieved_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error formatting alerts list response: {str(e)}")
            return {'error': 'Failed to format alerts list response'}
    
    async def alert_creation_response(self, alert: Alert, notifications_sent: bool = False) -> Dict[str, Any]:
        """Format alert creation response"""
        try:
            base_response = await self.alert_response(alert)
            
            return {
                'alert': base_response,
                'created': True,
                'notifications_sent': notifications_sent,
                'message': f"Alert '{alert.title}' created successfully",
                'created_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error formatting alert creation response: {str(e)}")
            return {'error': 'Failed to format alert creation response'}
    
    async def alert_update_response(self, alert: Alert, updated_fields: List[str] = None) -> Dict[str, Any]:
        """Format alert update response"""
        try:
            base_response = await self.alert_response(alert)
            
            return {
                'alert': base_response,
                'updated': True,
                'updated_fields': updated_fields or [],
                'message': f"Alert '{alert.title}' updated successfully",
                'updated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error formatting alert update response: {str(e)}")
            return {'error': 'Failed to format alert update response'}
    
    async def alert_operation_response(self, alert: Alert, operation: str, success: bool, user_id: str = None, note: str = None) -> Dict[str, Any]:
        """Format alert operation response"""
        try:
            base_response = await self.alert_response(alert)
            
            response = {
                'alert': base_response,
                'operation': operation,
                'success': success,
                'message': f"Alert '{alert.title}' {operation} {'successfully' if success else 'failed'}",
                'performed_at': datetime.utcnow().isoformat()
            }
            
            if user_id:
                response['performed_by'] = user_id
            
            if note:
                response['note'] = note
            
            return response
            
        except Exception as e:
            logger.error(f"Error formatting alert operation response: {str(e)}")
            return {'error': 'Failed to format alert operation response'}
    
    async def alert_search_response(self, alerts: List[Alert], query: str, filters: Dict[str, Any], total_count: int, limit: int, offset: int) -> Dict[str, Any]:
        """Format alert search response"""
        try:
            # Format alerts
            formatted_alerts = []
            for alert in alerts:
                formatted_alert = await self.alert_response(alert)
                formatted_alerts.append(formatted_alert)
            
            # Calculate search summary
            search_summary = await self._calculate_search_summary(alerts, query, filters)
            
            return {
                'alerts': formatted_alerts,
                'search': {
                    'query': query,
                    'filters': filters,
                    'total_results': total_count,
                    'returned_results': len(alerts),
                    'search_time': datetime.utcnow().isoformat()
                },
                'pagination': {
                    'total_count': total_count,
                    'limit': limit,
                    'offset': offset,
                    'has_more': offset + len(alerts) < total_count
                },
                'summary': search_summary
            }
            
        except Exception as e:
            logger.error(f"Error formatting alert search response: {str(e)}")
            return {'error': 'Failed to format alert search response'}
    
    async def alert_statistics_response(self, database_stats: Dict[str, Any], service_stats: Dict[str, Any], critical_alerts: List[Alert]) -> Dict[str, Any]:
        """Format alert statistics response"""
        try:
            # Format critical alerts
            formatted_critical = []
            for alert in critical_alerts:
                formatted_alert = await self.alert_response(alert)
                formatted_critical.append(formatted_alert)
            
            # Calculate additional metrics
            metrics = await self._calculate_statistics_metrics(database_stats, service_stats)
            
            return {
                'overview': {
                    'total_alerts': database_stats.get('total_alerts', 0),
                    'active_alerts': database_stats.get('active_alerts', 0),
                    'recent_alerts': database_stats.get('recent_alerts', 0),
                    'critical_alerts_count': len(critical_alerts)
                },
                'distribution': {
                    'severity': database_stats.get('severity_distribution', {}),
                    'status': database_stats.get('status_distribution', {})
                },
                'metrics': metrics,
                'critical_alerts': formatted_critical,
                'service_stats': service_stats,
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error formatting alert statistics response: {str(e)}")
            return {'error': 'Failed to format alert statistics response'}
    
    async def alert_trends_response(self, trends: Dict[str, Any], metrics: Dict[str, Any], period: int) -> Dict[str, Any]:
        """Format alert trends response"""
        try:
            # Format trend data for visualization
            daily_trends = trends.get('daily_trends', {})
            severity_trends = trends.get('severity_trends', {})
            
            # Prepare chart data
            chart_data = await self._prepare_chart_data(daily_trends, severity_trends)
            
            return {
                'trends': {
                    'daily': daily_trends,
                    'severity': severity_trends,
                    'period_days': period
                },
                'metrics': metrics,
                'charts': chart_data,
                'analysis': {
                    'trend_direction': metrics.get('trend_direction', 'unknown'),
                    'total_alerts': metrics.get('total_alerts', 0),
                    'daily_average': round(metrics.get('avg_daily', 0), 2),
                    'peak_day': await self._find_peak_day(daily_trends)
                },
                'generated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error formatting alert trends response: {str(e)}")
            return {'error': 'Failed to format alert trends response'}
    
    async def alert_health_response(self, health_data: Dict[str, Any]) -> Dict[str, Any]:
        """Format alert system health response"""
        try:
            system_health = health_data.get('system_health', 'unknown')
            test_results = health_data.get('test_results', {})
            
            # Calculate health score
            health_score = await self._calculate_health_score(test_results)
            
            return {
                'health': {
                    'status': system_health,
                    'score': health_score,
                    'message': self._get_health_message(system_health, health_score)
                },
                'components': {
                    'database': {
                        'status': 'healthy' if test_results.get('database_connection') else 'unhealthy',
                        'tested': test_results.get('database_connection', False)
                    },
                    'alert_creation': {
                        'status': 'healthy' if test_results.get('alert_creation') else 'unhealthy',
                        'tested': test_results.get('alert_creation', False)
                    },
                    'notifications': {
                        'status': 'healthy' if test_results.get('notification_service') else 'unhealthy',
                        'tested': test_results.get('notification_service', False)
                    },
                    'processing': {
                        'status': 'healthy' if test_results.get('alert_processing') else 'unhealthy',
                        'tested': test_results.get('alert_processing', False)
                    }
                },
                'tested_at': health_data.get('tested_at'),
                'next_check': (datetime.utcnow() + timedelta(minutes=5)).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error formatting alert health response: {str(e)}")
            return {'error': 'Failed to format alert health response'}
    
    async def alert_bulk_operation_response(self, operation: str, alert_ids: List[str], results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Format bulk operation response"""
        try:
            successful_operations = [r for r in results if r.get('success')]
            failed_operations = [r for r in results if not r.get('success')]
            
            return {
                'operation': operation,
                'summary': {
                    'total_requested': len(alert_ids),
                    'successful': len(successful_operations),
                    'failed': len(failed_operations),
                    'success_rate': len(successful_operations) / len(alert_ids) if alert_ids else 0
                },
                'results': results,
                'message': f"Bulk {operation} completed: {len(successful_operations)} successful, {len(failed_operations)} failed",
                'performed_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error formatting bulk operation response: {str(e)}")
            return {'error': 'Failed to format bulk operation response'}
    
    async def _format_history_entry(self, entry: AlertHistory) -> Dict[str, Any]:
        """Format single history entry"""
        return {
            'id': entry.id,
            'action': entry.action,
            'user_id': entry.user_id,
            'details': entry.details or {},
            'created_at': entry.created_at.isoformat(),
            'age': self._format_duration((datetime.utcnow() - entry.created_at).total_seconds())
        }
    
    async def _calculate_alerts_summary(self, alerts: List[Alert]) -> Dict[str, Any]:
        """Calculate summary statistics for alerts list"""
        if not alerts:
            return {
                'total_alerts': 0,
                'severity_breakdown': {},
                'status_breakdown': {},
                'avg_age': 0
            }
        
        severity_counts = {}
        status_counts = {}
        ages = []
        
        for alert in alerts:
            # Count by severity
            severity_counts[alert.severity] = severity_counts.get(alert.severity, 0) + 1
            
            # Count by status
            status_counts[alert.status] = status_counts.get(alert.status, 0) + 1
            
            # Calculate age
            age = (datetime.utcnow() - alert.created_at).total_seconds()
            ages.append(age)
        
        avg_age = sum(ages) / len(ages) if ages else 0
        
        return {
            'total_alerts': len(alerts),
            'severity_breakdown': severity_counts,
            'status_breakdown': status_counts,
            'avg_age': {
                'seconds': int(avg_age),
                'human': self._format_duration(avg_age)
            }
        }
    
    async def _calculate_search_summary(self, alerts: List[Alert], query: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate search summary statistics"""
        base_summary = await self._calculate_alerts_summary(alerts)
        
        return {
            **base_summary,
            'search_query': query,
            'filters_applied': len(filters),
            'filter_details': filters
        }
    
    async def _calculate_statistics_metrics(self, database_stats: Dict[str, Any], service_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate additional metrics for statistics"""
        total_alerts = database_stats.get('total_alerts', 0)
        active_alerts = database_stats.get('active_alerts', 0)
        recent_alerts = database_stats.get('recent_alerts', 0)
        
        return {
            'active_percentage': (active_alerts / total_alerts * 100) if total_alerts > 0 else 0,
            'recent_percentage': (recent_alerts / total_alerts * 100) if total_alerts > 0 else 0,
            'alert_rate': database_stats.get('alert_rate', {}),
            'system_load': 'high' if active_alerts > 100 else 'medium' if active_alerts > 50 else 'low'
        }
    
    async def _prepare_chart_data(self, daily_trends: Dict[str, Any], severity_trends: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare data for chart visualization"""
        # Daily trends chart
        daily_chart = {
            'labels': list(daily_trends.keys()),
            'data': list(daily_trends.values()),
            'type': 'line'
        }
        
        # Severity trends chart
        severity_chart = {
            'labels': [],
            'datasets': []
        }
        
        if severity_trends:
            dates = sorted(severity_trends.keys())
            severity_chart['labels'] = dates
            
            severities = set()
            for date_data in severity_trends.values():
                severities.update(date_data.keys())
            
            for severity in severities:
                data = [severity_trends[date].get(severity, 0) for date in dates]
                severity_chart['datasets'].append({
                    'label': severity.upper(),
                    'data': data,
                    'color': self.severity_colors.get(severity, '#808080')
                })
        
        return {
            'daily_trends': daily_chart,
            'severity_trends': severity_chart
        }
    
    async def _find_peak_day(self, daily_trends: Dict[str, Any]) -> Dict[str, Any]:
        """Find the day with the highest alert count"""
        if not daily_trends:
            return {}
        
        peak_date = max(daily_trends.keys(), key=lambda x: daily_trends[x])
        peak_count = daily_trends[peak_date]
        
        return {
            'date': peak_date,
            'count': peak_count
        }
    
    async def _calculate_health_score(self, test_results: Dict[str, Any]) -> int:
        """Calculate health score based on test results"""
        if not test_results:
            return 0
        
        total_tests = len(test_results)
        passed_tests = sum(1 for result in test_results.values() if result)
        
        return int((passed_tests / total_tests) * 100)
    
    def _get_health_message(self, health_status: str, health_score: int) -> str:
        """Get health message based on status and score"""
        if health_status == 'healthy':
            return f"All systems operational ({health_score}% healthy)"
        elif health_status == 'degraded':
            return f"Some systems experiencing issues ({health_score}% healthy)"
        else:
            return f"System health unknown ({health_score}% healthy)"
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{int(seconds)} seconds"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''}"
