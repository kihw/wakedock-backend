"""
Modèles Pydantic pour l'API d'alertes et notifications
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
from enum import Enum

# Réutilise les enums du service
from wakedock.core.alerts_service import (
    NotificationChannel, AlertSeverity, EscalationLevel, AlertState
)

class NotificationTargetRequest(BaseModel):
    """Modèle pour créer/modifier une cible de notification"""
    channel: NotificationChannel = Field(..., description="Type de canal de notification")
    name: str = Field(..., min_length=1, max_length=100, description="Nom de la cible")
    enabled: bool = Field(default=True, description="Si la cible est activée")
    
    # Configuration par canal
    email_address: Optional[str] = Field(None, description="Adresse email")
    
    webhook_url: Optional[str] = Field(None, description="URL du webhook")
    webhook_headers: Optional[Dict[str, str]] = Field(None, description="Headers HTTP du webhook")
    
    slack_webhook_url: Optional[str] = Field(None, description="URL webhook Slack")
    slack_channel: Optional[str] = Field(None, description="Canal Slack")
    slack_token: Optional[str] = Field(None, description="Token Slack")
    
    discord_webhook_url: Optional[str] = Field(None, description="URL webhook Discord")
    
    teams_webhook_url: Optional[str] = Field(None, description="URL webhook Teams")
    
    telegram_bot_token: Optional[str] = Field(None, description="Token bot Telegram")
    telegram_chat_id: Optional[str] = Field(None, description="Chat ID Telegram")
    
    @validator('email_address')
    def validate_email(cls, v, values):
        if values.get('channel') == NotificationChannel.EMAIL and not v:
            raise ValueError('Email address required for email notifications')
        return v
    
    @validator('webhook_url')
    def validate_webhook_url(cls, v, values):
        if values.get('channel') == NotificationChannel.WEBHOOK and not v:
            raise ValueError('Webhook URL required for webhook notifications')
        return v
    
    @validator('slack_webhook_url')
    def validate_slack_webhook(cls, v, values):
        if values.get('channel') == NotificationChannel.SLACK and not v:
            raise ValueError('Slack webhook URL required for Slack notifications')
        return v
    
    @validator('discord_webhook_url')
    def validate_discord_webhook(cls, v, values):
        if values.get('channel') == NotificationChannel.DISCORD and not v:
            raise ValueError('Discord webhook URL required for Discord notifications')
        return v
    
    @validator('teams_webhook_url')
    def validate_teams_webhook(cls, v, values):
        if values.get('channel') == NotificationChannel.TEAMS and not v:
            raise ValueError('Teams webhook URL required for Teams notifications')
        return v
    
    @validator('telegram_bot_token')
    def validate_telegram_token(cls, v, values):
        if values.get('channel') == NotificationChannel.TELEGRAM and not v:
            raise ValueError('Telegram bot token required for Telegram notifications')
        return v

class NotificationTargetResponse(BaseModel):
    """Modèle de réponse pour une cible de notification"""
    target_id: str = Field(..., description="ID unique de la cible")
    channel: NotificationChannel = Field(..., description="Type de canal")
    name: str = Field(..., description="Nom de la cible")
    enabled: bool = Field(..., description="Si la cible est activée")
    
    # Configuration masquée pour la sécurité
    has_email_config: bool = Field(default=False, description="A une configuration email")
    has_webhook_config: bool = Field(default=False, description="A une configuration webhook")
    has_slack_config: bool = Field(default=False, description="A une configuration Slack")
    has_discord_config: bool = Field(default=False, description="A une configuration Discord")
    has_teams_config: bool = Field(default=False, description="A une configuration Teams")
    has_telegram_config: bool = Field(default=False, description="A une configuration Telegram")

class AlertRuleRequest(BaseModel):
    """Modèle pour créer/modifier une règle d'alerte"""
    name: str = Field(..., min_length=1, max_length=200, description="Nom de la règle")
    description: str = Field(..., max_length=1000, description="Description de la règle")
    enabled: bool = Field(default=True, description="Si la règle est activée")
    
    # Conditions de déclenchement
    metric_type: str = Field(..., description="Type de métrique à surveiller")
    threshold_value: float = Field(..., description="Valeur seuil")
    comparison_operator: str = Field(..., description="Opérateur de comparaison")
    duration_minutes: int = Field(default=5, ge=1, le=1440, description="Durée avant déclenchement")
    
    # Filtres
    container_filters: Optional[Dict[str, str]] = Field(None, description="Filtres sur les conteneurs")
    service_filters: Optional[List[str]] = Field(None, description="Filtres sur les services")
    
    # Configuration de sévérité
    severity: AlertSeverity = Field(default=AlertSeverity.MEDIUM, description="Sévérité de l'alerte")
    
    # Cibles de notification
    notification_targets: List[str] = Field(default_factory=list, description="IDs des cibles de notification")
    
    # Escalade
    escalation_enabled: bool = Field(default=False, description="Si l'escalade est activée")
    escalation_delay_minutes: int = Field(default=30, ge=5, le=1440, description="Délai d'escalade")
    escalation_targets: Optional[Dict[str, List[str]]] = Field(None, description="Cibles par niveau d'escalade")
    
    # Suppression/regroupement
    suppression_enabled: bool = Field(default=False, description="Si la suppression est activée")
    suppression_duration_minutes: int = Field(default=60, ge=5, le=10080, description="Durée de suppression")
    grouping_keys: Optional[List[str]] = Field(None, description="Clés de regroupement")
    
    @validator('comparison_operator')
    def validate_operator(cls, v):
        valid_operators = ['>', '<', '>=', '<=', '==', '!=']
        if v not in valid_operators:
            raise ValueError(f'Operator must be one of: {valid_operators}')
        return v
    
    @validator('metric_type')
    def validate_metric_type(cls, v):
        valid_metrics = [
            'cpu_percent', 'memory_percent', 'memory_usage_bytes',
            'network_rx_bytes', 'network_tx_bytes', 'network_total_bytes'
        ]
        if v not in valid_metrics:
            raise ValueError(f'Metric type must be one of: {valid_metrics}')
        return v

class AlertRuleResponse(BaseModel):
    """Modèle de réponse pour une règle d'alerte"""
    rule_id: str = Field(..., description="ID unique de la règle")
    name: str = Field(..., description="Nom de la règle")
    description: str = Field(..., description="Description")
    enabled: bool = Field(..., description="Si activée")
    
    metric_type: str = Field(..., description="Type de métrique")
    threshold_value: float = Field(..., description="Valeur seuil")
    comparison_operator: str = Field(..., description="Opérateur")
    duration_minutes: int = Field(..., description="Durée")
    
    container_filters: Optional[Dict[str, str]] = Field(None, description="Filtres conteneurs")
    service_filters: Optional[List[str]] = Field(None, description="Filtres services")
    
    severity: AlertSeverity = Field(..., description="Sévérité")
    notification_targets: List[str] = Field(..., description="Cibles de notification")
    
    escalation_enabled: bool = Field(..., description="Escalade activée")
    escalation_delay_minutes: int = Field(..., description="Délai escalade")
    escalation_targets: Optional[Dict[str, List[str]]] = Field(None, description="Cibles escalade")
    
    suppression_enabled: bool = Field(..., description="Suppression activée")
    suppression_duration_minutes: int = Field(..., description="Durée suppression")
    grouping_keys: Optional[List[str]] = Field(None, description="Clés regroupement")
    
    created_at: datetime = Field(..., description="Date de création")
    updated_at: datetime = Field(..., description="Date de modification")

class AlertInstanceResponse(BaseModel):
    """Modèle de réponse pour une instance d'alerte"""
    alert_id: str = Field(..., description="ID unique de l'alerte")
    rule_id: str = Field(..., description="ID de la règle")
    rule_name: str = Field(..., description="Nom de la règle")
    
    container_id: str = Field(..., description="ID du conteneur")
    container_name: str = Field(..., description="Nom du conteneur")
    service_name: Optional[str] = Field(None, description="Nom du service")
    metric_type: str = Field(..., description="Type de métrique")
    current_value: float = Field(..., description="Valeur actuelle")
    threshold_value: float = Field(..., description="Valeur seuil")
    severity: AlertSeverity = Field(..., description="Sévérité")
    
    state: AlertState = Field(..., description="État de l'alerte")
    triggered_at: datetime = Field(..., description="Date de déclenchement")
    acknowledged_at: Optional[datetime] = Field(None, description="Date d'acquittement")
    resolved_at: Optional[datetime] = Field(None, description="Date de résolution")
    acknowledged_by: Optional[str] = Field(None, description="Acquittée par")
    
    escalation_level: EscalationLevel = Field(..., description="Niveau d'escalade")
    escalated_at: Optional[datetime] = Field(None, description="Date d'escalade")
    
    last_notification_at: Optional[datetime] = Field(None, description="Dernière notification")
    notifications_sent_count: int = Field(default=0, description="Nombre de notifications")
    
    group_key: Optional[str] = Field(None, description="Clé de regroupement")
    similar_alerts_count: int = Field(default=1, description="Nombre d'alertes similaires")

class AlertAcknowledgeRequest(BaseModel):
    """Modèle pour acquitter une alerte"""
    acknowledged_by: str = Field(..., min_length=1, max_length=100, description="Nom de la personne")
    comment: Optional[str] = Field(None, max_length=500, description="Commentaire optionnel")

class AlertsFilterRequest(BaseModel):
    """Modèle pour filtrer les alertes"""
    states: Optional[List[AlertState]] = Field(None, description="États des alertes")
    severities: Optional[List[AlertSeverity]] = Field(None, description="Sévérités")
    rule_ids: Optional[List[str]] = Field(None, description="IDs des règles")
    container_ids: Optional[List[str]] = Field(None, description="IDs des conteneurs")
    service_names: Optional[List[str]] = Field(None, description="Noms des services")
    
    from_date: Optional[datetime] = Field(None, description="Date de début")
    to_date: Optional[datetime] = Field(None, description="Date de fin")
    
    limit: int = Field(default=100, ge=1, le=1000, description="Limite de résultats")
    offset: int = Field(default=0, ge=0, description="Décalage")

class AlertsStatsResponse(BaseModel):
    """Modèle de réponse pour les statistiques d'alertes"""
    total_alerts: int = Field(..., description="Total des alertes")
    active_alerts: int = Field(..., description="Alertes actives")
    acknowledged_alerts: int = Field(..., description="Alertes acquittées")
    resolved_alerts: int = Field(..., description="Alertes résolues")
    
    alerts_by_severity: Dict[str, int] = Field(..., description="Répartition par sévérité")
    alerts_by_state: Dict[str, int] = Field(..., description="Répartition par état")
    alerts_by_rule: Dict[str, int] = Field(..., description="Répartition par règle")
    
    top_triggered_rules: List[Dict[str, Any]] = Field(..., description="Règles les plus déclenchées")
    most_affected_containers: List[Dict[str, Any]] = Field(..., description="Conteneurs les plus affectés")
    
    escalated_alerts: int = Field(..., description="Alertes escaladées")
    suppressed_alerts: int = Field(..., description="Alertes supprimées")

class NotificationTestRequest(BaseModel):
    """Modèle pour tester une notification"""
    target_id: str = Field(..., description="ID de la cible à tester")
    test_message: Optional[str] = Field(None, description="Message de test personnalisé")

class NotificationTestResponse(BaseModel):
    """Modèle de réponse pour un test de notification"""
    success: bool = Field(..., description="Si le test a réussi")
    message: str = Field(..., description="Message du résultat")
    sent_at: datetime = Field(..., description="Heure d'envoi")
    response_time_ms: int = Field(..., description="Temps de réponse en ms")

class AlertRuleTestRequest(BaseModel):
    """Modèle pour tester une règle d'alerte"""
    rule: AlertRuleRequest = Field(..., description="Règle à tester")
    test_metrics: List[Dict[str, Any]] = Field(..., description="Métriques de test")

class AlertRuleTestResponse(BaseModel):
    """Modèle de réponse pour un test de règle"""
    would_trigger: bool = Field(..., description="Si la règle se déclencherait")
    matching_containers: List[str] = Field(..., description="Conteneurs correspondants")
    threshold_violations: List[Dict[str, Any]] = Field(..., description="Violations de seuil")
    evaluation_details: Dict[str, Any] = Field(..., description="Détails de l'évaluation")

class AlertsServiceStatusResponse(BaseModel):
    """Modèle de réponse pour le statut du service d'alertes"""
    is_running: bool = Field(..., description="Si le service fonctionne")
    uptime_seconds: int = Field(..., description="Durée de fonctionnement")
    
    active_alerts_count: int = Field(..., description="Nombre d'alertes actives")
    alert_rules_count: int = Field(..., description="Nombre de règles")
    notification_targets_count: int = Field(..., description="Nombre de cibles")
    
    monitoring_enabled: bool = Field(..., description="Si le monitoring est activé")
    escalation_enabled: bool = Field(..., description="Si l'escalade est activée")
    
    last_evaluation: Optional[datetime] = Field(None, description="Dernière évaluation")
    next_evaluation: Optional[datetime] = Field(None, description="Prochaine évaluation")
    
    metrics_history_size: int = Field(..., description="Taille historique métriques")
    storage_path: str = Field(..., description="Chemin de stockage")

class AlertsExportRequest(BaseModel):
    """Modèle pour exporter les alertes"""
    format: str = Field(default='json', description="Format d'export (json, csv)")
    include_resolved: bool = Field(default=True, description="Inclure les alertes résolues")
    date_range_days: int = Field(default=30, ge=1, le=365, description="Plage de dates")
    
    filters: Optional[AlertsFilterRequest] = Field(None, description="Filtres optionnels")

class BulkAlertActionRequest(BaseModel):
    """Modèle pour actions en lot sur les alertes"""
    alert_ids: List[str] = Field(..., min_items=1, description="IDs des alertes")
    action: str = Field(..., description="Action à effectuer")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Paramètres de l'action")
    
    @validator('action')
    def validate_action(cls, v):
        valid_actions = ['acknowledge', 'resolve', 'suppress', 'escalate']
        if v not in valid_actions:
            raise ValueError(f'Action must be one of: {valid_actions}')
        return v

class BulkAlertActionResponse(BaseModel):
    """Modèle de réponse pour actions en lot"""
    total_processed: int = Field(..., description="Total traité")
    successful: int = Field(..., description="Réussites")
    failed: int = Field(..., description="Échecs")
    
    results: List[Dict[str, Any]] = Field(..., description="Résultats détaillés")
    errors: List[str] = Field(..., description="Erreurs rencontrées")

class AlertMetricsRequest(BaseModel):
    """Modèle pour récupérer les métriques d'alertes"""
    metric_types: List[str] = Field(..., description="Types de métriques")
    time_range_hours: int = Field(default=24, ge=1, le=168, description="Plage temporelle")
    granularity_minutes: int = Field(default=60, ge=5, le=1440, description="Granularité")

class AlertMetricsResponse(BaseModel):
    """Modèle de réponse pour les métriques d'alertes"""
    time_series: List[Dict[str, Any]] = Field(..., description="Données temporelles")
    aggregated_stats: Dict[str, Any] = Field(..., description="Statistiques agrégées")
    trends: Dict[str, str] = Field(..., description="Tendances détectées")

# Modèles pour l'intégration avec d'autres systèmes

class ExternalMonitoringIntegration(BaseModel):
    """Modèle pour intégration avec systèmes de monitoring externes"""
    integration_id: str = Field(..., description="ID de l'intégration")
    name: str = Field(..., description="Nom de l'intégration")
    type: str = Field(..., description="Type de système (prometheus, grafana, etc.)")
    enabled: bool = Field(default=True, description="Si activée")
    
    configuration: Dict[str, Any] = Field(..., description="Configuration spécifique")
    sync_interval_minutes: int = Field(default=5, ge=1, le=60, description="Intervalle de sync")
    
    last_sync: Optional[datetime] = Field(None, description="Dernière synchronisation")
    sync_status: str = Field(default='pending', description="Statut de sync")

class AlertWebhookEvent(BaseModel):
    """Modèle pour les événements webhook d'alertes"""
    event_type: str = Field(..., description="Type d'événement")
    alert: AlertInstanceResponse = Field(..., description="Données de l'alerte")
    timestamp: datetime = Field(..., description="Horodatage")
    source: str = Field(default='wakedock', description="Source de l'événement")
    
    metadata: Optional[Dict[str, Any]] = Field(None, description="Métadonnées additionnelles")

# Configurations par défaut et exemples

class DefaultAlertRules:
    """Règles d'alertes par défaut"""
    
    HIGH_CPU_USAGE = {
        "name": "High CPU Usage",
        "description": "Alert when container CPU usage exceeds 80%",
        "metric_type": "cpu_percent",
        "threshold_value": 80.0,
        "comparison_operator": ">",
        "duration_minutes": 5,
        "severity": AlertSeverity.HIGH
    }
    
    HIGH_MEMORY_USAGE = {
        "name": "High Memory Usage", 
        "description": "Alert when container memory usage exceeds 90%",
        "metric_type": "memory_percent",
        "threshold_value": 90.0,
        "comparison_operator": ">",
        "duration_minutes": 3,
        "severity": AlertSeverity.CRITICAL
    }
    
    LOW_MEMORY_AVAILABLE = {
        "name": "Low Memory Available",
        "description": "Alert when available memory is below 10%",
        "metric_type": "memory_percent",
        "threshold_value": 10.0,
        "comparison_operator": "<",
        "duration_minutes": 2,
        "severity": AlertSeverity.CRITICAL
    }
    
    NETWORK_HIGH_TRAFFIC = {
        "name": "High Network Traffic",
        "description": "Alert when network traffic exceeds 1GB/hour",
        "metric_type": "network_total_bytes",
        "threshold_value": 1073741824,  # 1GB
        "comparison_operator": ">",
        "duration_minutes": 60,
        "severity": AlertSeverity.MEDIUM
    }

class SampleNotificationTargets:
    """Exemples de cibles de notification"""
    
    EMAIL_ADMIN = {
        "channel": NotificationChannel.EMAIL,
        "name": "Administrator Email",
        "email_address": "admin@example.com"
    }
    
    SLACK_DEVOPS = {
        "channel": NotificationChannel.SLACK,
        "name": "DevOps Slack Channel",
        "slack_webhook_url": "https://hooks.slack.com/services/...",
        "slack_channel": "#devops-alerts"
    }
    
    WEBHOOK_MONITORING = {
        "channel": NotificationChannel.WEBHOOK,
        "name": "Monitoring System Webhook",
        "webhook_url": "https://monitoring.example.com/webhooks/alerts",
        "webhook_headers": {
            "Authorization": "Bearer token123",
            "Content-Type": "application/json"
        }
    }
