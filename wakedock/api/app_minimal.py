"""
Minimal FastAPI application for WakeDock - bypasses complex dependencies
"""

import logging
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import datetime
import json
import asyncio

logger = logging.getLogger(__name__)

# Response models
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    message: str = "WakeDock Backend (Minimal) is running"

class ServiceResponse(BaseModel):
    id: str
    name: str
    status: str
    image: str
    created_at: str
    updated_at: str

class SystemOverviewResponse(BaseModel):
    total_services: int
    running_services: int
    stopped_services: int
    total_containers: int
    system_uptime: str

def create_minimal_app() -> FastAPI:
    """Create minimal FastAPI application without complex dependencies"""
    
    app = FastAPI(
        title="WakeDock API (Minimal)",
        description="Minimal WakeDock API for debugging and development",
        version="0.1.0",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json"
    )
    
    # WebSocket connection manager
    class ConnectionManager:
        def __init__(self):
            self.active_connections: List[WebSocket] = []
        
        async def connect(self, websocket: WebSocket):
            await websocket.accept()
            self.active_connections.append(websocket)
        
        def disconnect(self, websocket: WebSocket):
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        
        async def send_message(self, message: str, websocket: WebSocket):
            try:
                await websocket.send_text(message)
            except:
                self.disconnect(websocket)
        
        async def broadcast(self, message: str):
            for connection in self.active_connections[:]:  # Copy list to avoid modification during iteration
                try:
                    await connection.send_text(message)
                except:
                    self.disconnect(connection)
    
    manager = ConnectionManager()
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Health endpoint
    @app.get("/api/v1/health", response_model=HealthResponse)
    async def health():
        return HealthResponse(
            status="healthy",
            timestamp=datetime.datetime.utcnow().isoformat()
        )
    
    # System overview endpoint
    @app.get("/api/v1/system/overview", response_model=SystemOverviewResponse)
    async def system_overview():
        return SystemOverviewResponse(
            total_services=5,
            running_services=3,
            stopped_services=2,
            total_containers=5,
            system_uptime="2 days, 4:30:15"
        )
    
    # Services endpoints (mock data)
    @app.get("/api/v1/services", response_model=List[ServiceResponse])
    async def get_services():
        mock_services = [
            {
                "id": "1",
                "name": "nginx-proxy",
                "status": "running",
                "image": "nginx:latest",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00"
            },
            {
                "id": "2",
                "name": "redis-cache",
                "status": "running",
                "image": "redis:alpine",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00"
            },
            {
                "id": "3",
                "name": "postgres-db",
                "status": "stopped",
                "image": "postgres:15",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00"
            }
        ]
        return [ServiceResponse(**service) for service in mock_services]
    
    @app.get("/api/v1/services/{service_id}", response_model=ServiceResponse)
    async def get_service(service_id: str):
        if service_id == "1":
            return ServiceResponse(
                id="1",
                name="nginx-proxy",
                status="running",
                image="nginx:latest",
                created_at="2024-01-01T00:00:00",
                updated_at="2024-01-01T00:00:00"
            )
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Auth endpoints (mock)
    class LoginRequest(BaseModel):
        username: str
        password: str
    
    @app.post("/api/v1/auth/login")
    async def login(credentials: LoginRequest):
        # Mock authentication - always succeed for testing
        return {
            "access_token": "mock-jwt-token",
            "token_type": "bearer",
            "user": {
                "id": 1,
                "username": credentials.username,
                "email": f"{credentials.username}@example.com",
                "role": "admin"
            }
        }
    
    @app.get("/api/v1/auth/me")
    async def get_current_user():
        return {
            "id": 1,
            "username": "admin",
            "email": "admin@example.com",
            "role": "admin"
        }
    
    # Containers endpoint
    @app.get("/api/v1/containers")
    async def get_containers():
        return []
    
    # Stacks endpoint
    @app.get("/api/v1/stacks")
    async def get_stacks():
        return []
    
    # WebSocket endpoint for monitoring
    @app.websocket("/api/v1/monitoring/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await manager.connect(websocket)
        try:
            # Start background task for periodic updates
            async def send_periodic_updates():
                while websocket in manager.active_connections:
                    await asyncio.sleep(5)
                    metrics_data = {
                        "type": "metrics_update",
                        "data": {
                            "container_id": "mock-container-1",
                            "container_name": "wakedock-core",
                            "timestamp": datetime.datetime.utcnow().isoformat(),
                            "cpu_percent": 45.2,
                            "memory_usage": 256000000,
                            "memory_limit": 512000000,
                            "memory_percent": 50.0,
                            "network_rx_bytes": 1024000,
                            "network_tx_bytes": 2048000,
                            "block_read_bytes": 500000,
                            "block_write_bytes": 300000,
                            "pids": 25
                        }
                    }
                    await manager.send_message(json.dumps(metrics_data), websocket)
            
            # Start the periodic updates task
            update_task = asyncio.create_task(send_periodic_updates())
            
            # Listen for incoming messages
            while True:
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    # Handle different message types
                    if message.get("action") == "ping":
                        await manager.send_message(json.dumps({"type": "pong"}), websocket)
                    elif message.get("action") == "subscribe":
                        # Handle subscription requests
                        stream_type = message.get("stream_type")
                        response = {
                            "type": "subscription_confirmed",
                            "stream_type": stream_type,
                            "message": f"Subscribed to {stream_type}"
                        }
                        await manager.send_message(json.dumps(response), websocket)
                    
                except json.JSONDecodeError:
                    await manager.send_message(json.dumps({"type": "error", "message": "Invalid JSON"}), websocket)
                    
        except WebSocketDisconnect:
            manager.disconnect(websocket)
            if 'update_task' in locals():
                update_task.cancel()
    
    # Container endpoints
    @app.get("/api/v1/monitoring/containers")
    async def monitoring_containers():
        return {
            "containers": [
                {
                    "container_id": "mock-container-1",
                    "container_name": "wakedock-core",
                    "service_name": "backend",
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "cpu_percent": 45.2,
                    "memory_usage": 256000000,
                    "memory_limit": 512000000,
                    "memory_percent": 50.0,
                    "network_rx_bytes": 1024000,
                    "network_tx_bytes": 2048000,
                    "block_read_bytes": 500000,
                    "block_write_bytes": 300000,
                    "pids": 25
                },
                {
                    "container_id": "mock-container-2",
                    "container_name": "wakedock-caddy",
                    "service_name": "proxy",
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "cpu_percent": 12.8,
                    "memory_usage": 128000000,
                    "memory_limit": 256000000,
                    "memory_percent": 50.0,
                    "network_rx_bytes": 2048000,
                    "network_tx_bytes": 1024000,
                    "block_read_bytes": 200000,
                    "block_write_bytes": 100000,
                    "pids": 15
                }
            ]
        }
    
    @app.post("/api/v1/monitoring/start")
    async def monitoring_start():
        return {"status": "started", "message": "Monitoring started successfully"}
    
    @app.post("/api/v1/monitoring/stop")
    async def monitoring_stop():
        return {"status": "stopped", "message": "Monitoring stopped successfully"}
    
    # Monitoring endpoints
    @app.get("/api/v1/monitoring/status")
    async def monitoring_status():
        return {
            "monitoring": {
                "is_running": True,
                "monitored_containers": 3,
                "collection_interval": 5,
                "retention_days": 30
            },
            "websocket": {
                "is_running": True,
                "active_connections": 1,
                "total_connections": 15,
                "messages_sent": 450
            },
            "thresholds": {
                "cpu_warning": 70,
                "cpu_critical": 90,
                "memory_warning": 80,
                "memory_critical": 95
            }
        }
    
    @app.get("/api/v1/monitoring/overview")
    async def monitoring_overview():
        return {
            "status": "healthy",
            "services_count": 5,
            "active_alerts": 2,
            "system_load": {
                "cpu": 45.2,
                "memory": 72.1,
                "disk": 23.8
            },
            "uptime": "2d 4h 30m"
        }
    
    @app.get("/api/v1/monitoring/metrics")
    async def monitoring_metrics():
        return {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "metrics": {
                "cpu_usage": 45.2,
                "memory_usage": 72.1,
                "disk_usage": 23.8,
                "network_io": {
                    "bytes_sent": 1024000,
                    "bytes_received": 2048000
                },
                "active_connections": 127
            }
        }
    
    @app.get("/api/v1/monitoring/alerts")
    async def monitoring_alerts():
        return [
            {
                "id": 1,
                "title": "High CPU Usage",
                "severity": "warning",
                "status": "active",
                "created_at": "2025-01-19T10:30:00Z",
                "description": "CPU usage above 80% for 5 minutes"
            },
            {
                "id": 2,
                "title": "Service Restart Required",
                "severity": "info",
                "status": "active", 
                "created_at": "2025-01-19T09:15:00Z",
                "description": "web-service needs restart"
            }
        ]
    
    # WebSocket monitoring endpoint (mock)
    @app.get("/api/v1/monitoring/live")
    async def monitoring_live():
        return {
            "status": "connected",
            "live_metrics": {
                "cpu": 45.2,
                "memory": 72.1,
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
        }
    
    # Logs endpoints
    @app.get("/api/v1/logs/status")
    async def logs_status():
        return {
            "status": "healthy",
            "total_logs": 15420,
            "log_sources": ["wakedock-core", "wakedock-caddy", "wakedock-dashboard"],
            "last_updated": datetime.datetime.utcnow().isoformat(),
            "storage_size": "125MB"
        }
    
    @app.get("/api/v1/logs/statistics")
    async def logs_statistics():
        return {
            "total_entries": 15420,
            "entries_by_level": {
                "error": 45,
                "warning": 123,
                "info": 14520,
                "debug": 732
            },
            "entries_by_service": {
                "wakedock-core": 8450,
                "wakedock-caddy": 4320,
                "wakedock-dashboard": 2650
            },
            "time_range": {
                "start": (datetime.datetime.utcnow() - datetime.timedelta(days=7)).isoformat(),
                "end": datetime.datetime.utcnow().isoformat()
            }
        }
    
    @app.get("/api/v1/logs/search")
    async def logs_search(limit: int = 50, page: int = 1, search: str = ""):
        # Simulate more results based on limit
        base_results = [
            {
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "level": "info",
                "service": "wakedock-core",
                "message": "Container metrics collected successfully"
            },
            {
                "timestamp": (datetime.datetime.utcnow() - datetime.timedelta(minutes=1)).isoformat(),
                "level": "warning",
                "service": "wakedock-caddy",
                "message": "High memory usage detected"
            },
            {
                "timestamp": (datetime.datetime.utcnow() - datetime.timedelta(minutes=2)).isoformat(),
                "level": "info",
                "service": "wakedock-dashboard",
                "message": "Dashboard server started"
            },
            {
                "timestamp": (datetime.datetime.utcnow() - datetime.timedelta(minutes=5)).isoformat(),
                "level": "error",
                "service": "wakedock-core",
                "message": "Failed to connect to database, retrying..."
            },
            {
                "timestamp": (datetime.datetime.utcnow() - datetime.timedelta(minutes=10)).isoformat(),
                "level": "info",
                "service": "wakedock-postgres",
                "message": "Database connection established"
            }
        ]
        
        # Apply search filter if provided
        results = base_results
        if search:
            results = [r for r in base_results if search.lower() in r["message"].lower()]
        
        # Apply pagination
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_results = results[start_idx:end_idx]
        
        return {
            "results": paginated_results,
            "total": len(results),
            "page": page,
            "limit": limit,
            "total_pages": (len(results) + limit - 1) // limit
        }
    
    # Error reporting endpoint
    @app.post("/api/error-report")
    async def error_report(error_data: dict):
        # Log the error for debugging purposes
        logger.error(f"Frontend error report: {error_data}")
        return {"status": "received", "message": "Error report logged"}
    
    logger.info("Minimal WakeDock API created successfully")
    return app

# Create the app instance
app = create_minimal_app()