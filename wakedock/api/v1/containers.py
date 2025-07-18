"""
Advanced Container Orchestration API for WakeDock v1.0.0

This module provides advanced container management capabilities including:
- Granular container controls
- Real-time monitoring
- Network management
- Volume and storage management
- Health checks and auto-recovery
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer
import docker
import psutil
import asyncio
import json
import logging
from pathlib import Path

from wakedock.core.database import get_database
from wakedock.core.security import get_current_user
from wakedock.core.docker_manager import DockerManager
from wakedock.models.user import User

# Initialize router
router = APIRouter(prefix="/api/v1/containers", tags=["containers"])
security = HTTPBearer()

# Pydantic models
class ContainerResource(BaseModel):
    cpu_usage: float
    memory_usage: float
    memory_limit: int
    network_rx: int
    network_tx: int
    disk_usage: int
    disk_limit: int

class ContainerStatus(BaseModel):
    id: str
    name: str
    image: str
    status: str
    state: str
    created_at: datetime
    started_at: Optional[datetime]
    ports: Dict[str, Any]
    networks: Dict[str, Any]
    volumes: List[str]
    environment: Dict[str, str]
    resources: ContainerResource
    health_status: Optional[str] = None
    restart_count: int = 0

class ContainerControl(BaseModel):
    action: str  # start, stop, restart, pause, unpause, kill
    force: bool = False
    signal: Optional[str] = None

class ContainerScaling(BaseModel):
    replicas: int
    service_name: str
    update_strategy: str = "rolling"

class NetworkConfig(BaseModel):
    name: str
    driver: str = "bridge"
    subnet: Optional[str] = None
    gateway: Optional[str] = None
    options: Dict[str, Any] = {}

class VolumeConfig(BaseModel):
    name: str
    driver: str = "local"
    options: Dict[str, Any] = {}
    labels: Dict[str, str] = {}

class HealthCheckConfig(BaseModel):
    test: List[str]
    interval: str = "30s"
    timeout: str = "5s"
    retries: int = 3
    start_period: str = "0s"

class ContainerLogs(BaseModel):
    container_id: str
    logs: List[str]
    timestamp: datetime
    stdout: bool = True
    stderr: bool = True
    tail: int = 100

class ContainerMetrics(BaseModel):
    container_id: str
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_usage: int
    memory_limit: int
    network_rx_bytes: int
    network_tx_bytes: int
    disk_read_bytes: int
    disk_write_bytes: int

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
    
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# Dependency injection
async def get_docker_manager():
    """Get Docker manager instance"""
    return DockerManager()

# Advanced Container Control Endpoints

@router.get("/", response_model=List[ContainerStatus])
async def list_containers(
    all_containers: bool = False,
    filters: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    docker_manager: DockerManager = Depends(get_docker_manager)
):
    """List all containers with detailed status"""
    try:
        containers = await docker_manager.list_containers(all=all_containers)
        container_statuses = []
        
        for container in containers:
            # Get container stats
            stats = await get_container_stats(container.id)
            
            # Get container details
            details = await docker_manager.get_container_details(container.id)
            
            container_status = ContainerStatus(
                id=container.id,
                name=container.name,
                image=container.image.tags[0] if container.image.tags else "unknown",
                status=container.status,
                state=container.attrs.get('State', {}).get('Status', 'unknown'),
                created_at=datetime.fromisoformat(container.attrs['Created'].replace('Z', '+00:00')),
                started_at=datetime.fromisoformat(container.attrs['State']['StartedAt'].replace('Z', '+00:00')) if container.attrs['State']['StartedAt'] != '0001-01-01T00:00:00Z' else None,
                ports=container.ports,
                networks=container.attrs.get('NetworkSettings', {}).get('Networks', {}),
                volumes=container.attrs.get('Mounts', []),
                environment=container.attrs.get('Config', {}).get('Env', []),
                resources=stats,
                health_status=container.attrs.get('State', {}).get('Health', {}).get('Status'),
                restart_count=container.attrs.get('RestartCount', 0)
            )
            
            container_statuses.append(container_status)
        
        return container_statuses
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list containers: {str(e)}")

@router.get("/{container_id}", response_model=ContainerStatus)
async def get_container_details(
    container_id: str,
    current_user: User = Depends(get_current_user),
    docker_manager: DockerManager = Depends(get_docker_manager)
):
    """Get detailed container information"""
    try:
        container = await docker_manager.get_container(container_id)
        if not container:
            raise HTTPException(status_code=404, detail="Container not found")
        
        # Get container stats
        stats = await get_container_stats(container_id)
        
        container_status = ContainerStatus(
            id=container.id,
            name=container.name,
            image=container.image.tags[0] if container.image.tags else "unknown",
            status=container.status,
            state=container.attrs.get('State', {}).get('Status', 'unknown'),
            created_at=datetime.fromisoformat(container.attrs['Created'].replace('Z', '+00:00')),
            started_at=datetime.fromisoformat(container.attrs['State']['StartedAt'].replace('Z', '+00:00')) if container.attrs['State']['StartedAt'] != '0001-01-01T00:00:00Z' else None,
            ports=container.ports,
            networks=container.attrs.get('NetworkSettings', {}).get('Networks', {}),
            volumes=container.attrs.get('Mounts', []),
            environment=container.attrs.get('Config', {}).get('Env', []),
            resources=stats,
            health_status=container.attrs.get('State', {}).get('Health', {}).get('Status'),
            restart_count=container.attrs.get('RestartCount', 0)
        )
        
        return container_status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get container details: {str(e)}")

@router.post("/{container_id}/control")
async def control_container(
    container_id: str,
    control: ContainerControl,
    current_user: User = Depends(get_current_user),
    docker_manager: DockerManager = Depends(get_docker_manager)
):
    """Control container (start, stop, restart, pause, unpause, kill)"""
    try:
        container = await docker_manager.get_container(container_id)
        if not container:
            raise HTTPException(status_code=404, detail="Container not found")
        
        result = None
        
        if control.action == "start":
            result = await docker_manager.start_container(container_id)
        elif control.action == "stop":
            result = await docker_manager.stop_container(container_id, force=control.force)
        elif control.action == "restart":
            result = await docker_manager.restart_container(container_id)
        elif control.action == "pause":
            result = await docker_manager.pause_container(container_id)
        elif control.action == "unpause":
            result = await docker_manager.unpause_container(container_id)
        elif control.action == "kill":
            result = await docker_manager.kill_container(container_id, signal=control.signal)
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
        
        # Broadcast status update
        await manager.broadcast(json.dumps({
            "type": "container_status_update",
            "container_id": container_id,
            "action": control.action,
            "timestamp": datetime.now().isoformat()
        }))
        
        return {
            "container_id": container_id,
            "action": control.action,
            "success": result,
            "message": f"Container {control.action} completed"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to control container: {str(e)}")

@router.get("/{container_id}/logs", response_model=ContainerLogs)
async def get_container_logs(
    container_id: str,
    tail: int = 100,
    since: Optional[str] = None,
    until: Optional[str] = None,
    stdout: bool = True,
    stderr: bool = True,
    current_user: User = Depends(get_current_user),
    docker_manager: DockerManager = Depends(get_docker_manager)
):
    """Get container logs"""
    try:
        container = await docker_manager.get_container(container_id)
        if not container:
            raise HTTPException(status_code=404, detail="Container not found")
        
        logs = await docker_manager.get_container_logs(
            container_id,
            tail=tail,
            since=since,
            until=until,
            stdout=stdout,
            stderr=stderr
        )
        
        return ContainerLogs(
            container_id=container_id,
            logs=logs,
            timestamp=datetime.now(),
            stdout=stdout,
            stderr=stderr,
            tail=tail
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get container logs: {str(e)}")

@router.get("/{container_id}/metrics", response_model=ContainerMetrics)
async def get_container_metrics(
    container_id: str,
    current_user: User = Depends(get_current_user),
    docker_manager: DockerManager = Depends(get_docker_manager)
):
    """Get real-time container metrics"""
    try:
        container = await docker_manager.get_container(container_id)
        if not container:
            raise HTTPException(status_code=404, detail="Container not found")
        
        stats = await get_container_stats(container_id)
        
        return ContainerMetrics(
            container_id=container_id,
            timestamp=datetime.now(),
            cpu_percent=stats.cpu_usage,
            memory_percent=stats.memory_usage,
            memory_usage=stats.memory_limit,
            memory_limit=stats.memory_limit,
            network_rx_bytes=stats.network_rx,
            network_tx_bytes=stats.network_tx,
            disk_read_bytes=stats.disk_usage,
            disk_write_bytes=stats.disk_limit
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get container metrics: {str(e)}")

@router.post("/{container_id}/exec")
async def exec_container_command(
    container_id: str,
    command: List[str],
    current_user: User = Depends(get_current_user),
    docker_manager: DockerManager = Depends(get_docker_manager)
):
    """Execute command in container"""
    try:
        container = await docker_manager.get_container(container_id)
        if not container:
            raise HTTPException(status_code=404, detail="Container not found")
        
        result = await docker_manager.exec_container(container_id, command)
        
        return {
            "container_id": container_id,
            "command": command,
            "exit_code": result.exit_code,
            "output": result.output.decode('utf-8') if result.output else "",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute command: {str(e)}")

# Network Management Endpoints

@router.get("/networks", response_model=List[Dict[str, Any]])
async def list_networks(
    current_user: User = Depends(get_current_user),
    docker_manager: DockerManager = Depends(get_docker_manager)
):
    """List all Docker networks"""
    try:
        networks = await docker_manager.list_networks()
        return [
            {
                "id": network.id,
                "name": network.name,
                "driver": network.attrs.get('Driver', 'unknown'),
                "scope": network.attrs.get('Scope', 'unknown'),
                "subnet": network.attrs.get('IPAM', {}).get('Config', [{}])[0].get('Subnet'),
                "gateway": network.attrs.get('IPAM', {}).get('Config', [{}])[0].get('Gateway'),
                "containers": len(network.attrs.get('Containers', {})),
                "created": network.attrs.get('Created')
            }
            for network in networks
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list networks: {str(e)}")

@router.post("/networks")
async def create_network(
    network_config: NetworkConfig,
    current_user: User = Depends(get_current_user),
    docker_manager: DockerManager = Depends(get_docker_manager)
):
    """Create a new Docker network"""
    try:
        network = await docker_manager.create_network(
            name=network_config.name,
            driver=network_config.driver,
            subnet=network_config.subnet,
            gateway=network_config.gateway,
            options=network_config.options
        )
        
        return {
            "id": network.id,
            "name": network.name,
            "driver": network_config.driver,
            "message": "Network created successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create network: {str(e)}")

@router.delete("/networks/{network_id}")
async def delete_network(
    network_id: str,
    current_user: User = Depends(get_current_user),
    docker_manager: DockerManager = Depends(get_docker_manager)
):
    """Delete a Docker network"""
    try:
        await docker_manager.delete_network(network_id)
        
        return {
            "network_id": network_id,
            "message": "Network deleted successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete network: {str(e)}")

@router.post("/{container_id}/networks/{network_id}/connect")
async def connect_container_to_network(
    container_id: str,
    network_id: str,
    current_user: User = Depends(get_current_user),
    docker_manager: DockerManager = Depends(get_docker_manager)
):
    """Connect container to network"""
    try:
        await docker_manager.connect_container_to_network(container_id, network_id)
        
        return {
            "container_id": container_id,
            "network_id": network_id,
            "message": "Container connected to network successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to connect container to network: {str(e)}")

@router.delete("/{container_id}/networks/{network_id}/disconnect")
async def disconnect_container_from_network(
    container_id: str,
    network_id: str,
    current_user: User = Depends(get_current_user),
    docker_manager: DockerManager = Depends(get_docker_manager)
):
    """Disconnect container from network"""
    try:
        await docker_manager.disconnect_container_from_network(container_id, network_id)
        
        return {
            "container_id": container_id,
            "network_id": network_id,
            "message": "Container disconnected from network successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to disconnect container from network: {str(e)}")

# Volume Management Endpoints

@router.get("/volumes", response_model=List[Dict[str, Any]])
async def list_volumes(
    current_user: User = Depends(get_current_user),
    docker_manager: DockerManager = Depends(get_docker_manager)
):
    """List all Docker volumes"""
    try:
        volumes = await docker_manager.list_volumes()
        return [
            {
                "name": volume.name,
                "driver": volume.attrs.get('Driver', 'unknown'),
                "mountpoint": volume.attrs.get('Mountpoint'),
                "created": volume.attrs.get('CreatedAt'),
                "scope": volume.attrs.get('Scope', 'unknown'),
                "labels": volume.attrs.get('Labels', {}),
                "options": volume.attrs.get('Options', {})
            }
            for volume in volumes
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list volumes: {str(e)}")

@router.post("/volumes")
async def create_volume(
    volume_config: VolumeConfig,
    current_user: User = Depends(get_current_user),
    docker_manager: DockerManager = Depends(get_docker_manager)
):
    """Create a new Docker volume"""
    try:
        volume = await docker_manager.create_volume(
            name=volume_config.name,
            driver=volume_config.driver,
            options=volume_config.options,
            labels=volume_config.labels
        )
        
        return {
            "name": volume.name,
            "driver": volume_config.driver,
            "message": "Volume created successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create volume: {str(e)}")

@router.delete("/volumes/{volume_name}")
async def delete_volume(
    volume_name: str,
    force: bool = False,
    current_user: User = Depends(get_current_user),
    docker_manager: DockerManager = Depends(get_docker_manager)
):
    """Delete a Docker volume"""
    try:
        await docker_manager.delete_volume(volume_name, force=force)
        
        return {
            "volume_name": volume_name,
            "message": "Volume deleted successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete volume: {str(e)}")

# Real-time monitoring WebSocket

@router.websocket("/ws/monitor")
async def websocket_monitor(websocket: WebSocket):
    """WebSocket endpoint for real-time container monitoring"""
    await manager.connect(websocket)
    try:
        while True:
            # Get system stats
            system_stats = {
                "timestamp": datetime.now().isoformat(),
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
                "network_io": psutil.net_io_counters()._asdict()
            }
            
            # Get container stats
            docker_client = docker.from_env()
            containers = docker_client.containers.list()
            
            container_stats = []
            for container in containers:
                try:
                    stats = container.stats(stream=False)
                    cpu_percent = calculate_cpu_percent(stats)
                    memory_percent = calculate_memory_percent(stats)
                    
                    container_stats.append({
                        "id": container.id,
                        "name": container.name,
                        "cpu_percent": cpu_percent,
                        "memory_percent": memory_percent,
                        "status": container.status
                    })
                except Exception:
                    continue
            
            # Send data
            await websocket.send_json({
                "type": "monitoring_data",
                "system": system_stats,
                "containers": container_stats
            })
            
            await asyncio.sleep(5)  # Update every 5 seconds
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Helper functions

async def get_container_stats(container_id: str) -> ContainerResource:
    """Get container resource usage statistics"""
    try:
        docker_client = docker.from_env()
        container = docker_client.containers.get(container_id)
        
        if container.status != 'running':
            return ContainerResource(
                cpu_usage=0.0,
                memory_usage=0.0,
                memory_limit=0,
                network_rx=0,
                network_tx=0,
                disk_usage=0,
                disk_limit=0
            )
        
        stats = container.stats(stream=False)
        
        cpu_percent = calculate_cpu_percent(stats)
        memory_percent = calculate_memory_percent(stats)
        
        return ContainerResource(
            cpu_usage=cpu_percent,
            memory_usage=memory_percent,
            memory_limit=stats.get('memory_stats', {}).get('limit', 0),
            network_rx=stats.get('networks', {}).get('eth0', {}).get('rx_bytes', 0),
            network_tx=stats.get('networks', {}).get('eth0', {}).get('tx_bytes', 0),
            disk_usage=stats.get('blkio_stats', {}).get('io_service_bytes_recursive', [{}])[0].get('value', 0),
            disk_limit=0  # Docker doesn't provide disk limit directly
        )
        
    except Exception as e:
        logging.error(f"Failed to get container stats: {str(e)}")
        return ContainerResource(
            cpu_usage=0.0,
            memory_usage=0.0,
            memory_limit=0,
            network_rx=0,
            network_tx=0,
            disk_usage=0,
            disk_limit=0
        )

def calculate_cpu_percent(stats: Dict[str, Any]) -> float:
    """Calculate CPU usage percentage from Docker stats"""
    try:
        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
        system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
        
        if system_delta > 0:
            return (cpu_delta / system_delta) * len(stats['cpu_stats']['cpu_usage']['percpu_usage']) * 100.0
        return 0.0
        
    except (KeyError, ZeroDivisionError):
        return 0.0

def calculate_memory_percent(stats: Dict[str, Any]) -> float:
    """Calculate memory usage percentage from Docker stats"""
    try:
        memory_usage = stats['memory_stats']['usage']
        memory_limit = stats['memory_stats']['limit']
        
        if memory_limit > 0:
            return (memory_usage / memory_limit) * 100.0
        return 0.0
        
    except (KeyError, ZeroDivisionError):
        return 0.0
