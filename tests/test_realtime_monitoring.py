"""
Tests pour le système de monitoring temps réel (version 0.2.2)
"""
import asyncio
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
import tempfile

from wakedock.core.metrics_collector import (
    MetricsCollector, MetricType, AlertLevel, ContainerMetrics, Alert,
    ThresholdConfig
)
from wakedock.core.websocket_service import (
    MetricsWebSocketService, StreamType, MessageType, WebSocketMessage,
    ClientConnection
)
from wakedock.core.docker_manager import DockerManager

class TestMetricsCollector:
    """Tests pour le collecteur de métriques"""
    
    @pytest.fixture
    def mock_docker_manager(self):
        """Mock du gestionnaire Docker"""
        manager = Mock(spec=DockerManager)
        manager.list_containers.return_value = []
        manager.get_container_info.return_value = {}
        manager.get_container_stats.return_value = {}
        return manager
    
    @pytest.fixture
    def temp_storage(self):
        """Répertoire temporaire pour les tests"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def metrics_collector(self, mock_docker_manager, temp_storage):
        """Instance du collecteur pour les tests"""
        return MetricsCollector(mock_docker_manager, temp_storage)
    
    def test_initialization(self, metrics_collector):
        """Test de l'initialisation du collecteur"""
        assert not metrics_collector.is_running
        assert metrics_collector.collection_interval == 5
        assert metrics_collector.retention_days == 7
        assert len(metrics_collector.thresholds) == 4
        assert MetricType.CPU_PERCENT in metrics_collector.thresholds
    
    def test_threshold_configuration(self, metrics_collector):
        """Test de la configuration des seuils"""
        # Vérifie les seuils par défaut
        cpu_threshold = metrics_collector.thresholds[MetricType.CPU_PERCENT]
        assert cpu_threshold.warning_threshold == 70.0
        assert cpu_threshold.critical_threshold == 90.0
        assert cpu_threshold.enabled is True
        
        # Met à jour un seuil
        metrics_collector.update_threshold(
            MetricType.CPU_PERCENT, 
            warning=80.0, 
            critical=95.0, 
            enabled=False
        )
        
        updated_threshold = metrics_collector.thresholds[MetricType.CPU_PERCENT]
        assert updated_threshold.warning_threshold == 80.0
        assert updated_threshold.critical_threshold == 95.0
        assert updated_threshold.enabled is False
    
    @pytest.mark.asyncio
    async def test_container_discovery(self, metrics_collector, mock_docker_manager):
        """Test de la découverte des conteneurs"""
        # Mock des conteneurs
        mock_container = Mock()
        mock_container.id = "container123"
        mock_docker_manager.list_containers.return_value = [mock_container]
        mock_docker_manager.get_container_info.return_value = {
            'name': 'test-container',
            'labels': {'com.docker.compose.service': 'web'}
        }
        
        # Découvre les conteneurs
        await metrics_collector._discover_containers()
        
        assert "container123" in metrics_collector.monitored_containers
        assert metrics_collector.monitored_containers["container123"] == "test-container"
    
    def test_cpu_calculation(self, metrics_collector):
        """Test du calcul du pourcentage CPU"""
        # Stats CPU simulées
        cpu_stats = {
            'cpu_usage': {'total_usage': 2000000000},  # 2 secondes
            'system_cpu_usage': 10000000000,  # 10 secondes
            'online_cpus': 2
        }
        
        precpu_stats = {
            'cpu_usage': {'total_usage': 1000000000},  # 1 seconde
            'system_cpu_usage': 9000000000   # 9 secondes
        }
        
        cpu_percent = metrics_collector._calculate_cpu_percent(cpu_stats, precpu_stats)
        
        # (2-1) / (10-9) * 2 * 100 = 200%
        expected = 200.0
        assert abs(cpu_percent - expected) < 0.1
    
    @pytest.mark.asyncio
    async def test_metrics_collection(self, metrics_collector, mock_docker_manager):
        """Test de la collecte de métriques"""
        # Mock des stats de conteneur
        stats = {
            'cpu_stats': {
                'cpu_usage': {'total_usage': 1000000000},
                'system_cpu_usage': 5000000000,
                'online_cpus': 1
            },
            'precpu_stats': {
                'cpu_usage': {'total_usage': 500000000},
                'system_cpu_usage': 4000000000
            },
            'memory_stats': {
                'usage': 1073741824,  # 1GB
                'limit': 2147483648,  # 2GB
                'stats': {'cache': 104857600}  # 100MB
            },
            'networks': {
                'eth0': {
                    'rx_bytes': 1048576,  # 1MB
                    'tx_bytes': 2097152,  # 2MB
                    'rx_packets': 100,
                    'tx_packets': 200
                }
            },
            'blkio_stats': {
                'io_service_bytes_recursive': [
                    {'op': 'read', 'value': 10485760},   # 10MB
                    {'op': 'write', 'value': 20971520}  # 20MB
                ]
            },
            'pids_stats': {'current': 25}
        }
        
        mock_docker_manager.get_container_stats.return_value = stats
        mock_docker_manager.get_container_info.return_value = {
            'name': 'test-container',
            'labels': {'com.docker.compose.service': 'web'}
        }
        
        # Collecte les métriques
        metrics = await metrics_collector._collect_container_metrics("container123", "test-container")
        
        assert metrics is not None
        assert metrics.container_id == "container123"
        assert metrics.container_name == "test-container"
        assert metrics.service_name == "web"
        assert metrics.memory_usage == 1073741824
        assert metrics.memory_percent == 50.0  # 1GB / 2GB * 100
        assert metrics.network_rx_bytes == 1048576
        assert metrics.network_tx_bytes == 2097152
        assert metrics.pids == 25
    
    @pytest.mark.asyncio
    async def test_threshold_checking(self, metrics_collector):
        """Test de la vérification des seuils"""
        # Crée des métriques de test avec CPU élevé
        metrics = ContainerMetrics(
            container_id="container123",
            container_name="test-container",
            service_name="web",
            timestamp=datetime.utcnow(),
            cpu_percent=95.0,  # Au-dessus du seuil critique
            cpu_usage=1000000000,
            cpu_system_usage=5000000000,
            memory_usage=1073741824,
            memory_limit=2147483648,
            memory_percent=50.0,
            memory_cache=104857600,
            network_rx_bytes=1048576,
            network_tx_bytes=2097152,
            network_rx_packets=100,
            network_tx_packets=200,
            block_read_bytes=10485760,
            block_write_bytes=20971520,
            pids=25
        )
        
        # Mock de la méthode de traitement d'alerte
        alerts_processed = []
        
        async def mock_process_alert(alert):
            alerts_processed.append(alert)
        
        metrics_collector._process_alert = mock_process_alert
        
        # Vérifie les seuils
        await metrics_collector._check_thresholds(metrics)
        
        # Doit générer une alerte CPU critique
        assert len(alerts_processed) == 1
        alert = alerts_processed[0]
        assert alert.level == AlertLevel.CRITICAL
        assert alert.metric_type == MetricType.CPU_PERCENT
        assert alert.value == 95.0
    
    @pytest.mark.asyncio
    async def test_metrics_storage(self, metrics_collector, temp_storage):
        """Test du stockage des métriques"""
        # Crée des métriques de test
        metrics = ContainerMetrics(
            container_id="container123",
            container_name="test-container",
            service_name="web",
            timestamp=datetime.utcnow(),
            cpu_percent=50.0,
            cpu_usage=1000000000,
            cpu_system_usage=5000000000,
            memory_usage=1073741824,
            memory_limit=2147483648,
            memory_percent=50.0,
            memory_cache=104857600,
            network_rx_bytes=1048576,
            network_tx_bytes=2097152,
            network_rx_packets=100,
            network_tx_packets=200,
            block_read_bytes=10485760,
            block_write_bytes=20971520,
            pids=25
        )
        
        # Stocke les métriques
        await metrics_collector._store_metrics(metrics)
        
        # Vérifie que le fichier a été créé
        date_str = metrics.timestamp.strftime('%Y-%m-%d')
        metrics_file = Path(temp_storage) / f"metrics_{date_str}.jsonl"
        assert metrics_file.exists()
        
        # Vérifie le contenu
        with open(metrics_file, 'r') as f:
            line = f.readline().strip()
            stored_data = json.loads(line)
            assert stored_data['container_id'] == "container123"
            assert stored_data['cpu_percent'] == 50.0

class TestWebSocketService:
    """Tests pour le service WebSocket"""
    
    @pytest.fixture
    def mock_metrics_collector(self):
        """Mock du collecteur de métriques"""
        collector = Mock(spec=MetricsCollector)
        collector.is_running = True
        collector.monitored_containers = {"container123": "test-container"}
        collector.get_recent_metrics = AsyncMock(return_value=[])
        collector.get_recent_alerts = AsyncMock(return_value=[])
        collector.get_stats.return_value = {
            'is_running': True,
            'monitored_containers': 1
        }
        collector.add_alert_callback = Mock()
        collector.remove_alert_callback = Mock()
        return collector
    
    @pytest.fixture
    def websocket_service(self, mock_metrics_collector):
        """Instance du service WebSocket pour les tests"""
        return MetricsWebSocketService(mock_metrics_collector)
    
    def test_initialization(self, websocket_service):
        """Test de l'initialisation du service"""
        assert not websocket_service.is_running
        assert websocket_service.ping_interval == 30
        assert websocket_service.client_timeout == 60
        assert websocket_service.max_clients == 100
    
    def test_websocket_message(self):
        """Test de la création de messages WebSocket"""
        data = {"test": "data"}
        message = WebSocketMessage(MessageType.METRICS_UPDATE, data)
        
        assert message.type == MessageType.METRICS_UPDATE
        assert message.data == data
        assert isinstance(message.timestamp, datetime)
        
        # Test de sérialisation
        json_str = message.to_json()
        parsed = json.loads(json_str)
        assert parsed['type'] == 'metrics_update'
        assert parsed['data'] == data
    
    def test_client_connection(self):
        """Test de la gestion des connexions client"""
        mock_websocket = Mock()
        client = ClientConnection(mock_websocket, "client123")
        
        assert client.client_id == "client123"
        assert len(client.subscriptions) == 0
        assert client.is_active is True
        
        # Test d'abonnement
        client.subscribe(StreamType.METRICS, {"container_ids": ["container123"]})
        assert StreamType.METRICS in client.subscriptions
        assert client.filters['metrics']['container_ids'] == ["container123"]
        
        # Test de désabonnement
        client.unsubscribe(StreamType.METRICS)
        assert StreamType.METRICS not in client.subscriptions
    
    @pytest.mark.asyncio
    async def test_service_startup_shutdown(self, websocket_service, mock_metrics_collector):
        """Test du démarrage et arrêt du service"""
        # Démarrage
        await websocket_service.start()
        assert websocket_service.is_running is True
        assert mock_metrics_collector.add_alert_callback.called
        
        # Arrêt
        await websocket_service.stop()
        assert websocket_service.is_running is False
        assert mock_metrics_collector.remove_alert_callback.called

class TestMonitoringIntegration:
    """Tests d'intégration pour le monitoring"""
    
    @pytest.fixture
    def mock_docker_manager(self):
        """Mock du gestionnaire Docker avec données complètes"""
        manager = Mock(spec=DockerManager)
        
        # Mock des conteneurs
        mock_container = Mock()
        mock_container.id = "container123"
        manager.list_containers.return_value = [mock_container]
        
        # Mock des infos conteneur
        manager.get_container_info.return_value = {
            'name': 'test-container',
            'labels': {'com.docker.compose.service': 'web'}
        }
        
        # Mock des stats
        manager.get_container_stats.return_value = {
            'cpu_stats': {
                'cpu_usage': {'total_usage': 2000000000},
                'system_cpu_usage': 10000000000,
                'online_cpus': 1
            },
            'precpu_stats': {
                'cpu_usage': {'total_usage': 1000000000},
                'system_cpu_usage': 9000000000
            },
            'memory_stats': {
                'usage': 1073741824,
                'limit': 2147483648,
                'stats': {'cache': 104857600}
            },
            'networks': {
                'eth0': {
                    'rx_bytes': 1048576,
                    'tx_bytes': 2097152,
                    'rx_packets': 100,
                    'tx_packets': 200
                }
            },
            'blkio_stats': {
                'io_service_bytes_recursive': [
                    {'op': 'read', 'value': 10485760},
                    {'op': 'write', 'value': 20971520}
                ]
            },
            'pids_stats': {'current': 25}
        }
        
        return manager
    
    @pytest.mark.asyncio
    async def test_end_to_end_monitoring(self, mock_docker_manager):
        """Test de bout en bout du système de monitoring"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Crée les composants
            collector = MetricsCollector(mock_docker_manager, tmpdir)
            ws_service = MetricsWebSocketService(collector)
            
            # Démarre le monitoring
            await collector.start()
            await ws_service.start()
            
            try:
                # Simule un cycle de collecte
                await collector._discover_containers()
                
                # Vérifie que les conteneurs sont découverts
                assert "container123" in collector.monitored_containers
                
                # Collecte les métriques
                metrics = await collector._collect_container_metrics(
                    "container123", 
                    "test-container"
                )
                
                # Vérifie les métriques
                assert metrics is not None
                assert metrics.cpu_percent > 0
                assert metrics.memory_percent == 50.0
                
                # Stocke et vérifie le stockage
                await collector._store_metrics(metrics)
                
                date_str = metrics.timestamp.strftime('%Y-%m-%d')
                metrics_file = Path(tmpdir) / f"metrics_{date_str}.jsonl"
                assert metrics_file.exists()
                
                # Récupère les métriques récentes
                recent_metrics = await collector.get_recent_metrics(hours=1)
                assert len(recent_metrics) >= 1
                
            finally:
                # Nettoie
                await ws_service.stop()
                await collector.stop()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
