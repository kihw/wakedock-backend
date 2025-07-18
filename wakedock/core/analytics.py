"""
Advanced Analytics Service for WakeDock
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import json
import time
from collections import defaultdict, deque
import statistics

logger = logging.getLogger(__name__)


class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class EventType(Enum):
    USER_ACTION = "user_action"
    SYSTEM_EVENT = "system_event"
    PERFORMANCE = "performance"
    ERROR = "error"
    API_CALL = "api_call"


@dataclass
class MetricPoint:
    """Single metric data point"""
    timestamp: float
    value: Union[int, float]
    labels: Dict[str, str] = None
    
    def __post_init__(self):
        if self.labels is None:
            self.labels = {}


@dataclass
class Event:
    """Analytics event"""
    id: str
    type: EventType
    name: str
    timestamp: float
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    properties: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.properties is None:
            self.properties = {}


@dataclass
class PerformanceMetrics:
    """Performance metrics structure"""
    response_time: float
    cpu_usage: float
    memory_usage: float
    disk_io: float
    network_io: float
    error_rate: float
    throughput: float
    availability: float


class AnalyticsService:
    """
    Advanced analytics service for collecting, processing, and analyzing metrics
    """
    
    def __init__(self, retention_days: int = 30):
        self.retention_days = retention_days
        self.metrics: Dict[str, List[MetricPoint]] = defaultdict(list)
        self.events: List[Event] = []
        self.performance_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.user_sessions: Dict[str, Dict[str, Any]] = {}
        self.api_metrics: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.feature_usage: Dict[str, int] = defaultdict(int)
        self.real_time_metrics: Dict[str, Any] = {}
        self.alerts: List[Dict[str, Any]] = []
        self.cleanup_task = None
        
        # Don't start background tasks during initialization
        # They will be started when the service is properly initialized
    
    async def initialize(self) -> None:
        """Initialize analytics service"""
        logger.info("Initializing analytics service")
        await self.cleanup_old_data()
        await self.calculate_baseline_metrics()
        # Start background tasks after initialization
        self.start_background_tasks()
        logger.info("Analytics service initialized")
    
    def start_background_tasks(self) -> None:
        """Start background tasks for analytics processing"""
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self.periodic_cleanup())
    
    async def periodic_cleanup(self) -> None:
        """Periodic cleanup of old data"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self.cleanup_old_data()
                await self.calculate_baseline_metrics()
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
    
    async def cleanup_old_data(self) -> None:
        """Clean up old analytics data"""
        cutoff_time = time.time() - (self.retention_days * 24 * 3600)
        
        # Clean up metrics
        for metric_name in list(self.metrics.keys()):
            self.metrics[metric_name] = [
                point for point in self.metrics[metric_name]
                if point.timestamp > cutoff_time
            ]
            if not self.metrics[metric_name]:
                del self.metrics[metric_name]
        
        # Clean up events
        self.events = [
            event for event in self.events
            if event.timestamp > cutoff_time
        ]
        
        logger.info(f"Cleaned up analytics data older than {self.retention_days} days")
    
    async def calculate_baseline_metrics(self) -> None:
        """Calculate baseline metrics for anomaly detection"""
        try:
            # Calculate average response times
            response_times = []
            for points in self.performance_data.values():
                response_times.extend([p.get('response_time', 0) for p in points])
            
            if response_times:
                baseline_response_time = statistics.mean(response_times)
                self.real_time_metrics['baseline_response_time'] = baseline_response_time
        except Exception as e:
            logger.error(f"Error calculating baseline metrics: {e}")
    
    async def record_metric(self, name: str, value: Union[int, float], 
                          metric_type: MetricType = MetricType.GAUGE,
                          labels: Dict[str, str] = None) -> None:
        """Record a metric point"""
        try:
            point = MetricPoint(
                timestamp=time.time(),
                value=value,
                labels=labels or {}
            )
            
            self.metrics[name].append(point)
            
            # Update real-time metrics
            await self.update_real_time_metrics(name, value, metric_type)
            
            # Check for anomalies
            await self.check_anomalies(name, value)
            
        except Exception as e:
            logger.error(f"Error recording metric {name}: {e}")
    
    async def update_real_time_metrics(self, name: str, value: Union[int, float], 
                                     metric_type: MetricType) -> None:
        """Update real-time metrics"""
        try:
            if metric_type == MetricType.COUNTER:
                self.real_time_metrics[f"{name}_total"] = self.real_time_metrics.get(f"{name}_total", 0) + value
            elif metric_type == MetricType.GAUGE:
                self.real_time_metrics[name] = value
            elif metric_type == MetricType.HISTOGRAM:
                hist_data = self.real_time_metrics.get(f"{name}_histogram", [])
                hist_data.append(value)
                if len(hist_data) > 100:  # Keep last 100 values
                    hist_data = hist_data[-100:]
                self.real_time_metrics[f"{name}_histogram"] = hist_data
        except Exception as e:
            logger.error(f"Error updating real-time metrics: {e}")
    
    async def check_anomalies(self, name: str, value: Union[int, float]) -> None:
        """Check for anomalies in metrics"""
        try:
            # Simple anomaly detection based on recent data
            recent_points = [p.value for p in self.metrics[name][-50:]]  # Last 50 points
            
            if len(recent_points) >= 10:
                mean_val = statistics.mean(recent_points)
                std_dev = statistics.stdev(recent_points)
                
                # Check if current value is more than 2 standard deviations away
                if abs(value - mean_val) > 2 * std_dev:
                    await self.create_alert(
                        f"Anomaly detected in {name}",
                        f"Value {value} is significantly different from recent average {mean_val:.2f}",
                        "warning"
                    )
        except Exception as e:
            logger.error(f"Error checking anomalies: {e}")
    
    async def record_event(self, event: Event) -> None:
        """Record an analytics event"""
        try:
            self.events.append(event)
            
            # Update feature usage
            if event.type == EventType.USER_ACTION:
                self.feature_usage[event.name] += 1
            
            # Update error counts
            if event.type == EventType.ERROR:
                self.error_counts[event.name] += 1
            
            # Update session data
            if event.session_id:
                await self.update_session_data(event)
            
        except Exception as e:
            logger.error(f"Error recording event: {e}")
    
    async def update_session_data(self, event: Event) -> None:
        """Update session data based on event"""
        try:
            session_id = event.session_id
            
            if session_id not in self.user_sessions:
                self.user_sessions[session_id] = {
                    'start_time': event.timestamp,
                    'last_activity': event.timestamp,
                    'user_id': event.user_id,
                    'events': 0,
                    'pages_visited': set(),
                    'actions': []
                }
            
            session = self.user_sessions[session_id]
            session['last_activity'] = event.timestamp
            session['events'] += 1
            session['actions'].append({
                'name': event.name,
                'timestamp': event.timestamp,
                'properties': event.properties
            })
            
            # Track page visits
            if event.name == 'page_view':
                page = event.properties.get('page', '')
                session['pages_visited'].add(page)
                
        except Exception as e:
            logger.error(f"Error updating session data: {e}")
    
    async def record_api_call(self, endpoint: str, method: str, status_code: int, 
                            response_time: float, user_id: Optional[str] = None) -> None:
        """Record API call metrics"""
        try:
            # Record basic metrics
            await self.record_metric(f"api_response_time_{endpoint}", response_time, MetricType.HISTOGRAM)
            await self.record_metric(f"api_calls_{endpoint}", 1, MetricType.COUNTER)
            await self.record_metric(f"api_status_{status_code}", 1, MetricType.COUNTER)
            
            # Update API metrics
            if endpoint not in self.api_metrics:
                self.api_metrics[endpoint] = {
                    'total_calls': 0,
                    'total_response_time': 0,
                    'status_codes': defaultdict(int),
                    'error_count': 0
                }
            
            api_data = self.api_metrics[endpoint]
            api_data['total_calls'] += 1
            api_data['total_response_time'] += response_time
            api_data['status_codes'][status_code] += 1
            
            if status_code >= 400:
                api_data['error_count'] += 1
            
            # Record API event
            event = Event(
                id=f"api_{endpoint}_{int(time.time() * 1000)}",
                type=EventType.API_CALL,
                name=f"{method} {endpoint}",
                timestamp=time.time(),
                user_id=user_id,
                properties={
                    'method': method,
                    'endpoint': endpoint,
                    'status_code': status_code,
                    'response_time': response_time
                }
            )
            await self.record_event(event)
            
        except Exception as e:
            logger.error(f"Error recording API call: {e}")
    
    async def record_performance_metrics(self, metrics: PerformanceMetrics) -> None:
        """Record performance metrics"""
        try:
            timestamp = time.time()
            
            # Record individual metrics
            await self.record_metric("cpu_usage", metrics.cpu_usage)
            await self.record_metric("memory_usage", metrics.memory_usage)
            await self.record_metric("disk_io", metrics.disk_io)
            await self.record_metric("network_io", metrics.network_io)
            await self.record_metric("error_rate", metrics.error_rate)
            await self.record_metric("throughput", metrics.throughput)
            await self.record_metric("availability", metrics.availability)
            
            # Store for performance analysis
            perf_data = {
                'timestamp': timestamp,
                'response_time': metrics.response_time,
                'cpu_usage': metrics.cpu_usage,
                'memory_usage': metrics.memory_usage,
                'disk_io': metrics.disk_io,
                'network_io': metrics.network_io,
                'error_rate': metrics.error_rate,
                'throughput': metrics.throughput,
                'availability': metrics.availability
            }
            
            self.performance_data['system'].append(perf_data)
            
        except Exception as e:
            logger.error(f"Error recording performance metrics: {e}")
    
    async def create_alert(self, title: str, message: str, level: str = "info") -> None:
        """Create an analytics alert"""
        try:
            alert = {
                'id': f"alert_{int(time.time() * 1000)}",
                'title': title,
                'message': message,
                'level': level,
                'timestamp': time.time(),
                'acknowledged': False
            }
            
            self.alerts.append(alert)
            
            # Keep only last 100 alerts
            if len(self.alerts) > 100:
                self.alerts = self.alerts[-100:]
                
            logger.info(f"Analytics alert created: {title}")
            
        except Exception as e:
            logger.error(f"Error creating alert: {e}")
    
    async def get_metrics(self, name: Optional[str] = None, 
                        start_time: Optional[float] = None,
                        end_time: Optional[float] = None) -> Dict[str, Any]:
        """Get metrics data"""
        try:
            if name:
                points = self.metrics.get(name, [])
            else:
                points = []
                for metric_points in self.metrics.values():
                    points.extend(metric_points)
            
            # Filter by time range
            if start_time or end_time:
                filtered_points = []
                for point in points:
                    if start_time and point.timestamp < start_time:
                        continue
                    if end_time and point.timestamp > end_time:
                        continue
                    filtered_points.append(point)
                points = filtered_points
            
            return {
                'name': name,
                'points': [asdict(point) for point in points],
                'count': len(points),
                'start_time': start_time,
                'end_time': end_time
            }
            
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return {}
    
    async def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        try:
            system_data = list(self.performance_data['system'])
            
            if not system_data:
                return {}
            
            # Calculate averages
            avg_response_time = statistics.mean([d['response_time'] for d in system_data])
            avg_cpu = statistics.mean([d['cpu_usage'] for d in system_data])
            avg_memory = statistics.mean([d['memory_usage'] for d in system_data])
            avg_throughput = statistics.mean([d['throughput'] for d in system_data])
            avg_availability = statistics.mean([d['availability'] for d in system_data])
            
            return {
                'average_response_time': avg_response_time,
                'average_cpu_usage': avg_cpu,
                'average_memory_usage': avg_memory,
                'average_throughput': avg_throughput,
                'average_availability': avg_availability,
                'total_data_points': len(system_data),
                'time_range': {
                    'start': min(d['timestamp'] for d in system_data),
                    'end': max(d['timestamp'] for d in system_data)
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {}
    
    async def get_user_analytics(self) -> Dict[str, Any]:
        """Get user analytics"""
        try:
            active_sessions = len(self.user_sessions)
            total_events = len(self.events)
            
            # Calculate session duration
            session_durations = []
            for session in self.user_sessions.values():
                duration = session['last_activity'] - session['start_time']
                session_durations.append(duration)
            
            avg_session_duration = statistics.mean(session_durations) if session_durations else 0
            
            # Most used features
            top_features = sorted(self.feature_usage.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                'active_sessions': active_sessions,
                'total_events': total_events,
                'average_session_duration': avg_session_duration,
                'top_features': top_features,
                'total_errors': sum(self.error_counts.values()),
                'error_breakdown': dict(self.error_counts)
            }
            
        except Exception as e:
            logger.error(f"Error getting user analytics: {e}")
            return {}
    
    async def get_api_analytics(self) -> Dict[str, Any]:
        """Get API analytics"""
        try:
            total_calls = sum(data['total_calls'] for data in self.api_metrics.values())
            total_errors = sum(data['error_count'] for data in self.api_metrics.values())
            
            # Calculate average response time per endpoint
            endpoint_stats = []
            for endpoint, data in self.api_metrics.items():
                avg_response_time = data['total_response_time'] / data['total_calls']
                error_rate = (data['error_count'] / data['total_calls']) * 100
                
                endpoint_stats.append({
                    'endpoint': endpoint,
                    'total_calls': data['total_calls'],
                    'average_response_time': avg_response_time,
                    'error_rate': error_rate,
                    'status_codes': dict(data['status_codes'])
                })
            
            # Sort by most called endpoints
            endpoint_stats.sort(key=lambda x: x['total_calls'], reverse=True)
            
            return {
                'total_api_calls': total_calls,
                'total_errors': total_errors,
                'overall_error_rate': (total_errors / total_calls * 100) if total_calls > 0 else 0,
                'endpoint_stats': endpoint_stats[:20]  # Top 20 endpoints
            }
            
        except Exception as e:
            logger.error(f"Error getting API analytics: {e}")
            return {}
    
    async def get_real_time_metrics(self) -> Dict[str, Any]:
        """Get real-time metrics"""
        try:
            return {
                'timestamp': time.time(),
                'metrics': dict(self.real_time_metrics),
                'active_sessions': len(self.user_sessions),
                'recent_events': len([e for e in self.events if e.timestamp > time.time() - 300]),  # Last 5 minutes
                'alerts': [a for a in self.alerts if not a['acknowledged']]
            }
            
        except Exception as e:
            logger.error(f"Error getting real-time metrics: {e}")
            return {}
    
    async def get_alerts(self, acknowledged: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Get alerts"""
        try:
            alerts = self.alerts
            
            if acknowledged is not None:
                alerts = [a for a in alerts if a['acknowledged'] == acknowledged]
            
            return sorted(alerts, key=lambda x: x['timestamp'], reverse=True)
            
        except Exception as e:
            logger.error(f"Error getting alerts: {e}")
            return []
    
    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        try:
            for alert in self.alerts:
                if alert['id'] == alert_id:
                    alert['acknowledged'] = True
                    return True
            return False
            
        except Exception as e:
            logger.error(f"Error acknowledging alert: {e}")
            return False
    
    async def export_analytics_data(self, start_time: Optional[float] = None,
                                  end_time: Optional[float] = None,
                                  format: str = "json") -> Dict[str, Any]:
        """Export analytics data"""
        try:
            export_data = {
                'export_timestamp': time.time(),
                'start_time': start_time,
                'end_time': end_time,
                'format': format,
                'data': {
                    'metrics': {},
                    'events': [],
                    'performance': list(self.performance_data['system']),
                    'user_analytics': await self.get_user_analytics(),
                    'api_analytics': await self.get_api_analytics(),
                    'alerts': self.alerts
                }
            }
            
            # Export metrics
            for name, points in self.metrics.items():
                filtered_points = points
                if start_time or end_time:
                    filtered_points = [
                        p for p in points
                        if (not start_time or p.timestamp >= start_time) and
                           (not end_time or p.timestamp <= end_time)
                    ]
                export_data['data']['metrics'][name] = [asdict(p) for p in filtered_points]
            
            # Export events
            filtered_events = self.events
            if start_time or end_time:
                filtered_events = [
                    e for e in self.events
                    if (not start_time or e.timestamp >= start_time) and
                       (not end_time or e.timestamp <= end_time)
                ]
            export_data['data']['events'] = [asdict(e) for e in filtered_events]
            
            return export_data
            
        except Exception as e:
            logger.error(f"Error exporting analytics data: {e}")
            return {}
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics"""
        try:
            current_time = time.time()
            
            # Check recent performance data
            recent_data = [
                d for d in self.performance_data['system']
                if d['timestamp'] > current_time - 300  # Last 5 minutes
            ]
            
            if not recent_data:
                return {'status': 'unknown', 'message': 'No recent performance data'}
            
            # Calculate health indicators
            avg_cpu = statistics.mean([d['cpu_usage'] for d in recent_data])
            avg_memory = statistics.mean([d['memory_usage'] for d in recent_data])
            avg_error_rate = statistics.mean([d['error_rate'] for d in recent_data])
            avg_availability = statistics.mean([d['availability'] for d in recent_data])
            
            # Determine health status
            health_score = 100
            issues = []
            
            if avg_cpu > 80:
                health_score -= 20
                issues.append("High CPU usage")
            
            if avg_memory > 85:
                health_score -= 20
                issues.append("High memory usage")
            
            if avg_error_rate > 5:
                health_score -= 25
                issues.append("High error rate")
            
            if avg_availability < 95:
                health_score -= 30
                issues.append("Low availability")
            
            if health_score >= 80:
                status = "healthy"
            elif health_score >= 60:
                status = "warning"
            else:
                status = "critical"
            
            return {
                'status': status,
                'health_score': health_score,
                'issues': issues,
                'metrics': {
                    'cpu_usage': avg_cpu,
                    'memory_usage': avg_memory,
                    'error_rate': avg_error_rate,
                    'availability': avg_availability
                },
                'timestamp': current_time
            }
            
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {'status': 'error', 'message': str(e)}


# Global analytics service instance
analytics_service = AnalyticsService()