"""
Tests pour le système d'alertes et notifications
"""
import pytest
import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from wakedock.core.alerts_service import (
    AlertsService, AlertRule, NotificationTarget, AlertInstance,
    NotificationChannel, AlertSeverity, EscalationLevel, AlertState
)
from wakedock.core.metrics_collector import MetricsCollector, ContainerMetric

class TestAlertsService:
    """Tests pour le service d'alertes"""
    
    @pytest.fixture
    async def mock_metrics_collector(self):
        """Mock du collecteur de métriques"""
        collector = Mock(spec=MetricsCollector)
        collector.get_recent_metrics = AsyncMock(return_value=[])
        return collector
    
    @pytest.fixture
    async def temp_storage(self):
        """Répertoire temporaire pour les tests"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    async def alerts_service(self, mock_metrics_collector, temp_storage):
        """Service d'alertes pour les tests"""
        service = AlertsService(
            metrics_collector=mock_metrics_collector,
            storage_path=temp_storage
        )
        yield service
        
        # Cleanup
        if service.is_running:
            await service.stop()
    
    @pytest.mark.asyncio
    async def test_service_start_stop(self, alerts_service):
        """Test démarrage et arrêt du service"""
        assert not alerts_service.is_running
        
        await alerts_service.start()
        assert alerts_service.is_running
        assert alerts_service.monitoring_task is not None
        assert alerts_service.escalation_task is not None
        
        await alerts_service.stop()
        assert not alerts_service.is_running
    
    @pytest.mark.asyncio
    async def test_add_alert_rule(self, alerts_service):
        """Test ajout d'une règle d'alerte"""
        rule = AlertRule(
            rule_id="test_rule_1",
            name="Test High CPU",
            description="Test rule for high CPU usage",
            metric_type="cpu_percent",
            threshold_value=80.0,
            comparison_operator=">",
            duration_minutes=5,
            severity=AlertSeverity.HIGH,
            notification_targets=[]
        )
        
        success = await alerts_service.add_alert_rule(rule)
        assert success
        assert rule.rule_id in alerts_service.alert_rules
        assert alerts_service.alert_rules[rule.rule_id].name == "Test High CPU"
    
    @pytest.mark.asyncio
    async def test_add_notification_target(self, alerts_service):
        """Test ajout d'une cible de notification"""
        target = NotificationTarget(
            channel=NotificationChannel.EMAIL,
            name="Test Email",
            enabled=True,
            email_address="test@example.com"
        )
        
        success = await alerts_service.add_notification_target(target)
        assert success
        
        # Vérifie que la cible a été ajoutée
        target_id = f"{target.channel.value}_{target.name.lower().replace(' ', '_')}"
        assert target_id in alerts_service.notification_targets
    
    def test_extract_metric_value(self, alerts_service):
        """Test extraction de valeur de métrique"""
        metric = Mock()
        metric.cpu_percent = 75.5
        metric.memory_percent = 60.2
        metric.memory_usage_bytes = 1024 * 1024 * 512  # 512MB
        metric.network_rx_bytes = 1000
        metric.network_tx_bytes = 2000
        
        assert alerts_service._extract_metric_value(metric, "cpu_percent") == 75.5
        assert alerts_service._extract_metric_value(metric, "memory_percent") == 60.2
        assert alerts_service._extract_metric_value(metric, "memory_usage_bytes") == 1024 * 1024 * 512
        assert alerts_service._extract_metric_value(metric, "network_total_bytes") == 3000
        assert alerts_service._extract_metric_value(metric, "unknown_metric") is None
    
    def test_compare_values(self, alerts_service):
        """Test comparaison de valeurs"""
        assert alerts_service._compare_values(85.0, 80.0, ">") == True
        assert alerts_service._compare_values(75.0, 80.0, ">") == False
        assert alerts_service._compare_values(75.0, 80.0, "<") == True
        assert alerts_service._compare_values(85.0, 80.0, "<") == False
        assert alerts_service._compare_values(80.0, 80.0, ">=") == True
        assert alerts_service._compare_values(79.0, 80.0, ">=") == False
        assert alerts_service._compare_values(80.0, 80.0, "<=") == True
        assert alerts_service._compare_values(81.0, 80.0, "<=") == False
        assert alerts_service._compare_values(80.0, 80.0, "==") == True
        assert alerts_service._compare_values(80.1, 80.0, "==") == False
        assert alerts_service._compare_values(80.1, 80.0, "!=") == True
        assert alerts_service._compare_values(80.0, 80.0, "!=") == False
    
    def test_matches_container_filters(self, alerts_service):
        """Test correspondance des filtres de conteneur"""
        metric = Mock()
        metric.container_name = "web-server-1"
        metric.service_name = "web"
        metric.container_id = "abc123def456"
        
        # Test filtre par nom
        assert alerts_service._matches_container_filters(metric, {"name": "web-server"}) == True
        assert alerts_service._matches_container_filters(metric, {"name": "database"}) == False
        
        # Test filtre par service
        assert alerts_service._matches_container_filters(metric, {"service": "web"}) == True
        assert alerts_service._matches_container_filters(metric, {"service": "db"}) == False
        
        # Test filtre par ID
        assert alerts_service._matches_container_filters(metric, {"id": "abc123"}) == True
        assert alerts_service._matches_container_filters(metric, {"id": "xyz789"}) == False
        
        # Test filtres multiples
        filters = {"name": "web", "service": "web"}
        assert alerts_service._matches_container_filters(metric, filters) == True
        
        filters = {"name": "web", "service": "db"}
        assert alerts_service._matches_container_filters(metric, filters) == False
    
    def test_generate_group_key(self, alerts_service):
        """Test génération de clé de regroupement"""
        alert = AlertInstance(
            alert_id="test_alert",
            rule_id="test_rule",
            rule_name="Test Rule",
            container_id="container_123",
            container_name="test-container",
            service_name="test-service",
            metric_type="cpu_percent",
            current_value=85.0,
            threshold_value=80.0,
            severity=AlertSeverity.HIGH
        )
        
        # Test avec différentes clés de regroupement
        key = alerts_service._generate_group_key(alert, ["service_name", "metric_type"])
        assert key == "test-service:cpu_percent"
        
        key = alerts_service._generate_group_key(alert, ["severity", "rule_id"])
        assert key == "high:test_rule"
    
    def test_is_alert_suppressed(self, alerts_service):
        """Test suppression d'alertes"""
        rule = AlertRule(
            rule_id="test_rule",
            name="Test Rule",
            description="Test",
            metric_type="cpu_percent",
            threshold_value=80.0,
            comparison_operator=">",
            suppression_enabled=True,
            suppression_duration_minutes=60
        )
        
        container_id = "container_123"
        
        # Initialement pas supprimée
        assert not alerts_service._is_alert_suppressed(rule, container_id)
        
        # Ajoute une suppression
        suppression_key = f"{rule.rule_id}:{container_id}"
        alerts_service.suppression_cache[suppression_key] = \
            datetime.utcnow() + timedelta(minutes=30)
        
        # Maintenant supprimée
        assert alerts_service._is_alert_suppressed(rule, container_id)
        
        # Test avec suppression expirée
        alerts_service.suppression_cache[suppression_key] = \
            datetime.utcnow() - timedelta(minutes=30)
        
        # Plus supprimée et cache nettoyé
        assert not alerts_service._is_alert_suppressed(rule, container_id)
        assert suppression_key not in alerts_service.suppression_cache
    
    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, alerts_service):
        """Test acquittement d'alerte"""
        alert = AlertInstance(
            alert_id="test_alert",
            rule_id="test_rule",
            rule_name="Test Rule",
            container_id="container_123",
            container_name="test-container",
            service_name="test-service",
            metric_type="cpu_percent",
            current_value=85.0,
            threshold_value=80.0,
            severity=AlertSeverity.HIGH
        )
        
        alerts_service.active_alerts[alert.alert_id] = alert
        
        success = await alerts_service.acknowledge_alert(alert.alert_id, "test_user")
        assert success
        assert alert.state == AlertState.ACKNOWLEDGED
        assert alert.acknowledged_by == "test_user"
        assert alert.acknowledged_at is not None
    
    @pytest.mark.asyncio
    async def test_configuration_save_load(self, alerts_service, temp_storage):
        """Test sauvegarde et chargement de configuration"""
        # Ajoute une règle et une cible
        rule = AlertRule(
            rule_id="test_rule",
            name="Test Rule",
            description="Test",
            metric_type="cpu_percent",
            threshold_value=80.0,
            comparison_operator=">"
        )
        
        target = NotificationTarget(
            channel=NotificationChannel.EMAIL,
            name="Test Email",
            email_address="test@example.com"
        )
        
        await alerts_service.add_alert_rule(rule)
        await alerts_service.add_notification_target(target)
        
        # Sauvegarde
        await alerts_service._save_configuration()
        
        # Vérifie que le fichier existe
        config_file = Path(temp_storage) / "alerts_config.json"
        assert config_file.exists()
        
        # Crée un nouveau service et charge la configuration
        new_service = AlertsService(
            metrics_collector=Mock(),
            storage_path=temp_storage
        )
        
        await new_service._load_configuration()
        
        # Vérifie que la configuration a été chargée
        assert rule.rule_id in new_service.alert_rules
        assert new_service.alert_rules[rule.rule_id].name == "Test Rule"
        
        target_id = f"{target.channel.value}_{target.name.lower().replace(' ', '_')}"
        assert target_id in new_service.notification_targets
        assert new_service.notification_targets[target_id].email_address == "test@example.com"

class TestNotificationChannels:
    """Tests pour les canaux de notification"""
    
    @pytest.fixture
    def alert_instance(self):
        """Instance d'alerte pour les tests"""
        return AlertInstance(
            alert_id="test_alert",
            rule_id="test_rule",
            rule_name="Test Alert",
            container_id="container_123",
            container_name="test-container",
            service_name="test-service",
            metric_type="cpu_percent",
            current_value=85.0,
            threshold_value=80.0,
            severity=AlertSeverity.HIGH
        )
    
    @pytest.fixture
    async def alerts_service(self):
        """Service d'alertes pour les tests de notification"""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AlertsService(
                metrics_collector=Mock(),
                storage_path=temp_dir
            )
            yield service
    
    def test_render_template(self, alerts_service, alert_instance):
        """Test rendu des templates de message"""
        # Test template email subject
        subject = alerts_service._render_template('email_subject', alert_instance)
        assert "Test Alert" in subject
        assert "HIGH" in subject
        
        # Test template email body
        body = alerts_service._render_template('email_body', alert_instance)
        assert "Test Alert" in body
        assert "test-container" in body
        assert "85.0" in body
        assert "80.0" in body
    
    def test_get_severity_color(self, alerts_service):
        """Test couleurs de sévérité"""
        assert alerts_service._get_severity_color(AlertSeverity.LOW) == '#36a2eb'
        assert alerts_service._get_severity_color(AlertSeverity.MEDIUM) == '#ffcd56'
        assert alerts_service._get_severity_color(AlertSeverity.HIGH) == '#ff6384'
        assert alerts_service._get_severity_color(AlertSeverity.CRITICAL) == '#dc2626'
    
    @pytest.mark.asyncio
    async def test_send_webhook_notification(self, alerts_service, alert_instance):
        """Test notification webhook"""
        target = NotificationTarget(
            channel=NotificationChannel.WEBHOOK,
            name="Test Webhook",
            webhook_url="https://example.com/webhook",
            webhook_headers={"Authorization": "Bearer token123"}
        )
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
            
            success = await alerts_service._send_webhook_notification(alert_instance, target)
            assert success
    
    @pytest.mark.asyncio
    async def test_send_slack_notification(self, alerts_service, alert_instance):
        """Test notification Slack"""
        target = NotificationTarget(
            channel=NotificationChannel.SLACK,
            name="Test Slack",
            slack_webhook_url="https://hooks.slack.com/services/test",
            slack_channel="#alerts"
        )
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_response
            
            success = await alerts_service._send_slack_notification(alert_instance, target)
            assert success

class TestAlertEscalation:
    """Tests pour l'escalade d'alertes"""
    
    @pytest.fixture
    async def alerts_service_with_escalation(self):
        """Service d'alertes configuré pour l'escalade"""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AlertsService(
                metrics_collector=Mock(),
                storage_path=temp_dir
            )
            
            # Ajoute une règle avec escalade
            rule = AlertRule(
                rule_id="escalation_rule",
                name="Escalation Test",
                description="Test escalation",
                metric_type="cpu_percent",
                threshold_value=90.0,
                comparison_operator=">",
                escalation_enabled=True,
                escalation_delay_minutes=5,
                escalation_targets={
                    EscalationLevel.LEVEL_1: ["email_admin"],
                    EscalationLevel.LEVEL_2: ["slack_devops"],
                    EscalationLevel.LEVEL_3: ["email_cto"]
                }
            )
            
            await service.add_alert_rule(rule)
            yield service
    
    @pytest.mark.asyncio
    async def test_should_escalate_alert(self, alerts_service_with_escalation):
        """Test détection d'escalade nécessaire"""
        # Crée une alerte ancienne
        alert = AlertInstance(
            alert_id="escalation_test",
            rule_id="escalation_rule",
            rule_name="Escalation Test",
            container_id="container_123",
            container_name="test-container",
            metric_type="cpu_percent",
            current_value=95.0,
            threshold_value=90.0,
            severity=AlertSeverity.CRITICAL,
            triggered_at=datetime.utcnow() - timedelta(minutes=10)  # 10 minutes ago
        )
        
        current_time = datetime.utcnow()
        
        # Devrait escalader (alerte ancienne de 10 min, délai de 5 min)
        should_escalate = await alerts_service_with_escalation._should_escalate_alert(alert, current_time)
        assert should_escalate
        
        # Test avec alerte récente
        alert.triggered_at = datetime.utcnow() - timedelta(minutes=2)  # 2 minutes ago
        should_escalate = await alerts_service_with_escalation._should_escalate_alert(alert, current_time)
        assert not should_escalate
        
        # Test avec alerte déjà au niveau max
        alert.escalation_level = EscalationLevel.LEVEL_3
        alert.triggered_at = datetime.utcnow() - timedelta(minutes=10)
        should_escalate = await alerts_service_with_escalation._should_escalate_alert(alert, current_time)
        assert not should_escalate
    
    @pytest.mark.asyncio
    async def test_escalate_alert(self, alerts_service_with_escalation):
        """Test escalade d'alerte"""
        alert = AlertInstance(
            alert_id="escalation_test",
            rule_id="escalation_rule",
            rule_name="Escalation Test",
            container_id="container_123",
            container_name="test-container",
            metric_type="cpu_percent",
            current_value=95.0,
            threshold_value=90.0,
            severity=AlertSeverity.CRITICAL,
            escalation_level=EscalationLevel.LEVEL_1
        )
        
        # Mock de la méthode d'envoi de notification
        alerts_service_with_escalation._send_notification = AsyncMock(return_value=True)
        
        await alerts_service_with_escalation._escalate_alert(alert)
        
        # Vérifie l'escalade au niveau 2
        assert alert.escalation_level == EscalationLevel.LEVEL_2
        assert alert.escalated_at is not None
        
        # Escalade au niveau 3
        await alerts_service_with_escalation._escalate_alert(alert)
        assert alert.escalation_level == EscalationLevel.LEVEL_3
        
        # Tentative d'escalade au-delà du niveau max
        original_level = alert.escalation_level
        await alerts_service_with_escalation._escalate_alert(alert)
        assert alert.escalation_level == original_level  # Pas de changement

class TestAlertMetrics:
    """Tests pour les métriques d'alertes"""
    
    @pytest.mark.asyncio
    async def test_get_service_stats(self):
        """Test statistiques du service"""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AlertsService(
                metrics_collector=Mock(),
                storage_path=temp_dir
            )
            
            stats = service.get_service_stats()
            
            assert 'is_running' in stats
            assert 'active_alerts_count' in stats
            assert 'alert_rules_count' in stats
            assert 'notification_targets_count' in stats
            assert 'storage_path' in stats
            
            assert stats['is_running'] == False
            assert stats['active_alerts_count'] == 0
            assert stats['alert_rules_count'] == 0
            assert stats['notification_targets_count'] == 0
            assert stats['storage_path'] == temp_dir

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
