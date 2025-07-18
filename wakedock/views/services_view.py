"""
Views for Docker services
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from wakedock.views.base_view import BaseView
from wakedock.models.stack import StackInfo, ContainerStackInfo


class ServicesView(BaseView):
    """View class for Docker services responses"""
    
    @staticmethod
    def service_detail_response(service: StackInfo) -> Dict[str, Any]:
        """Format a single service for API response"""
        return BaseView.success_response(
            data=ServicesView._format_service_data(service),
            message=f"Service '{service.name}' retrieved successfully"
        )
    
    @staticmethod
    def service_list_response(
        services: List[StackInfo],
        total: int,
        page: int,
        page_size: int
    ) -> Dict[str, Any]:
        """Format services list for API response"""
        formatted_services = [
            ServicesView._format_service_summary(service)
            for service in services
        ]
        
        return BaseView.paginated_response(
            items=formatted_services,
            total=total,
            page=page,
            page_size=page_size,
            message=f"Retrieved {len(services)} services"
        )
    
    @staticmethod
    def service_created_response(service: StackInfo) -> Dict[str, Any]:
        """Format service creation response"""
        return BaseView.created_response(
            data=ServicesView._format_service_data(service),
            message=f"Service '{service.name}' created successfully"
        )
    
    @staticmethod
    def service_updated_response(service: StackInfo) -> Dict[str, Any]:
        """Format service update response"""
        return BaseView.updated_response(
            data=ServicesView._format_service_data(service),
            message=f"Service '{service.name}' updated successfully"
        )
    
    @staticmethod
    def service_deleted_response(service_name: str) -> Dict[str, Any]:
        """Format service deletion response"""
        return BaseView.deleted_response(
            message=f"Service '{service_name}' deleted successfully"
        )
    
    @staticmethod
    def service_action_response(service: StackInfo, action: str) -> Dict[str, Any]:
        """Format service action response"""
        return BaseView.success_response(
            data=ServicesView._format_service_summary(service),
            message=f"Service '{service.name}' {action} completed successfully"
        )
    
    @staticmethod
    def service_logs_response(service_name: str, logs: List[str]) -> Dict[str, Any]:
        """Format service logs response"""
        return BaseView.success_response(
            data={
                "service_name": service_name,
                "logs": logs,
                "log_count": len(logs)
            },
            message=f"Retrieved {len(logs)} log entries for service '{service_name}'"
        )
    
    @staticmethod
    def service_stats_response(service_name: str, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Format service statistics response"""
        return BaseView.success_response(
            data={
                "service_name": service_name,
                "statistics": stats,
                "timestamp": datetime.utcnow().isoformat()
            },
            message=f"Service '{service_name}' statistics retrieved successfully"
        )
    
    @staticmethod
    def service_containers_response(
        service_name: str,
        containers: List[ContainerStackInfo]
    ) -> Dict[str, Any]:
        """Format service containers response"""
        formatted_containers = [
            ServicesView._format_container_data(container)
            for container in containers
        ]
        
        return BaseView.success_response(
            data={
                "service_name": service_name,
                "containers": formatted_containers,
                "container_count": len(containers)
            },
            message=f"Retrieved {len(containers)} containers for service '{service_name}'"
        )
    
    @staticmethod
    def services_summary_response(summary: Dict[str, Any]) -> Dict[str, Any]:
        """Format services summary response"""
        return BaseView.success_response(
            data=summary,
            message="Services summary retrieved successfully"
        )
    
    @staticmethod
    def bulk_action_response(results: Dict[str, Any], action: str) -> Dict[str, Any]:
        """Format bulk action response"""
        success_count = len(results.get('success', []))
        failed_count = len(results.get('failed', []))
        
        return BaseView.success_response(
            data=results,
            message=f"Bulk {action} completed: {success_count} successful, {failed_count} failed"
        )
    
    @staticmethod
    def service_not_found_response(service_id: str) -> Dict[str, Any]:
        """Format service not found response"""
        return BaseView.not_found_response(
            resource="Service",
            identifier=service_id
        )
    
    @staticmethod
    def service_validation_error_response(errors: List[str]) -> Dict[str, Any]:
        """Format service validation error response"""
        return BaseView.validation_error_response(
            message="Service validation failed",
            details={"errors": errors}
        )
    
    @staticmethod
    def service_conflict_response(service_name: str) -> Dict[str, Any]:
        """Format service conflict response"""
        return BaseView.error_response(
            message=f"Service '{service_name}' already exists",
            status_code=409,
            error_code="CONFLICT"
        )
    
    @staticmethod
    def service_operation_error_response(service_name: str, operation: str, error: str) -> Dict[str, Any]:
        """Format service operation error response"""
        return BaseView.error_response(
            message=f"Failed to {operation} service '{service_name}'",
            details={"error": error},
            status_code=500,
            error_code="OPERATION_ERROR"
        )
    
    # Private formatting methods
    @staticmethod
    def _format_service_data(service: StackInfo) -> Dict[str, Any]:
        """Format complete service data"""
        return {
            "id": service.id,
            "name": service.name,
            "type": service.type,
            "status": service.status,
            "created": service.created.isoformat() if service.created else None,
            "updated": service.updated.isoformat() if hasattr(service, 'updated') and service.updated else None,
            "description": getattr(service, 'description', None),
            "ports": getattr(service, 'ports', []),
            "environment": getattr(service, 'environment', {}),
            "volumes": getattr(service, 'volumes', []),
            "labels": getattr(service, 'labels', {}),
            "containers": getattr(service, 'containers', []),
            "networks": getattr(service, 'networks', []),
            "depends_on": getattr(service, 'depends_on', []),
            "health_check": getattr(service, 'health_check', None),
            "restart_policy": getattr(service, 'restart_policy', 'unless-stopped'),
            "resources": getattr(service, 'resources', {}),
            "metadata": {
                "compose_file": getattr(service, 'compose_file', None),
                "project_name": getattr(service, 'project_name', None),
                "tags": getattr(service, 'tags', [])
            }
        }
    
    @staticmethod
    def _format_service_summary(service: StackInfo) -> Dict[str, Any]:
        """Format service summary data"""
        return {
            "id": service.id,
            "name": service.name,
            "type": service.type,
            "status": service.status,
            "created": service.created.isoformat() if service.created else None,
            "description": getattr(service, 'description', None),
            "container_count": len(getattr(service, 'containers', [])),
            "port_count": len(getattr(service, 'ports', [])),
            "health_status": ServicesView._get_health_status(service),
            "quick_actions": ServicesView._get_quick_actions(service)
        }
    
    @staticmethod
    def _format_container_data(container: ContainerStackInfo) -> Dict[str, Any]:
        """Format container data"""
        return {
            "id": container.container_id,
            "name": container.container_name,
            "image": container.image,
            "status": container.status,
            "service_name": container.service_name,
            "replica_number": container.replica_number,
            "ports": container.ports,
            "environment": container.environment,
            "labels": container.labels,
            "depends_on": container.depends_on
        }
    
    @staticmethod
    def _get_health_status(service: StackInfo) -> str:
        """Get service health status"""
        if hasattr(service, 'health_check') and service.health_check:
            return service.health_check.get('status', 'unknown')
        
        # Infer health from service status
        if service.status == 'running':
            return 'healthy'
        elif service.status == 'error':
            return 'unhealthy'
        else:
            return 'unknown'
    
    @staticmethod
    def _get_quick_actions(service: StackInfo) -> List[str]:
        """Get available quick actions for service"""
        actions = []
        
        if service.status == 'running':
            actions.extend(['stop', 'restart', 'logs', 'stats'])
        elif service.status == 'stopped':
            actions.extend(['start', 'delete'])
        elif service.status == 'error':
            actions.extend(['restart', 'logs', 'rebuild'])
        
        # Always available actions
        actions.extend(['edit', 'clone'])
        
        return actions
    
    @staticmethod
    def format_service_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
        """Format service filters for display"""
        formatted_filters = {}
        
        if 'status' in filters and filters['status']:
            formatted_filters['status'] = filters['status']
        
        if 'type' in filters and filters['type']:
            formatted_filters['type'] = filters['type']
        
        if 'search' in filters and filters['search']:
            formatted_filters['search'] = filters['search']
        
        return formatted_filters
    
    @staticmethod
    def format_service_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Format service metrics for display"""
        return {
            "cpu_usage": f"{metrics.get('cpu_usage', 0):.1f}%",
            "memory_usage": f"{metrics.get('memory_usage', 0)} MB",
            "network_io": {
                "rx": f"{metrics.get('network_rx', 0) / 1024:.1f} KB",
                "tx": f"{metrics.get('network_tx', 0) / 1024:.1f} KB"
            },
            "disk_usage": f"{metrics.get('disk_usage', 0) / 1024 / 1024:.1f} MB",
            "uptime": metrics.get('uptime', 'unknown'),
            "last_updated": datetime.utcnow().isoformat()
        }
