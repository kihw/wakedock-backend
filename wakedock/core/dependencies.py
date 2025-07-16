"""
Dépendances FastAPI pour l'application WakeDock
"""
from functools import lru_cache
from wakedock.core.docker_client import DockerClient
from wakedock.core.metrics_collector import MetricsCollector
from wakedock.core.alerts_service import AlertsService

# Instances globales
_docker_client: DockerClient = None
_metrics_collector: MetricsCollector = None
_alerts_service: AlertsService = None

def get_docker_client() -> DockerClient:
    """
    Dépendance FastAPI pour obtenir le client Docker
    """
    global _docker_client
    
    if _docker_client is None:
        _docker_client = DockerClient()
    
    return _docker_client

def get_metrics_collector() -> MetricsCollector:
    """
    Dépendance FastAPI pour obtenir le collecteur de métriques
    """
    global _metrics_collector
    
    if _metrics_collector is None:
        docker_client = get_docker_client()
        _metrics_collector = MetricsCollector(docker_client)
    
    return _metrics_collector

def get_alerts_service() -> AlertsService:
    """
    Dépendance FastAPI pour obtenir le service d'alertes
    """
    global _alerts_service
    
    if _alerts_service is None:
        metrics_collector = get_metrics_collector()
        _alerts_service = AlertsService(
            metrics_collector=metrics_collector,
            storage_path="/var/log/wakedock/alerts"
        )
    
    return _alerts_service

async def startup_services():
    """
    Démarre tous les services au startup de l'application
    """
    # Démarre le collecteur de métriques
    metrics_collector = get_metrics_collector()
    await metrics_collector.start()
    
    # Démarre le service d'alertes
    alerts_service = get_alerts_service()
    await alerts_service.start()

async def shutdown_services():
    """
    Arrête tous les services au shutdown de l'application
    """
    global _alerts_service, _metrics_collector, _docker_client
    
    # Arrête le service d'alertes
    if _alerts_service:
        await _alerts_service.stop()
        _alerts_service = None
    
    # Arrête le collecteur de métriques
    if _metrics_collector:
        await _metrics_collector.stop()
        _metrics_collector = None
    
    # Ferme le client Docker
    if _docker_client:
        _docker_client.close()
        _docker_client = None
