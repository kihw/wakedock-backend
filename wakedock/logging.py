"""
WakeDock Logging Module

Provides structured logging with correlation IDs, JSON formatting,
and integration with monitoring systems.
"""

import json
import logging
import logging.config
import os
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

from pythonjsonlogger import jsonlogger


# Context variable for correlation ID tracking
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


class CorrelationFilter(logging.Filter):
    """Add correlation ID to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id.get()
        record.service = "wakedock"
        record.version = getattr(__import__('wakedock'), '__version__', 'unknown')
        return True


class StructuredFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with additional fields."""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        super().add_fields(log_record, record, message_dict)
        
        # Add timestamp in ISO format
        log_record['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        
        # Add standard fields
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['service'] = getattr(record, 'service', 'wakedock')
        log_record['version'] = getattr(record, 'version', 'unknown')
        
        # Add correlation ID if present
        if hasattr(record, 'correlation_id') and record.correlation_id:
            log_record['correlation_id'] = record.correlation_id
        
        # Add file information
        log_record['file'] = {
            'name': record.filename,
            'line': record.lineno,
            'function': record.funcName
        }
        
        # Add process information
        log_record['process'] = {
            'id': os.getpid(),
            'name': record.processName,
            'thread': record.threadName
        }
        
        # Add custom fields from extra
        for key, value in message_dict.items():
            if key not in log_record:
                log_record[key] = value


class ColoredConsoleFormatter(logging.Formatter):
    """Colored formatter for console output."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        # Add correlation ID to message if present
        correlation_id_str = ""
        if hasattr(record, 'correlation_id') and record.correlation_id:
            correlation_id_str = f" [{record.correlation_id[:8]}]"
        
        # Format the message
        log_color = self.COLORS.get(record.levelname, '')
        reset = self.RESET
        
        # Create formatted message
        formatted = super().format(record)
        
        return f"{log_color}[{record.levelname}]{reset} {formatted}{correlation_id_str}"


def setup_logging(
    level: Union[str, int] = "INFO",
    log_file: Optional[Path] = None,
    json_logs: bool = True,
    console_logs: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> None:
    """
    Configure logging for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        json_logs: Whether to use JSON formatting for file logs
        console_logs: Whether to enable console logging
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup files to keep
    """
    
    # Create logs directory if needed
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Base configuration
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'console': {
                '()': ColoredConsoleFormatter,
                'format': '%(asctime)s - %(name)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'json': {
                '()': StructuredFormatter,
                'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
            },
            'plain': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            }
        },
        'filters': {
            'correlation': {
                '()': CorrelationFilter
            }
        },
        'handlers': {},
        'loggers': {
            'wakedock': {
                'level': level,
                'handlers': [],
                'propagate': False
            },
            'uvicorn': {
                'level': 'INFO',
                'handlers': [],
                'propagate': False
            },
            'uvicorn.access': {
                'level': 'INFO',
                'handlers': [],
                'propagate': False
            }
        },
        'root': {
            'level': level,
            'handlers': []
        }
    }
    
    # Console handler
    if console_logs:
        config['handlers']['console'] = {
            'class': 'logging.StreamHandler',
            'level': level,
            'formatter': 'console',
            'filters': ['correlation'],
            'stream': 'ext://sys.stdout'
        }
        
        # Add console handler to loggers
        for logger_name in config['loggers']:
            config['loggers'][logger_name]['handlers'].append('console')
        config['root']['handlers'].append('console')
    
    # File handler
    if log_file:
        config['handlers']['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': level,
            'formatter': 'json' if json_logs else 'plain',
            'filters': ['correlation'],
            'filename': str(log_file),
            'maxBytes': max_bytes,
            'backupCount': backup_count,
            'encoding': 'utf-8'
        }
        
        # Add file handler to loggers
        for logger_name in config['loggers']:
            config['loggers'][logger_name]['handlers'].append('file')
        config['root']['handlers'].append('file')
    
    # Apply configuration
    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance."""
    return logging.getLogger(name)


def set_correlation_id(correlation_id_value: Optional[str] = None) -> str:
    """
    Set correlation ID for current context.
    
    Args:
        correlation_id_value: Correlation ID to set. If None, generates a new UUID.
        
    Returns:
        The correlation ID that was set.
    """
    if correlation_id_value is None:
        correlation_id_value = str(uuid.uuid4())
    
    correlation_id.set(correlation_id_value)
    return correlation_id_value


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return correlation_id.get()


def clear_correlation_id() -> None:
    """Clear correlation ID from current context."""
    correlation_id.set(None)


class LoggerMixin:
    """Mixin class to add logging capabilities."""
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class."""
        return get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")


def log_function_call(func):
    """Decorator to log function calls with parameters and return values."""
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        
        # Log function entry
        logger.debug(
            f"Calling {func.__name__}",
            extra={
                'function': func.__name__,
                'module': func.__module__,
                'args_count': len(args),
                'kwargs_keys': list(kwargs.keys()),
                'event': 'function_call_start'
            }
        )
        
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            
            # Log successful completion
            duration = time.time() - start_time
            logger.debug(
                f"Completed {func.__name__}",
                extra={
                    'function': func.__name__,
                    'module': func.__module__,
                    'duration': duration,
                    'event': 'function_call_success'
                }
            )
            
            return result
            
        except Exception as e:
            # Log exception
            duration = time.time() - start_time
            logger.error(
                f"Error in {func.__name__}: {e}",
                extra={
                    'function': func.__name__,
                    'module': func.__module__,
                    'duration': duration,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'event': 'function_call_error'
                },
                exc_info=True
            )
            raise
    
    return wrapper


def log_async_function_call(func):
    """Decorator to log async function calls."""
    import functools
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        
        # Log function entry
        logger.debug(
            f"Calling async {func.__name__}",
            extra={
                'function': func.__name__,
                'module': func.__module__,
                'args_count': len(args),
                'kwargs_keys': list(kwargs.keys()),
                'event': 'async_function_call_start'
            }
        )
        
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            
            # Log successful completion
            duration = time.time() - start_time
            logger.debug(
                f"Completed async {func.__name__}",
                extra={
                    'function': func.__name__,
                    'module': func.__module__,
                    'duration': duration,
                    'event': 'async_function_call_success'
                }
            )
            
            return result
            
        except Exception as e:
            # Log exception
            duration = time.time() - start_time
            logger.error(
                f"Error in async {func.__name__}: {e}",
                extra={
                    'function': func.__name__,
                    'module': func.__module__,
                    'duration': duration,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'event': 'async_function_call_error'
                },
                exc_info=True
            )
            raise
    
    return wrapper


class RequestLogger:
    """Request logging middleware for FastAPI."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    async def __call__(self, request, call_next):
        # Generate correlation ID for this request
        request_id = set_correlation_id()
        
        # Extract request information
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Log request start
        start_time = time.time()
        self.logger.info(
            f"{request.method} {request.url.path}",
            extra={
                'event': 'request_start',
                'method': request.method,
                'path': request.url.path,
                'client_ip': client_ip,
                'user_agent': user_agent,
                'query_params': dict(request.query_params),
                'request_id': request_id
            }
        )
        
        try:
            response = await call_next(request)
            
            # Log successful response
            duration = time.time() - start_time
            self.logger.info(
                f"{request.method} {request.url.path} - {response.status_code}",
                extra={
                    'event': 'request_success',
                    'method': request.method,
                    'path': request.url.path,
                    'status_code': response.status_code,
                    'duration': duration,
                    'client_ip': client_ip,
                    'request_id': request_id
                }
            )
            
            return response
            
        except Exception as e:
            # Log request error
            duration = time.time() - start_time
            self.logger.error(
                f"{request.method} {request.url.path} - Error: {e}",
                extra={
                    'event': 'request_error',
                    'method': request.method,
                    'path': request.url.path,
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'duration': duration,
                    'client_ip': client_ip,
                    'request_id': request_id
                },
                exc_info=True
            )
            raise
        finally:
            # Clear correlation ID
            clear_correlation_id()


# Security-related logging functions
def log_security_event(event_type: str, details: Dict[str, Any], level: str = "WARNING") -> None:
    """Log security-related events."""
    security_logger = get_logger("wakedock.security")
    
    log_level = getattr(logging, level.upper(), logging.WARNING)
    security_logger.log(
        log_level,
        f"Security event: {event_type}",
        extra={
            'event': 'security_event',
            'event_type': event_type,
            'timestamp': datetime.utcnow().isoformat(),
            **details
        }
    )


def log_authentication_attempt(username: str, ip_address: str, success: bool, reason: Optional[str] = None) -> None:
    """Log authentication attempts."""
    log_security_event(
        "authentication_attempt",
        {
            'username': username,
            'ip_address': ip_address,
            'success': success,
            'reason': reason
        },
        level="INFO" if success else "WARNING"
    )


def log_authorization_failure(username: str, resource: str, action: str, ip_address: str) -> None:
    """Log authorization failures."""
    log_security_event(
        "authorization_failure",
        {
            'username': username,
            'resource': resource,
            'action': action,
            'ip_address': ip_address
        },
        level="WARNING"
    )


def log_rate_limit_exceeded(ip_address: str, endpoint: str, limit: int) -> None:
    """Log rate limit violations."""
    log_security_event(
        "rate_limit_exceeded",
        {
            'ip_address': ip_address,
            'endpoint': endpoint,
            'limit': limit
        },
        level="WARNING"
    )


# Initialize logging based on environment
def init_logging():
    """Initialize logging based on environment variables."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = os.getenv("LOG_FILE")
    json_logs = os.getenv("JSON_LOGS", "true").lower() == "true"
    console_logs = os.getenv("CONSOLE_LOGS", "true").lower() == "true"
    
    log_file_path = Path(log_file) if log_file else None
    
    setup_logging(
        level=log_level,
        log_file=log_file_path,
        json_logs=json_logs,
        console_logs=console_logs
    )


# Export commonly used items
__all__ = [
    'setup_logging',
    'get_logger',
    'set_correlation_id',
    'get_correlation_id',
    'clear_correlation_id',
    'LoggerMixin',
    'log_function_call',
    'log_async_function_call',
    'RequestLogger',
    'log_security_event',
    'log_authentication_attempt',
    'log_authorization_failure',
    'log_rate_limit_exceeded',
    'init_logging'
]
