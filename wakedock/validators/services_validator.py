"""
Validator for Docker services
"""

from typing import Dict, Any, List
import re

from wakedock.validators.base_validator import BaseValidator, ValidationError
from wakedock.models.stack import StackStatus, StackType


class ServicesValidator(BaseValidator):
    """Validator for Docker services"""
    
    def __init__(self, strict: bool = False):
        super().__init__(strict)
        self.service_name_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$'
        self.valid_statuses = [status.value for status in StackStatus]
        self.valid_types = [stack_type.value for stack_type in StackType]
    
    def _validate_data(self, data: Any) -> None:
        """Validate service data"""
        if not isinstance(data, dict):
            raise ValidationError("Service data must be a dictionary")
        
        # Required fields validation
        required_fields = ['name', 'type']
        for field in required_fields:
            if field not in data or not data[field]:
                raise ValidationError(f"Field '{field}' is required")
        
        # Service name validation
        self._validate_service_name(data['name'])
        
        # Service type validation
        self._validate_service_type(data['type'])
        
        # Service status validation (if provided)
        if 'status' in data and data['status']:
            self._validate_service_status(data['status'])
        
        # Ports validation (if provided)
        if 'ports' in data and data['ports']:
            self._validate_ports(data['ports'])
        
        # Environment variables validation (if provided)
        if 'environment' in data and data['environment']:
            self._validate_environment(data['environment'])
        
        # Volumes validation (if provided)
        if 'volumes' in data and data['volumes']:
            self._validate_volumes(data['volumes'])
        
        # Labels validation (if provided)
        if 'labels' in data and data['labels']:
            self._validate_labels(data['labels'])
    
    def validate_update(self, data: Dict[str, Any]) -> bool:
        """Validate service update data"""
        self.errors = []
        
        try:
            if not isinstance(data, dict):
                raise ValidationError("Service update data must be a dictionary")
            
            # Validate only provided fields
            if 'name' in data and data['name']:
                self._validate_service_name(data['name'])
            
            if 'type' in data and data['type']:
                self._validate_service_type(data['type'])
            
            if 'status' in data and data['status']:
                self._validate_service_status(data['status'])
            
            if 'ports' in data and data['ports']:
                self._validate_ports(data['ports'])
            
            if 'environment' in data and data['environment']:
                self._validate_environment(data['environment'])
            
            if 'volumes' in data and data['volumes']:
                self._validate_volumes(data['volumes'])
            
            if 'labels' in data and data['labels']:
                self._validate_labels(data['labels'])
            
            return len(self.errors) == 0
            
        except ValidationError as e:
            self.errors.append(e.message)
            return False
        except Exception as e:
            if self.strict:
                raise
            self.errors.append(str(e))
            return False
    
    def _validate_service_name(self, name: str) -> None:
        """Validate service name"""
        if not isinstance(name, str):
            raise ValidationError("Service name must be a string")
        
        if len(name) < 1:
            raise ValidationError("Service name cannot be empty")
        
        if len(name) > 63:
            raise ValidationError("Service name cannot exceed 63 characters")
        
        if not re.match(self.service_name_pattern, name):
            raise ValidationError(
                "Service name must start and end with alphanumeric characters "
                "and can contain dots, dashes, and underscores in between"
            )
        
        # Check for reserved names
        reserved_names = ['docker', 'localhost', 'host', 'gateway']
        if name.lower() in reserved_names:
            raise ValidationError(f"Service name '{name}' is reserved")
    
    def _validate_service_type(self, service_type: str) -> None:
        """Validate service type"""
        if not isinstance(service_type, str):
            raise ValidationError("Service type must be a string")
        
        if service_type not in self.valid_types:
            raise ValidationError(f"Service type must be one of: {self.valid_types}")
    
    def _validate_service_status(self, status: str) -> None:
        """Validate service status"""
        if not isinstance(status, str):
            raise ValidationError("Service status must be a string")
        
        if status not in self.valid_statuses:
            raise ValidationError(f"Service status must be one of: {self.valid_statuses}")
    
    def _validate_ports(self, ports: List[Dict[str, Any]]) -> None:
        """Validate service ports"""
        if not isinstance(ports, list):
            raise ValidationError("Ports must be a list")
        
        used_host_ports = set()
        
        for i, port in enumerate(ports):
            if not isinstance(port, dict):
                raise ValidationError(f"Port {i} must be a dictionary")
            
            # Required fields
            if 'host' not in port or 'container' not in port:
                raise ValidationError(f"Port {i} must have 'host' and 'container' fields")
            
            # Validate port numbers
            host_port = port['host']
            container_port = port['container']
            
            if not isinstance(host_port, int) or not (1 <= host_port <= 65535):
                raise ValidationError(f"Port {i} host port must be between 1 and 65535")
            
            if not isinstance(container_port, int) or not (1 <= container_port <= 65535):
                raise ValidationError(f"Port {i} container port must be between 1 and 65535")
            
            # Check for duplicate host ports
            if host_port in used_host_ports:
                raise ValidationError(f"Port {i} host port {host_port} is already used")
            used_host_ports.add(host_port)
            
            # Validate protocol
            if 'protocol' in port:
                protocol = port['protocol']
                if protocol not in ['tcp', 'udp']:
                    raise ValidationError(f"Port {i} protocol must be 'tcp' or 'udp'")
    
    def _validate_environment(self, environment: Dict[str, str]) -> None:
        """Validate environment variables"""
        if not isinstance(environment, dict):
            raise ValidationError("Environment must be a dictionary")
        
        for key, value in environment.items():
            if not isinstance(key, str):
                raise ValidationError(f"Environment key must be a string: {key}")
            
            if not key:
                raise ValidationError("Environment key cannot be empty")
            
            if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', key):
                raise ValidationError(f"Environment key '{key}' contains invalid characters")
            
            if not isinstance(value, str):
                raise ValidationError(f"Environment value for '{key}' must be a string")
    
    def _validate_volumes(self, volumes: List[Dict[str, Any]]) -> None:
        """Validate service volumes"""
        if not isinstance(volumes, list):
            raise ValidationError("Volumes must be a list")
        
        for i, volume in enumerate(volumes):
            if not isinstance(volume, dict):
                raise ValidationError(f"Volume {i} must be a dictionary")
            
            # Required fields
            if 'host' not in volume or 'container' not in volume:
                raise ValidationError(f"Volume {i} must have 'host' and 'container' fields")
            
            # Validate paths
            host_path = volume['host']
            container_path = volume['container']
            
            if not isinstance(host_path, str) or not host_path:
                raise ValidationError(f"Volume {i} host path must be a non-empty string")
            
            if not isinstance(container_path, str) or not container_path:
                raise ValidationError(f"Volume {i} container path must be a non-empty string")
            
            # Validate container path format
            if not container_path.startswith('/'):
                raise ValidationError(f"Volume {i} container path must be absolute")
            
            # Validate mode
            if 'mode' in volume:
                mode = volume['mode']
                if mode not in ['rw', 'ro']:
                    raise ValidationError(f"Volume {i} mode must be 'rw' or 'ro'")
    
    def _validate_labels(self, labels: Dict[str, str]) -> None:
        """Validate service labels"""
        if not isinstance(labels, dict):
            raise ValidationError("Labels must be a dictionary")
        
        for key, value in labels.items():
            if not isinstance(key, str):
                raise ValidationError(f"Label key must be a string: {key}")
            
            if not isinstance(value, str):
                raise ValidationError(f"Label value for '{key}' must be a string")
            
            if not key:
                raise ValidationError("Label key cannot be empty")
            
            # Validate label key format (Docker label format)
            if not re.match(r'^[a-z0-9]([a-z0-9._-]*[a-z0-9])?$', key):
                raise ValidationError(f"Label key '{key}' contains invalid characters")
    
    def validate_service_action(self, action: str) -> bool:
        """Validate service action"""
        self.errors = []
        
        if not isinstance(action, str):
            self.errors.append("Action must be a string")
            return False
        
        valid_actions = ['start', 'stop', 'restart', 'rebuild', 'delete', 'pause', 'unpause']
        if action.lower() not in valid_actions:
            self.errors.append(f"Action must be one of: {valid_actions}")
            return False
        
        return True
    
    def validate_service_filters(self, filters: Dict[str, Any]) -> bool:
        """Validate service filters"""
        self.errors = []
        
        if not isinstance(filters, dict):
            self.errors.append("Filters must be a dictionary")
            return False
        
        # Validate status filter
        if 'status' in filters:
            status = filters['status']
            if status and status not in self.valid_statuses:
                self.errors.append(f"Status filter must be one of: {self.valid_statuses}")
        
        # Validate type filter
        if 'type' in filters:
            service_type = filters['type']
            if service_type and service_type not in self.valid_types:
                self.errors.append(f"Type filter must be one of: {self.valid_types}")
        
        # Validate search filter
        if 'search' in filters:
            search = filters['search']
            if search and not isinstance(search, str):
                self.errors.append("Search filter must be a string")
        
        return len(self.errors) == 0
    
    def validate_pagination(self, page: int, page_size: int) -> bool:
        """Validate pagination parameters"""
        self.errors = []
        
        if not isinstance(page, int) or page < 1:
            self.errors.append("Page must be a positive integer")
        
        if not isinstance(page_size, int) or page_size < 1 or page_size > 100:
            self.errors.append("Page size must be between 1 and 100")
        
        return len(self.errors) == 0
