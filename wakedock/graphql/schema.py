"""
GraphQL schema definition for WakeDock
"""

import strawberry
from typing import List, Optional
from datetime import datetime

from .types import (
    Container,
    Service,
    Network,
    Volume,
    SystemInfo,
    HealthCheck,
    ContainerStats,
    ServiceStats,
    NetworkStats,
    VolumeStats,
)
from .resolvers import (
    ContainerResolver,
    ServiceResolver,
    NetworkResolver,
    VolumeResolver,
    SystemResolver,
    StatsResolver,
)


@strawberry.type
class Query:
    """GraphQL Query root"""
    
    # Container queries
    containers: List[Container] = strawberry.field(resolver=ContainerResolver.get_containers)
    container: Optional[Container] = strawberry.field(resolver=ContainerResolver.get_container)
    
    # Service queries
    services: List[Service] = strawberry.field(resolver=ServiceResolver.get_services)
    service: Optional[Service] = strawberry.field(resolver=ServiceResolver.get_service)
    
    # Network queries
    networks: List[Network] = strawberry.field(resolver=NetworkResolver.get_networks)
    network: Optional[Network] = strawberry.field(resolver=NetworkResolver.get_network)
    
    # Volume queries
    volumes: List[Volume] = strawberry.field(resolver=VolumeResolver.get_volumes)
    volume: Optional[Volume] = strawberry.field(resolver=VolumeResolver.get_volume)
    
    # System queries
    system_info: SystemInfo = strawberry.field(resolver=SystemResolver.get_system_info)
    health_check: HealthCheck = strawberry.field(resolver=SystemResolver.get_health_check)
    
    # Stats queries
    container_stats: Optional[ContainerStats] = strawberry.field(resolver=StatsResolver.get_container_stats)
    service_stats: Optional[ServiceStats] = strawberry.field(resolver=StatsResolver.get_service_stats)
    network_stats: List[NetworkStats] = strawberry.field(resolver=StatsResolver.get_network_stats)
    volume_stats: List[VolumeStats] = strawberry.field(resolver=StatsResolver.get_volume_stats)
    
    # Aggregated queries
    dashboard_summary: "DashboardSummary" = strawberry.field(resolver=SystemResolver.get_dashboard_summary)


@strawberry.type
class Mutation:
    """GraphQL Mutation root"""
    
    # Container mutations
    start_container: Container = strawberry.field(resolver=ContainerResolver.start_container)
    stop_container: Container = strawberry.field(resolver=ContainerResolver.stop_container)
    restart_container: Container = strawberry.field(resolver=ContainerResolver.restart_container)
    remove_container: bool = strawberry.field(resolver=ContainerResolver.remove_container)
    
    # Service mutations
    create_service: Service = strawberry.field(resolver=ServiceResolver.create_service)
    update_service: Service = strawberry.field(resolver=ServiceResolver.update_service)
    delete_service: bool = strawberry.field(resolver=ServiceResolver.delete_service)
    
    # Network mutations
    create_network: Network = strawberry.field(resolver=NetworkResolver.create_network)
    remove_network: bool = strawberry.field(resolver=NetworkResolver.remove_network)
    
    # Volume mutations
    create_volume: Volume = strawberry.field(resolver=VolumeResolver.create_volume)
    remove_volume: bool = strawberry.field(resolver=VolumeResolver.remove_volume)


@strawberry.type
class Subscription:
    """GraphQL Subscription root"""
    
    # Real-time updates
    container_events: Container = strawberry.field(resolver=ContainerResolver.container_events)
    service_events: Service = strawberry.field(resolver=ServiceResolver.service_events)
    system_metrics: SystemInfo = strawberry.field(resolver=SystemResolver.system_metrics)
    
    # Stats subscriptions
    container_stats_stream: ContainerStats = strawberry.field(resolver=StatsResolver.container_stats_stream)
    service_stats_stream: ServiceStats = strawberry.field(resolver=StatsResolver.service_stats_stream)


@strawberry.type
class DashboardSummary:
    """Dashboard summary data"""
    containers_count: int
    services_count: int
    networks_count: int
    volumes_count: int
    running_containers: int
    stopped_containers: int
    total_memory_usage: float
    total_cpu_usage: float
    last_updated: datetime


# Create the schema
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)