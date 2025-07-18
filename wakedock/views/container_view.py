"""
Container view for API response formatting - MVC Architecture
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from wakedock.views.base_view import BaseView
from wakedock.models.container import Container, ContainerLog, ContainerMetrics

import logging
logger = logging.getLogger(__name__)


class ContainerView(BaseView):
    """View for container API response formatting"""
    
    def __init__(self):
        super().__init__()
    
    async def container_response(self, container: Container, docker_info: Optional[Dict] = None) -> Dict[str, Any]:
        """Format single container response"""
        try:
            response = {
                "success": True,
                "data": {
                    "id": container.id,
                    "container_id": container.container_id,
                    "name": container.name,
                    "image": container.image,
                    "command": container.command,
                    "status": container.status,
                    "environment": container.environment,
                    "ports": container.ports,
                    "volumes": container.volumes,
                    "labels": container.labels,
                    "restart_policy": container.restart_policy,
                    "created_at": container.created_at.isoformat() if container.created_at else None,
                    "updated_at": container.updated_at.isoformat() if container.updated_at else None,
                    "uptime": self._calculate_uptime(container.created_at) if container.created_at else None
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Add Docker info if available
            if docker_info:
                response["data"]["docker_info"] = docker_info
            
            return response
            
        except Exception as e:
            logger.error(f"Error formatting container response: {str(e)}")
            return await self.error_response(
                "Failed to format container response",
                "CONTAINER_FORMAT_ERROR"
            )
    
    async def containers_list_response(
        self,
        containers: List[Container],
        total_count: int,
        limit: int,
        offset: int,
        has_more: bool = False
    ) -> Dict[str, Any]:
        """Format containers list response"""
        try:
            container_data = []
            
            for container in containers:
                container_info = {
                    "id": container.id,
                    "container_id": container.container_id,
                    "name": container.name,
                    "image": container.image,
                    "status": container.status,
                    "created_at": container.created_at.isoformat() if container.created_at else None,
                    "uptime": self._calculate_uptime(container.created_at) if container.created_at else None,
                    "ports": container.ports,
                    "labels": container.labels
                }
                container_data.append(container_info)
            
            response = {
                "success": True,
                "data": {
                    "containers": container_data,
                    "pagination": {
                        "total_count": total_count,
                        "limit": limit,
                        "offset": offset,
                        "has_more": has_more,
                        "current_page": (offset // limit) + 1,
                        "total_pages": (total_count + limit - 1) // limit
                    }
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error formatting containers list response: {str(e)}")
            return await self.error_response(
                "Failed to format containers list",
                "CONTAINERS_LIST_FORMAT_ERROR"
            )
    
    async def container_creation_response(
        self,
        container: Container,
        docker_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Format container creation response"""
        try:
            response = {
                "success": True,
                "message": "Container created successfully",
                "data": {
                    "id": container.id,
                    "container_id": container.container_id,
                    "name": container.name,
                    "image": container.image,
                    "status": container.status,
                    "created_at": container.created_at.isoformat() if container.created_at else None
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Add Docker info if available
            if docker_info:
                response["data"]["docker_info"] = docker_info
            
            return response
            
        except Exception as e:
            logger.error(f"Error formatting container creation response: {str(e)}")
            return await self.error_response(
                "Failed to format container creation response",
                "CONTAINER_CREATION_FORMAT_ERROR"
            )
    
    async def container_operation_response(
        self,
        container: Container,
        operation: str,
        success: bool = True,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Format container operation response (start, stop, restart, etc.)"""
        try:
            response = {
                "success": success,
                "message": message or f"Container {operation} {'successful' if success else 'failed'}",
                "data": {
                    "id": container.id,
                    "container_id": container.container_id,
                    "name": container.name,
                    "operation": operation,
                    "status": container.status,
                    "timestamp": datetime.utcnow().isoformat()
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error formatting container operation response: {str(e)}")
            return await self.error_response(
                "Failed to format container operation response",
                "CONTAINER_OPERATION_FORMAT_ERROR"
            )
    
    async def container_logs_response(
        self,
        container: Container,
        docker_logs: List[str],
        db_logs: List[ContainerLog],
        total_logs: int
    ) -> Dict[str, Any]:
        """Format container logs response"""
        try:
            # Format Docker logs
            formatted_docker_logs = []
            for log_line in docker_logs:
                formatted_docker_logs.append({
                    "source": "docker",
                    "message": log_line,
                    "timestamp": datetime.utcnow().isoformat()  # Would need to parse from log
                })
            
            # Format database logs
            formatted_db_logs = []
            for log in db_logs:
                formatted_db_logs.append({
                    "source": "database",
                    "level": log.log_level,
                    "message": log.message,
                    "timestamp": log.timestamp.isoformat() if log.timestamp else None
                })
            
            response = {
                "success": True,
                "data": {
                    "container": {
                        "id": container.id,
                        "container_id": container.container_id,
                        "name": container.name
                    },
                    "logs": {
                        "docker_logs": formatted_docker_logs,
                        "db_logs": formatted_db_logs,
                        "total_count": total_logs
                    }
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error formatting container logs response: {str(e)}")
            return await self.error_response(
                "Failed to format container logs",
                "CONTAINER_LOGS_FORMAT_ERROR"
            )
    
    async def container_stats_response(
        self,
        container: Container,
        current_stats: Dict[str, Any],
        metrics_history: List[ContainerMetrics] = None
    ) -> Dict[str, Any]:
        """Format container statistics response"""
        try:
            # Format metrics history
            formatted_metrics = []
            if metrics_history:
                for metric in metrics_history:
                    formatted_metrics.append({
                        "cpu_usage": metric.cpu_usage,
                        "memory_usage": metric.memory_usage,
                        "memory_limit": metric.memory_limit,
                        "memory_percentage": (metric.memory_usage / metric.memory_limit * 100) if metric.memory_limit > 0 else 0,
                        "network_rx": metric.network_rx,
                        "network_tx": metric.network_tx,
                        "disk_read": metric.disk_read,
                        "disk_write": metric.disk_write,
                        "timestamp": metric.timestamp.isoformat() if metric.timestamp else None
                    })
            
            response = {
                "success": True,
                "data": {
                    "container": {
                        "id": container.id,
                        "container_id": container.container_id,
                        "name": container.name,
                        "status": container.status,
                        "uptime": self._calculate_uptime(container.created_at) if container.created_at else None
                    },
                    "current_stats": current_stats,
                    "metrics_history": formatted_metrics,
                    "history_count": len(formatted_metrics)
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error formatting container stats response: {str(e)}")
            return await self.error_response(
                "Failed to format container statistics",
                "CONTAINER_STATS_FORMAT_ERROR"
            )
    
    async def container_search_response(
        self,
        containers: List[Container],
        query: str,
        filters: Dict[str, Any],
        total_count: int,
        limit: int,
        offset: int
    ) -> Dict[str, Any]:
        """Format container search response"""
        try:
            container_data = []
            
            for container in containers:
                container_info = {
                    "id": container.id,
                    "container_id": container.container_id,
                    "name": container.name,
                    "image": container.image,
                    "status": container.status,
                    "created_at": container.created_at.isoformat() if container.created_at else None,
                    "uptime": self._calculate_uptime(container.created_at) if container.created_at else None,
                    "ports": container.ports,
                    "labels": container.labels
                }
                container_data.append(container_info)
            
            response = {
                "success": True,
                "data": {
                    "containers": container_data,
                    "search": {
                        "query": query,
                        "filters": filters,
                        "total_results": total_count,
                        "limit": limit,
                        "offset": offset
                    }
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error formatting container search response: {str(e)}")
            return await self.error_response(
                "Failed to format container search results",
                "CONTAINER_SEARCH_FORMAT_ERROR"
            )
    
    async def container_statistics_response(
        self,
        database_stats: Dict[str, Any],
        docker_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format container statistics response"""
        try:
            response = {
                "success": True,
                "data": {
                    "database_statistics": database_stats,
                    "docker_statistics": docker_stats,
                    "summary": {
                        "total_containers": database_stats.get("total_containers", 0),
                        "running_containers": database_stats.get("running_containers", 0),
                        "stopped_containers": database_stats.get("stopped_containers", 0),
                        "uptime_percentage": database_stats.get("uptime_percentage", 0),
                        "containers_by_image": database_stats.get("containers_by_image", {})
                    }
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error formatting container statistics response: {str(e)}")
            return await self.error_response(
                "Failed to format container statistics",
                "CONTAINER_STATISTICS_FORMAT_ERROR"
            )
    
    async def container_sync_response(
        self,
        synced_count: int,
        created_count: int,
        updated_count: int
    ) -> Dict[str, Any]:
        """Format container synchronization response"""
        try:
            response = {
                "success": True,
                "message": "Container synchronization completed",
                "data": {
                    "synchronization": {
                        "synced_count": synced_count,
                        "created_count": created_count,
                        "updated_count": updated_count,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error formatting container sync response: {str(e)}")
            return await self.error_response(
                "Failed to format container synchronization response",
                "CONTAINER_SYNC_FORMAT_ERROR"
            )
    
    async def container_command_response(
        self,
        container: Container,
        command: str,
        exit_code: int,
        output: str
    ) -> Dict[str, Any]:
        """Format container command execution response"""
        try:
            response = {
                "success": exit_code == 0,
                "message": f"Command executed {'successfully' if exit_code == 0 else 'with errors'}",
                "data": {
                    "container": {
                        "id": container.id,
                        "container_id": container.container_id,
                        "name": container.name
                    },
                    "execution": {
                        "command": command,
                        "exit_code": exit_code,
                        "output": output,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error formatting container command response: {str(e)}")
            return await self.error_response(
                "Failed to format command execution response",
                "CONTAINER_COMMAND_FORMAT_ERROR"
            )
    
    async def container_health_response(self, container: Container) -> Dict[str, Any]:
        """Format container health check response"""
        try:
            response = {
                "success": True,
                "data": {
                    "container": {
                        "id": container.id,
                        "container_id": container.container_id,
                        "name": container.name,
                        "status": container.status,
                        "health_status": "healthy" if container.status == "running" else "unhealthy",
                        "uptime": self._calculate_uptime(container.created_at) if container.created_at else None
                    },
                    "health_check": {
                        "timestamp": datetime.utcnow().isoformat(),
                        "status": "healthy" if container.status == "running" else "unhealthy"
                    }
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error formatting container health response: {str(e)}")
            return await self.error_response(
                "Failed to format container health response",
                "CONTAINER_HEALTH_FORMAT_ERROR"
            )
    
    async def image_list_response(self, images: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Format Docker images list response"""
        try:
            response = {
                "success": True,
                "data": {
                    "images": images,
                    "total_count": len(images)
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error formatting image list response: {str(e)}")
            return await self.error_response(
                "Failed to format image list",
                "IMAGE_LIST_FORMAT_ERROR"
            )
    
    async def image_pull_response(self, image_info: Dict[str, Any]) -> Dict[str, Any]:
        """Format Docker image pull response"""
        try:
            response = {
                "success": True,
                "message": "Image pulled successfully",
                "data": {
                    "image": image_info
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error formatting image pull response: {str(e)}")
            return await self.error_response(
                "Failed to format image pull response",
                "IMAGE_PULL_FORMAT_ERROR"
            )
    
    def _calculate_uptime(self, created_at: datetime) -> str:
        """Calculate container uptime"""
        if not created_at:
            return "Unknown"
        
        uptime = datetime.utcnow() - created_at
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
