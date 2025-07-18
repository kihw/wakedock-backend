"""
Container validator for data validation - MVC Architecture
"""

from typing import Dict, Any, Optional, List
import re
from datetime import datetime

from wakedock.validators.base_validator import BaseValidator
from wakedock.core.exceptions import ValidationError

import logging
logger = logging.getLogger(__name__)


class ContainerValidator(BaseValidator):
    """Validator for container data validation"""
    
    def __init__(self):
        super().__init__()
        
        # Valid container statuses
        self.valid_statuses = [
            'created', 'running', 'paused', 'restarting', 
            'removing', 'exited', 'dead', 'stopped'
        ]
        
        # Valid log levels
        self.valid_log_levels = [
            'DEBUG', 'INFO', 'WARN', 'ERROR', 'FATAL'
        ]
        
        # Container name pattern (Docker naming rules)
        self.container_name_pattern = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]*$')
        
        # Container ID pattern (Docker container ID format)
        self.container_id_pattern = re.compile(r'^[a-f0-9]{12,64}$')
        
        # Image name pattern (Docker image naming rules)
        self.image_name_pattern = re.compile(
            r'^(?:[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(?::[0-9]+)?\/[a-zA-Z0-9]([a-zA-Z0-9\-._]{0,61}[a-zA-Z0-9])?(?::[a-zA-Z0-9]([a-zA-Z0-9\-._]{0,127}[a-zA-Z0-9])?)?$|^[a-zA-Z0-9]([a-zA-Z0-9\-._]{0,61}[a-zA-Z0-9])?(?::[a-zA-Z0-9]([a-zA-Z0-9\-._]{0,127}[a-zA-Z0-9])?)?$'
        )
    
    async def validate_container_creation(self, container_data: Dict[str, Any]) -> None:
        """Validate container creation data"""
        errors = []
        
        # Required fields
        required_fields = ['name', 'image']
        for field in required_fields:
            if field not in container_data or not container_data[field]:
                errors.append(f"Field '{field}' is required")
        
        # Validate container name
        if 'name' in container_data:
            await self._validate_container_name(container_data['name'], errors)
        
        # Validate image name
        if 'image' in container_data:
            await self._validate_image_name(container_data['image'], errors)
        
        # Validate ports
        if 'ports' in container_data:
            await self._validate_ports(container_data['ports'], errors)
        
        # Validate volumes
        if 'volumes' in container_data:
            await self._validate_volumes(container_data['volumes'], errors)
        
        # Validate environment variables
        if 'environment' in container_data:
            await self._validate_environment(container_data['environment'], errors)
        
        # Validate labels
        if 'labels' in container_data:
            await self._validate_labels(container_data['labels'], errors)
        
        # Validate restart policy
        if 'restart_policy' in container_data:
            await self._validate_restart_policy(container_data['restart_policy'], errors)
        
        # Validate resource limits
        if 'resources' in container_data:
            await self._validate_resources(container_data['resources'], errors)
        
        if errors:
            raise ValidationError(f"Container creation validation failed: {', '.join(errors)}")
    
    async def validate_container_id(self, container_id: str) -> None:
        """Validate container ID format"""
        if not container_id:
            raise ValidationError("Container ID is required")
        
        if not isinstance(container_id, str):
            raise ValidationError("Container ID must be a string")
        
        if not self.container_id_pattern.match(container_id):
            raise ValidationError("Invalid container ID format")
    
    async def validate_container_name(self, name: str) -> None:
        """Validate container name"""
        if not name:
            raise ValidationError("Container name is required")
        
        if not isinstance(name, str):
            raise ValidationError("Container name must be a string")
        
        if len(name) > 128:
            raise ValidationError("Container name must be 128 characters or less")
        
        if not self.container_name_pattern.match(name):
            raise ValidationError("Invalid container name format")
    
    async def validate_container_status(self, status: str) -> None:
        """Validate container status"""
        if not status:
            raise ValidationError("Container status is required")
        
        if not isinstance(status, str):
            raise ValidationError("Container status must be a string")
        
        if status not in self.valid_statuses:
            raise ValidationError(f"Invalid container status. Must be one of: {', '.join(self.valid_statuses)}")
    
    async def validate_log_level(self, level: str) -> None:
        """Validate log level"""
        if not level:
            raise ValidationError("Log level is required")
        
        if not isinstance(level, str):
            raise ValidationError("Log level must be a string")
        
        if level.upper() not in self.valid_log_levels:
            raise ValidationError(f"Invalid log level. Must be one of: {', '.join(self.valid_log_levels)}")
    
    async def validate_search_query(self, query: str) -> None:
        """Validate search query"""
        if not query:
            raise ValidationError("Search query is required")
        
        if not isinstance(query, str):
            raise ValidationError("Search query must be a string")
        
        if len(query) < 2:
            raise ValidationError("Search query must be at least 2 characters")
        
        if len(query) > 100:
            raise ValidationError("Search query must be 100 characters or less")
    
    async def validate_container_update(self, update_data: Dict[str, Any]) -> None:
        """Validate container update data"""
        errors = []
        
        # Validate allowed update fields
        allowed_fields = [
            'name', 'labels', 'restart_policy', 'resources',
            'environment', 'volumes', 'ports'
        ]
        
        for field in update_data:
            if field not in allowed_fields:
                errors.append(f"Field '{field}' is not allowed for updates")
        
        # Validate individual fields
        if 'name' in update_data:
            await self._validate_container_name(update_data['name'], errors)
        
        if 'labels' in update_data:
            await self._validate_labels(update_data['labels'], errors)
        
        if 'restart_policy' in update_data:
            await self._validate_restart_policy(update_data['restart_policy'], errors)
        
        if 'resources' in update_data:
            await self._validate_resources(update_data['resources'], errors)
        
        if 'environment' in update_data:
            await self._validate_environment(update_data['environment'], errors)
        
        if 'volumes' in update_data:
            await self._validate_volumes(update_data['volumes'], errors)
        
        if 'ports' in update_data:
            await self._validate_ports(update_data['ports'], errors)
        
        if errors:
            raise ValidationError(f"Container update validation failed: {', '.join(errors)}")
    
    async def validate_metrics_data(self, metrics: Dict[str, Any]) -> None:
        """Validate container metrics data"""
        errors = []
        
        # Required metrics fields
        required_fields = ['cpu_usage', 'memory_usage', 'memory_limit']
        for field in required_fields:
            if field not in metrics:
                errors.append(f"Metric '{field}' is required")
        
        # Validate CPU usage
        if 'cpu_usage' in metrics:
            if not isinstance(metrics['cpu_usage'], (int, float)):
                errors.append("CPU usage must be a number")
            elif metrics['cpu_usage'] < 0 or metrics['cpu_usage'] > 100:
                errors.append("CPU usage must be between 0 and 100")
        
        # Validate memory usage
        if 'memory_usage' in metrics:
            if not isinstance(metrics['memory_usage'], int):
                errors.append("Memory usage must be an integer")
            elif metrics['memory_usage'] < 0:
                errors.append("Memory usage must be non-negative")
        
        # Validate memory limit
        if 'memory_limit' in metrics:
            if not isinstance(metrics['memory_limit'], int):
                errors.append("Memory limit must be an integer")
            elif metrics['memory_limit'] < 0:
                errors.append("Memory limit must be non-negative")
        
        # Validate network metrics
        if 'network_rx' in metrics:
            if not isinstance(metrics['network_rx'], int):
                errors.append("Network RX must be an integer")
            elif metrics['network_rx'] < 0:
                errors.append("Network RX must be non-negative")
        
        if 'network_tx' in metrics:
            if not isinstance(metrics['network_tx'], int):
                errors.append("Network TX must be an integer")
            elif metrics['network_tx'] < 0:
                errors.append("Network TX must be non-negative")
        
        # Validate disk metrics
        if 'disk_read' in metrics:
            if not isinstance(metrics['disk_read'], int):
                errors.append("Disk read must be an integer")
            elif metrics['disk_read'] < 0:
                errors.append("Disk read must be non-negative")
        
        if 'disk_write' in metrics:
            if not isinstance(metrics['disk_write'], int):
                errors.append("Disk write must be an integer")
            elif metrics['disk_write'] < 0:
                errors.append("Disk write must be non-negative")
        
        if errors:
            raise ValidationError(f"Metrics validation failed: {', '.join(errors)}")
    
    async def validate_log_data(self, log_data: Dict[str, Any]) -> None:
        """Validate container log data"""
        errors = []
        
        # Required fields
        required_fields = ['message', 'level']
        for field in required_fields:
            if field not in log_data or not log_data[field]:
                errors.append(f"Field '{field}' is required")
        
        # Validate log level
        if 'level' in log_data:
            if log_data['level'].upper() not in self.valid_log_levels:
                errors.append(f"Invalid log level. Must be one of: {', '.join(self.valid_log_levels)}")
        
        # Validate message
        if 'message' in log_data:
            if not isinstance(log_data['message'], str):
                errors.append("Log message must be a string")
            elif len(log_data['message']) > 10000:
                errors.append("Log message must be 10000 characters or less")
        
        # Validate source
        if 'source' in log_data:
            if not isinstance(log_data['source'], str):
                errors.append("Log source must be a string")
            elif len(log_data['source']) > 100:
                errors.append("Log source must be 100 characters or less")
        
        if errors:
            raise ValidationError(f"Log data validation failed: {', '.join(errors)}")
    
    # Private helper methods
    async def _validate_container_name(self, name: str, errors: List[str]) -> None:
        """Helper to validate container name"""
        if not isinstance(name, str):
            errors.append("Container name must be a string")
        elif len(name) > 128:
            errors.append("Container name must be 128 characters or less")
        elif not self.container_name_pattern.match(name):
            errors.append("Invalid container name format")
    
    async def _validate_image_name(self, image: str, errors: List[str]) -> None:
        """Helper to validate image name"""
        if not isinstance(image, str):
            errors.append("Image name must be a string")
        elif len(image) > 255:
            errors.append("Image name must be 255 characters or less")
        # Note: Docker image validation is complex, simplified here
        elif not image.strip():
            errors.append("Image name cannot be empty")
    
    async def _validate_ports(self, ports: Dict[str, Any], errors: List[str]) -> None:
        """Helper to validate port mappings"""
        if not isinstance(ports, dict):
            errors.append("Ports must be a dictionary")
            return
        
        for container_port, host_port in ports.items():
            # Validate container port
            if not isinstance(container_port, str):
                errors.append("Container port must be a string")
            elif not container_port.isdigit():
                errors.append("Container port must be numeric")
            elif not (1 <= int(container_port) <= 65535):
                errors.append("Container port must be between 1 and 65535")
            
            # Validate host port
            if host_port is not None:
                if not isinstance(host_port, (int, str)):
                    errors.append("Host port must be a number or string")
                elif isinstance(host_port, str) and not host_port.isdigit():
                    errors.append("Host port must be numeric")
                elif not (1 <= int(host_port) <= 65535):
                    errors.append("Host port must be between 1 and 65535")
    
    async def _validate_volumes(self, volumes: Dict[str, Any], errors: List[str]) -> None:
        """Helper to validate volume mappings"""
        if not isinstance(volumes, dict):
            errors.append("Volumes must be a dictionary")
            return
        
        for host_path, container_path in volumes.items():
            # Validate host path
            if not isinstance(host_path, str):
                errors.append("Host path must be a string")
            elif not host_path.startswith('/'):
                errors.append("Host path must be absolute")
            
            # Validate container path
            if not isinstance(container_path, str):
                errors.append("Container path must be a string")
            elif not container_path.startswith('/'):
                errors.append("Container path must be absolute")
    
    async def _validate_environment(self, environment: Dict[str, Any], errors: List[str]) -> None:
        """Helper to validate environment variables"""
        if not isinstance(environment, dict):
            errors.append("Environment must be a dictionary")
            return
        
        for key, value in environment.items():
            # Validate key
            if not isinstance(key, str):
                errors.append("Environment variable key must be a string")
            elif not key.strip():
                errors.append("Environment variable key cannot be empty")
            elif '=' in key:
                errors.append("Environment variable key cannot contain '='")
            
            # Validate value
            if not isinstance(value, str):
                errors.append("Environment variable value must be a string")
    
    async def _validate_labels(self, labels: Dict[str, Any], errors: List[str]) -> None:
        """Helper to validate container labels"""
        if not isinstance(labels, dict):
            errors.append("Labels must be a dictionary")
            return
        
        for key, value in labels.items():
            # Validate key
            if not isinstance(key, str):
                errors.append("Label key must be a string")
            elif not key.strip():
                errors.append("Label key cannot be empty")
            
            # Validate value
            if not isinstance(value, str):
                errors.append("Label value must be a string")
    
    async def _validate_restart_policy(self, restart_policy: Dict[str, Any], errors: List[str]) -> None:
        """Helper to validate restart policy"""
        if not isinstance(restart_policy, dict):
            errors.append("Restart policy must be a dictionary")
            return
        
        valid_policies = ['no', 'always', 'on-failure', 'unless-stopped']
        
        if 'name' in restart_policy:
            if restart_policy['name'] not in valid_policies:
                errors.append(f"Invalid restart policy. Must be one of: {', '.join(valid_policies)}")
        
        if 'maximum_retry_count' in restart_policy:
            if not isinstance(restart_policy['maximum_retry_count'], int):
                errors.append("Maximum retry count must be an integer")
            elif restart_policy['maximum_retry_count'] < 0:
                errors.append("Maximum retry count must be non-negative")
    
    async def _validate_resources(self, resources: Dict[str, Any], errors: List[str]) -> None:
        """Helper to validate resource limits"""
        if not isinstance(resources, dict):
            errors.append("Resources must be a dictionary")
            return
        
        # Validate CPU limit
        if 'cpu_limit' in resources:
            if not isinstance(resources['cpu_limit'], (int, float)):
                errors.append("CPU limit must be a number")
            elif resources['cpu_limit'] <= 0:
                errors.append("CPU limit must be positive")
        
        # Validate memory limit
        if 'memory_limit' in resources:
            if not isinstance(resources['memory_limit'], int):
                errors.append("Memory limit must be an integer")
            elif resources['memory_limit'] <= 0:
                errors.append("Memory limit must be positive")
        
        # Validate CPU reservation
        if 'cpu_reservation' in resources:
            if not isinstance(resources['cpu_reservation'], (int, float)):
                errors.append("CPU reservation must be a number")
            elif resources['cpu_reservation'] < 0:
                errors.append("CPU reservation must be non-negative")
        
        # Validate memory reservation
        if 'memory_reservation' in resources:
            if not isinstance(resources['memory_reservation'], int):
                errors.append("Memory reservation must be an integer")
            elif resources['memory_reservation'] < 0:
                errors.append("Memory reservation must be non-negative")
