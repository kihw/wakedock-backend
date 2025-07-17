"""
Routes API pour l'audit de sécurité avancé
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from wakedock.core.auth_middleware import PermissionRequired
from wakedock.core.dependencies import get_current_user
from wakedock.core.security_audit_service import (
    AnomalyType,
    get_security_audit_service,
    SecurityAuditService,
    SecurityEventData,
    SecurityEventType,
)
from wakedock.models.user import User

router = APIRouter(prefix="/security-audit", tags=["security-audit"])

# Modèles Pydantic pour les requêtes/réponses

class SecurityEventRequest(BaseModel):
    """Modèle pour créer un événement de sécurité"""
    event_type: SecurityEventType
    user_id: Optional[int] = None
    username: Optional[str] = None
    ip_address: str
    user_agent: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    success: bool = True
    details: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}

class SecurityEventResponse(BaseModel):
    """Modèle de réponse pour un événement de sécurité"""
    event_id: str
    event_type: str
    severity: str
    risk_score: int
    user_id: Optional[int]
    ip_address: str
    details: Dict[str, Any]
    metadata: Dict[str, Any]
    created_at: str

class AnomalyResponse(BaseModel):
    """Modèle de réponse pour une anomalie"""
    id: int
    anomaly_type: str
    severity: str
    confidence: float
    user_id: Optional[int]
    description: str
    evidence: Dict[str, Any]
    recommended_actions: List[str]
    resolved: bool
    created_at: str
    resolved_at: Optional[str]

class SecurityMetricsResponse(BaseModel):
    """Modèle de réponse pour les métriques de sécurité"""
    period_days: int
    events_by_type: Dict[str, int]
    unresolved_anomalies: int
    average_risk_score: float
    suspicious_ips: List[Dict[str, Any]]
    total_events: int
    generated_at: str

class AnomalyResolutionRequest(BaseModel):
    """Modèle pour résoudre une anomalie"""
    resolution_notes: str = ""

class SecurityReportRequest(BaseModel):
    """Modèle pour générer un rapport de sécurité"""
    start_date: datetime
    end_date: datetime
    include_events: bool = True
    include_anomalies: bool = True
    include_metrics: bool = True
    format: str = Field(default="json", regex="^(json|csv|pdf)$")

# Routes pour les événements de sécurité

@router.post("/events", response_model=Dict[str, str])
@PermissionRequired("audit.create")
async def create_security_event(
    event_request: SecurityEventRequest,
    current_user: User = Depends(get_current_user),
    security_service: SecurityAuditService = Depends(get_security_audit_service)
):
    """
    Crée un nouvel événement de sécurité
    """
    try:
        event_data = SecurityEventData(**event_request.dict())
        event_id = await security_service.log_security_event(event_data)
        
        return {
            "event_id": event_id,
            "status": "created",
            "message": "Événement de sécurité enregistré avec succès"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la création de l'événement: {str(e)}")

@router.get("/events", response_model=List[SecurityEventResponse])
@PermissionRequired("audit.view")
async def get_security_events(
    start_date: Optional[datetime] = Query(None, description="Date de début (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="Date de fin (ISO format)"),
    event_types: Optional[List[SecurityEventType]] = Query(None, description="Types d'événements à filtrer"),
    user_id: Optional[int] = Query(None, description="ID utilisateur à filtrer"),
    severity: Optional[str] = Query(None, description="Sévérité à filtrer"),
    limit: int = Query(100, ge=1, le=1000, description="Nombre maximum d'événements à retourner"),
    current_user: User = Depends(get_current_user),
    security_service: SecurityAuditService = Depends(get_security_audit_service)
):
    """
    Récupère la liste des événements de sécurité avec filtres
    """
    try:
        events = await security_service.get_security_events(
            start_date=start_date,
            end_date=end_date,
            event_types=event_types,
            user_id=user_id,
            severity=severity,
            limit=limit
        )
        
        return [SecurityEventResponse(**event) for event in events]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des événements: {str(e)}")

@router.get("/events/types", response_model=List[str])
@PermissionRequired("audit.view")
async def get_security_event_types(
    current_user: User = Depends(get_current_user)
):
    """
    Récupère la liste des types d'événements de sécurité disponibles
    """
    return [event_type.value for event_type in SecurityEventType]

# Routes pour les anomalies

@router.get("/anomalies", response_model=List[AnomalyResponse])
@PermissionRequired("audit.view")
async def get_anomalies(
    start_date: Optional[datetime] = Query(None, description="Date de début"),
    end_date: Optional[datetime] = Query(None, description="Date de fin"),
    severity: Optional[str] = Query(None, description="Sévérité à filtrer"),
    resolved: Optional[bool] = Query(None, description="État de résolution"),
    limit: int = Query(50, ge=1, le=500, description="Nombre maximum d'anomalies"),
    current_user: User = Depends(get_current_user),
    security_service: SecurityAuditService = Depends(get_security_audit_service)
):
    """
    Récupère la liste des anomalies détectées avec filtres
    """
    try:
        anomalies = await security_service.get_anomalies(
            start_date=start_date,
            end_date=end_date,
            severity=severity,
            resolved=resolved,
            limit=limit
        )
        
        return [AnomalyResponse(**anomaly) for anomaly in anomalies]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la récupération des anomalies: {str(e)}")

@router.post("/anomalies/{anomaly_id}/resolve")
@PermissionRequired("audit.update")
async def resolve_anomaly(
    anomaly_id: int,
    resolution_request: AnomalyResolutionRequest,
    current_user: User = Depends(get_current_user),
    security_service: SecurityAuditService = Depends(get_security_audit_service)
):
    """
    Marque une anomalie comme résolue
    """
    try:
        await security_service.resolve_anomaly(
            anomaly_id=anomaly_id,
            resolved_by=current_user.id,
            resolution_notes=resolution_request.resolution_notes
        )
        
        return {
            "anomaly_id": anomaly_id,
            "status": "resolved",
            "resolved_by": current_user.id,
            "resolved_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la résolution de l'anomalie: {str(e)}")

@router.get("/anomalies/types", response_model=List[str])
@PermissionRequired("audit.view")
async def get_anomaly_types(
    current_user: User = Depends(get_current_user)
):
    """
    Récupère la liste des types d'anomalies détectables
    """
    return [anomaly_type.value for anomaly_type in AnomalyType]

# Routes pour les métriques et dashboard

@router.get("/metrics", response_model=SecurityMetricsResponse)
@PermissionRequired("audit.view")
async def get_security_metrics(
    days: int = Query(7, ge=1, le=365, description="Nombre de jours pour le calcul des métriques"),
    current_user: User = Depends(get_current_user),
    security_service: SecurityAuditService = Depends(get_security_audit_service)
):
    """
    Récupère les métriques de sécurité pour le dashboard
    """
    try:
        metrics = await security_service.get_security_metrics(days=days)
        return SecurityMetricsResponse(**metrics)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du calcul des métriques: {str(e)}")

@router.get("/dashboard/summary")
@PermissionRequired("audit.view")
async def get_security_dashboard_summary(
    current_user: User = Depends(get_current_user),
    security_service: SecurityAuditService = Depends(get_security_audit_service)
):
    """
    Récupère un résumé pour le dashboard de sécurité
    """
    try:
        # Métriques des 24 dernières heures
        recent_metrics = await security_service.get_security_metrics(days=1)
        
        # Anomalies non résolues
        unresolved_anomalies = await security_service.get_anomalies(
            resolved=False,
            limit=10
        )
        
        # Événements récents à risque élevé
        high_risk_events = await security_service.get_security_events(
            start_date=datetime.utcnow() - timedelta(hours=24),
            limit=10
        )
        high_risk_events = [e for e in high_risk_events if e.get('risk_score', 0) > 70]
        
        return {
            "summary": {
                "total_events_24h": recent_metrics.get('total_events', 0),
                "unresolved_anomalies": len(unresolved_anomalies),
                "high_risk_events_24h": len(high_risk_events),
                "average_risk_score": recent_metrics.get('average_risk_score', 0)
            },
            "recent_anomalies": unresolved_anomalies[:5],
            "high_risk_events": high_risk_events[:5],
            "security_status": "good" if len(unresolved_anomalies) == 0 else "warning" if len(unresolved_anomalies) < 5 else "critical"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors de la génération du résumé: {str(e)}")

# Routes pour les rapports et exports

@router.post("/reports/generate")
@PermissionRequired("audit.export")
async def generate_security_report(
    report_request: SecurityReportRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    security_service: SecurityAuditService = Depends(get_security_audit_service)
):
    """
    Génère un rapport de sécurité (traitement en arrière-plan)
    """
    try:
        # Valider les dates
        if report_request.end_date <= report_request.start_date:
            raise HTTPException(status_code=400, detail="La date de fin doit être postérieure à la date de début")
        
        # Valider la période (max 1 an)
        if (report_request.end_date - report_request.start_date).days > 365:
            raise HTTPException(status_code=400, detail="La période du rapport ne peut pas dépasser 1 an")
        
        # Générer un ID de rapport
        report_id = f"security_report_{current_user.id}_{int(datetime.utcnow().timestamp())}"
        
        # Lancer la génération en arrière-plan
        background_tasks.add_task(
            _generate_report_background,
            report_id,
            report_request,
            current_user.id,
            security_service
        )
        
        return {
            "report_id": report_id,
            "status": "generating",
            "message": "La génération du rapport a été lancée en arrière-plan",
            "estimated_completion": (datetime.utcnow() + timedelta(minutes=5)).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du lancement de la génération du rapport: {str(e)}")

@router.get("/reports/{report_id}/status")
@PermissionRequired("audit.export")
async def get_report_status(
    report_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Récupère le statut d'un rapport en cours de génération
    """
    # Cette fonctionnalité nécessiterait un système de suivi des tâches
    # Pour l'instant, on retourne un statut basique
    return {
        "report_id": report_id,
        "status": "completed",  # Placeholder
        "progress": 100,
        "download_url": f"/api/v1/security-audit/reports/{report_id}/download"
    }

# Routes pour la maintenance et configuration

@router.post("/maintenance/cleanup-logs")
@PermissionRequired("admin")
async def cleanup_old_logs(
    current_user: User = Depends(get_current_user),
    security_service: SecurityAuditService = Depends(get_security_audit_service)
):
    """
    Lance le nettoyage manuel des anciens logs de sécurité
    """
    try:
        # Lancer le nettoyage (normalement fait automatiquement)
        await security_service._cleanup_old_logs()
        
        return {
            "status": "completed",
            "message": "Nettoyage des anciens logs terminé",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lors du nettoyage: {str(e)}")

@router.get("/configuration")
@PermissionRequired("audit.view")
async def get_security_configuration(
    current_user: User = Depends(get_current_user),
    security_service: SecurityAuditService = Depends(get_security_audit_service)
):
    """
    Récupère la configuration actuelle du système d'audit de sécurité
    """
    return {
        "log_retention_days": security_service.log_retention_days,
        "compressed_log_retention_days": security_service.compressed_log_retention_days,
        "max_failed_logins": security_service.max_failed_logins,
        "suspicious_request_threshold": security_service.suspicious_request_threshold,
        "encryption_enabled": security_service._encryption_key is not None,
        "anomaly_detection_enabled": True,
        "storage_path": str(security_service.storage_path)
    }

@router.get("/health")
@PermissionRequired("audit.view")
async def get_security_audit_health(
    current_user: User = Depends(get_current_user),
    security_service: SecurityAuditService = Depends(get_security_audit_service)
):
    """
    Vérifie l'état de santé du système d'audit de sécurité
    """
    try:
        queue_size = security_service.event_queue.qsize()
        processing_active = security_service.processing_task and not security_service.processing_task.done()
        
        return {
            "status": "healthy",
            "queue_size": queue_size,
            "processing_active": processing_active,
            "encryption_active": security_service._encryption_key is not None,
            "storage_accessible": security_service.storage_path.exists(),
            "last_check": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "last_check": datetime.utcnow().isoformat()
        }

# Fonction utilitaire pour la génération de rapports en arrière-plan

async def _generate_report_background(
    report_id: str,
    report_request: SecurityReportRequest,
    user_id: int,
    security_service: SecurityAuditService
):
    """
    Génère un rapport de sécurité en arrière-plan
    """
    try:
        report_data = {
            "report_id": report_id,
            "generated_by": user_id,
            "generated_at": datetime.utcnow().isoformat(),
            "period": {
                "start_date": report_request.start_date.isoformat(),
                "end_date": report_request.end_date.isoformat()
            }
        }
        
        if report_request.include_events:
            events = await security_service.get_security_events(
                start_date=report_request.start_date,
                end_date=report_request.end_date,
                limit=10000  # Large limit pour le rapport
            )
            report_data["events"] = events
        
        if report_request.include_anomalies:
            anomalies = await security_service.get_anomalies(
                start_date=report_request.start_date,
                end_date=report_request.end_date,
                limit=1000
            )
            report_data["anomalies"] = anomalies
        
        if report_request.include_metrics:
            period_days = (report_request.end_date - report_request.start_date).days
            metrics = await security_service.get_security_metrics(days=period_days)
            report_data["metrics"] = metrics
        
        # Sauvegarder le rapport (implémentation simplifiée)
        # Dans un vrai système, on utiliserait un stockage persistant et un système de queue
        
        return report_data
        
    except Exception as e:
        # Log l'erreur
        logger.error(f"Erreur génération rapport {report_id}: {e}")
        raise
