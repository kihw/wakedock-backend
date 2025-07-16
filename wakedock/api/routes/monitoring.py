"""
Routes API pour le monitoring temps réel des conteneurs Docker
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from wakedock.core.metrics_collector import (
    MetricsCollector, MetricType, AlertLevel, ThresholdConfig, ContainerMetrics, Alert
)
from wakedock.core.websocket_service import MetricsWebSocketService, StreamType
from wakedock.core.docker_manager import get_docker_manager

logger = logging.getLogger(__name__)

# Instances globales
metrics_collector: Optional[MetricsCollector] = None
websocket_service: Optional[MetricsWebSocketService] = None

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])

# Modèles Pydantic pour l'API

class MetricsQuery(BaseModel):
    """Paramètres de requête pour les métriques"""
    container_id: Optional[str] = None
    service_name: Optional[str] = None
    hours: int = Field(default=1, ge=1, le=168)  # 1 heure à 1 semaine
    limit: int = Field(default=1000, ge=1, le=10000)

class AlertsQuery(BaseModel):
    """Paramètres de requête pour les alertes"""
    container_id: Optional[str] = None
    service_name: Optional[str] = None
    level: Optional[AlertLevel] = None
    hours: int = Field(default=24, ge=1, le=168)
    limit: int = Field(default=100, ge=1, le=1000)

class ThresholdUpdate(BaseModel):
    """Mise à jour d'un seuil d'alerte"""
    metric_type: MetricType
    warning_threshold: float = Field(ge=0)
    critical_threshold: float = Field(ge=0)
    enabled: bool = True

class MonitoringConfig(BaseModel):
    """Configuration du monitoring"""
    collection_interval: int = Field(default=5, ge=1, le=60)
    retention_days: int = Field(default=7, ge=1, le=30)
    thresholds: List[ThresholdUpdate] = Field(default_factory=list)

class SystemStatus(BaseModel):
    """Statut du système de monitoring"""
    is_running: bool
    monitored_containers: int
    collection_interval: int
    retention_days: int
    storage_path: str
    uptime: str
    websocket_connections: int

async def get_metrics_collector() -> MetricsCollector:
    """Récupère l'instance du collecteur de métriques"""
    global metrics_collector
    if metrics_collector is None:
        docker_manager = get_docker_manager()
        metrics_collector = MetricsCollector(docker_manager)
        await metrics_collector.start()
    return metrics_collector

async def get_websocket_service() -> MetricsWebSocketService:
    """Récupère l'instance du service WebSocket"""
    global websocket_service
    if websocket_service is None:
        collector = await get_metrics_collector()
        websocket_service = MetricsWebSocketService(collector)
        await websocket_service.start()
    return websocket_service

@router.get("/status", response_model=Dict)
async def get_monitoring_status():
    """
    Récupère le statut du système de monitoring
    """
    try:
        collector = await get_metrics_collector()
        ws_service = await get_websocket_service()
        
        collector_stats = collector.get_stats()
        ws_stats = ws_service.get_stats()
        
        return {
            "monitoring": {
                "is_running": collector_stats['is_running'],
                "monitored_containers": collector_stats['monitored_containers'],
                "collection_interval": collector_stats['collection_interval'],
                "retention_days": collector_stats['retention_days'],
                "storage_path": collector_stats['storage_path']
            },
            "websocket": {
                "is_running": ws_stats['is_running'],
                "active_connections": ws_stats['active_connections'],
                "total_connections": ws_stats['total_connections'],
                "messages_sent": ws_stats['messages_sent']
            },
            "thresholds": collector_stats['thresholds']
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/start")
async def start_monitoring():
    """
    Démarre le système de monitoring
    """
    try:
        collector = await get_metrics_collector()
        ws_service = await get_websocket_service()
        
        if not collector.is_running:
            await collector.start()
        
        if not ws_service.is_running:
            await ws_service.start()
        
        return {"message": "Monitoring démarré avec succès"}
    except Exception as e:
        logger.error(f"Erreur lors du démarrage du monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop")
async def stop_monitoring():
    """
    Arrête le système de monitoring
    """
    try:
        global metrics_collector, websocket_service
        
        if websocket_service and websocket_service.is_running:
            await websocket_service.stop()
        
        if metrics_collector and metrics_collector.is_running:
            await metrics_collector.stop()
        
        return {"message": "Monitoring arrêté avec succès"}
    except Exception as e:
        logger.error(f"Erreur lors de l'arrêt du monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics", response_model=List[Dict])
async def get_metrics(
    container_id: Optional[str] = Query(None, description="ID du conteneur"),
    service_name: Optional[str] = Query(None, description="Nom du service"),
    hours: int = Query(1, ge=1, le=168, description="Nombre d'heures à récupérer"),
    limit: int = Query(1000, ge=1, le=10000, description="Limite de résultats")
):
    """
    Récupère les métriques de monitoring
    """
    try:
        collector = await get_metrics_collector()
        
        # Récupère les métriques
        metrics = await collector.get_recent_metrics(
            container_id=container_id,
            hours=hours,
            limit=limit
        )
        
        # Filtre par service si spécifié
        if service_name:
            metrics = [m for m in metrics if m.service_name == service_name]
        
        # Convertit en dictionnaires
        return [metric.to_dict() for metric in metrics]
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des métriques: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/metrics/query", response_model=List[Dict])
async def query_metrics(query: MetricsQuery):
    """
    Requête avancée pour les métriques
    """
    try:
        collector = await get_metrics_collector()
        
        metrics = await collector.get_recent_metrics(
            container_id=query.container_id,
            hours=query.hours,
            limit=query.limit
        )
        
        # Filtre par service si spécifié
        if query.service_name:
            metrics = [m for m in metrics if m.service_name == query.service_name]
        
        return [metric.to_dict() for metric in metrics]
        
    except Exception as e:
        logger.error(f"Erreur lors de la requête de métriques: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics/{container_id}/latest", response_model=Dict)
async def get_latest_metrics(container_id: str):
    """
    Récupère les dernières métriques d'un conteneur
    """
    try:
        collector = await get_metrics_collector()
        
        metrics = await collector.get_recent_metrics(
            container_id=container_id,
            hours=1,
            limit=1
        )
        
        if not metrics:
            raise HTTPException(status_code=404, detail="Aucune métrique trouvée pour ce conteneur")
        
        return metrics[0].to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des métriques du conteneur: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/alerts", response_model=List[Dict])
async def get_alerts(
    container_id: Optional[str] = Query(None, description="ID du conteneur"),
    service_name: Optional[str] = Query(None, description="Nom du service"),
    level: Optional[AlertLevel] = Query(None, description="Niveau d'alerte"),
    hours: int = Query(24, ge=1, le=168, description="Nombre d'heures à récupérer"),
    limit: int = Query(100, ge=1, le=1000, description="Limite de résultats")
):
    """
    Récupère les alertes de monitoring
    """
    try:
        collector = await get_metrics_collector()
        
        alerts = await collector.get_recent_alerts(
            container_id=container_id,
            hours=hours,
            limit=limit
        )
        
        # Filtre par service si spécifié
        if service_name:
            alerts = [a for a in alerts if a.service_name == service_name]
        
        # Filtre par niveau si spécifié
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        return [alert.to_dict() for alert in alerts]
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des alertes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/alerts/query", response_model=List[Dict])
async def query_alerts(query: AlertsQuery):
    """
    Requête avancée pour les alertes
    """
    try:
        collector = await get_metrics_collector()
        
        alerts = await collector.get_recent_alerts(
            container_id=query.container_id,
            hours=query.hours,
            limit=query.limit
        )
        
        # Filtre par service si spécifié
        if query.service_name:
            alerts = [a for a in alerts if a.service_name == query.service_name]
        
        # Filtre par niveau si spécifié
        if query.level:
            alerts = [a for a in alerts if a.level == query.level]
        
        return [alert.to_dict() for alert in alerts]
        
    except Exception as e:
        logger.error(f"Erreur lors de la requête d'alertes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/thresholds", response_model=Dict)
async def get_thresholds():
    """
    Récupère les seuils d'alerte configurés
    """
    try:
        collector = await get_metrics_collector()
        stats = collector.get_stats()
        return {"thresholds": stats['thresholds']}
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des seuils: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/thresholds/{metric_type}")
async def update_threshold(metric_type: MetricType, threshold: ThresholdUpdate):
    """
    Met à jour un seuil d'alerte
    """
    try:
        if threshold.warning_threshold >= threshold.critical_threshold:
            raise HTTPException(
                status_code=400, 
                detail="Le seuil d'avertissement doit être inférieur au seuil critique"
            )
        
        collector = await get_metrics_collector()
        collector.update_threshold(
            metric_type=metric_type,
            warning=threshold.warning_threshold,
            critical=threshold.critical_threshold,
            enabled=threshold.enabled
        )
        
        return {"message": f"Seuil {metric_type.value} mis à jour avec succès"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du seuil: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/config")
async def update_config(config: MonitoringConfig):
    """
    Met à jour la configuration du monitoring
    """
    try:
        collector = await get_metrics_collector()
        
        # Met à jour l'intervalle de collecte
        collector.collection_interval = config.collection_interval
        collector.retention_days = config.retention_days
        
        # Met à jour les seuils
        for threshold in config.thresholds:
            if threshold.warning_threshold >= threshold.critical_threshold:
                raise HTTPException(
                    status_code=400,
                    detail=f"Seuil d'avertissement >= critique pour {threshold.metric_type.value}"
                )
            
            collector.update_threshold(
                metric_type=threshold.metric_type,
                warning=threshold.warning_threshold,
                critical=threshold.critical_threshold,
                enabled=threshold.enabled
            )
        
        return {"message": "Configuration mise à jour avec succès"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/containers")
async def get_monitored_containers():
    """
    Liste les conteneurs actuellement monitorés
    """
    try:
        collector = await get_metrics_collector()
        
        containers = []
        for container_id, container_name in collector.monitored_containers.items():
            # Récupère les dernières métriques
            recent_metrics = await collector.get_recent_metrics(
                container_id=container_id,
                hours=1,
                limit=1
            )
            
            container_info = {
                "container_id": container_id,
                "container_name": container_name,
                "last_update": None,
                "service_name": None
            }
            
            if recent_metrics:
                metric = recent_metrics[0]
                container_info.update({
                    "last_update": metric.timestamp.isoformat(),
                    "service_name": metric.service_name,
                    "cpu_percent": metric.cpu_percent,
                    "memory_percent": metric.memory_percent,
                    "network_rx_mb": metric.network_rx_bytes / 1024 / 1024,
                    "network_tx_mb": metric.network_tx_bytes / 1024 / 1024
                })
            
            containers.append(container_info)
        
        return {"containers": containers}
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des conteneurs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/statistics")
async def get_monitoring_statistics():
    """
    Récupère les statistiques de monitoring
    """
    try:
        collector = await get_metrics_collector()
        ws_service = await get_websocket_service()
        
        # Statistiques du collecteur
        collector_stats = collector.get_stats()
        
        # Statistiques WebSocket
        ws_stats = ws_service.get_stats()
        
        # Compte les alertes récentes par niveau
        recent_alerts = await collector.get_recent_alerts(hours=24, limit=1000)
        alert_counts = {
            "critical": len([a for a in recent_alerts if a.level == AlertLevel.CRITICAL]),
            "warning": len([a for a in recent_alerts if a.level == AlertLevel.WARNING]),
            "info": len([a for a in recent_alerts if a.level == AlertLevel.INFO])
        }
        
        # Métriques récentes pour calculer des moyennes
        recent_metrics = await collector.get_recent_metrics(hours=1, limit=1000)
        
        avg_cpu = 0
        avg_memory = 0
        total_network_rx = 0
        total_network_tx = 0
        
        if recent_metrics:
            avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
            avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
            total_network_rx = sum(m.network_rx_bytes for m in recent_metrics) / 1024 / 1024
            total_network_tx = sum(m.network_tx_bytes for m in recent_metrics) / 1024 / 1024
        
        return {
            "collector": collector_stats,
            "websocket": ws_stats,
            "alerts": {
                "total_last_24h": len(recent_alerts),
                "by_level": alert_counts
            },
            "performance": {
                "avg_cpu_percent": round(avg_cpu, 2),
                "avg_memory_percent": round(avg_memory, 2),
                "total_network_rx_mb": round(total_network_rx, 2),
                "total_network_tx_mb": round(total_network_tx, 2),
                "metrics_count_last_hour": len(recent_metrics)
            }
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Point d'entrée WebSocket pour le streaming temps réel
    """
    client_id = str(uuid4())
    
    try:
        # Récupère le service WebSocket
        ws_service = await get_websocket_service()
        
        # Délègue la gestion au service
        await ws_service.handle_client_connection(websocket, client_id)
        
    except WebSocketDisconnect:
        logger.info(f"WebSocket client {client_id} disconnected normally")
    except Exception as e:
        logger.error(f"Erreur WebSocket pour client {client_id}: {e}")

@router.post("/test/alert")
async def test_alert(
    container_id: str = Body(..., description="ID du conteneur"),
    metric_type: MetricType = Body(..., description="Type de métrique"),
    value: float = Body(..., description="Valeur de test"),
    level: AlertLevel = Body(AlertLevel.WARNING, description="Niveau d'alerte")
):
    """
    Génère une alerte de test (pour développement/debug)
    """
    try:
        collector = await get_metrics_collector()
        ws_service = await get_websocket_service()
        
        # Trouve le nom du conteneur
        container_name = collector.monitored_containers.get(container_id, container_id)
        
        # Crée une alerte de test
        test_alert = Alert(
            container_id=container_id,
            container_name=container_name,
            service_name="test-service",
            timestamp=datetime.utcnow(),
            level=level,
            metric_type=metric_type,
            value=value,
            threshold=50.0,  # Seuil fictif
            message=f"Alerte de test: {metric_type.value} = {value}"
        )
        
        # Traite l'alerte
        await collector._process_alert(test_alert)
        
        return {"message": "Alerte de test générée", "alert": test_alert.to_dict()}
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération de l'alerte de test: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Gestionnaire de lifecycle pour nettoyer les ressources
@router.on_event("shutdown")
async def shutdown_monitoring():
    """Nettoie les ressources lors de l'arrêt"""
    global metrics_collector, websocket_service
    
    try:
        if websocket_service and websocket_service.is_running:
            await websocket_service.stop()
        
        if metrics_collector and metrics_collector.is_running:
            await metrics_collector.stop()
            
        logger.info("Ressources de monitoring nettoyées")
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des ressources: {e}")
