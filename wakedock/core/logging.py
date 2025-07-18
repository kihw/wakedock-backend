"""
Core logging module for WakeDock application
"""

import logging
import sys
from typing import Optional
from pathlib import Path

# Default logging configuration
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DEFAULT_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def setup_logging(
    level: int = DEFAULT_LOG_LEVEL,
    format_str: str = DEFAULT_LOG_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT,
    log_file: Optional[str] = None
) -> None:
    """
    Set up application logging configuration
    
    Args:
        level: Logging level (default: INFO)
        format_str: Log message format string
        date_format: Date format string
        log_file: Optional log file path
    """
    
    # Create formatter
    formatter = logging.Formatter(format_str, date_format)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def set_log_level(level: int) -> None:
    """
    Set the logging level for the root logger
    
    Args:
        level: New logging level
    """
    logging.getLogger().setLevel(level)


# Logger instances for common modules
analytics_logger = get_logger('wakedock.analytics')
containers_logger = get_logger('wakedock.containers')
auth_logger = get_logger('wakedock.auth')
dashboard_logger = get_logger('wakedock.dashboard')
alerts_logger = get_logger('wakedock.alerts')
api_logger = get_logger('wakedock.api')
database_logger = get_logger('wakedock.database')

# Set up basic logging configuration
setup_logging()
