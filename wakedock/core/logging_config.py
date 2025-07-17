"""
Logging configuration for WakeDock
"""
import logging
import logging.config
from typing import Any, Dict


def setup_logging(config: Dict[str, Any] = None):
    """Setup logging configuration"""
    if config is None:
        config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'default': {
                    'format': '[%(asctime)s] %(name)s %(levelname)s: %(message)s'
                }
            },
            'handlers': {
                'console': {
                    'class': 'logging.StreamHandler',
                    'formatter': 'default'
                }
            },
            'root': {
                'level': 'INFO',
                'handlers': ['console']
            }
        }
    
    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """Get logger instance"""
    return logging.getLogger(name)
