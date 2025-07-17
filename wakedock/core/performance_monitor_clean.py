"""
WakeDock v0.6.2 - Performance Monitoring System
Real-time performance tracking, metrics collection, and optimization insights
"""

import asyncio
import statistics
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union

import psutil

from wakedock.core.cache import CacheNamespace, get_cache_manager
from wakedock.core.logging_config import get_logger

logger = get_logger("performance")


class MetricType(str, Enum):
    """
    Types of performance metrics
    """

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class AlertSeverity(str, Enum):
    """
    Alert severity levels
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PerformanceMetric:
    """
    Performance metric data structure
    """

    name: str
    value: Union[int, float]
    metric_type: MetricType
    timestamp: datetime
    tags: Dict[str, str]
    unit: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "type": self.metric_type.value,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags,
            "unit": self.unit,
        }


@dataclass
class SystemResources:
    """
    System resource metrics
    """

    cpu_percent: float
    memory_percent: float
    memory_used: int
    memory_available: int
    disk_usage_percent: float
    disk_free: int
    network_bytes_sent: int
    network_bytes_recv: int
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class APIPerformance:
    """
    API endpoint performance metrics
    """

    endpoint: str
    method: str
    response_time: float
    status_code: int
    timestamp: datetime
    request_size: Optional[int] = None
    response_size: Optional[int] = None
    user_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PerformanceAlert:
    """
    Performance alert definition
    """

    name: str
    metric_name: str
    threshold_value: float
    comparison_operator: str  # >, <, >=, <=, ==, !=
    severity: AlertSeverity
    message_template: str
    cooldown_seconds: int = 300

    def evaluate(self, metric_value: float) -> bool:
        """
        Evaluate if alert should trigger
        """
        operators = {
            ">": lambda x, y: x > y,
            "<": lambda x, y: x < y,
            ">=": lambda x, y: x >= y,
            "<=": lambda x, y: x <= y,
            "==": lambda x, y: x == y,
            "!=": lambda x, y: x != y,
        }

        op = operators.get(self.comparison_operator)
        if not op:
            return False

        return op(metric_value, self.threshold_value)

    def format_message(self, metric_value: float) -> str:
        """
        Format alert message
        """
        return self.message_template.format(
            metric_name=self.metric_name,
            value=metric_value,
            threshold=self.threshold_value,
        )


class MetricsCollector:
    """
    Collects and aggregates performance metrics
    """

    def __init__(self, retention_hours: int = 24):
        self.retention_hours = retention_hours
        self.metrics_buffer = defaultdict(lambda: deque(maxlen=1000))
        self.aggregated_metrics = defaultdict(dict)
        self.last_system_check = datetime.utcnow()

    async def record_metric(
        self,
        name: str,
        value: Union[int, float],
        metric_type: MetricType,
        tags: Optional[Dict[str, str]] = None,
        unit: Optional[str] = None,
    ):
        """
        Record a performance metric
        """
        metric = PerformanceMetric(
            name=name,
            value=value,
            metric_type=metric_type,
            timestamp=datetime.utcnow(),
            tags=tags or {},
            unit=unit,
        )

        # Add to buffer
        self.metrics_buffer[name].append(metric)

        # Store in cache for real-time access
        cache = await get_cache_manager()
        await cache.set(
            CacheNamespace.METRICS,
            f"current:{name}",
            metric.to_dict(),
            ttl=3600,
            tags=["metrics", "current"],
        )

        logger.debug(f"Recorded metric: {name} = {value} {unit or ''}")

    async def record_api_performance(
        self,
        endpoint: str,
        method: str,
        response_time: float,
        status_code: int,
        request_size: Optional[int] = None,
        response_size: Optional[int] = None,
        user_id: Optional[str] = None,
    ):
        """
        Record API performance metrics
        """
        api_perf = APIPerformance(
            endpoint=endpoint,
            method=method,
            response_time=response_time,
            status_code=status_code,
            timestamp=datetime.utcnow(),
            request_size=request_size,
            response_size=response_size,
            user_id=user_id,
        )

        # Record individual metrics
        await self.record_metric(
            f"api.response_time",
            response_time,
            MetricType.TIMER,
            tags={"endpoint": endpoint, "method": method, "status": str(status_code)},
            unit="ms",
        )

        await self.record_metric(
            f"api.requests",
            1,
            MetricType.COUNTER,
            tags={"endpoint": endpoint, "method": method, "status": str(status_code)},
        )

        if request_size:
            await self.record_metric(
                f"api.request_size",
                request_size,
                MetricType.HISTOGRAM,
                tags={"endpoint": endpoint, "method": method},
                unit="bytes",
            )

        if response_size:
            await self.record_metric(
                f"api.response_size",
                response_size,
                MetricType.HISTOGRAM,
                tags={"endpoint": endpoint, "method": method},
                unit="bytes",
            )

    async def collect_system_metrics(self):
        """
        Collect system resource metrics
        """
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            # Memory usage
            memory = psutil.virtual_memory()

            # Disk usage
            disk = psutil.disk_usage("/")

            # Network stats
            network = psutil.net_io_counters()

            resources = SystemResources(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used=memory.used,
                memory_available=memory.available,
                disk_usage_percent=disk.percent,
                disk_free=disk.free,
                network_bytes_sent=network.bytes_sent,
                network_bytes_recv=network.bytes_recv,
                timestamp=datetime.utcnow(),
            )

            # Record individual metrics
            await self.record_metric(
                "system.cpu_percent", cpu_percent, MetricType.GAUGE, unit="%"
            )
            await self.record_metric(
                "system.memory_percent", memory.percent, MetricType.GAUGE, unit="%"
            )
            await self.record_metric(
                "system.memory_used", memory.used, MetricType.GAUGE, unit="bytes"
            )
            await self.record_metric(
                "system.disk_percent", disk.percent, MetricType.GAUGE, unit="%"
            )
            await self.record_metric(
                "system.network_sent",
                network.bytes_sent,
                MetricType.COUNTER,
                unit="bytes",
            )
            await self.record_metric(
                "system.network_recv",
                network.bytes_recv,
                MetricType.COUNTER,
                unit="bytes",
            )

            # Store aggregated system metrics
            cache = await get_cache_manager()
            await cache.set(
                CacheNamespace.METRICS,
                "system:current",
                resources.to_dict(),
                ttl=60,
                tags=["system", "current"],
            )

            self.last_system_check = datetime.utcnow()

        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")

    async def get_metric_statistics(
        self, metric_name: str, time_window_minutes: int = 60
    ) -> Dict[str, float]:
        """
        Get statistical analysis of a metric
        """
        cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)

        if metric_name not in self.metrics_buffer:
            return {}

        # Filter metrics by time window
        recent_metrics = [
            m for m in self.metrics_buffer[metric_name] if m.timestamp >= cutoff_time
        ]

        if not recent_metrics:
            return {}

        values = [m.value for m in recent_metrics]

        try:
            stats = {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "std_dev": statistics.stdev(values) if len(values) > 1 else 0,
            }

            # Add percentiles
            if len(values) >= 2:
                sorted_values = sorted(values)
                stats.update(
                    {
                        "p50": statistics.median(sorted_values),
                        "p90": sorted_values[int(len(sorted_values) * 0.9)],
                        "p95": sorted_values[int(len(sorted_values) * 0.95)],
                        "p99": sorted_values[int(len(sorted_values) * 0.99)],
                    }
                )

            return stats

        except Exception as e:
            logger.error(f"Failed to calculate statistics for {metric_name}: {e}")
            return {}

    async def get_trending_metrics(
        self, time_window_minutes: int = 60
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get trending analysis for all metrics
        """
        trending = {}

        for metric_name in self.metrics_buffer.keys():
            stats = await self.get_metric_statistics(metric_name, time_window_minutes)
            if stats:
                trending[metric_name] = stats

        return trending

    def cleanup_old_metrics(self):
        """
        Clean up old metrics beyond retention period
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=self.retention_hours)

        for metric_name, metrics in self.metrics_buffer.items():
            # Remove old metrics
            while metrics and metrics[0].timestamp < cutoff_time:
                metrics.popleft()


class AlertManager:
    """
    Manages performance alerts and notifications
    """

    def __init__(self):
        self.alerts = []
        self.alert_history = deque(maxlen=1000)
        self.alert_cooldowns = {}

    def add_alert(self, alert: PerformanceAlert):
        """
        Add a performance alert
        """
        self.alerts.append(alert)
        logger.info(f"Added performance alert: {alert.name}")

    async def check_alerts(self, metrics_collector: MetricsCollector):
        """
        Check all alerts against current metrics
        """
        current_time = datetime.utcnow()

        for alert in self.alerts:
            # Check cooldown
            cooldown_key = f"{alert.name}:{alert.metric_name}"
            if cooldown_key in self.alert_cooldowns:
                cooldown_end = self.alert_cooldowns[cooldown_key]
                if current_time < cooldown_end:
                    continue

            # Get current metric value
            cache = await get_cache_manager()
            current_metric = await cache.get(
                CacheNamespace.METRICS, f"current:{alert.metric_name}"
            )

            if not current_metric:
                continue

            metric_value = current_metric.get("value")
            if metric_value is None:
                continue

            # Evaluate alert condition
            if alert.evaluate(metric_value):
                await self._trigger_alert(alert, metric_value, current_time)

                # Set cooldown
                self.alert_cooldowns[cooldown_key] = current_time + timedelta(
                    seconds=alert.cooldown_seconds
                )

    async def _trigger_alert(
        self, alert: PerformanceAlert, metric_value: float, timestamp: datetime
    ):
        """
        Trigger an alert
        """
        alert_data = {
            "alert_name": alert.name,
            "metric_name": alert.metric_name,
            "metric_value": metric_value,
            "threshold": alert.threshold_value,
            "severity": alert.severity.value,
            "message": alert.format_message(metric_value),
            "timestamp": timestamp.isoformat(),
        }

        # Store alert in history
        self.alert_history.append(alert_data)

        # Cache alert for real-time access
        cache = await get_cache_manager()
        await cache.set(
            CacheNamespace.METRICS,
            f"alert:{alert.name}:{int(timestamp.timestamp())}",
            alert_data,
            ttl=86400,  # 24 hours
            tags=["alerts", alert.severity.value],
        )

        logger.warning(f"Performance alert triggered: {alert_data['message']}")

        # TODO: Send notification (email, webhook, etc.)

    def get_recent_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get recent alerts
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        return [
            alert
            for alert in self.alert_history
            if datetime.fromisoformat(alert["timestamp"]) >= cutoff_time
        ]


class PerformanceMonitor:
    """
    Main performance monitoring system
    """

    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager()
        self.monitoring_active = False
        self._monitoring_task = None

        # Setup default alerts
        self._setup_default_alerts()

    def _setup_default_alerts(self):
        """
        Setup default performance alerts
        """
        default_alerts = [
            PerformanceAlert(
                name="high_cpu_usage",
                metric_name="system.cpu_percent",
                threshold_value=85.0,
                comparison_operator=">",
                severity=AlertSeverity.HIGH,
                message_template="High CPU usage detected: {value:.1f}% (threshold: {threshold}%)",
            ),
            PerformanceAlert(
                name="high_memory_usage",
                metric_name="system.memory_percent",
                threshold_value=90.0,
                comparison_operator=">",
                severity=AlertSeverity.HIGH,
                message_template="High memory usage detected: {value:.1f}% (threshold: {threshold}%)",
            ),
            PerformanceAlert(
                name="slow_api_response",
                metric_name="api.response_time",
                threshold_value=5000.0,  # 5 seconds
                comparison_operator=">",
                severity=AlertSeverity.MEDIUM,
                message_template="Slow API response detected: {value:.0f}ms (threshold: {threshold}ms)",
            ),
            PerformanceAlert(
                name="high_disk_usage",
                metric_name="system.disk_percent",
                threshold_value=85.0,
                comparison_operator=">",
                severity=AlertSeverity.MEDIUM,
                message_template="High disk usage detected: {value:.1f}% (threshold: {threshold}%)",
            ),
        ]

        for alert in default_alerts:
            self.alert_manager.add_alert(alert)

    async def start_monitoring(self, interval_seconds: int = 30):
        """
        Start continuous performance monitoring
        """
        if self.monitoring_active:
            return

        self.monitoring_active = True
        self._monitoring_task = asyncio.create_task(
            self._monitoring_loop(interval_seconds)
        )

        logger.info(f"Performance monitoring started (interval: {interval_seconds}s)")

    async def stop_monitoring(self):
        """
        Stop performance monitoring
        """
        self.monitoring_active = False

        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("Performance monitoring stopped")

    async def _monitoring_loop(self, interval_seconds: int):
        """
        Main monitoring loop
        """
        while self.monitoring_active:
            try:
                # Collect system metrics
                await self.metrics_collector.collect_system_metrics()

                # Check alerts
                await self.alert_manager.check_alerts(self.metrics_collector)

                # Cleanup old metrics
                self.metrics_collector.cleanup_old_metrics()

                await asyncio.sleep(interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval_seconds)

    async def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data
        """
        try:
            # Get current system metrics
            cache = await get_cache_manager()
            system_metrics = await cache.get(CacheNamespace.METRICS, "system:current")

            # Get trending metrics
            trending = await self.metrics_collector.get_trending_metrics(60)

            # Get recent alerts
            recent_alerts = self.alert_manager.get_recent_alerts(24)

            # Get cache performance
            cache_stats = await cache.get_stats()

            return {
                "system_resources": system_metrics,
                "trending_metrics": trending,
                "recent_alerts": recent_alerts,
                "cache_performance": cache_stats,
                "monitoring_status": {
                    "active": self.monitoring_active,
                    "last_check": self.metrics_collector.last_system_check.isoformat(),
                    "alerts_configured": len(self.alert_manager.alerts),
                },
            }

        except Exception as e:
            logger.error(f"Failed to get dashboard data: {e}")
            return {}


# Global performance monitor instance
performance_monitor: Optional[PerformanceMonitor] = None


async def get_performance_monitor() -> PerformanceMonitor:
    """
    Get or create global performance monitor
    """
    global performance_monitor
    if performance_monitor is None:
        performance_monitor = PerformanceMonitor()
    return performance_monitor


# Decorator for automatic performance tracking
def track_performance(metric_name: Optional[str] = None, include_args: bool = False):
    """
    Decorator for tracking function performance
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            monitor = await get_performance_monitor()
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)

                execution_time = (time.time() - start_time) * 1000  # Convert to ms

                # Record performance metric
                name = metric_name or f"function.{func.__name__}.execution_time"
                tags = {"function": func.__name__}

                if include_args and args:
                    tags["args_count"] = str(len(args))

                await monitor.metrics_collector.record_metric(
                    name, execution_time, MetricType.TIMER, tags=tags, unit="ms"
                )

                return result

            except Exception as e:
                # Record error metric
                await monitor.metrics_collector.record_metric(
                    f"function.{func.__name__}.errors",
                    1,
                    MetricType.COUNTER,
                    tags={"function": func.__name__, "error_type": type(e).__name__},
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, use asyncio.create_task
            start_time = time.time()

            try:
                result = func(*args, **kwargs)

                execution_time = (time.time() - start_time) * 1000

                # Schedule async metric recording
                asyncio.create_task(
                    _record_sync_metric(
                        func.__name__, execution_time, metric_name, include_args, args
                    )
                )

                return result

            except Exception as e:
                asyncio.create_task(_record_sync_error(func.__name__, type(e).__name__))
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


async def _record_sync_metric(
    func_name: str,
    execution_time: float,
    metric_name: Optional[str],
    include_args: bool,
    args: tuple,
):
    """
    Record metric for synchronous function
    """
    try:
        monitor = await get_performance_monitor()

        name = metric_name or f"function.{func_name}.execution_time"
        tags = {"function": func_name}

        if include_args and args:
            tags["args_count"] = str(len(args))

        await monitor.metrics_collector.record_metric(
            name, execution_time, MetricType.TIMER, tags=tags, unit="ms"
        )
    except Exception as e:
        logger.error(f"Failed to record sync metric: {e}")


async def _record_sync_error(func_name: str, error_type: str):
    """
    Record error metric for synchronous function
    """
    try:
        monitor = await get_performance_monitor()
        await monitor.metrics_collector.record_metric(
            f"function.{func_name}.errors",
            1,
            MetricType.COUNTER,
            tags={"function": func_name, "error_type": error_type},
        )
    except Exception as e:
        logger.error(f"Failed to record sync error: {e}")
