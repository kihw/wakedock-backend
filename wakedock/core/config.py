"""
Configuration management for WakeDock core
"""
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class CoreConfig:
    """Core configuration manager"""
    
    def __init__(self):
        self.settings: Dict[str, Any] = {}
    
    def get(self, key: str, default=None):
        """Get configuration value"""
        return self.settings.get(key, default)
    
    def set(self, key: str, value: Any):
        """Set configuration value"""
        self.settings[key] = value


config = CoreConfig()
