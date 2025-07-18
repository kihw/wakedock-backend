"""
GraphQL resolvers for WakeDock
"""

import strawberry
from typing import List, Optional, Dict, Any, AsyncGenerator
from datetime import datetime
import asyncio
import json

from ..core.container_service import ContainerService
from ..core.service_manager import ServiceManager
from ..core.network_manager import NetworkManager
from ..core.volume_manager import VolumeManager
from ..core.system_monitor import SystemMonitor
from ..core.stats_collector import StatsCollector
from .types import (
    Container, Service, Network, Volume, SystemInfo, HealthCheck,
    ContainerStats, ServiceStats, NetworkStats, VolumeStats,
    ContainerInput, ServiceInput, NetworkInput, VolumeInput,
    PaginationInput, FilterInput, SortInput
)


class ContainerResolver:
    """Container GraphQL resolvers"""
    
    @staticmethod
    async def get_containers(
        info,
        pagination: Optional[PaginationInput] = None,
        filter: Optional[FilterInput] = None,
        sort: Optional[SortInput] = None
    ) -> List[Container]:
        """Get all containers with optional filtering and pagination"""
        container_service = ContainerService()
        
        # Apply filters
        filters = {}
        if filter:
            if filter.status:
                filters['status'] = filter.status
            if filter.labels:
                filters['labels'] = filter.labels
            if filter.created_since:
                filters['created_since'] = filter.created_since
            if filter.created_before:
                filters['created_before'] = filter.created_before
        
        # Apply sorting
        sort_by = None
        if sort:
            sort_by = f"{sort.field}:{sort.direction}"
        
        # Apply pagination
        limit = pagination.limit if pagination else 20
        offset = pagination.offset if pagination else 0
        
        containers = await container_service.get_containers(
            filters=filters,
            sort_by=sort_by,
            limit=limit,
            offset=offset
        )
        
        return [ContainerResolver._convert_container(c) for c in containers]
    
    @staticmethod
    async def get_container(info, container_id: str) -> Optional[Container]:
        """Get a specific container by ID"""
        container_service = ContainerService()
        container = await container_service.get_container(container_id)
        
        if container:
            return ContainerResolver._convert_container(container)
        return None
    
    @staticmethod
    async def start_container(info, container_id: str) -> Container:
        """Start a container"""
        container_service = ContainerService()
        await container_service.start_container(container_id)
        container = await container_service.get_container(container_id)
        return ContainerResolver._convert_container(container)
    
    @staticmethod
    async def stop_container(info, container_id: str) -> Container:
        """Stop a container"""
        container_service = ContainerService()
        await container_service.stop_container(container_id)
        container = await container_service.get_container(container_id)
        return ContainerResolver._convert_container(container)
    
    @staticmethod
    async def restart_container(info, container_id: str) -> Container:
        """Restart a container"""
        container_service = ContainerService()
        await container_service.restart_container(container_id)
        container = await container_service.get_container(container_id)
        return ContainerResolver._convert_container(container)
    
    @staticmethod
    async def remove_container(info, container_id: str, force: bool = False) -> bool:
        """Remove a container"""
        container_service = ContainerService()
        return await container_service.remove_container(container_id, force=force)
    
    @staticmethod
    async def container_events(info, container_id: Optional[str] = None) -> AsyncGenerator[Container, None]:
        """Subscribe to container events"""
        container_service = ContainerService()
        
        async for event in container_service.watch_events(container_id):
            if event.get('Type') == 'container':
                container = await container_service.get_container(event.get('Actor', {}).get('ID'))
                if container:
                    yield ContainerResolver._convert_container(container)
    
    @staticmethod
    def _convert_container(container_data: Dict[str, Any]) -> Container:
        """Convert container data to GraphQL type"""
        return Container(
            id=container_data['id'],
            name=container_data['name'],
            image=container_data['image'],
            status=container_data['status'],
            state=container_data['state'],
            created=container_data['created'],
            started=container_data.get('started'),
            finished=container_data.get('finished'),
            ports=container_data.get('ports', []),
            mounts=container_data.get('mounts', []),
            labels=container_data.get('labels', {}),
            env_vars=container_data.get('env_vars', {}),
            networks=container_data.get('networks', []),
            restart_policy=container_data.get('restart_policy', 'no'),
            cpu_percent=container_data.get('cpu_percent'),
            memory_usage=container_data.get('memory_usage'),
            memory_limit=container_data.get('memory_limit'),
        )


class ServiceResolver:
    """Service GraphQL resolvers"""
    
    @staticmethod
    async def get_services(
        info,
        pagination: Optional[PaginationInput] = None,
        filter: Optional[FilterInput] = None
    ) -> List[Service]:
        """Get all services"""
        service_manager = ServiceManager()
        
        filters = {}
        if filter:
            if filter.status:
                filters['status'] = filter.status
            if filter.labels:
                filters['labels'] = filter.labels
        
        limit = pagination.limit if pagination else 20
        offset = pagination.offset if pagination else 0
        
        services = await service_manager.get_services(
            filters=filters,
            limit=limit,
            offset=offset
        )
        
        return [ServiceResolver._convert_service(s) for s in services]
    
    @staticmethod
    async def get_service(info, service_id: str) -> Optional[Service]:
        """Get a specific service"""
        service_manager = ServiceManager()
        service = await service_manager.get_service(service_id)
        
        if service:
            return ServiceResolver._convert_service(service)
        return None
    
    @staticmethod
    async def create_service(info, service_input: ServiceInput) -> Service:
        """Create a new service"""
        service_manager = ServiceManager()
        
        service_config = {
            'name': service_input.name,
            'image': service_input.image,
            'replicas': service_input.replicas,
            'ports': service_input.ports or [],
            'env_vars': service_input.env_vars or {},
            'networks': service_input.networks or [],
            'labels': service_input.labels or {},
            'constraints': service_input.constraints or [],
            'mode': service_input.mode,
        }
        
        service = await service_manager.create_service(service_config)
        return ServiceResolver._convert_service(service)
    
    @staticmethod
    async def update_service(info, service_id: str, service_input: ServiceInput) -> Service:
        """Update an existing service"""
        service_manager = ServiceManager()
        
        service_config = {
            'name': service_input.name,
            'image': service_input.image,
            'replicas': service_input.replicas,
            'ports': service_input.ports or [],
            'env_vars': service_input.env_vars or {},
            'networks': service_input.networks or [],
            'labels': service_input.labels or {},
            'constraints': service_input.constraints or [],
            'mode': service_input.mode,
        }
        
        service = await service_manager.update_service(service_id, service_config)
        return ServiceResolver._convert_service(service)
    
    @staticmethod
    async def delete_service(info, service_id: str) -> bool:
        """Delete a service"""
        service_manager = ServiceManager()
        return await service_manager.delete_service(service_id)
    
    @staticmethod
    async def service_events(info, service_id: Optional[str] = None) -> AsyncGenerator[Service, None]:
        """Subscribe to service events"""
        service_manager = ServiceManager()
        
        async for event in service_manager.watch_events(service_id):
            if event.get('Type') == 'service':
                service = await service_manager.get_service(event.get('Actor', {}).get('ID'))
                if service:
                    yield ServiceResolver._convert_service(service)
    
    @staticmethod
    def _convert_service(service_data: Dict[str, Any]) -> Service:
        """Convert service data to GraphQL type"""
        return Service(
            id=service_data['id'],
            name=service_data['name'],
            image=service_data['image'],
            replicas=service_data.get('replicas', 1),
            status=service_data['status'],
            created=service_data['created'],
            updated=service_data.get('updated', service_data['created']),
            ports=service_data.get('ports', []),
            networks=service_data.get('networks', []),
            labels=service_data.get('labels', {}),
            env_vars=service_data.get('env_vars', {}),
            constraints=service_data.get('constraints', []),
            mode=service_data.get('mode', 'replicated'),
            endpoint_mode=service_data.get('endpoint_mode', 'vip'),
        )


class NetworkResolver:
    """Network GraphQL resolvers"""
    
    @staticmethod
    async def get_networks(info) -> List[Network]:
        """Get all networks"""
        network_manager = NetworkManager()
        networks = await network_manager.get_networks()
        return [NetworkResolver._convert_network(n) for n in networks]
    
    @staticmethod
    async def get_network(info, network_id: str) -> Optional[Network]:
        """Get a specific network"""
        network_manager = NetworkManager()
        network = await network_manager.get_network(network_id)
        
        if network:
            return NetworkResolver._convert_network(network)
        return None
    
    @staticmethod
    async def create_network(info, network_input: NetworkInput) -> Network:
        """Create a new network"""
        network_manager = NetworkManager()
        
        network_config = {
            'name': network_input.name,
            'driver': network_input.driver,
            'internal': network_input.internal,
            'attachable': network_input.attachable,
            'labels': network_input.labels or {},
            'ipam_config': network_input.ipam_config or [],
        }
        
        network = await network_manager.create_network(network_config)
        return NetworkResolver._convert_network(network)
    
    @staticmethod
    async def remove_network(info, network_id: str) -> bool:
        """Remove a network"""
        network_manager = NetworkManager()
        return await network_manager.remove_network(network_id)
    
    @staticmethod
    def _convert_network(network_data: Dict[str, Any]) -> Network:
        """Convert network data to GraphQL type"""
        return Network(
            id=network_data['id'],
            name=network_data['name'],
            driver=network_data['driver'],
            scope=network_data.get('scope', 'local'),
            internal=network_data.get('internal', False),
            attachable=network_data.get('attachable', True),
            ingress=network_data.get('ingress', False),
            ipam_config=network_data.get('ipam_config', []),
            containers=network_data.get('containers', []),
            services=network_data.get('services', []),
            created=network_data['created'],
            labels=network_data.get('labels', {}),
        )


class VolumeResolver:
    """Volume GraphQL resolvers"""
    
    @staticmethod
    async def get_volumes(info) -> List[Volume]:
        """Get all volumes"""
        volume_manager = VolumeManager()
        volumes = await volume_manager.get_volumes()
        return [VolumeResolver._convert_volume(v) for v in volumes]
    
    @staticmethod
    async def get_volume(info, volume_name: str) -> Optional[Volume]:
        """Get a specific volume"""
        volume_manager = VolumeManager()
        volume = await volume_manager.get_volume(volume_name)
        
        if volume:
            return VolumeResolver._convert_volume(volume)
        return None
    
    @staticmethod
    async def create_volume(info, volume_input: VolumeInput) -> Volume:
        """Create a new volume"""
        volume_manager = VolumeManager()
        
        volume_config = {
            'name': volume_input.name,
            'driver': volume_input.driver,
            'labels': volume_input.labels or {},
            'driver_opts': volume_input.driver_opts or {},
        }
        
        volume = await volume_manager.create_volume(volume_config)
        return VolumeResolver._convert_volume(volume)
    
    @staticmethod
    async def remove_volume(info, volume_name: str, force: bool = False) -> bool:
        """Remove a volume"""
        volume_manager = VolumeManager()
        return await volume_manager.remove_volume(volume_name, force=force)
    
    @staticmethod
    def _convert_volume(volume_data: Dict[str, Any]) -> Volume:
        """Convert volume data to GraphQL type"""
        return Volume(
            name=volume_data['name'],
            driver=volume_data['driver'],
            mountpoint=volume_data['mountpoint'],
            created=volume_data['created'],
            labels=volume_data.get('labels', {}),
            scope=volume_data.get('scope', 'local'),
            size=volume_data.get('size'),
            usage=volume_data.get('usage'),
        )


class SystemResolver:
    """System GraphQL resolvers"""
    
    @staticmethod
    async def get_system_info(info) -> SystemInfo:
        """Get system information"""
        system_monitor = SystemMonitor()
        system_info = await system_monitor.get_system_info()
        
        return SystemInfo(
            version=system_info['version'],
            api_version=system_info['api_version'],
            docker_version=system_info['docker_version'],
            platform=system_info['platform'],
            architecture=system_info['architecture'],
            cpu_count=system_info['cpu_count'],
            memory_total=system_info['memory_total'],
            memory_available=system_info['memory_available'],
            disk_total=system_info['disk_total'],
            disk_available=system_info['disk_available'],
            uptime=system_info['uptime'],
            containers_running=system_info['containers_running'],
            containers_stopped=system_info['containers_stopped'],
            containers_paused=system_info['containers_paused'],
            images_count=system_info['images_count'],
            volumes_count=system_info['volumes_count'],
            networks_count=system_info['networks_count'],
        )
    
    @staticmethod
    async def get_health_check(info) -> HealthCheck:
        """Get health check result"""
        system_monitor = SystemMonitor()
        health = await system_monitor.health_check()
        
        return HealthCheck(
            status=health['status'],
            timestamp=health['timestamp'],
            duration=health['duration'],
            services=health['services'],
            errors=health['errors'],
        )
    
    @staticmethod
    async def get_dashboard_summary(info):
        """Get dashboard summary data"""
        system_monitor = SystemMonitor()
        summary = await system_monitor.get_dashboard_summary()
        
        return {
            'containers_count': summary['containers_count'],
            'services_count': summary['services_count'],
            'networks_count': summary['networks_count'],
            'volumes_count': summary['volumes_count'],
            'running_containers': summary['running_containers'],
            'stopped_containers': summary['stopped_containers'],
            'total_memory_usage': summary['total_memory_usage'],
            'total_cpu_usage': summary['total_cpu_usage'],
            'last_updated': summary['last_updated'],
        }
    
    @staticmethod
    async def system_metrics(info) -> AsyncGenerator[SystemInfo, None]:
        """Subscribe to system metrics"""
        system_monitor = SystemMonitor()
        
        while True:
            system_info = await system_monitor.get_system_info()
            yield SystemResolver._convert_system_info(system_info)
            await asyncio.sleep(5)  # Update every 5 seconds
    
    @staticmethod
    def _convert_system_info(system_info: Dict[str, Any]) -> SystemInfo:
        """Convert system info to GraphQL type"""
        return SystemInfo(
            version=system_info['version'],
            api_version=system_info['api_version'],
            docker_version=system_info['docker_version'],
            platform=system_info['platform'],
            architecture=system_info['architecture'],
            cpu_count=system_info['cpu_count'],
            memory_total=system_info['memory_total'],
            memory_available=system_info['memory_available'],
            disk_total=system_info['disk_total'],
            disk_available=system_info['disk_available'],
            uptime=system_info['uptime'],
            containers_running=system_info['containers_running'],
            containers_stopped=system_info['containers_stopped'],
            containers_paused=system_info['containers_paused'],
            images_count=system_info['images_count'],
            volumes_count=system_info['volumes_count'],
            networks_count=system_info['networks_count'],
        )


class StatsResolver:
    """Statistics GraphQL resolvers"""
    
    @staticmethod
    async def get_container_stats(info, container_id: str) -> Optional[ContainerStats]:
        """Get container statistics"""
        stats_collector = StatsCollector()
        stats = await stats_collector.get_container_stats(container_id)
        
        if stats:
            return ContainerStats(
                container_id=stats['container_id'],
                cpu_percent=stats['cpu_percent'],
                memory_usage=stats['memory_usage'],
                memory_limit=stats['memory_limit'],
                memory_percent=stats['memory_percent'],
                network_rx_bytes=stats['network_rx_bytes'],
                network_tx_bytes=stats['network_tx_bytes'],
                block_read_bytes=stats['block_read_bytes'],
                block_write_bytes=stats['block_write_bytes'],
                timestamp=stats['timestamp'],
            )
        return None
    
    @staticmethod
    async def get_service_stats(info, service_id: str) -> Optional[ServiceStats]:
        """Get service statistics"""
        stats_collector = StatsCollector()
        stats = await stats_collector.get_service_stats(service_id)
        
        if stats:
            return ServiceStats(
                service_id=stats['service_id'],
                replicas_running=stats['replicas_running'],
                replicas_desired=stats['replicas_desired'],
                tasks_running=stats['tasks_running'],
                tasks_desired=stats['tasks_desired'],
                cpu_usage=stats['cpu_usage'],
                memory_usage=stats['memory_usage'],
                network_ingress=stats['network_ingress'],
                network_egress=stats['network_egress'],
                timestamp=stats['timestamp'],
            )
        return None
    
    @staticmethod
    async def get_network_stats(info) -> List[NetworkStats]:
        """Get network statistics"""
        stats_collector = StatsCollector()
        stats_list = await stats_collector.get_network_stats()
        
        return [
            NetworkStats(
                network_id=stats['network_id'],
                containers_connected=stats['containers_connected'],
                services_connected=stats['services_connected'],
                total_rx_bytes=stats['total_rx_bytes'],
                total_tx_bytes=stats['total_tx_bytes'],
                packets_rx=stats['packets_rx'],
                packets_tx=stats['packets_tx'],
                timestamp=stats['timestamp'],
            )
            for stats in stats_list
        ]
    
    @staticmethod
    async def get_volume_stats(info) -> List[VolumeStats]:
        """Get volume statistics"""
        stats_collector = StatsCollector()
        stats_list = await stats_collector.get_volume_stats()
        
        return [
            VolumeStats(
                volume_name=stats['volume_name'],
                size_bytes=stats['size_bytes'],
                used_bytes=stats['used_bytes'],
                available_bytes=stats['available_bytes'],
                used_by_containers=stats['used_by_containers'],
                timestamp=stats['timestamp'],
            )
            for stats in stats_list
        ]
    
    @staticmethod
    async def container_stats_stream(info, container_id: str) -> AsyncGenerator[ContainerStats, None]:
        """Subscribe to container statistics stream"""
        stats_collector = StatsCollector()
        
        async for stats in stats_collector.stream_container_stats(container_id):
            yield ContainerStats(
                container_id=stats['container_id'],
                cpu_percent=stats['cpu_percent'],
                memory_usage=stats['memory_usage'],
                memory_limit=stats['memory_limit'],
                memory_percent=stats['memory_percent'],
                network_rx_bytes=stats['network_rx_bytes'],
                network_tx_bytes=stats['network_tx_bytes'],
                block_read_bytes=stats['block_read_bytes'],
                block_write_bytes=stats['block_write_bytes'],
                timestamp=stats['timestamp'],
            )
    
    @staticmethod
    async def service_stats_stream(info, service_id: str) -> AsyncGenerator[ServiceStats, None]:
        """Subscribe to service statistics stream"""
        stats_collector = StatsCollector()
        
        async for stats in stats_collector.stream_service_stats(service_id):
            yield ServiceStats(
                service_id=stats['service_id'],
                replicas_running=stats['replicas_running'],
                replicas_desired=stats['replicas_desired'],
                tasks_running=stats['tasks_running'],
                tasks_desired=stats['tasks_desired'],
                cpu_usage=stats['cpu_usage'],
                memory_usage=stats['memory_usage'],
                network_ingress=stats['network_ingress'],
                network_egress=stats['network_egress'],
                timestamp=stats['timestamp'],
            )