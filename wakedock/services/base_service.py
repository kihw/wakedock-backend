"""
Base service class for WakeDock MVC architecture
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic
import logging
from datetime import datetime

# Type variable for service classes
ServiceType = TypeVar('ServiceType')


class BaseService(ABC):
    """Base service class for business logic operations"""
    
    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(f"wakedock.services.{self.name}")
        self._initialized = False
        self._config = {}
    
    async def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize the service with configuration"""
        if self._initialized:
            return
        
        self._config = config or {}
        await self._initialize_service()
        self._initialized = True
        self.logger.info(f"Service {self.name} initialized successfully")
    
    async def _initialize_service(self) -> None:
        """Override this method to implement service-specific initialization"""
        pass
    
    async def shutdown(self) -> None:
        """Shutdown the service gracefully"""
        if not self._initialized:
            return
        
        await self._shutdown_service()
        self._initialized = False
        self.logger.info(f"Service {self.name} shutdown successfully")
    
    async def _shutdown_service(self) -> None:
        """Override this method to implement service-specific shutdown"""
        pass
    
    def is_initialized(self) -> bool:
        """Check if the service is initialized"""
        return self._initialized
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self._config.get(key, default)
    
    def set_config(self, key: str, value: Any) -> None:
        """Set configuration value"""
        self._config[key] = value
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check for the service"""
        return {
            "service": self.name,
            "status": "healthy" if self._initialized else "not_initialized",
            "timestamp": datetime.utcnow().isoformat(),
            "details": await self._health_check_details()
        }
    
    async def _health_check_details(self) -> Dict[str, Any]:
        """Override this method to provide service-specific health check details"""
        return {}
    
    def log_info(self, message: str, **kwargs) -> None:
        """Log info message"""
        self.logger.info(message, extra=kwargs)
    
    def log_warning(self, message: str, **kwargs) -> None:
        """Log warning message"""
        self.logger.warning(message, extra=kwargs)
    
    def log_error(self, message: str, **kwargs) -> None:
        """Log error message"""
        self.logger.error(message, extra=kwargs)
    
    def log_debug(self, message: str, **kwargs) -> None:
        """Log debug message"""
        self.logger.debug(message, extra=kwargs)
    
    async def validate_input(self, data: Any, validation_rules: Optional[Dict[str, Any]] = None) -> bool:
        """Validate input data against rules"""
        if not validation_rules:
            return True
        
        # Implement basic validation logic
        for field, rules in validation_rules.items():
            if 'required' in rules and rules['required']:
                if not data.get(field):
                    raise ValueError(f"Field '{field}' is required")
            
            if 'type' in rules and data.get(field) is not None:
                expected_type = rules['type']
                if not isinstance(data.get(field), expected_type):
                    raise ValueError(f"Field '{field}' must be of type {expected_type.__name__}")
            
            if 'min_length' in rules and data.get(field) is not None:
                if len(str(data.get(field))) < rules['min_length']:
                    raise ValueError(f"Field '{field}' must be at least {rules['min_length']} characters long")
            
            if 'max_length' in rules and data.get(field) is not None:
                if len(str(data.get(field))) > rules['max_length']:
                    raise ValueError(f"Field '{field}' must be at most {rules['max_length']} characters long")
        
        return True
    
    async def execute_with_retry(
        self,
        func: callable,
        max_retries: int = 3,
        delay: float = 1.0,
        backoff_factor: float = 2.0,
        *args,
        **kwargs
    ) -> Any:
        """Execute a function with retry logic"""
        import asyncio
        
        for attempt in range(max_retries):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    self.log_error(f"Failed to execute function after {max_retries} attempts: {str(e)}")
                    raise
                
                self.log_warning(f"Attempt {attempt + 1} failed, retrying in {delay} seconds: {str(e)}")
                await asyncio.sleep(delay)
                delay *= backoff_factor
    
    async def process_batch(
        self,
        items: List[Any],
        batch_size: int = 100,
        processor: callable = None
    ) -> List[Any]:
        """Process items in batches"""
        if not processor:
            raise ValueError("Processor function is required")
        
        results = []
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            self.log_debug(f"Processing batch {i // batch_size + 1} with {len(batch)} items")
            
            if asyncio.iscoroutinefunction(processor):
                batch_results = await processor(batch)
            else:
                batch_results = processor(batch)
            
            results.extend(batch_results)
        
        return results
    
    async def cache_result(
        self,
        key: str,
        func: callable,
        ttl: int = 300,
        *args,
        **kwargs
    ) -> Any:
        """Cache function result (basic implementation)"""
        # This is a basic implementation - in production, use Redis or similar
        cache_key = f"{self.name}:{key}"
        
        # For now, just execute the function without caching
        # TODO: Implement proper caching mechanism
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics"""
        return {
            "service": self.name,
            "initialized": self._initialized,
            "config_keys": list(self._config.keys()),
            "timestamp": datetime.utcnow().isoformat()
        }
