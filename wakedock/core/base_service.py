"""
Base service class for WakeDock
"""
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseService(ABC):
    """Base class for all services"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"wakedock.{name}")
    
    @abstractmethod
    async def start(self):
        """Start the service"""
        pass
    
    @abstractmethod
    async def stop(self):
        """Stop the service"""
        pass
    
    async def health_check(self) -> bool:
        """Health check for the service"""
        return True
