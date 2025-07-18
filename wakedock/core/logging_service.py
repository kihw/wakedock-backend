"""
Centralized Logging Service for WakeDock
"""

import logging
import asyncio
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import time
import gzip
import os
from pathlib import Path
from collections import deque, defaultdict
import re

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogSource(Enum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    SYSTEM = "system"
    PLUGIN = "plugin"
    DOCKER = "docker"
    CADDY = "caddy"
    POSTGRES = "postgres"
    REDIS = "redis"


@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: float
    level: LogLevel
    source: LogSource
    service: str
    message: str
    context: Dict[str, Any] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.context is None:
            self.context = {}


class LoggingService:
    """
    Centralized logging service for collecting, processing, and analyzing logs
    """
    
    def __init__(self, log_dir: str = "logs", max_memory_logs: int = 10000):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        self.max_memory_logs = max_memory_logs
        self.memory_logs: deque = deque(maxlen=max_memory_logs)
        self.log_files: Dict[str, Path] = {}
        
        # Log statistics
        self.log_stats = {
            'total_logs': 0,
            'logs_by_level': defaultdict(int),
            'logs_by_source': defaultdict(int),
            'logs_by_service': defaultdict(int),
            'errors_by_service': defaultdict(int),
            'recent_errors': deque(maxlen=100)
        }
        
        # Log streaming
        self.log_streams: Dict[str, asyncio.Queue] = {}
        
        # Log rotation settings
        self.max_file_size = 50 * 1024 * 1024  # 50MB
        self.max_files = 10
        self.compression_enabled = True
        
        # Background tasks
        self.rotation_task = None
        self.cleanup_task = None
        
        # Start background tasks
        self.start_background_tasks()
    
    async def initialize(self) -> None:
        """Initialize logging service"""
        logger.info("Initializing centralized logging service")
        
        # Create log directories
        for source in LogSource:
            source_dir = self.log_dir / source.value
            source_dir.mkdir(exist_ok=True)
        
        # Load existing logs summary
        await self.load_log_summary()
        
        logger.info("Centralized logging service initialized")
    
    def start_background_tasks(self) -> None:
        """Start background tasks for log management"""
        self.rotation_task = asyncio.create_task(self.periodic_rotation())
        self.cleanup_task = asyncio.create_task(self.periodic_cleanup())
    
    async def periodic_rotation(self) -> None:
        """Periodic log rotation"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self.rotate_logs()
            except Exception as e:
                logger.error(f"Error in periodic rotation: {e}")
    
    async def periodic_cleanup(self) -> None:
        """Periodic cleanup of old logs"""
        while True:
            try:
                await asyncio.sleep(86400)  # Run every day
                await self.cleanup_old_logs()
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
    
    async def log(self, entry: LogEntry) -> None:
        """Log an entry"""
        try:
            # Add to memory logs
            self.memory_logs.append(entry)
            
            # Update statistics
            self.log_stats['total_logs'] += 1
            self.log_stats['logs_by_level'][entry.level.value] += 1
            self.log_stats['logs_by_source'][entry.source.value] += 1
            self.log_stats['logs_by_service'][entry.service] += 1
            
            # Track errors
            if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                self.log_stats['errors_by_service'][entry.service] += 1
                self.log_stats['recent_errors'].append(entry)
            
            # Write to file
            await self.write_to_file(entry)
            
            # Stream to subscribers
            await self.stream_log(entry)
            
        except Exception as e:
            logger.error(f"Error logging entry: {e}")
    
    async def write_to_file(self, entry: LogEntry) -> None:
        """Write log entry to file"""
        try:
            # Get log file path
            log_file = self.get_log_file_path(entry.source, entry.service)
            
            # Format log entry
            log_line = self.format_log_entry(entry)
            
            # Write to file
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_line + '\n')
            
            # Check if rotation is needed
            if log_file.stat().st_size > self.max_file_size:
                await self.rotate_log_file(log_file)
                
        except Exception as e:
            logger.error(f"Error writing to log file: {e}")
    
    def get_log_file_path(self, source: LogSource, service: str) -> Path:
        """Get log file path for source and service"""
        source_dir = self.log_dir / source.value
        return source_dir / f"{service}.log"
    
    def format_log_entry(self, entry: LogEntry) -> str:
        """Format log entry as JSON string"""
        entry_dict = asdict(entry)
        entry_dict['timestamp'] = datetime.fromtimestamp(entry.timestamp).isoformat()
        entry_dict['level'] = entry.level.value
        entry_dict['source'] = entry.source.value
        return json.dumps(entry_dict, ensure_ascii=False)
    
    async def stream_log(self, entry: LogEntry) -> None:
        """Stream log entry to subscribers"""
        try:
            # Stream to all active streams
            for stream_id, queue in list(self.log_streams.items()):
                try:
                    await queue.put(entry)
                except Exception as e:
                    logger.error(f"Error streaming log to {stream_id}: {e}")
                    # Remove broken stream
                    del self.log_streams[stream_id]
        except Exception as e:
            logger.error(f"Error streaming log: {e}")
    
    async def rotate_log_file(self, log_file: Path) -> None:
        """Rotate a single log file"""
        try:
            # Create rotated filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated_name = f"{log_file.stem}_{timestamp}.log"
            rotated_path = log_file.parent / rotated_name
            
            # Move current file to rotated name
            log_file.rename(rotated_path)
            
            # Compress if enabled
            if self.compression_enabled:
                await self.compress_log_file(rotated_path)
            
            # Clean up old files
            await self.cleanup_old_files(log_file.parent, log_file.stem)
            
            logger.info(f"Rotated log file: {log_file} -> {rotated_path}")
            
        except Exception as e:
            logger.error(f"Error rotating log file {log_file}: {e}")
    
    async def compress_log_file(self, log_file: Path) -> None:
        """Compress a log file"""
        try:
            compressed_path = log_file.with_suffix('.log.gz')
            
            with open(log_file, 'rb') as f_in:
                with gzip.open(compressed_path, 'wb') as f_out:
                    f_out.writelines(f_in)
            
            # Remove original file
            log_file.unlink()
            
            logger.info(f"Compressed log file: {log_file} -> {compressed_path}")
            
        except Exception as e:
            logger.error(f"Error compressing log file {log_file}: {e}")
    
    async def cleanup_old_files(self, directory: Path, prefix: str) -> None:
        """Clean up old log files"""
        try:
            # Get all log files with the prefix
            log_files = list(directory.glob(f"{prefix}_*.log*"))
            
            # Sort by modification time (newest first)
            log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            # Remove files beyond max_files limit
            for old_file in log_files[self.max_files:]:
                old_file.unlink()
                logger.info(f"Removed old log file: {old_file}")
                
        except Exception as e:
            logger.error(f"Error cleaning up old files: {e}")
    
    async def rotate_logs(self) -> None:
        """Rotate all log files that need rotation"""
        try:
            for source in LogSource:
                source_dir = self.log_dir / source.value
                if source_dir.exists():
                    for log_file in source_dir.glob("*.log"):
                        if log_file.stat().st_size > self.max_file_size:
                            await self.rotate_log_file(log_file)
        except Exception as e:
            logger.error(f"Error rotating logs: {e}")
    
    async def cleanup_old_logs(self) -> None:
        """Clean up old log files"""
        try:
            cutoff_time = time.time() - (30 * 24 * 3600)  # 30 days
            
            for source in LogSource:
                source_dir = self.log_dir / source.value
                if source_dir.exists():
                    for log_file in source_dir.glob("*"):
                        if log_file.stat().st_mtime < cutoff_time:
                            log_file.unlink()
                            logger.info(f"Removed old log file: {log_file}")
        except Exception as e:
            logger.error(f"Error cleaning up old logs: {e}")
    
    async def load_log_summary(self) -> None:
        """Load log summary from existing files"""
        try:
            # This would normally load from a summary file
            # For now, we'll just reset the stats
            self.log_stats = {
                'total_logs': 0,
                'logs_by_level': defaultdict(int),
                'logs_by_source': defaultdict(int),
                'logs_by_service': defaultdict(int),
                'errors_by_service': defaultdict(int),
                'recent_errors': deque(maxlen=100)
            }
        except Exception as e:
            logger.error(f"Error loading log summary: {e}")
    
    async def search_logs(self, query: str, 
                         level: Optional[LogLevel] = None,
                         source: Optional[LogSource] = None,
                         service: Optional[str] = None,
                         start_time: Optional[float] = None,
                         end_time: Optional[float] = None,
                         limit: int = 100) -> List[LogEntry]:
        """Search logs with filters"""
        try:
            results = []
            
            # Search in memory logs first
            for entry in reversed(self.memory_logs):
                if len(results) >= limit:
                    break
                
                # Apply filters
                if level and entry.level != level:
                    continue
                
                if source and entry.source != source:
                    continue
                
                if service and entry.service != service:
                    continue
                
                if start_time and entry.timestamp < start_time:
                    continue
                
                if end_time and entry.timestamp > end_time:
                    continue
                
                # Search in message and context
                if query:
                    search_text = f"{entry.message} {json.dumps(entry.context)}".lower()
                    if query.lower() not in search_text:
                        continue
                
                results.append(entry)
            
            # If we need more results, search in files
            if len(results) < limit:
                file_results = await self.search_log_files(
                    query, level, source, service, start_time, end_time, limit - len(results)
                )
                results.extend(file_results)
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Error searching logs: {e}")
            return []
    
    async def search_log_files(self, query: str,
                              level: Optional[LogLevel] = None,
                              source: Optional[LogSource] = None,
                              service: Optional[str] = None,
                              start_time: Optional[float] = None,
                              end_time: Optional[float] = None,
                              limit: int = 100) -> List[LogEntry]:
        """Search in log files"""
        try:
            results = []
            
            # Determine which files to search
            if source:
                sources = [source]
            else:
                sources = list(LogSource)
            
            for src in sources:
                if len(results) >= limit:
                    break
                
                source_dir = self.log_dir / src.value
                if not source_dir.exists():
                    continue
                
                # Get log files for this source
                log_files = []
                if service:
                    log_files.extend(source_dir.glob(f"{service}*.log*"))
                else:
                    log_files.extend(source_dir.glob("*.log*"))
                
                # Sort by modification time (newest first)
                log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                
                for log_file in log_files:
                    if len(results) >= limit:
                        break
                    
                    file_results = await self.search_single_file(
                        log_file, query, level, start_time, end_time, limit - len(results)
                    )
                    results.extend(file_results)
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Error searching log files: {e}")
            return []
    
    async def search_single_file(self, log_file: Path, query: str,
                               level: Optional[LogLevel] = None,
                               start_time: Optional[float] = None,
                               end_time: Optional[float] = None,
                               limit: int = 100) -> List[LogEntry]:
        """Search in a single log file"""
        try:
            results = []
            
            # Handle compressed files
            if log_file.suffix == '.gz':
                open_func = gzip.open
                mode = 'rt'
            else:
                open_func = open
                mode = 'r'
            
            with open_func(log_file, mode, encoding='utf-8') as f:
                for line in f:
                    if len(results) >= limit:
                        break
                    
                    try:
                        entry_dict = json.loads(line.strip())
                        
                        # Convert back to LogEntry
                        entry = LogEntry(
                            timestamp=datetime.fromisoformat(entry_dict['timestamp']).timestamp(),
                            level=LogLevel(entry_dict['level']),
                            source=LogSource(entry_dict['source']),
                            service=entry_dict['service'],
                            message=entry_dict['message'],
                            context=entry_dict.get('context', {}),
                            user_id=entry_dict.get('user_id'),
                            session_id=entry_dict.get('session_id'),
                            request_id=entry_dict.get('request_id'),
                            trace_id=entry_dict.get('trace_id'),
                            error_details=entry_dict.get('error_details')
                        )
                        
                        # Apply filters
                        if level and entry.level != level:
                            continue
                        
                        if start_time and entry.timestamp < start_time:
                            continue
                        
                        if end_time and entry.timestamp > end_time:
                            continue
                        
                        # Search in message and context
                        if query:
                            search_text = f"{entry.message} {json.dumps(entry.context)}".lower()
                            if query.lower() not in search_text:
                                continue
                        
                        results.append(entry)
                        
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        # Skip malformed log entries
                        continue
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching file {log_file}: {e}")
            return []
    
    async def get_log_stream(self, stream_id: str) -> asyncio.Queue:
        """Get a log stream for real-time log viewing"""
        try:
            if stream_id not in self.log_streams:
                self.log_streams[stream_id] = asyncio.Queue(maxsize=1000)
            
            return self.log_streams[stream_id]
            
        except Exception as e:
            logger.error(f"Error creating log stream: {e}")
            return asyncio.Queue(maxsize=1000)
    
    async def close_log_stream(self, stream_id: str) -> None:
        """Close a log stream"""
        try:
            if stream_id in self.log_streams:
                del self.log_streams[stream_id]
        except Exception as e:
            logger.error(f"Error closing log stream: {e}")
    
    async def get_log_stats(self) -> Dict[str, Any]:
        """Get logging statistics"""
        try:
            return {
                'total_logs': self.log_stats['total_logs'],
                'logs_by_level': dict(self.log_stats['logs_by_level']),
                'logs_by_source': dict(self.log_stats['logs_by_source']),
                'logs_by_service': dict(self.log_stats['logs_by_service']),
                'errors_by_service': dict(self.log_stats['errors_by_service']),
                'recent_errors_count': len(self.log_stats['recent_errors']),
                'memory_logs_count': len(self.memory_logs),
                'active_streams': len(self.log_streams),
                'log_files_size': await self.get_log_files_size()
            }
        except Exception as e:
            logger.error(f"Error getting log stats: {e}")
            return {}
    
    async def get_log_files_size(self) -> int:
        """Get total size of log files"""
        try:
            total_size = 0
            
            for source in LogSource:
                source_dir = self.log_dir / source.value
                if source_dir.exists():
                    for log_file in source_dir.glob("*"):
                        total_size += log_file.stat().st_size
            
            return total_size
            
        except Exception as e:
            logger.error(f"Error getting log files size: {e}")
            return 0
    
    async def export_logs(self, start_time: Optional[float] = None,
                         end_time: Optional[float] = None,
                         format: str = "json") -> Dict[str, Any]:
        """Export logs"""
        try:
            export_data = {
                'export_timestamp': time.time(),
                'start_time': start_time,
                'end_time': end_time,
                'format': format,
                'logs': []
            }
            
            # Export from memory logs
            for entry in self.memory_logs:
                if start_time and entry.timestamp < start_time:
                    continue
                
                if end_time and entry.timestamp > end_time:
                    continue
                
                export_data['logs'].append(asdict(entry))
            
            # Add metadata
            export_data['metadata'] = await self.get_log_stats()
            
            return export_data
            
        except Exception as e:
            logger.error(f"Error exporting logs: {e}")
            return {}
    
    async def get_recent_errors(self, limit: int = 50) -> List[LogEntry]:
        """Get recent error logs"""
        try:
            return list(self.log_stats['recent_errors'])[-limit:]
        except Exception as e:
            logger.error(f"Error getting recent errors: {e}")
            return []
    
    async def get_log_levels(self) -> List[str]:
        """Get available log levels"""
        return [level.value for level in LogLevel]
    
    async def get_log_sources(self) -> List[str]:
        """Get available log sources"""
        return [source.value for source in LogSource]
    
    async def get_log_services(self) -> List[str]:
        """Get available log services"""
        return list(self.log_stats['logs_by_service'].keys())


# Global logging service instance
logging_service = LoggingService()