"""
Tests API pour le système d'alertes et notifications
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from wakedock.api.routes.alerts import router
from wakedock.core.alerts_service import (
    AlertsService, AlertRule, NotificationTarget, AlertInstance,
    NotificationChannel, AlertSeverity, EscalationLevel, AlertState
)

# Crée une app de test
app = FastAPI()
app.include_router(router)

class TestAlertsAPI:
    """Tests pour l'API d'alertes"""
    
    @pytest.fixture
    def mock_alerts_service(self):
        """Mock du service d'alertes"""
        service = Mock(spec=AlertsService)
        
        # Mock des données par défaut
        service.get_alert_rules.return_value = []
        service.get_notification_targets.return_value = []
        service.get_active_alerts.return_value = []
        service.get_alerts_history = AsyncMock(return_value=[])
        service.get_service_stats.return_value = {
            'is_running': True,
            'active_alerts_count': 0,
            'alert_rules_count': 0,
            'notification_targets_count': 0,
            'storage_path': '/tmp/test'
        }
        
        return service
    
    @pytest.fixture
    def client(self, mock_alerts_service):
        """Client de test avec service mocké"""
        with patch('wakedock.api.routes.alerts.get_alerts_service', return_value=mock_alerts_service):
            yield TestClient(app)
    
    def test_get_alert_rules_empty(self, client, mock_alerts_service):
        """Test récupération règles vides"""
        response = client.get("/alerts/rules")
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_alert_rules_with_data(self, client, mock_alerts_service):
        """Test récupération règles avec données"""
        rule = AlertRule(
            rule_id="test_rule",
            name="Test Rule",
            description="Test description",
            metric_type="cpu_percent",
            threshold_value=80.0,
            comparison_operator=">",
            duration_minutes=5,
            severity=AlertSeverity.HIGH,
            notification_targets=[]
        )
        
        mock_alerts_service.get_alert_rules.return_value = [rule]
        
        response = client.get("/alerts/rules")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 1
        assert data[0]['rule_id'] == "test_rule"
        assert data[0]['name'] == "Test Rule"
        assert data[0]['metric_type'] == "cpu_percent"
        assert data[0]['threshold_value'] == 80.0
        assert data[0]['severity'] == "high"
    
    def test_get_alert_rule_by_id(self, client, mock_alerts_service):
        """Test récupération règle par ID"""
        rule = AlertRule(
            rule_id="test_rule",
            name="Test Rule",
            description="Test description",
            metric_type="cpu_percent",
            threshold_value=80.0,
            comparison_operator=">",
            duration_minutes=5,
            severity=AlertSeverity.HIGH,
            notification_targets=[]
        )
        
        mock_alerts_service.alert_rules = {"test_rule": rule}
        
        response = client.get("/alerts/rules/test_rule")
        assert response.status_code == 200
        
        data = response.json()
        assert data['rule_id'] == "test_rule"
        assert data['name'] == "Test Rule"
    
    def test_get_alert_rule_not_found(self, client, mock_alerts_service):
        """Test règle introuvable"""
        mock_alerts_service.alert_rules = {}
        
        response = client.get("/alerts/rules/nonexistent")
        assert response.status_code == 404
    
    def test_create_alert_rule(self, client, mock_alerts_service):
        """Test création règle d'alerte"""
        mock_alerts_service.add_alert_rule = AsyncMock(return_value=True)
        mock_alerts_service.notification_targets = {}
        
        rule_data = {
            "name": "High CPU Alert",
            "description": "Alert when CPU exceeds 80%",
            "metric_type": "cpu_percent",
            "threshold_value": 80.0,
            "comparison_operator": ">",
            "duration_minutes": 5,
            "severity": "high",
            "notification_targets": []
        }
        
        response = client.post("/alerts/rules", json=rule_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data['name'] == "High CPU Alert"
        assert data['metric_type'] == "cpu_percent"
        assert data['threshold_value'] == 80.0
        
        # Vérifie que le service a été appelé
        mock_alerts_service.add_alert_rule.assert_called_once()
    
    def test_create_alert_rule_invalid_data(self, client, mock_alerts_service):
        """Test création règle avec données invalides"""
        rule_data = {
            "name": "Invalid Rule",
            "description": "Test",
            "metric_type": "invalid_metric",  # Métrique invalide
            "threshold_value": 80.0,
            "comparison_operator": ">",
            "duration_minutes": 5,
            "severity": "high",
            "notification_targets": []
        }
        
        response = client.post("/alerts/rules", json=rule_data)
        assert response.status_code == 422  # Validation error
    
    def test_update_alert_rule(self, client, mock_alerts_service):
        """Test mise à jour règle d'alerte"""
        existing_rule = AlertRule(
            rule_id="test_rule",
            name="Original Rule",
            description="Original description",
            metric_type="cpu_percent",
            threshold_value=70.0,
            comparison_operator=">",
            duration_minutes=5,
            severity=AlertSeverity.MEDIUM,
            notification_targets=[]
        )
        
        mock_alerts_service.alert_rules = {"test_rule": existing_rule}
        mock_alerts_service.update_alert_rule = AsyncMock(return_value=True)
        
        updated_data = {
            "name": "Updated Rule",
            "description": "Updated description",
            "metric_type": "cpu_percent",
            "threshold_value": 80.0,
            "comparison_operator": ">",
            "duration_minutes": 5,
            "severity": "high",
            "notification_targets": []
        }
        
        response = client.put("/alerts/rules/test_rule", json=updated_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data['name'] == "Updated Rule"
        assert data['threshold_value'] == 80.0
        assert data['severity'] == "high"
    
    def test_delete_alert_rule(self, client, mock_alerts_service):
        """Test suppression règle d'alerte"""
        mock_alerts_service.alert_rules = {"test_rule": Mock()}
        mock_alerts_service.delete_alert_rule = AsyncMock(return_value=True)
        
        response = client.delete("/alerts/rules/test_rule")
        assert response.status_code == 200
        
        data = response.json()
        assert "supprimée" in data['message']
        
        mock_alerts_service.delete_alert_rule.assert_called_once_with("test_rule")
    
    def test_get_notification_targets(self, client, mock_alerts_service):
        """Test récupération cibles de notification"""
        target = NotificationTarget(
            channel=NotificationChannel.EMAIL,
            name="Test Email",
            enabled=True,
            email_address="test@example.com"
        )
        
        mock_alerts_service.get_notification_targets.return_value = [target]
        mock_alerts_service.notification_targets = {"email_test_email": target}
        
        response = client.get("/alerts/targets")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 1
        assert data[0]['name'] == "Test Email"
        assert data[0]['channel'] == "email"
        assert data[0]['has_email_config'] == True
    
    def test_create_notification_target(self, client, mock_alerts_service):
        """Test création cible de notification"""
        mock_alerts_service.add_notification_target = AsyncMock(return_value=True)
        
        target_data = {
            "channel": "email",
            "name": "Admin Email",
            "enabled": True,
            "email_address": "admin@example.com"
        }
        
        response = client.post("/alerts/targets", json=target_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data['name'] == "Admin Email"
        assert data['channel'] == "email"
        assert data['has_email_config'] == True
    
    def test_create_notification_target_invalid(self, client, mock_alerts_service):
        """Test création cible avec données invalides"""
        target_data = {
            "channel": "email",
            "name": "Invalid Email",
            "enabled": True
            # email_address manquant pour canal email
        }
        
        response = client.post("/alerts/targets", json=target_data)
        assert response.status_code == 422  # Validation error
    
    def test_test_notification_target(self, client, mock_alerts_service):
        """Test d'une cible de notification"""
        target = NotificationTarget(
            channel=NotificationChannel.EMAIL,
            name="Test Email",
            enabled=True,
            email_address="test@example.com"
        )
        
        mock_alerts_service.notification_targets = {"test_target": target}
        mock_alerts_service._send_notification = AsyncMock(return_value=True)
        
        test_data = {
            "test_message": "Test notification from WakeDock"
        }
        
        response = client.post("/alerts/targets/test_target/test", json=test_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data['success'] == True
        assert "succès" in data['message']
        assert 'sent_at' in data
        assert 'response_time_ms' in data
    
    def test_get_active_alerts(self, client, mock_alerts_service):
        """Test récupération alertes actives"""
        alert = AlertInstance(
            alert_id="test_alert",
            rule_id="test_rule",
            rule_name="Test Alert",
            container_id="container_123",
            container_name="test-container",
            service_name="test-service",
            metric_type="cpu_percent",
            current_value=85.0,
            threshold_value=80.0,
            severity=AlertSeverity.HIGH,
            state=AlertState.ACTIVE
        )
        
        mock_alerts_service.get_active_alerts.return_value = [alert]
        
        response = client.get("/alerts/active")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 1
        assert data[0]['alert_id'] == "test_alert"
        assert data[0]['rule_name'] == "Test Alert"
        assert data[0]['container_name'] == "test-container"
        assert data[0]['severity'] == "high"
        assert data[0]['state'] == "active"
    
    def test_get_active_alerts_with_filters(self, client, mock_alerts_service):
        """Test récupération alertes actives avec filtres"""
        alert1 = AlertInstance(
            alert_id="alert_1",
            rule_id="rule_1",
            rule_name="CPU Alert",
            container_id="container_1",
            container_name="web-1",
            metric_type="cpu_percent",
            current_value=85.0,
            threshold_value=80.0,
            severity=AlertSeverity.HIGH,
            state=AlertState.ACTIVE
        )
        
        alert2 = AlertInstance(
            alert_id="alert_2",
            rule_id="rule_2",
            rule_name="Memory Alert",
            container_id="container_2",
            container_name="db-1",
            metric_type="memory_percent",
            current_value=90.0,
            threshold_value=85.0,
            severity=AlertSeverity.CRITICAL,
            state=AlertState.ACTIVE
        )
        
        mock_alerts_service.get_active_alerts.return_value = [alert1, alert2]
        
        # Test filtre par sévérité
        response = client.get("/alerts/active?severity=high")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 1
        assert data[0]['severity'] == "high"
        
        # Test filtre par conteneur
        response = client.get("/alerts/active?container_id=container_1")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 1
        assert data[0]['container_name'] == "web-1"
    
    def test_acknowledge_alert(self, client, mock_alerts_service):
        """Test acquittement d'alerte"""
        mock_alerts_service.acknowledge_alert = AsyncMock(return_value=True)
        
        ack_data = {
            "acknowledged_by": "admin_user"
        }
        
        response = client.post("/alerts/acknowledge/test_alert", json=ack_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "acquittée" in data['message']
        
        mock_alerts_service.acknowledge_alert.assert_called_once_with("test_alert", "admin_user")
    
    def test_acknowledge_alert_not_found(self, client, mock_alerts_service):
        """Test acquittement alerte inexistante"""
        mock_alerts_service.acknowledge_alert = AsyncMock(return_value=False)
        
        ack_data = {
            "acknowledged_by": "admin_user"
        }
        
        response = client.post("/alerts/acknowledge/nonexistent", json=ack_data)
        assert response.status_code == 404
    
    def test_bulk_alert_action(self, client, mock_alerts_service):
        """Test action en lot sur alertes"""
        # Mock des alertes actives
        alert1 = Mock()
        alert2 = Mock()
        mock_alerts_service.active_alerts = {
            "alert_1": alert1,
            "alert_2": alert2
        }
        mock_alerts_service.acknowledge_alert = AsyncMock(return_value=True)
        mock_alerts_service._resolve_alert = AsyncMock()
        
        action_data = {
            "alert_ids": ["alert_1", "alert_2"],
            "action": "acknowledge",
            "parameters": {
                "acknowledged_by": "admin_user"
            }
        }
        
        response = client.post("/alerts/bulk-action", json=action_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data['total_processed'] == 2
        assert data['successful'] == 2
        assert data['failed'] == 0
        assert len(data['results']) == 2
    
    def test_get_alerts_stats(self, client, mock_alerts_service):
        """Test statistiques d'alertes"""
        # Mock historique d'alertes
        alert1 = AlertInstance(
            alert_id="alert_1",
            rule_id="rule_1",
            rule_name="Test Alert 1",
            container_id="container_1",
            container_name="web-1",
            metric_type="cpu_percent",
            current_value=85.0,
            threshold_value=80.0,
            severity=AlertSeverity.HIGH,
            state=AlertState.ACTIVE
        )
        
        alert2 = AlertInstance(
            alert_id="alert_2",
            rule_id="rule_2",
            rule_name="Test Alert 2",
            container_id="container_2",
            container_name="db-1",
            metric_type="memory_percent",
            current_value=90.0,
            threshold_value=85.0,
            severity=AlertSeverity.CRITICAL,
            state=AlertState.RESOLVED
        )
        
        mock_alerts_service.get_alerts_history = AsyncMock(return_value=[alert1, alert2])
        mock_alerts_service.get_active_alerts.return_value = [alert1]
        
        response = client.get("/alerts/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert data['total_alerts'] == 2
        assert data['active_alerts'] == 1
        assert data['resolved_alerts'] == 1
        assert 'alerts_by_severity' in data
        assert 'alerts_by_state' in data
        assert 'top_triggered_rules' in data
        assert 'most_affected_containers' in data
    
    def test_export_alerts_json(self, client, mock_alerts_service):
        """Test export alertes en JSON"""
        alert = AlertInstance(
            alert_id="test_alert",
            rule_id="test_rule",
            rule_name="Test Alert",
            container_id="container_123",
            container_name="test-container",
            metric_type="cpu_percent",
            current_value=85.0,
            threshold_value=80.0,
            severity=AlertSeverity.HIGH,
            state=AlertState.ACTIVE
        )
        
        mock_alerts_service.get_alerts_history = AsyncMock(return_value=[alert])
        
        export_data = {
            "format": "json",
            "include_resolved": True,
            "date_range_days": 30
        }
        
        response = client.post("/alerts/export", json=export_data)
        assert response.status_code == 200
        assert response.headers['content-type'] == 'application/json'
        assert 'attachment' in response.headers['content-disposition']
    
    def test_export_alerts_csv(self, client, mock_alerts_service):
        """Test export alertes en CSV"""
        alert = AlertInstance(
            alert_id="test_alert",
            rule_id="test_rule",
            rule_name="Test Alert",
            container_id="container_123",
            container_name="test-container",
            metric_type="cpu_percent",
            current_value=85.0,
            threshold_value=80.0,
            severity=AlertSeverity.HIGH,
            state=AlertState.ACTIVE
        )
        
        mock_alerts_service.get_alerts_history = AsyncMock(return_value=[alert])
        
        export_data = {
            "format": "csv",
            "include_resolved": True,
            "date_range_days": 30
        }
        
        response = client.post("/alerts/export", json=export_data)
        assert response.status_code == 200
        assert response.headers['content-type'] == 'text/csv; charset=utf-8'
        assert 'attachment' in response.headers['content-disposition']
    
    def test_get_service_status(self, client, mock_alerts_service):
        """Test statut du service d'alertes"""
        response = client.get("/alerts/service/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data['is_running'] == True
        assert 'uptime_seconds' in data
        assert 'active_alerts_count' in data
        assert 'alert_rules_count' in data
        assert 'notification_targets_count' in data
        assert 'storage_path' in data
    
    def test_restart_service(self, client, mock_alerts_service):
        """Test redémarrage service d'alertes"""
        mock_alerts_service.stop = AsyncMock()
        mock_alerts_service.start = AsyncMock()
        
        response = client.post("/alerts/service/restart")
        assert response.status_code == 200
        
        data = response.json()
        assert "redémarrage" in data['message'].lower()
    
    def test_get_default_alert_rules(self, client, mock_alerts_service):
        """Test récupération règles par défaut"""
        response = client.get("/alerts/rules/defaults")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        # Les règles par défaut devraient inclure au moins high CPU et high memory
        rule_names = [rule['name'] for rule in data]
        assert any('CPU' in name for name in rule_names)
        assert any('Memory' in name for name in rule_names)

class TestAlertsAPIIntegration:
    """Tests d'intégration pour l'API d'alertes"""
    
    @pytest.mark.asyncio
    async def test_full_alert_workflow(self, client, mock_alerts_service):
        """Test workflow complet d'alerte"""
        # 1. Créer une cible de notification
        target_data = {
            "channel": "email",
            "name": "Test Admin",
            "enabled": True,
            "email_address": "admin@test.com"
        }
        
        mock_alerts_service.add_notification_target = AsyncMock(return_value=True)
        response = client.post("/alerts/targets", json=target_data)
        assert response.status_code == 200
        
        # 2. Créer une règle d'alerte
        rule_data = {
            "name": "Critical CPU Alert",
            "description": "Alert for critical CPU usage",
            "metric_type": "cpu_percent",
            "threshold_value": 90.0,
            "comparison_operator": ">",
            "duration_minutes": 3,
            "severity": "critical",
            "notification_targets": ["email_test_admin"]
        }
        
        mock_alerts_service.add_alert_rule = AsyncMock(return_value=True)
        mock_alerts_service.notification_targets = {"email_test_admin": Mock()}
        response = client.post("/alerts/rules", json=rule_data)
        assert response.status_code == 200
        
        # 3. Simuler une alerte active
        alert = AlertInstance(
            alert_id="critical_alert",
            rule_id="critical_rule",
            rule_name="Critical CPU Alert",
            container_id="container_123",
            container_name="web-server",
            metric_type="cpu_percent",
            current_value=95.0,
            threshold_value=90.0,
            severity=AlertSeverity.CRITICAL,
            state=AlertState.ACTIVE
        )
        
        mock_alerts_service.get_active_alerts.return_value = [alert]
        response = client.get("/alerts/active")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 1
        assert data[0]['severity'] == "critical"
        
        # 4. Acquitter l'alerte
        mock_alerts_service.acknowledge_alert = AsyncMock(return_value=True)
        ack_data = {"acknowledged_by": "admin"}
        response = client.post("/alerts/acknowledge/critical_alert", json=ack_data)
        assert response.status_code == 200

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
