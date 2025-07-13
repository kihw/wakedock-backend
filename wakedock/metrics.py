"""
WakeDock Metrics Module

Provides Prometheus metrics collection for monitoring system health,
performance, and business metrics.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from threading import Lock
import psutil
import docker
from prometheus_client import (
    Counter, Histogram, Gauge, Info, Summary,
    CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST,
    multiprocess, values
)
from prometheus_client.core import CollectorRegistry
from prometheus_client.exposition import MetricsHandler
from http.server import HTTPServer
import threading
import logging

from wakedock.core.orchestrator import DockerOrchestrator
from wakedock.database import get_session
from wakedock.database.models import Service, User


logger = logging.getLogger(__name__)


class MetricsCollector:
    """Main metrics collector for WakeDock."""
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()
        self._lock = Lock()
        self._docker_client = None
        self._last_collection = datetime.now()
        
        # Initialize metrics
        self._init_metrics()
        
        # Cache for expensive operations
        self._cache = {}
        self._cache_ttl = 30  # seconds
    
    def _init_metrics(self):
        """Initialize all Prometheus metrics."""
        
        # System metrics
        self.system_info = Info(
            'wakedock_system_info',
            'System information',
            registry=self.registry
        )
        
        self.cpu_usage = Gauge(
            'wakedock_cpu_usage_percent',
            'CPU usage percentage',
            registry=self.registry
        )
        
        self.memory_usage = Gauge(
            'wakedock_memory_usage_bytes',
            'Memory usage in bytes',
            registry=self.registry
        )
        
        self.memory_total = Gauge(
            'wakedock_memory_total_bytes',
            'Total memory in bytes',
            registry=self.registry
        )
        
        self.disk_usage = Gauge(
            'wakedock_disk_usage_bytes',
            'Disk usage in bytes',
            ['path'],
            registry=self.registry
        )
        
        self.disk_total = Gauge(
            'wakedock_disk_total_bytes',
            'Total disk space in bytes',
            ['path'],
            registry=self.registry
        )
        
        self.load_average = Gauge(
            'wakedock_load_average',
            'System load average',
            ['period'],
            registry=self.registry
        )
        
        # Application metrics
        self.app_info = Info(
            'wakedock_app_info',
            'Application information',
            registry=self.registry
        )
        
        self.uptime = Gauge(
            'wakedock_uptime_seconds',
            'Application uptime in seconds',
            registry=self.registry
        )
        
        # HTTP metrics
        self.http_requests_total = Counter(
            'wakedock_http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status_code'],
            registry=self.registry
        )
        
        self.http_request_duration = Histogram(
            'wakedock_http_request_duration_seconds',
            'HTTP request duration',
            ['method', 'endpoint'],
            registry=self.registry
        )
        
        self.http_requests_in_progress = Gauge(
            'wakedock_http_requests_in_progress',
            'Number of HTTP requests currently being processed',
            registry=self.registry
        )
        
        # Database metrics
        self.db_connections = Gauge(
            'wakedock_db_connections',
            'Number of database connections',
            ['state'],
            registry=self.registry
        )
        
        self.db_query_duration = Histogram(
            'wakedock_db_query_duration_seconds',
            'Database query duration',
            ['operation'],
            registry=self.registry
        )
        
        self.db_queries_total = Counter(
            'wakedock_db_queries_total',
            'Total database queries',
            ['operation', 'status'],
            registry=self.registry
        )
        
        # Service metrics
        self.services_total = Gauge(
            'wakedock_services_total',
            'Total number of services',
            registry=self.registry
        )
        
        self.services_by_status = Gauge(
            'wakedock_services_by_status',
            'Number of services by status',
            ['status'],
            registry=self.registry
        )
        
        self.service_operations_total = Counter(
            'wakedock_service_operations_total',
            'Total service operations',
            ['operation', 'status'],
            registry=self.registry
        )
        
        self.service_operation_duration = Histogram(
            'wakedock_service_operation_duration_seconds',
            'Service operation duration',
            ['operation'],
            registry=self.registry
        )
        
        # Docker metrics
        self.docker_containers_total = Gauge(
            'wakedock_docker_containers_total',
            'Total Docker containers',
            registry=self.registry
        )
        
        self.docker_containers_by_status = Gauge(
            'wakedock_docker_containers_by_status',
            'Docker containers by status',
            ['status'],
            registry=self.registry
        )
        
        self.docker_images_total = Gauge(
            'wakedock_docker_images_total',
            'Total Docker images',
            registry=self.registry
        )
        
        self.docker_volumes_total = Gauge(
            'wakedock_docker_volumes_total',
            'Total Docker volumes',
            registry=self.registry
        )
        
        self.docker_networks_total = Gauge(
            'wakedock_docker_networks_total',
            'Total Docker networks',
            registry=self.registry
        )
        
        # Authentication metrics
        self.auth_attempts_total = Counter(
            'wakedock_auth_attempts_total',
            'Total authentication attempts',
            ['status'],
            registry=self.registry
        )
        
        self.auth_tokens_issued = Counter(
            'wakedock_auth_tokens_issued_total',
            'Total authentication tokens issued',
            registry=self.registry
        )
        
        self.active_sessions = Gauge(
            'wakedock_active_sessions',
            'Number of active user sessions',
            registry=self.registry
        )
        
        # Users metrics
        self.users_total = Gauge(
            'wakedock_users_total',
            'Total number of users',
            registry=self.registry
        )
        
        self.users_by_role = Gauge(
            'wakedock_users_by_role',
            'Number of users by role',
            ['role'],
            registry=self.registry
        )
        
        # Error metrics
        self.errors_total = Counter(
            'wakedock_errors_total',
            'Total errors',
            ['type', 'component'],
            registry=self.registry
        )
        
        # Cache metrics
        self.cache_operations_total = Counter(
            'wakedock_cache_operations_total',
            'Total cache operations',
            ['operation', 'status'],
            registry=self.registry
        )
        
        self.cache_hit_ratio = Gauge(
            'wakedock_cache_hit_ratio',
            'Cache hit ratio',
            registry=self.registry
        )
    
    @property
    def docker_client(self):
        """Get Docker client instance."""
        if self._docker_client is None:
            try:
                self._docker_client = docker.from_env()
            except Exception as e:
                logger.error(f"Failed to initialize Docker client: {e}")
                return None
        return self._docker_client
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached value is still valid."""
        if key not in self._cache:
            return False
        
        cached_time = self._cache[key].get('timestamp')
        if not cached_time:
            return False
        
        return (datetime.now() - cached_time).seconds < self._cache_ttl
    
    def _get_cached_value(self, key: str) -> Any:
        """Get cached value."""
        if self._is_cache_valid(key):
            return self._cache[key]['value']
        return None
    
    def _set_cached_value(self, key: str, value: Any) -> None:
        """Set cached value."""
        self._cache[key] = {
            'value': value,
            'timestamp': datetime.now()
        }
    
    def collect_system_metrics(self):
        """Collect system-level metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.cpu_usage.set(cpu_percent)
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.memory_usage.set(memory.used)
            self.memory_total.set(memory.total)
            
            # Disk usage
            for disk in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(disk.mountpoint)
                    self.disk_usage.labels(path=disk.mountpoint).set(usage.used)
                    self.disk_total.labels(path=disk.mountpoint).set(usage.total)
                except (PermissionError, OSError):
                    continue
            
            # Load average
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (0, 0, 0)
            self.load_average.labels(period='1m').set(load_avg[0])
            self.load_average.labels(period='5m').set(load_avg[1])
            self.load_average.labels(period='15m').set(load_avg[2])
            
            # System info
            self.system_info.info({
                'hostname': psutil.os.uname().nodename,
                'os': psutil.os.uname().system,
                'architecture': psutil.os.uname().machine,
                'python_version': f"{psutil.sys.version_info.major}.{psutil.sys.version_info.minor}.{psutil.sys.version_info.micro}"
            })
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            self.errors_total.labels(type='collection_error', component='system').inc()
    
    def collect_docker_metrics(self):
        """Collect Docker-related metrics."""
        if not self.docker_client:
            return
        
        try:
            # Containers
            containers = self.docker_client.containers.list(all=True)
            self.docker_containers_total.set(len(containers))
            
            # Containers by status
            status_counts = {}
            for container in containers:
                status = container.status
                status_counts[status] = status_counts.get(status, 0) + 1
            
            for status, count in status_counts.items():
                self.docker_containers_by_status.labels(status=status).set(count)
            
            # Images
            images = self.docker_client.images.list()
            self.docker_images_total.set(len(images))
            
            # Volumes
            volumes = self.docker_client.volumes.list()
            self.docker_volumes_total.set(len(volumes))
            
            # Networks
            networks = self.docker_client.networks.list()
            self.docker_networks_total.set(len(networks))
            
        except Exception as e:
            logger.error(f"Error collecting Docker metrics: {e}")
            self.errors_total.labels(type='collection_error', component='docker').inc()
    
    def collect_database_metrics(self):
        """Collect database-related metrics."""
        try:
            with get_session() as db:
                # Count services
                services_count = db.query(Service).count()
                self.services_total.set(services_count)
                
                # Services by status
                status_counts = {}
                services = db.query(Service).all()
                for service in services:
                    status = service.status or 'unknown'
                    status_counts[status] = status_counts.get(status, 0) + 1
                
                for status, count in status_counts.items():
                    self.services_by_status.labels(status=status).set(count)
                
                # Count users
                users_count = db.query(User).count()
                self.users_total.set(users_count)
                
                # Users by role
                role_counts = {}
                users = db.query(User).all()
                for user in users:
                    role = user.role or 'user'
                    role_counts[role] = role_counts.get(role, 0) + 1
                
                for role, count in role_counts.items():
                    self.users_by_role.labels(role=role).set(count)
                
        except Exception as e:
            logger.error(f"Error collecting database metrics: {e}")
            self.errors_total.labels(type='collection_error', component='database').inc()
    
    def collect_all_metrics(self):
        """Collect all metrics."""
        with self._lock:
            logger.debug("Collecting metrics...")
            
            self.collect_system_metrics()
            self.collect_docker_metrics()
            self.collect_database_metrics()
            
            self._last_collection = datetime.now()
            logger.debug("Metrics collection completed")
    
    def record_http_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record HTTP request metrics."""
        self.http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).inc()
        
        self.http_request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def record_db_query(self, operation: str, duration: float, success: bool = True):
        """Record database query metrics."""
        status = 'success' if success else 'error'
        
        self.db_queries_total.labels(
            operation=operation,
            status=status
        ).inc()
        
        self.db_query_duration.labels(operation=operation).observe(duration)
    
    def record_service_operation(self, operation: str, duration: float, success: bool = True):
        """Record service operation metrics."""
        status = 'success' if success else 'error'
        
        self.service_operations_total.labels(
            operation=operation,
            status=status
        ).inc()
        
        self.service_operation_duration.labels(operation=operation).observe(duration)
    
    def record_auth_attempt(self, success: bool):
        """Record authentication attempt."""
        status = 'success' if success else 'failure'
        self.auth_attempts_total.labels(status=status).inc()
    
    def record_token_issued(self):
        """Record token issuance."""
        self.auth_tokens_issued.inc()
    
    def record_error(self, error_type: str, component: str):
        """Record an error."""
        self.errors_total.labels(type=error_type, component=component).inc()
    
    def record_cache_operation(self, operation: str, success: bool):
        """Record cache operation."""
        status = 'hit' if success and operation == 'get' else 'miss' if operation == 'get' else 'success' if success else 'error'
        self.cache_operations_total.labels(operation=operation, status=status).inc()
    
    def get_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        # Collect fresh metrics
        self.collect_all_metrics()
        
        # Generate metrics output
        return generate_latest(self.registry)


class MetricsServer:
    """HTTP server for metrics endpoint."""
    
    def __init__(self, collector: MetricsCollector, port: int = 9090, host: str = "0.0.0.0"):
        self.collector = collector
        self.port = port
        self.host = host
        self.server = None
        self.thread = None
    
    def start(self):
        """Start the metrics server."""
        if self.server:
            return
        
        class MetricsRequestHandler(MetricsHandler):
            def __init__(self, request, client_address, server, collector):
                self._collector = collector
                super().__init__(request, client_address, server)
            
            def do_GET(self):
                if self.path == '/metrics':
                    self.send_response(200)
                    self.send_header('Content-Type', CONTENT_TYPE_LATEST)
                    self.end_headers()
                    self.wfile.write(self._collector.get_metrics().encode('utf-8'))
                elif self.path == '/health':
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"status": "healthy"}')
                else:
                    self.send_response(404)
                    self.end_headers()
        
        def handler_factory(*args, **kwargs):
            return MetricsRequestHandler(*args, **kwargs, collector=self.collector)
        
        self.server = HTTPServer((self.host, self.port), handler_factory)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        
        logger.info(f"Metrics server started on {self.host}:{self.port}")
    
    def stop(self):
        """Stop the metrics server."""
        if self.server:
            self.server.shutdown()
            self.server = None
        
        if self.thread:
            self.thread.join()
            self.thread = None
        
        logger.info("Metrics server stopped")


class MetricsMiddleware:
    """Middleware to collect HTTP metrics."""
    
    def __init__(self, collector: MetricsCollector):
        self.collector = collector
    
    async def __call__(self, request, call_next):
        start_time = time.time()
        
        # Increment in-progress counter
        self.collector.http_requests_in_progress.inc()
        
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            # Record metrics
            self.collector.record_http_request(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code,
                duration=duration
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            
            # Record error
            self.collector.record_http_request(
                method=request.method,
                endpoint=request.url.path,
                status_code=500,
                duration=duration
            )
            
            self.collector.record_error('http_error', 'api')
            raise
        
        finally:
            # Decrement in-progress counter
            self.collector.http_requests_in_progress.dec()


# Global metrics instance
_metrics_collector = None
_metrics_server = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def init_metrics(port: int = 9090, host: str = "0.0.0.0") -> MetricsCollector:
    """Initialize metrics collection and server."""
    global _metrics_server
    
    collector = get_metrics_collector()
    
    # Set application info
    try:
        import wakedock
        version = getattr(wakedock, '__version__', 'unknown')
    except ImportError:
        version = 'unknown'
    
    collector.app_info.info({
        'version': version,
        'name': 'wakedock'
    })
    
    # Start metrics server
    if _metrics_server is None:
        _metrics_server = MetricsServer(collector, port, host)
        _metrics_server.start()
    
    return collector


def shutdown_metrics():
    """Shutdown metrics collection and server."""
    global _metrics_server
    if _metrics_server:
        _metrics_server.stop()
        _metrics_server = None


# Decorator for timing functions
def timed(operation: str, component: str = 'general'):
    """Decorator to time function execution and record metrics."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                if component == 'database':
                    collector.record_db_query(operation, duration, True)
                elif component == 'service':
                    collector.record_service_operation(operation, duration, True)
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                if component == 'database':
                    collector.record_db_query(operation, duration, False)
                elif component == 'service':
                    collector.record_service_operation(operation, duration, False)
                
                collector.record_error('function_error', component)
                raise
        
        return wrapper
    return decorator


# Export commonly used items
__all__ = [
    'MetricsCollector',
    'MetricsServer',
    'MetricsMiddleware',
    'get_metrics_collector',
    'init_metrics',
    'shutdown_metrics',
    'timed'
]
