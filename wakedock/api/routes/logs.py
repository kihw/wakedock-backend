"""
Logging API routes for WakeDock
"""

import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from datetime import datetime
import time
import json
import asyncio

from wakedock.core.auth import get_current_user
from wakedock.core.logging_service import logging_service, LogEntry, LogLevel, LogSource

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/logs", tags=["logs"])


class LogRequest(BaseModel):
    level: str
    source: str
    service: str
    message: str
    context: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    trace_id: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None


@router.get("/search")
async def search_logs(
    query: Optional[str] = Query(None, description="Search query"),
    level: Optional[str] = Query(None, description="Log level filter"),
    source: Optional[str] = Query(None, description="Log source filter"),
    service: Optional[str] = Query(None, description="Service filter"),
    start_time: Optional[float] = Query(None, description="Start time (Unix timestamp)"),
    end_time: Optional[float] = Query(None, description="End time (Unix timestamp)"),
    limit: int = Query(100, description="Maximum number of results"),
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Search logs with filters"""
    try:
        # Convert string enums to actual enums
        level_enum = LogLevel(level) if level else None
        source_enum = LogSource(source) if source else None
        
        # Search logs
        results = await logging_service.search_logs(
            query=query,
            level=level_enum,
            source=source_enum,
            service=service,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        
        # Convert results to dictionaries
        log_data = []
        for entry in results:
            log_dict = {
                'timestamp': entry.timestamp,
                'level': entry.level.value,
                'source': entry.source.value,
                'service': entry.service,
                'message': entry.message,
                'context': entry.context,
                'user_id': entry.user_id,
                'session_id': entry.session_id,
                'request_id': entry.request_id,
                'trace_id': entry.trace_id,
                'error_details': entry.error_details
            }
            log_data.append(log_dict)
        
        return {
            'success': True,
            'data': {
                'logs': log_data,
                'count': len(log_data),
                'query': query,
                'filters': {
                    'level': level,
                    'source': source,
                    'service': service,
                    'start_time': start_time,
                    'end_time': end_time,
                    'limit': limit
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to search logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to search logs")


@router.post("/")
async def create_log_entry(
    request: LogRequest,
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Create a new log entry"""
    try:
        # Create log entry
        entry = LogEntry(
            timestamp=time.time(),
            level=LogLevel(request.level),
            source=LogSource(request.source),
            service=request.service,
            message=request.message,
            context=request.context or {},
            user_id=request.user_id or user.get("id"),
            session_id=request.session_id,
            request_id=request.request_id,
            trace_id=request.trace_id,
            error_details=request.error_details
        )
        
        # Log the entry
        await logging_service.log(entry)
        
        return {
            'success': True,
            'message': 'Log entry created successfully'
        }
        
    except Exception as e:
        logger.error(f"Failed to create log entry: {e}")
        raise HTTPException(status_code=500, detail="Failed to create log entry")


@router.get("/stats")
async def get_log_stats(
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get logging statistics"""
    try:
        stats = await logging_service.get_log_stats()
        return {
            'success': True,
            'data': stats
        }
    except Exception as e:
        logger.error(f"Failed to get log stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get log stats")


@router.get("/tail")
async def tail_logs(
    service: Optional[str] = Query(None, description="Service to tail"),
    source: Optional[str] = Query(None, description="Source to tail"),
    level: Optional[str] = Query(None, description="Minimum log level"),
    lines: int = Query(100, description="Number of lines to return"),
    user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get latest log entries (tail functionality)"""
    try:
        # Convert string enums to actual enums
        level_enum = LogLevel(level) if level else None
        source_enum = LogSource(source) if source else None
        
        # Get recent logs
        results = await logging_service.search_logs(
            query=None,
            level=level_enum,
            source=source_enum,
            service=service,
            start_time=None,
            end_time=None,
            limit=lines
        )
        
        # Convert results to dictionaries
        log_data = []
        for entry in results:
            log_dict = {
                'timestamp': entry.timestamp,
                'level': entry.level.value,
                'source': entry.source.value,
                'service': entry.service,
                'message': entry.message,
                'context': entry.context,
                'user_id': entry.user_id,
                'session_id': entry.session_id,
                'request_id': entry.request_id,
                'trace_id': entry.trace_id,
                'error_details': entry.error_details
            }
            log_data.append(log_dict)
        
        return {
            'success': True,
            'data': {
                'logs': log_data,
                'count': len(log_data),
                'filters': {
                    'service': service,
                    'source': source,
                    'level': level,
                    'lines': lines
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to tail logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to tail logs")


# Initialize logging service on startup
@router.on_event("startup")
async def startup_event():
    """Initialize logging service"""
    await logging_service.initialize()
    logger.info("Logging service initialized")