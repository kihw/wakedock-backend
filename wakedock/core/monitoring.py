"""
Monitoring service for tracking service usage and auto-shutdown
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
import time

from wakedock.core.orchestrator import DockerOrchestrator
from wakedock.config import get_settings

logger = logging.getLogger(__name__)


class MonitoringService:
    """Service for monitoring containers and handling auto-shutdown"""
    
    def __init__(self):
        self.settings = get_settings()
        self.orchestrator: DockerOrchestrator = None
        self.monitoring_task: asyncio.Task = None
        self.running = False
        self.metrics_history: Dict[str, List[Dict[str, Any]]] = {}
    
    async def start(self):
        """Start the monitoring service"""
        logger.info("Starting monitoring service...")
        self.running = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
    
    async def stop(self):
        """Stop the monitoring service"""
        logger.info("Stopping monitoring service...")
        self.running = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
    
    def set_orchestrator(self, orchestrator: DockerOrchestrator):
        """Set the orchestrator instance"""
        self.orchestrator = orchestrator
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                await self._collect_metrics()
                await self._check_auto_shutdown()
                await asyncio.sleep(self.settings.monitoring.collect_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                await asyncio.sleep(30)  # Wait before retrying
    
    async def _collect_metrics(self):
        """Collect metrics for all running services"""
        if not self.orchestrator:
            return
        
        services = await self.orchestrator.list_services()
        
        for service in services:
            if service["status"] == "running":
                try:
                    stats = await self.orchestrator.get_service_stats(service["id"])
                    if stats:
                        self._store_metrics(service["id"], stats)
                except Exception as e:
                    logger.error(f"Failed to collect metrics for {service['name']}: {str(e)}")
    
    def _store_metrics(self, service_id: str, stats: Dict[str, Any]):
        """Store metrics in history"""
        if service_id not in self.metrics_history:
            self.metrics_history[service_id] = []
        
        # Add timestamp if not present
        if "timestamp" not in stats:
            stats["timestamp"] = datetime.now()
        
        self.metrics_history[service_id].append(stats)
        
        # Keep only recent metrics (based on retention period)
        retention_days = int(self.settings.monitoring.metrics_retention.replace("d", ""))
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        self.metrics_history[service_id] = [
            metric for metric in self.metrics_history[service_id]
            if metric["timestamp"] > cutoff_date
        ]
    
    async def _check_auto_shutdown(self):
        """Check services for auto-shutdown conditions"""
        if not self.orchestrator:
            return
        
        services = await self.orchestrator.list_services()
        
        for service in services:
            if service["status"] == "running":
                try:
                    should_shutdown = await self._should_shutdown_service(service)
                    if should_shutdown:
                        logger.info(f"Auto-shutting down service: {service['name']}")
                        await self.orchestrator.sleep_service(service["id"])
                except Exception as e:
                    logger.error(f"Error checking auto-shutdown for {service['name']}: {str(e)}")
    
    async def _should_shutdown_service(self, service: Dict[str, Any]) -> bool:
        """Check if a service should be shut down"""
        auto_shutdown = service.get("auto_shutdown", {})
        
        # Check inactivity timeout
        inactive_minutes = auto_shutdown.get("inactive_minutes", 30)
        if service.get("last_accessed"):
            last_access = service["last_accessed"]
            if isinstance(last_access, str):
                last_access = datetime.fromisoformat(last_access.replace("Z", "+00:00"))
            
            inactive_time = datetime.now() - last_access
            if inactive_time > timedelta(minutes=inactive_minutes):
                logger.info(f"Service {service['name']} inactive for {inactive_time}")
                return True
        
        # Check resource usage thresholds
        cpu_threshold = auto_shutdown.get("cpu_threshold", 5.0)
        memory_threshold = auto_shutdown.get("memory_threshold", 100)  # MB
        check_interval = auto_shutdown.get("check_interval", 300)  # seconds
        
        # Get recent metrics
        service_metrics = self.metrics_history.get(service["id"], [])
        if not service_metrics:
            return False
        
        # Check if resource usage has been consistently low
        cutoff_time = datetime.now() - timedelta(seconds=check_interval)
        recent_metrics = [
            metric for metric in service_metrics
            if metric["timestamp"] > cutoff_time
        ]
        
        if len(recent_metrics) < 3:  # Need at least 3 data points
            return False
        
        # Check CPU threshold
        low_cpu_count = sum(1 for metric in recent_metrics if metric.get("cpu_percent", 100) < cpu_threshold)
        cpu_ratio = low_cpu_count / len(recent_metrics)
        
        # Check memory threshold (convert to MB)
        memory_threshold_bytes = memory_threshold * 1024 * 1024
        low_memory_count = sum(1 for metric in recent_metrics if metric.get("memory_usage", float('inf')) < memory_threshold_bytes)
        memory_ratio = low_memory_count / len(recent_metrics)
        
        # Shutdown if both CPU and memory usage are consistently low
        if cpu_ratio >= 0.8 and memory_ratio >= 0.8:
            logger.info(f"Service {service['name']} has low resource usage - CPU: {cpu_ratio*100:.1f}%, Memory: {memory_ratio*100:.1f}%")
            return True
        
        return False
    
    async def get_service_metrics(self, service_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get metrics history for a service"""
        if service_id not in self.metrics_history:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            metric for metric in self.metrics_history[service_id]
            if metric["timestamp"] > cutoff_time
        ]
    
    async def get_system_overview(self) -> Dict[str, Any]:
        """Get system overview metrics"""
        if not self.orchestrator:
            return {}
        
        services = await self.orchestrator.list_services()
        
        total_services = len(services)
        running_services = len([s for s in services if s["status"] == "running"])
        stopped_services = len([s for s in services if s["status"] == "stopped"])
        
        # Calculate total resource usage
        total_cpu = 0
        total_memory = 0
        
        for service in services:
            if service["status"] == "running" and service.get("resource_usage"):
                total_cpu += service["resource_usage"].get("cpu_percent", 0)
                total_memory += service["resource_usage"].get("memory_usage", 0)
        
        return {
            "total_services": total_services,
            "running_services": running_services,
            "stopped_services": stopped_services,
            "total_cpu_usage": round(total_cpu, 2),
            "total_memory_usage": total_memory,
            "timestamp": datetime.now()
        }
