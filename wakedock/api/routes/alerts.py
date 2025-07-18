"""
API Routes pour le système d'alertes et notifications
"""
import asyncio
import csv
import io
import json
import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse

from wakedock.core.alerts_service import (
    AlertInstance,
    AlertRule,
    AlertSeverity,
    AlertsService,
    AlertState,
    EscalationLevel,
    NotificationChannel,
    NotificationTarget,
)
from wakedock.core.dependencies import get_alerts_service
from wakedock.models.alerts import (
    AlertAcknowledgeRequest,
    AlertInstanceResponse,
    AlertMetricsRequest,
    AlertMetricsResponse,
    AlertRuleRequest,
    AlertRuleResponse,
    AlertRuleTestRequest,
    AlertRuleTestResponse,
    AlertsExportRequest,
    AlertsFilterRequest,
    AlertsServiceStatusResponse,
    AlertsStatsResponse,
    BulkAlertActionRequest,
    BulkAlertActionResponse,
    DefaultAlertRules,
    NotificationTargetRequest,
    NotificationTargetResponse,
    NotificationTestRequest,
    NotificationTestResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])

# ============================================================================
# GESTION DES RÈGLES D'ALERTES
# ============================================================================

@router.get("/rules", response_model=List[AlertRuleResponse])
async def get_alert_rules(
    enabled_only: bool = Query(False, description="Retourner seulement les règles activées"),
    alerts_service: AlertsService = Depends(get_alerts_service)
):
    """Récupère toutes les règles d'alertes"""
    try:
        rules = alerts_service.get_alert_rules()
        
        if enabled_only:
            rules = [rule for rule in rules if rule.enabled]
        
        return [_convert_alert_rule_to_response(rule) for rule in rules]
        
    except Exception as e:
        logger.error(f"Erreur récupération règles d'alertes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rules/{rule_id}", response_model=AlertRuleResponse)
async def get_alert_rule(
    rule_id: str = Path(..., description="ID de la règle"),
    alerts_service: AlertsService = Depends(get_alerts_service)
):
    """Récupère une règle d'alerte spécifique"""
    try:
        rule = alerts_service.alert_rules.get(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="Règle d'alerte introuvable")
        
        return _convert_alert_rule_to_response(rule)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur récupération règle {rule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rules", response_model=AlertRuleResponse)
async def create_alert_rule(
    rule_request: AlertRuleRequest,
    alerts_service: AlertsService = Depends(get_alerts_service)
):
    """Crée une nouvelle règle d'alerte"""
    try:
        # Génère un ID unique
        rule_id = f"rule_{int(time.time())}_{rule_request.name.lower().replace(' ', '_')}"
        
        # Convertit les escalation_targets si présent
        escalation_targets = None
        if rule_request.escalation_targets:
            escalation_targets = {}
            for level_str, targets in rule_request.escalation_targets.items():
                try:
                    level = EscalationLevel(level_str)
                    escalation_targets[level] = targets
                except ValueError:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Niveau d'escalade invalide: {level_str}"
                    )
        
        # Crée la règle
        rule = AlertRule(
            rule_id=rule_id,
            name=rule_request.name,
            description=rule_request.description,
            enabled=rule_request.enabled,
            metric_type=rule_request.metric_type,
            threshold_value=rule_request.threshold_value,
            comparison_operator=rule_request.comparison_operator,
            duration_minutes=rule_request.duration_minutes,
            container_filters=rule_request.container_filters or {},
            service_filters=rule_request.service_filters or [],
            severity=rule_request.severity,
            notification_targets=rule_request.notification_targets,
            escalation_enabled=rule_request.escalation_enabled,
            escalation_delay_minutes=rule_request.escalation_delay_minutes,
            escalation_targets=escalation_targets,
            suppression_enabled=rule_request.suppression_enabled,
            suppression_duration_minutes=rule_request.suppression_duration_minutes,
            grouping_keys=rule_request.grouping_keys
        )
        
        # Valide les cibles de notification
        for target_id in rule.notification_targets:
            if target_id not in alerts_service.notification_targets:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cible de notification introuvable: {target_id}"
                )
        
        success = await alerts_service.add_alert_rule(rule)
        if not success:
            raise HTTPException(status_code=500, detail="Échec création règle")
        
        return _convert_alert_rule_to_response(rule)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur création règle d'alerte: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: str = Path(..., description="ID de la règle"),
    rule_request: AlertRuleRequest = ...,
    alerts_service: AlertsService = Depends(get_alerts_service)
):
    """Met à jour une règle d'alerte existante"""
    try:
        if rule_id not in alerts_service.alert_rules:
            raise HTTPException(status_code=404, detail="Règle d'alerte introuvable")
        
        existing_rule = alerts_service.alert_rules[rule_id]
        
        # Convertit les escalation_targets si présent
        escalation_targets = None
        if rule_request.escalation_targets:
            escalation_targets = {}
            for level_str, targets in rule_request.escalation_targets.items():
                try:
                    level = EscalationLevel(level_str)
                    escalation_targets[level] = targets
                except ValueError:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Niveau d'escalade invalide: {level_str}"
                    )
        
        # Met à jour la règle
        updated_rule = AlertRule(
            rule_id=rule_id,
            name=rule_request.name,
            description=rule_request.description,
            enabled=rule_request.enabled,
            metric_type=rule_request.metric_type,
            threshold_value=rule_request.threshold_value,
            comparison_operator=rule_request.comparison_operator,
            duration_minutes=rule_request.duration_minutes,
            container_filters=rule_request.container_filters or {},
            service_filters=rule_request.service_filters or [],
            severity=rule_request.severity,
            notification_targets=rule_request.notification_targets,
            escalation_enabled=rule_request.escalation_enabled,
            escalation_delay_minutes=rule_request.escalation_delay_minutes,
            escalation_targets=escalation_targets,
            suppression_enabled=rule_request.suppression_enabled,
            suppression_duration_minutes=rule_request.suppression_duration_minutes,
            grouping_keys=rule_request.grouping_keys,
            created_at=existing_rule.created_at  # Conserve la date de création
        )
        
        success = await alerts_service.update_alert_rule(updated_rule)
        if not success:
            raise HTTPException(status_code=500, detail="Échec mise à jour règle")
        
        return _convert_alert_rule_to_response(updated_rule)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur mise à jour règle {rule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/rules/{rule_id}")
async def delete_alert_rule(
    rule_id: str = Path(..., description="ID de la règle"),
    alerts_service: AlertsService = Depends(get_alerts_service)
):
    """Supprime une règle d'alerte"""
    try:
        if rule_id not in alerts_service.alert_rules:
            raise HTTPException(status_code=404, detail="Règle d'alerte introuvable")
        
        success = await alerts_service.delete_alert_rule(rule_id)
        if not success:
            raise HTTPException(status_code=500, detail="Échec suppression règle")
        
        return {"message": "Règle d'alerte supprimée avec succès"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur suppression règle {rule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/rules/{rule_id}/test", response_model=AlertRuleTestResponse)
async def test_alert_rule(
    rule_id: str = Path(..., description="ID de la règle"),
    test_request: AlertRuleTestRequest = ...,
    alerts_service: AlertsService = Depends(get_alerts_service)
):
    """Teste une règle d'alerte avec des métriques simulées"""
    try:
        # Note: Cette fonction nécessiterait une implémentation spécifique
        # pour simuler l'évaluation d'une règle avec des données de test
        
        # Pour l'instant, retourne un exemple de réponse
        return AlertRuleTestResponse(
            would_trigger=True,
            matching_containers=["container_123", "container_456"],
            threshold_violations=[
                {
                    "container_id": "container_123",
                    "value": 85.5,
                    "threshold": 80.0,
                    "violation": True
                }
            ],
            evaluation_details={
                "evaluated_at": datetime.utcnow().isoformat(),
                "metrics_count": len(test_request.test_metrics),
                "evaluation_duration_ms": 150
            }
        )
        
    except Exception as e:
        logger.error(f"Erreur test règle {rule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/rules/defaults", response_model=List[AlertRuleRequest])
async def get_default_alert_rules():
    """Récupère les règles d'alertes par défaut disponibles"""
    try:
        defaults = []
        
        for attr_name in dir(DefaultAlertRules):
            if not attr_name.startswith('_'):
                rule_data = getattr(DefaultAlertRules, attr_name)
                if isinstance(rule_data, dict):
                    defaults.append(AlertRuleRequest(**rule_data))
        
        return defaults
        
    except Exception as e:
        logger.error(f"Erreur récupération règles par défaut: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# GESTION DES CIBLES DE NOTIFICATION
# ============================================================================

@router.get("/targets", response_model=List[NotificationTargetResponse])
async def get_notification_targets(
    enabled_only: bool = Query(False, description="Retourner seulement les cibles activées"),
    channel: Optional[NotificationChannel] = Query(None, description="Filtrer par type de canal"),
    alerts_service: AlertsService = Depends(get_alerts_service)
):
    """Récupère toutes les cibles de notification"""
    try:
        targets = alerts_service.get_notification_targets()
        
        if enabled_only:
            targets = [target for target in targets if target.enabled]
        
        if channel:
            targets = [target for target in targets if target.channel == channel]
        
        return [_convert_notification_target_to_response(target, target_id) 
                for target_id, target in alerts_service.notification_targets.items()
                if target in targets]
        
    except Exception as e:
        logger.error(f"Erreur récupération cibles notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/targets", response_model=NotificationTargetResponse)
async def create_notification_target(
    target_request: NotificationTargetRequest,
    alerts_service: AlertsService = Depends(get_alerts_service)
):
    """Crée une nouvelle cible de notification"""
    try:
        # Crée la cible
        target = NotificationTarget(
            channel=target_request.channel,
            name=target_request.name,
            enabled=target_request.enabled,
            email_address=target_request.email_address,
            webhook_url=target_request.webhook_url,
            webhook_headers=target_request.webhook_headers,
            slack_webhook_url=target_request.slack_webhook_url,
            slack_channel=target_request.slack_channel,
            slack_token=target_request.slack_token,
            discord_webhook_url=target_request.discord_webhook_url,
            teams_webhook_url=target_request.teams_webhook_url,
            telegram_bot_token=target_request.telegram_bot_token,
            telegram_chat_id=target_request.telegram_chat_id
        )
        
        success = await alerts_service.add_notification_target(target)
        if not success:
            raise HTTPException(status_code=500, detail="Échec création cible")
        
        # Génère l'ID de la cible créée
        target_id = f"{target.channel.value}_{target.name.lower().replace(' ', '_')}"
        
        return _convert_notification_target_to_response(target, target_id)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur création cible notification: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/targets/{target_id}/test", response_model=NotificationTestResponse)
async def test_notification_target(
    target_id: str = Path(..., description="ID de la cible"),
    test_request: NotificationTestRequest = ...,
    alerts_service: AlertsService = Depends(get_alerts_service)
):
    """Teste une cible de notification"""
    try:
        target = alerts_service.notification_targets.get(target_id)
        if not target:
            raise HTTPException(status_code=404, detail="Cible de notification introuvable")
        
        start_time = time.time()
        
        # Crée une alerte de test
        test_alert = AlertInstance(
            alert_id="test_alert",
            rule_id="test_rule",
            rule_name="Test Notification",
            container_id="test_container",
            container_name="test-container",
            service_name="test-service",
            metric_type="cpu_percent",
            current_value=85.5,
            threshold_value=80.0,
            severity=AlertSeverity.MEDIUM
        )
        
        # Personnalise le message si fourni
        if test_request.test_message:
            test_alert.rule_name = test_request.test_message
        
        # Envoie la notification de test
        success = await alerts_service._send_notification(test_alert, target)
        
        response_time = int((time.time() - start_time) * 1000)
        
        return NotificationTestResponse(
            success=success,
            message="Notification envoyée avec succès" if success else "Échec envoi notification",
            sent_at=datetime.utcnow(),
            response_time_ms=response_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur test notification {target_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# GESTION DES ALERTES ACTIVES
# ============================================================================

@router.get("/active", response_model=List[AlertInstanceResponse])
async def get_active_alerts(
    severity: Optional[List[AlertSeverity]] = Query(None, description="Filtrer par sévérité"),
    rule_id: Optional[str] = Query(None, description="Filtrer par règle"),
    container_id: Optional[str] = Query(None, description="Filtrer par conteneur"),
    service_name: Optional[str] = Query(None, description="Filtrer par service"),
    limit: int = Query(100, ge=1, le=1000, description="Limite de résultats"),
    alerts_service: AlertsService = Depends(get_alerts_service)
):
    """Récupère toutes les alertes actives"""
    try:
        alerts = alerts_service.get_active_alerts()
        
        # Applique les filtres
        if severity:
            alerts = [alert for alert in alerts if alert.severity in severity]
        
        if rule_id:
            alerts = [alert for alert in alerts if alert.rule_id == rule_id]
        
        if container_id:
            alerts = [alert for alert in alerts if alert.container_id == container_id]
        
        if service_name:
            alerts = [alert for alert in alerts if alert.service_name == service_name]
        
        # Limite les résultats
        alerts = alerts[:limit]
        
        return [_convert_alert_instance_to_response(alert) for alert in alerts]
        
    except Exception as e:
        logger.error(f"Erreur récupération alertes actives: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history", response_model=List[AlertInstanceResponse])
async def get_alerts_history(
    days: int = Query(7, ge=1, le=365, description="Nombre de jours d'historique"),
    filters: AlertsFilterRequest = Depends(),
    alerts_service: AlertsService = Depends(get_alerts_service)
):
    """Récupère l'historique des alertes"""
    try:
        alerts = await alerts_service.get_alerts_history(days)
        
        # Applique les filtres
        if filters.states:
            alerts = [alert for alert in alerts if alert.state in filters.states]
        
        if filters.severities:
            alerts = [alert for alert in alerts if alert.severity in filters.severities]
        
        if filters.rule_ids:
            alerts = [alert for alert in alerts if alert.rule_id in filters.rule_ids]
        
        if filters.container_ids:
            alerts = [alert for alert in alerts if alert.container_id in filters.container_ids]
        
        if filters.service_names:
            alerts = [alert for alert in alerts if alert.service_name in filters.service_names]
        
        if filters.from_date:
            alerts = [alert for alert in alerts if alert.triggered_at >= filters.from_date]
        
        if filters.to_date:
            alerts = [alert for alert in alerts if alert.triggered_at <= filters.to_date]
        
        # Pagination
        start_idx = filters.offset
        end_idx = start_idx + filters.limit
        alerts = alerts[start_idx:end_idx]
        
        return [_convert_alert_instance_to_response(alert) for alert in alerts]
        
    except Exception as e:
        logger.error(f"Erreur récupération historique alertes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/acknowledge/{alert_id}")
async def acknowledge_alert(
    alert_id: str = Path(..., description="ID de l'alerte"),
    ack_request: AlertAcknowledgeRequest = ...,
    alerts_service: AlertsService = Depends(get_alerts_service)
):
    """Acquitte une alerte"""
    try:
        success = await alerts_service.acknowledge_alert(alert_id, ack_request.acknowledged_by)
        
        if not success:
            raise HTTPException(status_code=404, detail="Alerte introuvable ou déjà acquittée")
        
        return {"message": "Alerte acquittée avec succès"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur acquittement alerte {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bulk-action", response_model=BulkAlertActionResponse)
async def bulk_alert_action(
    action_request: BulkAlertActionRequest,
    alerts_service: AlertsService = Depends(get_alerts_service)
):
    """Effectue une action en lot sur plusieurs alertes"""
    try:
        results = []
        errors = []
        successful = 0
        
        for alert_id in action_request.alert_ids:
            try:
                if action_request.action == "acknowledge":
                    user = action_request.parameters.get("acknowledged_by", "system")
                    success = await alerts_service.acknowledge_alert(alert_id, user)
                    
                elif action_request.action == "resolve":
                    alert = alerts_service.active_alerts.get(alert_id)
                    if alert:
                        await alerts_service._resolve_alert(alert)
                        success = True
                    else:
                        success = False
                        
                # Autres actions peuvent être ajoutées ici
                else:
                    success = False
                    errors.append(f"Action non supportée: {action_request.action}")
                    continue
                
                if success:
                    successful += 1
                    results.append({"alert_id": alert_id, "success": True})
                else:
                    results.append({"alert_id": alert_id, "success": False, "error": "Échec action"})
                    
            except Exception as e:
                errors.append(f"Erreur pour {alert_id}: {str(e)}")
                results.append({"alert_id": alert_id, "success": False, "error": str(e)})
        
        return BulkAlertActionResponse(
            total_processed=len(action_request.alert_ids),
            successful=successful,
            failed=len(action_request.alert_ids) - successful,
            results=results,
            errors=errors
        )
        
    except Exception as e:
        logger.error(f"Erreur action en lot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# STATISTIQUES ET MÉTRIQUES
# ============================================================================

@router.get("/stats", response_model=AlertsStatsResponse)
async def get_alerts_stats(
    days: int = Query(30, ge=1, le=365, description="Période d'analyse"),
    alerts_service: AlertsService = Depends(get_alerts_service)
):
    """Récupère les statistiques des alertes"""
    try:
        # Récupère l'historique
        alerts = await alerts_service.get_alerts_history(days)
        active_alerts = alerts_service.get_active_alerts()
        
        # Calcule les statistiques
        total_alerts = len(alerts)
        active_count = len(active_alerts)
        acknowledged_count = len([a for a in alerts if a.state == AlertState.ACKNOWLEDGED])
        resolved_count = len([a for a in alerts if a.state == AlertState.RESOLVED])
        
        # Répartition par sévérité
        alerts_by_severity = {}
        for severity in AlertSeverity:
            count = len([a for a in alerts if a.severity == severity])
            alerts_by_severity[severity.value] = count
        
        # Répartition par état
        alerts_by_state = {}
        for state in AlertState:
            count = len([a for a in alerts if a.state == state])
            alerts_by_state[state.value] = count
        
        # Répartition par règle
        alerts_by_rule = {}
        for alert in alerts:
            rule_name = alert.rule_name
            alerts_by_rule[rule_name] = alerts_by_rule.get(rule_name, 0) + 1
        
        # Top règles déclenchées
        top_triggered_rules = [
            {"rule_name": rule, "count": count}
            for rule, count in sorted(alerts_by_rule.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        # Conteneurs les plus affectés
        container_counts = {}
        for alert in alerts:
            container = alert.container_name
            container_counts[container] = container_counts.get(container, 0) + 1
        
        most_affected_containers = [
            {"container_name": container, "count": count}
            for container, count in sorted(container_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        # Alertes escaladées et supprimées
        escalated_alerts = len([a for a in alerts if a.escalation_level != EscalationLevel.LEVEL_1])
        suppressed_alerts = len([a for a in alerts if a.state == AlertState.SUPPRESSED])
        
        return AlertsStatsResponse(
            total_alerts=total_alerts,
            active_alerts=active_count,
            acknowledged_alerts=acknowledged_count,
            resolved_alerts=resolved_count,
            alerts_by_severity=alerts_by_severity,
            alerts_by_state=alerts_by_state,
            alerts_by_rule=alerts_by_rule,
            top_triggered_rules=top_triggered_rules,
            most_affected_containers=most_affected_containers,
            escalated_alerts=escalated_alerts,
            suppressed_alerts=suppressed_alerts
        )
        
    except Exception as e:
        logger.error(f"Erreur calcul statistiques alertes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/metrics", response_model=AlertMetricsResponse)
async def get_alert_metrics(
    metrics_request: AlertMetricsRequest = Depends(),
    alerts_service: AlertsService = Depends(get_alerts_service)
):
    """Récupère les métriques d'alertes sous forme de séries temporelles"""
    try:
        # Récupère l'historique pour la période demandée
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=metrics_request.time_range_hours)
        
        alerts = await alerts_service.get_alerts_history(
            days=metrics_request.time_range_hours // 24 + 1
        )
        
        # Filtre par période
        alerts = [
            alert for alert in alerts 
            if start_time <= alert.triggered_at <= end_time
        ]
        
        # Génère les séries temporelles
        time_series = []
        current_time = start_time
        granularity = timedelta(minutes=metrics_request.granularity_minutes)
        
        while current_time <= end_time:
            period_end = current_time + granularity
            period_alerts = [
                alert for alert in alerts
                if current_time <= alert.triggered_at < period_end
            ]
            
            time_point = {
                "timestamp": current_time.isoformat(),
                "total_alerts": len(period_alerts)
            }
            
            # Ajoute les métriques par type demandé
            for metric_type in metrics_request.metric_types:
                if metric_type == "alerts_by_severity":
                    for severity in AlertSeverity:
                        count = len([a for a in period_alerts if a.severity == severity])
                        time_point[f"severity_{severity.value}"] = count
                        
                elif metric_type == "alerts_by_state":
                    for state in AlertState:
                        count = len([a for a in period_alerts if a.state == state])
                        time_point[f"state_{state.value}"] = count
                        
                elif metric_type == "response_times":
                    # Temps de réponse moyen (temps jusqu'à acquittement)
                    ack_times = []
                    for alert in period_alerts:
                        if alert.acknowledged_at:
                            response_time = (alert.acknowledged_at - alert.triggered_at).total_seconds()
                            ack_times.append(response_time)
                    
                    if ack_times:
                        time_point["avg_response_time_seconds"] = sum(ack_times) / len(ack_times)
                    else:
                        time_point["avg_response_time_seconds"] = 0
            
            time_series.append(time_point)
            current_time = period_end
        
        # Calcule les statistiques agrégées
        aggregated_stats = {
            "total_alerts": len(alerts),
            "avg_alerts_per_hour": len(alerts) / max(metrics_request.time_range_hours, 1),
            "peak_alerts_hour": max([tp["total_alerts"] for tp in time_series], default=0)
        }
        
        # Détecte les tendances
        trends = {}
        if len(time_series) >= 2:
            first_half = time_series[:len(time_series)//2]
            second_half = time_series[len(time_series)//2:]
            
            first_avg = sum(tp["total_alerts"] for tp in first_half) / len(first_half)
            second_avg = sum(tp["total_alerts"] for tp in second_half) / len(second_half)
            
            if second_avg > first_avg * 1.2:
                trends["overall"] = "increasing"
            elif second_avg < first_avg * 0.8:
                trends["overall"] = "decreasing"
            else:
                trends["overall"] = "stable"
        
        return AlertMetricsResponse(
            time_series=time_series,
            aggregated_stats=aggregated_stats,
            trends=trends
        )
        
    except Exception as e:
        logger.error(f"Erreur récupération métriques alertes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# EXPORT ET IMPORT
# ============================================================================

@router.post("/export")
async def export_alerts(
    export_request: AlertsExportRequest,
    alerts_service: AlertsService = Depends(get_alerts_service)
):
    """Exporte les alertes dans différents formats"""
    try:
        # Récupère les données
        alerts = await alerts_service.get_alerts_history(export_request.date_range_days)
        
        if not export_request.include_resolved:
            alerts = [alert for alert in alerts if alert.state != AlertState.RESOLVED]
        
        # Applique les filtres si fournis
        if export_request.filters:
            # Logique de filtrage similaire à get_alerts_history
            pass
        
        if export_request.format == 'json':
            data = [_convert_alert_instance_to_response(alert).dict() for alert in alerts]
            content = json.dumps(data, indent=2, default=str)
            media_type = "application/json"
            filename = f"wakedock_alerts_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            
        elif export_request.format == 'csv':
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Headers
            writer.writerow([
                'alert_id', 'rule_name', 'severity', 'container_name', 'service_name',
                'metric_type', 'current_value', 'threshold_value', 'state',
                'triggered_at', 'acknowledged_at', 'resolved_at'
            ])
            
            # Data
            for alert in alerts:
                writer.writerow([
                    alert.alert_id, alert.rule_name, alert.severity.value,
                    alert.container_name, alert.service_name or '',
                    alert.metric_type, alert.current_value, alert.threshold_value,
                    alert.state.value,
                    alert.triggered_at.isoformat(),
                    alert.acknowledged_at.isoformat() if alert.acknowledged_at else '',
                    alert.resolved_at.isoformat() if alert.resolved_at else ''
                ])
            
            content = output.getvalue()
            media_type = "text/csv"
            filename = f"wakedock_alerts_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            
        else:
            raise HTTPException(status_code=400, detail="Format non supporté")
        
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur export alertes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# STATUT DU SERVICE
# ============================================================================

@router.get("/service/status", response_model=AlertsServiceStatusResponse)
async def get_alerts_service_status(
    alerts_service: AlertsService = Depends(get_alerts_service)
):
    """Récupère le statut du service d'alertes"""
    try:
        stats = alerts_service.get_service_stats()
        
        return AlertsServiceStatusResponse(
            is_running=stats["is_running"],
            uptime_seconds=int(time.time()),  # Approximation
            active_alerts_count=stats["active_alerts_count"],
            alert_rules_count=stats["alert_rules_count"],
            notification_targets_count=stats["notification_targets_count"],
            monitoring_enabled=stats["is_running"],
            escalation_enabled=True,  # Toujours activé
            last_evaluation=datetime.utcnow() - timedelta(seconds=30),  # Approximation
            next_evaluation=datetime.utcnow() + timedelta(seconds=30),  # Approximation
            metrics_history_size=stats["metrics_history_containers"],
            storage_path=stats["storage_path"]
        )
        
    except Exception as e:
        logger.error(f"Erreur statut service alertes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/service/restart")
async def restart_alerts_service(
    background_tasks: BackgroundTasks,
    alerts_service: AlertsService = Depends(get_alerts_service)
):
    """Redémarre le service d'alertes"""
    try:
        async def restart_service():
            await alerts_service.stop()
            await asyncio.sleep(2)
            await alerts_service.start()
        
        background_tasks.add_task(restart_service)
        
        return {"message": "Redémarrage du service d'alertes initié"}
        
    except Exception as e:
        logger.error(f"Erreur redémarrage service alertes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def _convert_alert_rule_to_response(rule: AlertRule) -> AlertRuleResponse:
    """Convertit une AlertRule en AlertRuleResponse"""
    escalation_targets = None
    if rule.escalation_targets:
        escalation_targets = {
            level.value: targets for level, targets in rule.escalation_targets.items()
        }
    
    return AlertRuleResponse(
        rule_id=rule.rule_id,
        name=rule.name,
        description=rule.description,
        enabled=rule.enabled,
        metric_type=rule.metric_type,
        threshold_value=rule.threshold_value,
        comparison_operator=rule.comparison_operator,
        duration_minutes=rule.duration_minutes,
        container_filters=rule.container_filters,
        service_filters=rule.service_filters,
        severity=rule.severity,
        notification_targets=rule.notification_targets,
        escalation_enabled=rule.escalation_enabled,
        escalation_delay_minutes=rule.escalation_delay_minutes,
        escalation_targets=escalation_targets,
        suppression_enabled=rule.suppression_enabled,
        suppression_duration_minutes=rule.suppression_duration_minutes,
        grouping_keys=rule.grouping_keys,
        created_at=rule.created_at,
        updated_at=rule.updated_at
    )

def _convert_notification_target_to_response(target: NotificationTarget, target_id: str) -> NotificationTargetResponse:
    """Convertit une NotificationTarget en NotificationTargetResponse"""
    return NotificationTargetResponse(
        target_id=target_id,
        channel=target.channel,
        name=target.name,
        enabled=target.enabled,
        has_email_config=bool(target.email_address),
        has_webhook_config=bool(target.webhook_url),
        has_slack_config=bool(target.slack_webhook_url),
        has_discord_config=bool(target.discord_webhook_url),
        has_teams_config=bool(target.teams_webhook_url),
        has_telegram_config=bool(target.telegram_bot_token and target.telegram_chat_id)
    )

def _convert_alert_instance_to_response(alert: AlertInstance) -> AlertInstanceResponse:
    """Convertit une AlertInstance en AlertInstanceResponse"""
    return AlertInstanceResponse(
        alert_id=alert.alert_id,
        rule_id=alert.rule_id,
        rule_name=alert.rule_name,
        container_id=alert.container_id,
        container_name=alert.container_name,
        service_name=alert.service_name,
        metric_type=alert.metric_type,
        current_value=alert.current_value,
        threshold_value=alert.threshold_value,
        severity=alert.severity,
        state=alert.state,
        triggered_at=alert.triggered_at,
        acknowledged_at=alert.acknowledged_at,
        resolved_at=alert.resolved_at,
        acknowledged_by=alert.acknowledged_by,
        escalation_level=alert.escalation_level,
        escalated_at=alert.escalated_at,
        last_notification_at=alert.last_notification_at,
        notifications_sent_count=len(alert.notifications_sent),
        group_key=alert.group_key,
        similar_alerts_count=alert.similar_alerts_count
    )
