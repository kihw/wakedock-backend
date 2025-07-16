"""
Dépendances pour le système d'alertes
"""
from functools import lru_cache
from wakedock.core.alerts_service import AlertsService
from wakedock.core.metrics_collector import MetricsCollector

# Instance globale du service d'alertes
_alerts_service: AlertsService = None

def get_alerts_service() -> AlertsService:
    """
    Dépendance FastAPI pour obtenir le service d'alertes
    """
    global _alerts_service
    
    if _alerts_service is None:
        # Obtient le collecteur de métriques (doit être initialisé)
        from wakedock.core.dependencies import get_metrics_collector
        metrics_collector = get_metrics_collector()
        
        # Crée le service d'alertes
        _alerts_service = AlertsService(
            metrics_collector=metrics_collector,
            storage_path="/var/log/wakedock/alerts"
        )
    
    return _alerts_service

async def startup_alerts_service():
    """
    Démarre le service d'alertes au startup de l'application
    """
    alerts_service = get_alerts_service()
    await alerts_service.start()

async def shutdown_alerts_service():
    """
    Arrête le service d'alertes au shutdown de l'application
    """
    global _alerts_service
    if _alerts_service:
        await _alerts_service.stop()
        _alerts_service = None
