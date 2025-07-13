"""Health monitoring system for WakeDock services and components."""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass

import httpx
import docker
from sqlalchemy.orm import Session

from wakedock.config import get_settings
from wakedock.database.database import get_db_session
from wakedock.database.models import Service, ServiceStatus

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status enumeration."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    WARNING = "warning"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Health check configuration."""
    name: str
    check_function: Callable
    interval: int = 30  # seconds
    timeout: int = 5   # seconds
    max_failures: int = 3
    enabled: bool = True


@dataclass
class HealthResult:
    """Health check result."""
    name: str
    status: HealthStatus
    message: str
    timestamp: datetime
    response_time: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


class HealthMonitor:
    """Monitors health of services and system components."""
    
    def __init__(self):
        """Initialize health monitor."""
        self.settings = get_settings()
        self.checks: Dict[str, HealthCheck] = {}
        self.results: Dict[str, List[HealthResult]] = {}
        self.failure_counts: Dict[str, int] = {}
        self.running = False
        self.tasks: List[asyncio.Task] = []
        
        # Initialize default health checks
        self._register_default_checks()
    
    def _register_default_checks(self):
        """Register default health checks."""
        # Docker daemon health
        self.register_check(HealthCheck(
            name="docker_daemon",
            check_function=self._check_docker_daemon,
            interval=60,
            timeout=10
        ))
        
        # Database health
        self.register_check(HealthCheck(
            name="database",
            check_function=self._check_database,
            interval=30,
            timeout=5
        ))
        
        # Caddy health
        self.register_check(HealthCheck(
            name="caddy",
            check_function=self._check_caddy,
            interval=30,
            timeout=5
        ))
        
        # System resources
        self.register_check(HealthCheck(
            name="system_resources",
            check_function=self._check_system_resources,
            interval=60,
            timeout=5
        ))
    
    def register_check(self, health_check: HealthCheck):
        """Register a new health check."""
        self.checks[health_check.name] = health_check
        self.results[health_check.name] = []
        self.failure_counts[health_check.name] = 0
        logger.info(f"Registered health check: {health_check.name}")
    
    def unregister_check(self, name: str):
        """Unregister a health check."""
        if name in self.checks:
            del self.checks[name]
            del self.results[name]
            del self.failure_counts[name]
            logger.info(f"Unregistered health check: {name}")
    
    async def start(self):
        """Start health monitoring."""
        if self.running:
            return
        
        self.running = True
        logger.info("Starting health monitor")
        
        # Start monitoring tasks for each check
        for check in self.checks.values():
            if check.enabled:
                task = asyncio.create_task(self._monitor_check(check))
                self.tasks.append(task)
        
        logger.info(f"Started {len(self.tasks)} health check tasks")
    
    async def stop(self):
        """Stop health monitoring."""
        if not self.running:
            return
        
        self.running = False
        logger.info("Stopping health monitor")
        
        # Cancel all monitoring tasks
        for task in self.tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        self.tasks.clear()
        logger.info("Health monitor stopped")
    
    async def _monitor_check(self, check: HealthCheck):
        """Monitor a single health check."""
        while self.running:
            try:
                start_time = time.time()
                
                # Run the health check with timeout
                try:
                    result = await asyncio.wait_for(
                        check.check_function(),
                        timeout=check.timeout
                    )
                except asyncio.TimeoutError:
                    result = HealthResult(
                        name=check.name,
                        status=HealthStatus.UNHEALTHY,
                        message="Health check timed out",
                        timestamp=datetime.utcnow(),
                        response_time=check.timeout
                    )
                
                # Calculate response time
                response_time = time.time() - start_time
                if result.response_time is None:
                    result.response_time = response_time
                
                # Store result
                self._store_result(result)
                
                # Update failure count
                if result.status == HealthStatus.UNHEALTHY:
                    self.failure_counts[check.name] += 1
                else:
                    self.failure_counts[check.name] = 0
                
                # Log if unhealthy
                if result.status == HealthStatus.UNHEALTHY:
                    logger.warning(f"Health check '{check.name}' failed: {result.message}")
                
                # Check for max failures
                if self.failure_counts[check.name] >= check.max_failures:
                    logger.error(f"Health check '{check.name}' has exceeded max failures ({check.max_failures})")
                
            except Exception as e:
                logger.error(f"Error in health check '{check.name}': {e}")
                error_result = HealthResult(
                    name=check.name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Check error: {str(e)}",
                    timestamp=datetime.utcnow()
                )
                self._store_result(error_result)
            
            # Wait for next check
            await asyncio.sleep(check.interval)
    
    def _store_result(self, result: HealthResult):
        """Store a health check result."""
        if result.name not in self.results:
            self.results[result.name] = []
        
        self.results[result.name].append(result)
        
        # Keep only last 100 results per check
        if len(self.results[result.name]) > 100:
            self.results[result.name] = self.results[result.name][-100:]
    
    async def _check_docker_daemon(self) -> HealthResult:
        """Check Docker daemon health."""
        try:
            client = docker.from_env()
            info = client.info()
            
            return HealthResult(
                name="docker_daemon",
                status=HealthStatus.HEALTHY,
                message=f"Docker daemon running (Version: {info.get('ServerVersion', 'unknown')})",
                timestamp=datetime.utcnow(),
                details={"containers": info.get("Containers", 0)}
            )
        except Exception as e:
            return HealthResult(
                name="docker_daemon",
                status=HealthStatus.UNHEALTHY,
                message=f"Docker daemon unavailable: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def _check_database(self) -> HealthResult:
        """Check database connectivity."""
        try:
            from wakedock.database.database import db_manager
            
            with db_manager.get_session() as session:
                # Simple query to test connection
                session.execute("SELECT 1")
                
            return HealthResult(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Database connection successful",
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            return HealthResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def _check_caddy(self) -> HealthResult:
        """Check Caddy server health."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:2019/config/")
                
                if response.status_code == 200:
                    return HealthResult(
                        name="caddy",
                        status=HealthStatus.HEALTHY,
                        message="Caddy admin API responding",
                        timestamp=datetime.utcnow(),
                        details={"admin_port": 2019}
                    )
                else:
                    return HealthResult(
                        name="caddy",
                        status=HealthStatus.UNHEALTHY,
                        message=f"Caddy admin API returned {response.status_code}",
                        timestamp=datetime.utcnow()
                    )
        except Exception as e:
            return HealthResult(
                name="caddy",
                status=HealthStatus.UNHEALTHY,
                message=f"Caddy admin API unavailable: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def _check_system_resources(self) -> HealthResult:
        """Check system resource usage."""
        try:
            import psutil
            
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Determine status based on usage
            status = HealthStatus.HEALTHY
            warnings = []
            
            if cpu_percent > 90:
                status = HealthStatus.WARNING
                warnings.append(f"High CPU usage: {cpu_percent}%")
            elif cpu_percent > 95:
                status = HealthStatus.UNHEALTHY
                warnings.append(f"Critical CPU usage: {cpu_percent}%")
            
            if memory.percent > 90:
                status = HealthStatus.WARNING
                warnings.append(f"High memory usage: {memory.percent}%")
            elif memory.percent > 95:
                status = HealthStatus.UNHEALTHY
                warnings.append(f"Critical memory usage: {memory.percent}%")
            
            if disk.percent > 90:
                status = HealthStatus.WARNING
                warnings.append(f"High disk usage: {disk.percent}%")
            elif disk.percent > 95:
                status = HealthStatus.UNHEALTHY
                warnings.append(f"Critical disk usage: {disk.percent}%")
            
            message = "System resources normal"
            if warnings:
                message = "; ".join(warnings)
            
            return HealthResult(
                name="system_resources",
                status=status,
                message=message,
                timestamp=datetime.utcnow(),
                details={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "disk_percent": disk.percent
                }
            )
        except Exception as e:
            return HealthResult(
                name="system_resources",
                status=HealthStatus.UNKNOWN,
                message=f"Failed to get system resources: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    async def check_service_health(self, service: Service) -> HealthResult:
        """Check health of a specific service."""
        if service.status != ServiceStatus.RUNNING:
            return HealthResult(
                name=f"service_{service.name}",
                status=HealthStatus.UNHEALTHY,
                message=f"Service is not running (status: {service.status.value})",
                timestamp=datetime.utcnow()
            )
        
        # Try to reach service health endpoint
        try:
            if service.ports and len(service.ports) > 0:
                port = service.ports[0].get('host', 8080)
                health_url = f"http://localhost:{port}/health"
                
                async with httpx.AsyncClient() as client:
                    response = await client.get(health_url, timeout=5)
                    
                    if response.status_code == 200:
                        return HealthResult(
                            name=f"service_{service.name}",
                            status=HealthStatus.HEALTHY,
                            message="Service health endpoint responding",
                            timestamp=datetime.utcnow(),
                            details={"port": port, "health_url": health_url}
                        )
                    else:
                        return HealthResult(
                            name=f"service_{service.name}",
                            status=HealthStatus.WARNING,
                            message=f"Service health endpoint returned {response.status_code}",
                            timestamp=datetime.utcnow()
                        )
            else:
                return HealthResult(
                    name=f"service_{service.name}",
                    status=HealthStatus.WARNING,
                    message="No ports configured for health check",
                    timestamp=datetime.utcnow()
                )
                
        except Exception as e:
            return HealthResult(
                name=f"service_{service.name}",
                status=HealthStatus.UNHEALTHY,
                message=f"Service health check failed: {str(e)}",
                timestamp=datetime.utcnow()
            )
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get overall health summary."""
        summary = {
            "overall_status": HealthStatus.HEALTHY.value,
            "checks": {},
            "last_updated": datetime.utcnow().isoformat()
        }
        
        unhealthy_count = 0
        warning_count = 0
        
        for name, results in self.results.items():
            if results:
                latest = results[-1]
                summary["checks"][name] = {
                    "status": latest.status.value,
                    "message": latest.message,
                    "timestamp": latest.timestamp.isoformat(),
                    "response_time": latest.response_time,
                    "failure_count": self.failure_counts.get(name, 0)
                }
                
                if latest.status == HealthStatus.UNHEALTHY:
                    unhealthy_count += 1
                elif latest.status == HealthStatus.WARNING:
                    warning_count += 1
        
        # Determine overall status
        if unhealthy_count > 0:
            summary["overall_status"] = HealthStatus.UNHEALTHY.value
        elif warning_count > 0:
            summary["overall_status"] = HealthStatus.WARNING.value
        
        summary["stats"] = {
            "total_checks": len(self.checks),
            "unhealthy_count": unhealthy_count,
            "warning_count": warning_count
        }
        
        return summary
    
    def get_check_history(self, check_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get history for a specific health check."""
        if check_name not in self.results:
            return []
        
        results = self.results[check_name][-limit:]
        return [
            {
                "status": result.status.value,
                "message": result.message,
                "timestamp": result.timestamp.isoformat(),
                "response_time": result.response_time,
                "details": result.details
            }
            for result in results
        ]


# Global health monitor instance
health_monitor = HealthMonitor()
