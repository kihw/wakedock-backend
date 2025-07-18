"""
Service d'alertes et notifications automatiques avancé pour WakeDock
"""
import asyncio
import json
import logging
import re
import smtplib
import ssl
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
import aiohttp
from jinja2 import Template

from wakedock.config import get_settings
from wakedock.core.metrics_collector import MetricsCollector

logger = logging.getLogger(__name__)

class NotificationChannel(Enum):
    """Types de canaux de notification"""
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"
    DISCORD = "discord"
    TEAMS = "teams"
    TELEGRAM = "telegram"

class AlertSeverity(Enum):
    """Niveaux de sévérité des alertes"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class EscalationLevel(Enum):
    """Niveaux d'escalade"""
    LEVEL_1 = "level_1"  # Équipe technique
    LEVEL_2 = "level_2"  # Lead technique / Manager
    LEVEL_3 = "level_3"  # Direction / On-call senior

class AlertState(Enum):
    """États des alertes"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"

@dataclass
class NotificationTarget:
    """Cible de notification"""
    channel: NotificationChannel
    name: str
    enabled: bool = True
    
    # Configuration par canal
    # Email
    email_address: Optional[str] = None
    
    # Webhook
    webhook_url: Optional[str] = None
    webhook_headers: Optional[Dict[str, str]] = None
    
    # Slack
    slack_webhook_url: Optional[str] = None
    slack_channel: Optional[str] = None
    slack_token: Optional[str] = None
    
    # Discord
    discord_webhook_url: Optional[str] = None
    
    # Teams
    teams_webhook_url: Optional[str] = None
    
    # Telegram
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convertit en dictionnaire"""
        return {
            **asdict(self),
            'channel': self.channel.value
        }

@dataclass
class AlertRule:
    """Règle d'alerte configurée"""
    rule_id: str
    name: str
    description: str
    metric_type: str  # cpu_percent, memory_percent, etc.
    threshold_value: float
    comparison_operator: str  # >, <, >=, <=, ==, !=
    enabled: bool = True
    duration_minutes: int = 5  # Durée avant déclenchement
    
    # Filtres
    container_filters: Optional[Dict[str, str]] = None  # name, service, etc.
    service_filters: Optional[List[str]] = None
    
    # Configuration de sévérité
    severity: AlertSeverity = AlertSeverity.MEDIUM
    
    # Cibles de notification
    notification_targets: List[str] = None  # IDs des NotificationTarget
    
    # Escalade
    escalation_enabled: bool = False
    escalation_delay_minutes: int = 30
    escalation_targets: Optional[Dict[EscalationLevel, List[str]]] = None
    
    # Suppression/regroupement
    suppression_enabled: bool = False
    suppression_duration_minutes: int = 60
    grouping_keys: Optional[List[str]] = None  # Clés pour grouper les alertes
    
    # Métadonnées
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        if self.notification_targets is None:
            self.notification_targets = []
        if self.container_filters is None:
            self.container_filters = {}
        if self.service_filters is None:
            self.service_filters = []
    
    def to_dict(self) -> Dict:
        """Convertit en dictionnaire"""
        data = asdict(self)
        data['severity'] = self.severity.value
        data['created_at'] = self.created_at.isoformat() if self.created_at else None
        data['updated_at'] = self.updated_at.isoformat() if self.updated_at else None
        
        if self.escalation_targets:
            data['escalation_targets'] = {
                level.value: targets for level, targets in self.escalation_targets.items()
            }
        
        return data

@dataclass
class AlertInstance:
    """Instance d'alerte déclenchée"""
    alert_id: str
    rule_id: str
    rule_name: str
    
    # Données de l'alerte
    container_id: str
    container_name: str
    service_name: Optional[str]
    metric_type: str
    current_value: float
    threshold_value: float
    severity: AlertSeverity
    
    # État et historique
    state: AlertState = AlertState.ACTIVE
    triggered_at: datetime = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    
    # Escalade
    escalation_level: EscalationLevel = EscalationLevel.LEVEL_1
    escalated_at: Optional[datetime] = None
    
    # Notifications
    notifications_sent: List[Dict] = None  # Historique des notifications
    last_notification_at: Optional[datetime] = None
    
    # Regroupement
    group_key: Optional[str] = None
    similar_alerts_count: int = 1
    
    def __post_init__(self):
        if self.triggered_at is None:
            self.triggered_at = datetime.utcnow()
        if self.notifications_sent is None:
            self.notifications_sent = []
    
    def to_dict(self) -> Dict:
        """Convertit en dictionnaire"""
        data = asdict(self)
        data['state'] = self.state.value
        data['severity'] = self.severity.value
        data['escalation_level'] = self.escalation_level.value
        
        # Convertit les dates
        for field in ['triggered_at', 'acknowledged_at', 'resolved_at', 'escalated_at', 'last_notification_at']:
            if hasattr(self, field):
                value = getattr(self, field)
                data[field] = value.isoformat() if value else None
        
        return data

class AlertsService:
    """Service principal d'alertes et notifications"""
    
    def __init__(self, metrics_collector: MetricsCollector, storage_path: str = "/var/log/wakedock/alerts"):
        self.metrics_collector = metrics_collector
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.settings = get_settings()
        
        # État du service
        self.is_running = False
        self.monitoring_task: Optional[asyncio.Task] = None
        self.escalation_task: Optional[asyncio.Task] = None
        
        # Stockage en mémoire
        self.alert_rules: Dict[str, AlertRule] = {}
        self.notification_targets: Dict[str, NotificationTarget] = {}
        self.active_alerts: Dict[str, AlertInstance] = {}
        
        # Cache et optimisations
        self.rule_cache: Dict[str, Any] = {}
        self.suppression_cache: Dict[str, datetime] = {}
        
        # Historique des métriques pour détection de seuils
        self.metrics_history: Dict[str, List] = {}
        self.history_max_size = 100
        
        # Templates de messages
        self.message_templates = {
            'email_subject': 'WakeDock Alert: {{alert.rule_name}} - {{alert.severity|upper}}',
            'email_body': '''
            <h2>🚨 Alerte WakeDock</h2>
            <p><strong>Règle :</strong> {{alert.rule_name}}</p>
            <p><strong>Sévérité :</strong> <span style="color: {{severity_color}}">{{alert.severity|upper}}</span></p>
            <p><strong>Conteneur :</strong> {{alert.container_name}} ({{alert.container_id[:12]}})</p>
            {% if alert.service_name %}<p><strong>Service :</strong> {{alert.service_name}}</p>{% endif %}
            <p><strong>Métrique :</strong> {{alert.metric_type}}</p>
            <p><strong>Valeur actuelle :</strong> {{alert.current_value}}{{unit}}</p>
            <p><strong>Seuil :</strong> {{alert.threshold_value}}{{unit}}</p>
            <p><strong>Déclenchée à :</strong> {{alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC')}}</p>
            
            <hr>
            <p><em>Cette alerte a été générée automatiquement par WakeDock.</em></p>
            ''',
            'slack_message': '''
            :warning: *Alerte WakeDock*
            
            *Règle :* {{alert.rule_name}}
            *Sévérité :* {{alert.severity|upper}}
            *Conteneur :* {{alert.container_name}} (`{{alert.container_id[:12]}}`)
            {% if alert.service_name %}*Service :* {{alert.service_name}}{% endif %}
            *Métrique :* {{alert.metric_type}}
            *Valeur :* {{alert.current_value}}{{unit}} (seuil: {{alert.threshold_value}}{{unit}})
            *Heure :* {{alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC')}}
            '''
        }
    
    async def start(self):
        """Démarre le service d'alertes"""
        if self.is_running:
            return
        
        logger.info("Démarrage du service d'alertes et notifications")
        self.is_running = True
        
        # Charge la configuration depuis le stockage
        await self._load_configuration()
        
        # Démarre les tâches de fond
        self.monitoring_task = asyncio.create_task(self._monitoring_worker())
        self.escalation_task = asyncio.create_task(self._escalation_worker())
    
    async def stop(self):
        """Arrête le service d'alertes"""
        if not self.is_running:
            return
        
        logger.info("Arrêt du service d'alertes et notifications")
        self.is_running = False
        
        # Arrête les tâches
        if self.monitoring_task:
            self.monitoring_task.cancel()
        if self.escalation_task:
            self.escalation_task.cancel()
        
        # Sauvegarde la configuration
        await self._save_configuration()
    
    async def _monitoring_worker(self):
        """Worker principal de monitoring des alertes"""
        while self.is_running:
            try:
                # Récupère les métriques récentes
                recent_metrics = await self.metrics_collector.get_recent_metrics(
                    hours=1, limit=1000
                )
                
                # Met à jour l'historique des métriques
                self._update_metrics_history(recent_metrics)
                
                # Évalue toutes les règles d'alertes
                for rule in self.alert_rules.values():
                    if rule.enabled:
                        await self._evaluate_alert_rule(rule, recent_metrics)
                
                # Nettoie les alertes résolues anciennes
                await self._cleanup_old_alerts()
                
                # Attend avant la prochaine évaluation
                await asyncio.sleep(30)  # Évalue toutes les 30 secondes
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur dans le worker de monitoring d'alertes: {e}")
                await asyncio.sleep(60)
    
    async def _escalation_worker(self):
        """Worker pour l'escalade automatique des alertes"""
        while self.is_running:
            try:
                current_time = datetime.utcnow()
                
                for alert in list(self.active_alerts.values()):
                    # Vérifie si l'alerte nécessite une escalade
                    if await self._should_escalate_alert(alert, current_time):
                        await self._escalate_alert(alert)
                
                # Attend 5 minutes avant la prochaine vérification
                await asyncio.sleep(300)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur dans le worker d'escalade: {e}")
                await asyncio.sleep(300)
    
    def _update_metrics_history(self, metrics: List):
        """Met à jour l'historique des métriques pour l'évaluation des seuils"""
        for metric in metrics:
            key = f"{metric.container_id}:{metric.timestamp.isoformat()}"
            
            if metric.container_id not in self.metrics_history:
                self.metrics_history[metric.container_id] = []
            
            # Ajoute la métrique à l'historique
            self.metrics_history[metric.container_id].append({
                'timestamp': metric.timestamp,
                'cpu_percent': metric.cpu_percent,
                'memory_percent': metric.memory_percent,
                'network_rx_bytes': metric.network_rx_bytes,
                'network_tx_bytes': metric.network_tx_bytes,
                'container_name': metric.container_name,
                'service_name': metric.service_name
            })
            
            # Limite la taille de l'historique
            if len(self.metrics_history[metric.container_id]) > self.history_max_size:
                self.metrics_history[metric.container_id] = \
                    self.metrics_history[metric.container_id][-self.history_max_size:]
    
    async def _evaluate_alert_rule(self, rule: AlertRule, recent_metrics: List):
        """Évalue une règle d'alerte contre les métriques récentes"""
        try:
            # Filtre les métriques selon les critères de la règle
            relevant_metrics = self._filter_metrics_for_rule(rule, recent_metrics)
            
            for container_id, container_metrics in relevant_metrics.items():
                # Vérifie si le seuil est dépassé pendant la durée requise
                if self._check_threshold_violation(rule, container_metrics):
                    await self._trigger_alert(rule, container_id, container_metrics[-1])
                else:
                    # Vérifie si une alerte existante doit être résolue
                    await self._check_alert_resolution(rule, container_id, container_metrics[-1])
                    
        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation de la règle {rule.rule_id}: {e}")
    
    def _filter_metrics_for_rule(self, rule: AlertRule, metrics: List) -> Dict[str, List]:
        """Filtre les métriques selon les critères de la règle"""
        filtered = {}
        
        for metric in metrics:
            # Applique les filtres de conteneur
            if rule.container_filters:
                if not self._matches_container_filters(metric, rule.container_filters):
                    continue
            
            # Applique les filtres de service
            if rule.service_filters and metric.service_name not in rule.service_filters:
                continue
            
            # Groupe par conteneur
            if metric.container_id not in filtered:
                filtered[metric.container_id] = []
            
            filtered[metric.container_id].append(metric)
        
        # Trie par timestamp pour chaque conteneur
        for container_id in filtered:
            filtered[container_id].sort(key=lambda m: m.timestamp)
        
        return filtered
    
    def _matches_container_filters(self, metric, filters: Dict[str, str]) -> bool:
        """Vérifie si une métrique correspond aux filtres de conteneur"""
        for filter_key, filter_value in filters.items():
            if filter_key == 'name':
                if not re.search(filter_value, metric.container_name):
                    return False
            elif filter_key == 'service':
                if not re.search(filter_value, metric.service_name or ''):
                    return False
            elif filter_key == 'id':
                if not metric.container_id.startswith(filter_value):
                    return False
        
        return True
    
    def _check_threshold_violation(self, rule: AlertRule, container_metrics: List) -> bool:
        """Vérifie si le seuil est violé pendant la durée requise"""
        if not container_metrics:
            return False
        
        # Vérifie les métriques des dernières X minutes
        cutoff_time = datetime.utcnow() - timedelta(minutes=rule.duration_minutes)
        recent_metrics = [m for m in container_metrics if m.timestamp >= cutoff_time]
        
        if len(recent_metrics) < 2:  # Pas assez de données
            return False
        
        # Vérifie que TOUTES les métriques récentes violent le seuil
        violations = 0
        for metric in recent_metrics:
            value = self._extract_metric_value(metric, rule.metric_type)
            if value is not None and self._compare_values(value, rule.threshold_value, rule.comparison_operator):
                violations += 1
        
        # Le seuil est violé si au moins 80% des métriques récentes le violent
        violation_ratio = violations / len(recent_metrics)
        return violation_ratio >= 0.8
    
    def _extract_metric_value(self, metric, metric_type: str) -> Optional[float]:
        """Extrait la valeur de métrique selon le type"""
        if metric_type == 'cpu_percent':
            return metric.cpu_percent
        elif metric_type == 'memory_percent':
            return metric.memory_percent
        elif metric_type == 'memory_usage_bytes':
            return metric.memory_usage_bytes
        elif metric_type == 'network_rx_bytes':
            return metric.network_rx_bytes
        elif metric_type == 'network_tx_bytes':
            return metric.network_tx_bytes
        elif metric_type == 'network_total_bytes':
            return metric.network_rx_bytes + metric.network_tx_bytes
        
        return None
    
    def _compare_values(self, value: float, threshold: float, operator: str) -> bool:
        """Compare deux valeurs selon l'opérateur"""
        if operator == '>':
            return value > threshold
        elif operator == '<':
            return value < threshold
        elif operator == '>=':
            return value >= threshold
        elif operator == '<=':
            return value <= threshold
        elif operator == '==':
            return abs(value - threshold) < 0.01  # Tolérance pour les flottants
        elif operator == '!=':
            return abs(value - threshold) >= 0.01
        
        return False
    
    async def _trigger_alert(self, rule: AlertRule, container_id: str, latest_metric):
        """Déclenche une nouvelle alerte"""
        try:
            # Génère un ID unique pour l'alerte
            alert_id = f"{rule.rule_id}:{container_id}:{int(datetime.utcnow().timestamp())}"
            
            # Vérifie si l'alerte est supprimée
            if self._is_alert_suppressed(rule, container_id):
                logger.debug(f"Alerte supprimée pour {container_id}")
                return
            
            # Vérifie s'il y a déjà une alerte active pour cette combinaison
            existing_key = f"{rule.rule_id}:{container_id}"
            if any(alert.alert_id.startswith(existing_key) for alert in self.active_alerts.values()):
                logger.debug(f"Alerte déjà active pour {rule.rule_id}:{container_id}")
                return
            
            # Crée l'instance d'alerte
            current_value = self._extract_metric_value(latest_metric, rule.metric_type)
            
            alert = AlertInstance(
                alert_id=alert_id,
                rule_id=rule.rule_id,
                rule_name=rule.name,
                container_id=container_id,
                container_name=latest_metric.container_name,
                service_name=latest_metric.service_name,
                metric_type=rule.metric_type,
                current_value=current_value,
                threshold_value=rule.threshold_value,
                severity=rule.severity
            )
            
            # Détermine la clé de regroupement
            if rule.grouping_keys:
                alert.group_key = self._generate_group_key(alert, rule.grouping_keys)
            
            # Stocke l'alerte
            self.active_alerts[alert_id] = alert
            
            # Envoie les notifications
            await self._send_alert_notifications(alert, rule)
            
            # Active la suppression si configurée
            if rule.suppression_enabled:
                suppression_key = f"{rule.rule_id}:{container_id}"
                self.suppression_cache[suppression_key] = \
                    datetime.utcnow() + timedelta(minutes=rule.suppression_duration_minutes)
            
            # Sauvegarde l'alerte
            await self._save_alert(alert)
            
            logger.info(f"Alerte déclenchée: {alert.rule_name} pour {alert.container_name}")
            
        except Exception as e:
            logger.error(f"Erreur lors du déclenchement de l'alerte: {e}")
    
    def _is_alert_suppressed(self, rule: AlertRule, container_id: str) -> bool:
        """Vérifie si une alerte est supprimée"""
        if not rule.suppression_enabled:
            return False
        
        suppression_key = f"{rule.rule_id}:{container_id}"
        suppression_until = self.suppression_cache.get(suppression_key)
        
        if suppression_until and datetime.utcnow() < suppression_until:
            return True
        
        # Nettoie les suppressions expirées
        if suppression_until and datetime.utcnow() >= suppression_until:
            del self.suppression_cache[suppression_key]
        
        return False
    
    def _generate_group_key(self, alert: AlertInstance, grouping_keys: List[str]) -> str:
        """Génère une clé de regroupement pour l'alerte"""
        key_parts = []
        
        for key in grouping_keys:
            if key == 'service_name':
                key_parts.append(alert.service_name or 'unknown')
            elif key == 'metric_type':
                key_parts.append(alert.metric_type)
            elif key == 'severity':
                key_parts.append(alert.severity.value)
            elif key == 'rule_id':
                key_parts.append(alert.rule_id)
        
        return ':'.join(key_parts)
    
    async def _send_alert_notifications(self, alert: AlertInstance, rule: AlertRule):
        """Envoie les notifications pour une alerte"""
        for target_id in rule.notification_targets:
            target = self.notification_targets.get(target_id)
            if not target or not target.enabled:
                continue
            
            try:
                success = await self._send_notification(alert, target)
                
                # Enregistre dans l'historique
                alert.notifications_sent.append({
                    'target_id': target_id,
                    'channel': target.channel.value,
                    'sent_at': datetime.utcnow().isoformat(),
                    'success': success
                })
                
                if success:
                    alert.last_notification_at = datetime.utcnow()
                
            except Exception as e:
                logger.error(f"Erreur envoi notification {target.name}: {e}")
                alert.notifications_sent.append({
                    'target_id': target_id,
                    'channel': target.channel.value,
                    'sent_at': datetime.utcnow().isoformat(),
                    'success': False,
                    'error': str(e)
                })
    
    async def _send_notification(self, alert: AlertInstance, target: NotificationTarget) -> bool:
        """Envoie une notification via un canal spécifique"""
        try:
            if target.channel == NotificationChannel.EMAIL:
                return await self._send_email_notification(alert, target)
            elif target.channel == NotificationChannel.WEBHOOK:
                return await self._send_webhook_notification(alert, target)
            elif target.channel == NotificationChannel.SLACK:
                return await self._send_slack_notification(alert, target)
            elif target.channel == NotificationChannel.DISCORD:
                return await self._send_discord_notification(alert, target)
            elif target.channel == NotificationChannel.TEAMS:
                return await self._send_teams_notification(alert, target)
            elif target.channel == NotificationChannel.TELEGRAM:
                return await self._send_telegram_notification(alert, target)
            else:
                logger.warning(f"Canal de notification non supporté: {target.channel}")
                return False
                
        except Exception as e:
            logger.error(f"Erreur envoi notification {target.channel.value}: {e}")
            return False
    
    async def _send_email_notification(self, alert: AlertInstance, target: NotificationTarget) -> bool:
        """Envoie une notification par email"""
        try:
            # Prépare le contenu du message
            subject = self._render_template('email_subject', alert)
            body = self._render_template('email_body', alert)
            
            # Configuration SMTP
            smtp_config = self.settings.notifications.email
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = formataddr((smtp_config.sender_name, smtp_config.sender_email))
            msg['To'] = target.email_address
            
            # Ajoute le contenu HTML
            html_part = MIMEText(body, 'html')
            msg.attach(html_part)
            
            # Envoie l'email
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_config.smtp_server, smtp_config.smtp_port, context=context) as server:
                server.login(smtp_config.username, smtp_config.password)
                server.send_message(msg)
            
            logger.info(f"Email envoyé à {target.email_address} pour alerte {alert.alert_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur envoi email: {e}")
            return False
    
    async def _send_webhook_notification(self, alert: AlertInstance, target: NotificationTarget) -> bool:
        """Envoie une notification via webhook"""
        try:
            payload = {
                'alert_id': alert.alert_id,
                'rule_name': alert.rule_name,
                'severity': alert.severity.value,
                'container_name': alert.container_name,
                'container_id': alert.container_id,
                'service_name': alert.service_name,
                'metric_type': alert.metric_type,
                'current_value': alert.current_value,
                'threshold_value': alert.threshold_value,
                'triggered_at': alert.triggered_at.isoformat(),
                'state': alert.state.value
            }
            
            headers = {'Content-Type': 'application/json'}
            if target.webhook_headers:
                headers.update(target.webhook_headers)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    target.webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    success = response.status < 400
                    if not success:
                        logger.warning(f"Webhook responded with status {response.status}")
                    return success
                    
        except Exception as e:
            logger.error(f"Erreur envoi webhook: {e}")
            return False
    
    async def _send_slack_notification(self, alert: AlertInstance, target: NotificationTarget) -> bool:
        """Envoie une notification Slack"""
        try:
            message = self._render_template('slack_message', alert)
            
            # Determine emoji based on severity
            emoji_map = {
                AlertSeverity.LOW: ':information_source:',
                AlertSeverity.MEDIUM: ':warning:',
                AlertSeverity.HIGH: ':exclamation:',
                AlertSeverity.CRITICAL: ':rotating_light:'
            }
            
            payload = {
                'text': f"{emoji_map.get(alert.severity, ':warning:')} WakeDock Alert",
                'attachments': [{
                    'color': self._get_severity_color(alert.severity),
                    'title': alert.rule_name,
                    'text': message,
                    'footer': 'WakeDock Monitoring',
                    'ts': int(alert.triggered_at.timestamp())
                }]
            }
            
            if target.slack_channel:
                payload['channel'] = target.slack_channel
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    target.slack_webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    return response.status < 400
                    
        except Exception as e:
            logger.error(f"Erreur envoi Slack: {e}")
            return False
    
    async def _send_discord_notification(self, alert: AlertInstance, target: NotificationTarget) -> bool:
        """Envoie une notification Discord"""
        try:
            embed = {
                'title': f'🚨 {alert.rule_name}',
                'description': f'Alerte déclenchée pour le conteneur **{alert.container_name}**',
                'color': int(self._get_severity_color(alert.severity)[1:], 16),  # Convertit hex en int
                'fields': [
                    {'name': 'Sévérité', 'value': alert.severity.value.upper(), 'inline': True},
                    {'name': 'Conteneur', 'value': f'{alert.container_name}\n`{alert.container_id[:12]}`', 'inline': True},
                    {'name': 'Métrique', 'value': alert.metric_type, 'inline': True},
                    {'name': 'Valeur actuelle', 'value': str(alert.current_value), 'inline': True},
                    {'name': 'Seuil', 'value': str(alert.threshold_value), 'inline': True},
                ],
                'timestamp': alert.triggered_at.isoformat(),
                'footer': {'text': 'WakeDock Monitoring'}
            }
            
            if alert.service_name:
                embed['fields'].insert(2, {'name': 'Service', 'value': alert.service_name, 'inline': True})
            
            payload = {'embeds': [embed]}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    target.discord_webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    return response.status < 400
                    
        except Exception as e:
            logger.error(f"Erreur envoi Discord: {e}")
            return False
    
    async def _send_teams_notification(self, alert: AlertInstance, target: NotificationTarget) -> bool:
        """Envoie une notification Microsoft Teams"""
        try:
            # Format de carte adaptative pour Teams
            card = {
                '@type': 'MessageCard',
                '@context': 'http://schema.org/extensions',
                'themeColor': self._get_severity_color(alert.severity),
                'summary': f'WakeDock Alert: {alert.rule_name}',
                'sections': [{
                    'activityTitle': f'🚨 {alert.rule_name}',
                    'activitySubtitle': f'Severity: {alert.severity.value.upper()}',
                    'facts': [
                        {'name': 'Container', 'value': f'{alert.container_name} ({alert.container_id[:12]})'},
                        {'name': 'Metric', 'value': alert.metric_type},
                        {'name': 'Current Value', 'value': str(alert.current_value)},
                        {'name': 'Threshold', 'value': str(alert.threshold_value)},
                        {'name': 'Triggered At', 'value': alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
                    ]
                }]
            }
            
            if alert.service_name:
                card['sections'][0]['facts'].insert(1, {'name': 'Service', 'value': alert.service_name})
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    target.teams_webhook_url,
                    json=card,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    return response.status < 400
                    
        except Exception as e:
            logger.error(f"Erreur envoi Teams: {e}")
            return False
    
    async def _send_telegram_notification(self, alert: AlertInstance, target: NotificationTarget) -> bool:
        """Envoie une notification Telegram"""
        try:
            emoji_map = {
                AlertSeverity.LOW: 'ℹ️',
                AlertSeverity.MEDIUM: '⚠️',
                AlertSeverity.HIGH: '❗',
                AlertSeverity.CRITICAL: '🚨'
            }
            
            message = f"""
{emoji_map.get(alert.severity, '⚠️')} *WakeDock Alert*

*Règle:* {alert.rule_name}
*Sévérité:* {alert.severity.value.upper()}
*Conteneur:* {alert.container_name} (`{alert.container_id[:12]}`)
{f"*Service:* {alert.service_name}" if alert.service_name else ""}
*Métrique:* {alert.metric_type}
*Valeur:* {alert.current_value} (seuil: {alert.threshold_value})
*Heure:* {alert.triggered_at.strftime('%Y-%m-%d %H:%M:%S UTC')}
            """.strip()
            
            url = f"https://api.telegram.org/bot{target.telegram_bot_token}/sendMessage"
            payload = {
                'chat_id': target.telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    return response.status < 400
                    
        except Exception as e:
            logger.error(f"Erreur envoi Telegram: {e}")
            return False
    
    def _render_template(self, template_name: str, alert: AlertInstance) -> str:
        """Rend un template de message"""
        template_str = self.message_templates.get(template_name, '')
        template = Template(template_str)
        
        # Détermine l'unité basée sur le type de métrique
        unit = ''
        if 'percent' in alert.metric_type:
            unit = '%'
        elif 'bytes' in alert.metric_type:
            unit = ' bytes'
        
        return template.render(
            alert=alert,
            unit=unit,
            severity_color=self._get_severity_color(alert.severity)
        )
    
    def _get_severity_color(self, severity: AlertSeverity) -> str:
        """Retourne la couleur associée à une sévérité"""
        color_map = {
            AlertSeverity.LOW: '#36a2eb',      # Bleu
            AlertSeverity.MEDIUM: '#ffcd56',   # Jaune
            AlertSeverity.HIGH: '#ff6384',     # Orange/Rouge clair
            AlertSeverity.CRITICAL: '#dc2626'  # Rouge foncé
        }
        return color_map.get(severity, '#6b7280')  # Gris par défaut
    
    async def _check_alert_resolution(self, rule: AlertRule, container_id: str, latest_metric):
        """Vérifie si une alerte active doit être résolue"""
        # Trouve les alertes actives pour cette règle et ce conteneur
        alerts_to_resolve = [
            alert for alert in self.active_alerts.values()
            if (alert.rule_id == rule.rule_id and 
                alert.container_id == container_id and 
                alert.state == AlertState.ACTIVE)
        ]
        
        for alert in alerts_to_resolve:
            current_value = self._extract_metric_value(latest_metric, rule.metric_type)
            
            # Vérifie si la valeur est maintenant dans les limites
            if current_value is not None:
                if not self._compare_values(current_value, rule.threshold_value, rule.comparison_operator):
                    await self._resolve_alert(alert)
    
    async def _resolve_alert(self, alert: AlertInstance):
        """Résout une alerte"""
        try:
            alert.state = AlertState.RESOLVED
            alert.resolved_at = datetime.utcnow()
            
            # Supprime de la liste des alertes actives
            if alert.alert_id in self.active_alerts:
                del self.active_alerts[alert.alert_id]
            
            # Sauvegarde l'alerte résolue
            await self._save_alert(alert)
            
            logger.info(f"Alerte résolue: {alert.rule_name} pour {alert.container_name}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la résolution de l'alerte: {e}")
    
    async def _should_escalate_alert(self, alert: AlertInstance, current_time: datetime) -> bool:
        """Vérifie si une alerte doit être escaladée"""
        # Récupère la règle
        rule = self.alert_rules.get(alert.rule_id)
        if not rule or not rule.escalation_enabled:
            return False
        
        # Vérifie si l'alerte est déjà au niveau max d'escalade
        if alert.escalation_level == EscalationLevel.LEVEL_3:
            return False
        
        # Vérifie si assez de temps s'est écoulé depuis le déclenchement ou la dernière escalade
        time_since_trigger = current_time - alert.triggered_at
        time_since_escalation = current_time - (alert.escalated_at or alert.triggered_at)
        
        escalation_delay = timedelta(minutes=rule.escalation_delay_minutes)
        
        return (time_since_trigger >= escalation_delay and 
                time_since_escalation >= escalation_delay and
                alert.state == AlertState.ACTIVE)
    
    async def _escalate_alert(self, alert: AlertInstance):
        """Escalade une alerte au niveau suivant"""
        try:
            # Détermine le niveau suivant
            next_level = None
            if alert.escalation_level == EscalationLevel.LEVEL_1:
                next_level = EscalationLevel.LEVEL_2
            elif alert.escalation_level == EscalationLevel.LEVEL_2:
                next_level = EscalationLevel.LEVEL_3
            
            if not next_level:
                return
            
            alert.escalation_level = next_level
            alert.escalated_at = datetime.utcnow()
            
            # Récupère la règle pour les cibles d'escalade
            rule = self.alert_rules.get(alert.rule_id)
            if rule and rule.escalation_targets and next_level in rule.escalation_targets:
                # Envoie les notifications aux cibles d'escalade
                escalation_targets = rule.escalation_targets[next_level]
                for target_id in escalation_targets:
                    target = self.notification_targets.get(target_id)
                    if target and target.enabled:
                        await self._send_notification(alert, target)
            
            logger.info(f"Alerte escaladée au niveau {next_level.value}: {alert.rule_name}")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'escalade de l'alerte: {e}")
    
    async def _cleanup_old_alerts(self):
        """Nettoie les vieilles alertes résolues"""
        cutoff_time = datetime.utcnow() - timedelta(days=7)  # Garde 7 jours d'historique
        
        alerts_to_remove = [
            alert_id for alert_id, alert in self.active_alerts.items()
            if (alert.state in [AlertState.RESOLVED, AlertState.SUPPRESSED] and
                (alert.resolved_at or alert.triggered_at) < cutoff_time)
        ]
        
        for alert_id in alerts_to_remove:
            del self.active_alerts[alert_id]
    
    # Méthodes de gestion des règles et cibles
    
    async def add_alert_rule(self, rule: AlertRule) -> bool:
        """Ajoute une nouvelle règle d'alerte"""
        try:
            rule.updated_at = datetime.utcnow()
            self.alert_rules[rule.rule_id] = rule
            await self._save_configuration()
            logger.info(f"Règle d'alerte ajoutée: {rule.name}")
            return True
        except Exception as e:
            logger.error(f"Erreur ajout règle d'alerte: {e}")
            return False
    
    async def update_alert_rule(self, rule: AlertRule) -> bool:
        """Met à jour une règle d'alerte existante"""
        try:
            if rule.rule_id not in self.alert_rules:
                return False
            
            rule.updated_at = datetime.utcnow()
            self.alert_rules[rule.rule_id] = rule
            await self._save_configuration()
            logger.info(f"Règle d'alerte mise à jour: {rule.name}")
            return True
        except Exception as e:
            logger.error(f"Erreur mise à jour règle d'alerte: {e}")
            return False
    
    async def delete_alert_rule(self, rule_id: str) -> bool:
        """Supprime une règle d'alerte"""
        try:
            if rule_id not in self.alert_rules:
                return False
            
            del self.alert_rules[rule_id]
            await self._save_configuration()
            logger.info(f"Règle d'alerte supprimée: {rule_id}")
            return True
        except Exception as e:
            logger.error(f"Erreur suppression règle d'alerte: {e}")
            return False
    
    async def add_notification_target(self, target: NotificationTarget) -> bool:
        """Ajoute une nouvelle cible de notification"""
        try:
            target_id = f"{target.channel.value}_{target.name.lower().replace(' ', '_')}"
            self.notification_targets[target_id] = target
            await self._save_configuration()
            logger.info(f"Cible de notification ajoutée: {target.name}")
            return True
        except Exception as e:
            logger.error(f"Erreur ajout cible notification: {e}")
            return False
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Acquitte une alerte"""
        try:
            alert = self.active_alerts.get(alert_id)
            if not alert:
                return False
            
            alert.state = AlertState.ACKNOWLEDGED
            alert.acknowledged_at = datetime.utcnow()
            alert.acknowledged_by = acknowledged_by
            
            await self._save_alert(alert)
            logger.info(f"Alerte acquittée: {alert_id} par {acknowledged_by}")
            return True
        except Exception as e:
            logger.error(f"Erreur acquittement alerte: {e}")
            return False
    
    # Méthodes de stockage
    
    async def _save_configuration(self):
        """Sauvegarde la configuration des règles et cibles"""
        try:
            config = {
                'alert_rules': {
                    rule_id: rule.to_dict() for rule_id, rule in self.alert_rules.items()
                },
                'notification_targets': {
                    target_id: target.to_dict() for target_id, target in self.notification_targets.items()
                },
                'saved_at': datetime.utcnow().isoformat()
            }
            
            config_file = self.storage_path / 'alerts_config.json'
            async with aiofiles.open(config_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(config, indent=2))
                
        except Exception as e:
            logger.error(f"Erreur sauvegarde configuration alertes: {e}")
    
    async def _load_configuration(self):
        """Charge la configuration depuis le stockage"""
        try:
            config_file = self.storage_path / 'alerts_config.json'
            if not config_file.exists():
                return
            
            async with aiofiles.open(config_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                config = json.loads(content)
            
            # Charge les règles d'alertes
            for rule_id, rule_data in config.get('alert_rules', {}).items():
                rule_data['severity'] = AlertSeverity(rule_data['severity'])
                if rule_data.get('created_at'):
                    rule_data['created_at'] = datetime.fromisoformat(rule_data['created_at'])
                if rule_data.get('updated_at'):
                    rule_data['updated_at'] = datetime.fromisoformat(rule_data['updated_at'])
                
                # Reconstruit les escalation_targets
                if rule_data.get('escalation_targets'):
                    escalation_targets = {}
                    for level_str, targets in rule_data['escalation_targets'].items():
                        escalation_targets[EscalationLevel(level_str)] = targets
                    rule_data['escalation_targets'] = escalation_targets
                
                rule = AlertRule(**rule_data)
                self.alert_rules[rule_id] = rule
            
            # Charge les cibles de notification
            for target_id, target_data in config.get('notification_targets', {}).items():
                target_data['channel'] = NotificationChannel(target_data['channel'])
                target = NotificationTarget(**target_data)
                self.notification_targets[target_id] = target
            
            logger.info(f"Configuration alertes chargée: {len(self.alert_rules)} règles, {len(self.notification_targets)} cibles")
            
        except Exception as e:
            logger.error(f"Erreur chargement configuration alertes: {e}")
    
    async def _save_alert(self, alert: AlertInstance):
        """Sauvegarde une alerte dans l'historique"""
        try:
            date_str = datetime.utcnow().strftime('%Y-%m-%d')
            alerts_file = self.storage_path / f'alerts_history_{date_str}.jsonl'
            
            async with aiofiles.open(alerts_file, 'a', encoding='utf-8') as f:
                await f.write(json.dumps(alert.to_dict()) + '\n')
                
        except Exception as e:
            logger.error(f"Erreur sauvegarde alerte: {e}")
    
    # Méthodes d'accès aux données
    
    def get_active_alerts(self) -> List[AlertInstance]:
        """Retourne toutes les alertes actives"""
        return list(self.active_alerts.values())
    
    def get_alert_rules(self) -> List[AlertRule]:
        """Retourne toutes les règles d'alertes"""
        return list(self.alert_rules.values())
    
    def get_notification_targets(self) -> List[NotificationTarget]:
        """Retourne toutes les cibles de notification"""
        return list(self.notification_targets.values())
    
    async def get_alerts_history(self, days: int = 7) -> List[AlertInstance]:
        """Récupère l'historique des alertes"""
        alerts = []
        
        for day_offset in range(days):
            date = datetime.utcnow() - timedelta(days=day_offset)
            date_str = date.strftime('%Y-%m-%d')
            alerts_file = self.storage_path / f'alerts_history_{date_str}.jsonl'
            
            if not alerts_file.exists():
                continue
            
            try:
                async with aiofiles.open(alerts_file, 'r', encoding='utf-8') as f:
                    async for line in f:
                        try:
                            data = json.loads(line.strip())
                            
                            # Reconstruit l'objet AlertInstance
                            data['state'] = AlertState(data['state'])
                            data['severity'] = AlertSeverity(data['severity'])
                            data['escalation_level'] = EscalationLevel(data['escalation_level'])
                            
                            # Convertit les dates
                            for field in ['triggered_at', 'acknowledged_at', 'resolved_at', 'escalated_at', 'last_notification_at']:
                                if data.get(field):
                                    data[field] = datetime.fromisoformat(data[field])
                            
                            alert = AlertInstance(**data)
                            alerts.append(alert)
                            
                        except Exception as e:
                            logger.warning(f"Ligne d'alerte invalide ignorée: {e}")
                            
            except Exception as e:
                logger.error(f"Erreur lecture historique alertes: {e}")
        
        return sorted(alerts, key=lambda a: a.triggered_at, reverse=True)
    
    def get_service_stats(self) -> Dict:
        """Retourne les statistiques du service d'alertes"""
        return {
            'is_running': self.is_running,
            'active_alerts_count': len(self.active_alerts),
            'alert_rules_count': len(self.alert_rules),
            'notification_targets_count': len(self.notification_targets),
            'suppressed_alerts_count': len(self.suppression_cache),
            'metrics_history_containers': len(self.metrics_history),
            'storage_path': str(self.storage_path)
        }
