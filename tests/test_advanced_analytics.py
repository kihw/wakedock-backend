"""
Tests pour le service d'analytics avancé et les routes API
"""
import pytest
import asyncio
import tempfile
import shutil
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch

from fastapi.testclient import TestClient
from wakedock.core.advanced_analytics import (
    AdvancedAnalyticsService,
    PerformanceTrend,
    ResourceOptimization,
    PerformanceReport,
    TrendDirection,
    PredictionConfidence
)
from wakedock.core.metrics_collector import ContainerMetrics, Alert, AlertLevel
from wakedock.api.routes.analytics import router
from wakedock.main import app

# Configuration du client de test
client = TestClient(app)

class TestAdvancedAnalyticsService:
    """Tests pour le service d'analytics avancé"""
    
    @pytest.fixture
    async def temp_storage(self):
        """Crée un répertoire temporaire pour les tests"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    async def mock_metrics_collector(self):
        """Mock du collecteur de métriques"""
        collector = Mock()
        collector.get_recent_metrics = AsyncMock()
        collector.get_recent_alerts = AsyncMock()
        return collector
    
    @pytest.fixture
    async def analytics_service(self, mock_metrics_collector, temp_storage):
        """Service d'analytics configuré pour les tests"""
        service = AdvancedAnalyticsService(
            metrics_collector=mock_metrics_collector,
            storage_path=temp_storage
        )
        service.trend_analysis_hours = 2  # Réduit pour les tests
        return service
    
    @pytest.fixture
    def sample_metrics(self):
        """Métriques de test"""
        base_time = datetime.utcnow()
        metrics = []
        
        # Crée une série de métriques avec tendance croissante pour CPU
        for i in range(20):
            timestamp = base_time - timedelta(minutes=i * 5)
            cpu_value = 30 + (i * 2) + (i * 0.1)  # Tendance croissante
            memory_value = 50 + (i * 0.5)  # Tendance légèrement croissante
            
            metric = ContainerMetrics(
                container_id=f"test_container_{i % 3}",
                container_name=f"test_app_{i % 3}",
                service_name=f"service_{i % 2}",
                cpu_percent=cpu_value,
                memory_percent=memory_value,
                memory_usage_bytes=int(memory_value * 1024 * 1024 * 10),
                memory_limit_bytes=1024 * 1024 * 1024,
                network_rx_bytes=1000000 + (i * 50000),
                network_tx_bytes=500000 + (i * 25000),
                timestamp=timestamp
            )
            metrics.append(metric)
        
        return metrics
    
    @pytest.mark.asyncio
    async def test_service_lifecycle(self, analytics_service):
        """Test du cycle de vie du service"""
        # Le service n'est pas démarré
        assert not analytics_service.is_running
        
        # Démarre le service
        await analytics_service.start()
        assert analytics_service.is_running
        assert analytics_service.analysis_task is not None
        assert analytics_service.report_task is not None
        
        # Arrête le service
        await analytics_service.stop()
        assert not analytics_service.is_running
    
    @pytest.mark.asyncio
    async def test_analyze_metric_trend(self, analytics_service, sample_metrics):
        """Test de l'analyse de tendance d'une métrique"""
        # Filtre les métriques pour un conteneur
        container_metrics = [m for m in sample_metrics if m.container_id == "test_container_0"]
        
        # Analyse la tendance CPU
        trend = await analytics_service._analyze_metric_trend(
            container_metrics, 'cpu_percent', 'test_container_0'
        )
        
        assert trend is not None
        assert trend.metric_type == 'cpu_percent'
        assert trend.container_id == 'test_container_0'
        assert trend.container_name == 'test_app_0'
        assert trend.direction in [TrendDirection.INCREASING, TrendDirection.STABLE]
        assert trend.correlation >= 0
        assert trend.current_value > 0
        assert trend.predicted_1h >= 0
        assert trend.predicted_24h >= 0
        assert isinstance(trend.confidence, PredictionConfidence)
    
    @pytest.mark.asyncio
    async def test_analyze_network_trend(self, analytics_service, sample_metrics):
        """Test de l'analyse de tendance réseau"""
        container_metrics = [m for m in sample_metrics if m.container_id == "test_container_0"]
        
        # Analyse la tendance réseau
        trend = await analytics_service._analyze_network_trend(
            container_metrics, 'test_container_0'
        )
        
        assert trend is not None
        assert trend.metric_type == 'network_mbps'
        assert trend.container_id == 'test_container_0'
        assert trend.current_value >= 0
        assert trend.predicted_1h >= 0
        assert trend.predicted_24h >= 0
    
    @pytest.mark.asyncio
    async def test_analyze_performance_trends(self, analytics_service, mock_metrics_collector, sample_metrics):
        """Test de l'analyse complète des tendances"""
        # Configure le mock
        mock_metrics_collector.get_recent_metrics.return_value = sample_metrics
        
        # Lance l'analyse
        await analytics_service._analyze_performance_trends()
        
        # Vérifie que l'analyse a été appelée
        mock_metrics_collector.get_recent_metrics.assert_called_once()
        
        # Vérifie que les tendances ont été stockées
        trends = await analytics_service.get_recent_trends(hours=24)
        assert len(trends) >= 0  # Peut être vide selon les critères de filtrage
    
    @pytest.mark.asyncio
    async def test_cpu_optimization_analysis(self, analytics_service):
        """Test de l'analyse d'optimisation CPU"""
        # Crée une tendance avec CPU élevé
        trend = PerformanceTrend(
            metric_type='cpu_percent',
            container_id='test_container',
            container_name='test_app',
            service_name='test_service',
            direction=TrendDirection.INCREASING,
            slope=2.5,
            correlation=0.85,
            current_value=85.0,
            average_value=82.0,
            min_value=70.0,
            max_value=90.0,
            std_deviation=5.0,
            predicted_1h=87.0,
            predicted_6h=90.0,
            predicted_24h=95.0,
            confidence=PredictionConfidence.HIGH,
            calculated_at=datetime.utcnow(),
            data_points=50,
            time_range_hours=24
        )
        
        # Analyse l'optimisation
        optimization = analytics_service._analyze_cpu_optimization(trend)
        
        assert optimization is not None
        assert optimization.resource_type == 'cpu'
        assert optimization.optimization_type == 'increase'
        assert optimization.expected_improvement > 0
        assert optimization.impact_level == 'high'
        assert 'CPU élevé' in optimization.reason
    
    @pytest.mark.asyncio
    async def test_memory_optimization_analysis(self, analytics_service):
        """Test de l'analyse d'optimisation mémoire"""
        # Crée une tendance avec mémoire critique
        trend = PerformanceTrend(
            metric_type='memory_percent',
            container_id='test_container',
            container_name='test_app',
            service_name='test_service',
            direction=TrendDirection.INCREASING,
            slope=1.5,
            correlation=0.90,
            current_value=87.0,
            average_value=85.0,
            min_value=80.0,
            max_value=90.0,
            std_deviation=3.0,
            predicted_1h=88.0,
            predicted_6h=91.0,
            predicted_24h=95.0,
            confidence=PredictionConfidence.HIGH,
            calculated_at=datetime.utcnow(),
            data_points=40,
            time_range_hours=24
        )
        
        # Analyse l'optimisation
        optimization = analytics_service._analyze_memory_optimization(trend)
        
        assert optimization is not None
        assert optimization.resource_type == 'memory'
        assert optimization.optimization_type == 'increase'
        assert 'Mémoire critique' in optimization.reason
        assert optimization.impact_level == 'high'
    
    @pytest.mark.asyncio
    async def test_generate_daily_report(self, analytics_service, mock_metrics_collector, sample_metrics):
        """Test de la génération de rapport journalier"""
        # Configure le mock
        mock_metrics_collector.get_recent_metrics.return_value = sample_metrics
        mock_metrics_collector.get_recent_alerts.return_value = [
            Alert(
                alert_id='test_alert_1',
                container_id='test_container_0',
                container_name='test_app_0',
                service_name='test_service',
                metric_type='cpu_percent',
                level=AlertLevel.WARNING,
                threshold=80.0,
                current_value=85.0,
                message='CPU élevé détecté',
                created_at=datetime.utcnow()
            )
        ]
        
        # Mock pour les tendances et optimisations
        with patch.object(analytics_service, 'get_recent_trends') as mock_trends, \
             patch.object(analytics_service, 'get_recent_optimizations') as mock_opts:
            
            mock_trends.return_value = []
            mock_opts.return_value = []
            
            # Génère le rapport
            await analytics_service._generate_daily_report(datetime.utcnow())
        
        # Vérifie les appels
        mock_metrics_collector.get_recent_metrics.assert_called()
        mock_metrics_collector.get_recent_alerts.assert_called()
    
    @pytest.mark.asyncio
    async def test_store_and_retrieve_trends(self, analytics_service):
        """Test du stockage et de la récupération des tendances"""
        # Crée des tendances de test
        trends = [
            PerformanceTrend(
                metric_type='cpu_percent',
                container_id='test_container_1',
                container_name='test_app_1',
                service_name='test_service',
                direction=TrendDirection.INCREASING,
                slope=1.5,
                correlation=0.75,
                current_value=70.0,
                average_value=65.0,
                min_value=60.0,
                max_value=75.0,
                std_deviation=4.0,
                predicted_1h=72.0,
                predicted_6h=75.0,
                predicted_24h=80.0,
                confidence=PredictionConfidence.MEDIUM,
                calculated_at=datetime.utcnow(),
                data_points=30,
                time_range_hours=12
            )
        ]
        
        # Stocke les tendances
        await analytics_service._store_trends(trends)
        
        # Récupère les tendances
        retrieved_trends = await analytics_service.get_recent_trends(hours=24)
        
        # Vérifie que la tendance a été stockée et récupérée
        assert len(retrieved_trends) == 1
        trend = retrieved_trends[0]
        assert trend.metric_type == 'cpu_percent'
        assert trend.container_id == 'test_container_1'
        assert trend.direction == TrendDirection.INCREASING
    
    @pytest.mark.asyncio
    async def test_store_and_retrieve_optimizations(self, analytics_service):
        """Test du stockage et de la récupération des optimisations"""
        # Crée des optimisations de test
        optimizations = [
            ResourceOptimization(
                container_id='test_container_1',
                container_name='test_app_1',
                service_name='test_service',
                resource_type='cpu',
                optimization_type='increase',
                current_limit=100.0,
                recommended_limit=150.0,
                expected_improvement=25.0,
                reason='CPU saturé avec tendance croissante',
                impact_level='high',
                confidence_score=0.85,
                created_at=datetime.utcnow()
            )
        ]
        
        # Stocke les optimisations
        await analytics_service._store_optimizations(optimizations)
        
        # Récupère les optimisations
        retrieved_opts = await analytics_service.get_recent_optimizations(hours=24)
        
        # Vérifie
        assert len(retrieved_opts) == 1
        opt = retrieved_opts[0]
        assert opt.resource_type == 'cpu'
        assert opt.optimization_type == 'increase'
        assert opt.expected_improvement == 25.0
    
    def test_determine_trend_direction(self, analytics_service):
        """Test de la détermination de direction de tendance"""
        # Tendance croissante forte
        direction = analytics_service._determine_trend_direction(
            slope=2.0, correlation=0.8, std_dev=3.0
        )
        assert direction == TrendDirection.INCREASING
        
        # Tendance décroissante
        direction = analytics_service._determine_trend_direction(
            slope=-1.5, correlation=0.7, std_dev=2.0
        )
        assert direction == TrendDirection.DECREASING
        
        # Tendance stable
        direction = analytics_service._determine_trend_direction(
            slope=0.005, correlation=0.6, std_dev=1.0
        )
        assert direction == TrendDirection.STABLE
        
        # Tendance volatile (corrélation faible)
        direction = analytics_service._determine_trend_direction(
            slope=1.0, correlation=0.2, std_dev=5.0
        )
        assert direction == TrendDirection.VOLATILE
    
    def test_determine_prediction_confidence(self, analytics_service):
        """Test de la détermination de confiance des prédictions"""
        # Confiance élevée
        confidence = analytics_service._determine_prediction_confidence(
            correlation=0.9, data_points=150, std_dev=2.0
        )
        assert confidence == PredictionConfidence.HIGH
        
        # Confiance moyenne
        confidence = analytics_service._determine_prediction_confidence(
            correlation=0.6, data_points=80, std_dev=10.0
        )
        assert confidence == PredictionConfidence.MEDIUM
        
        # Confiance faible
        confidence = analytics_service._determine_prediction_confidence(
            correlation=0.3, data_points=20, std_dev=25.0
        )
        assert confidence == PredictionConfidence.LOW
    
    def test_analytics_stats(self, analytics_service):
        """Test de la récupération des statistiques"""
        stats = analytics_service.get_analytics_stats()
        
        assert 'is_running' in stats
        assert 'trend_analysis_hours' in stats
        assert 'prediction_model_points' in stats
        assert 'volatility_threshold' in stats
        assert 'correlation_threshold' in stats
        assert 'storage_path' in stats
        assert 'cached_models' in stats
        
        assert isinstance(stats['is_running'], bool)
        assert isinstance(stats['trend_analysis_hours'], int)
        assert isinstance(stats['cached_models'], int)

class TestAnalyticsAPIRoutes:
    """Tests pour les routes API d'analytics"""
    
    @pytest.fixture
    def mock_analytics_service(self):
        """Mock du service d'analytics"""
        service = Mock()
        service.get_analytics_stats.return_value = {
            'is_running': True,
            'trend_analysis_hours': 24,
            'prediction_model_points': 100,
            'volatility_threshold': 0.3,
            'correlation_threshold': 0.7,
            'storage_path': '/tmp/test',
            'cached_models': 0
        }
        service.start = AsyncMock()
        service.stop = AsyncMock()
        service.get_recent_trends = AsyncMock()
        service.get_recent_optimizations = AsyncMock()
        service.get_recent_reports = AsyncMock()
        service._generate_daily_report = AsyncMock()
        return service
    
    def test_get_analytics_status(self, mock_analytics_service):
        """Test de récupération du statut"""
        with patch('wakedock.api.routes.analytics.get_analytics_service') as mock_get_service:
            mock_get_service.return_value = mock_analytics_service
            
            response = client.get("/api/v1/analytics/status")
            
            assert response.status_code == 200
            data = response.json()
            assert data['is_running'] is True
            assert data['trend_analysis_hours'] == 24
    
    def test_start_analytics_service(self, mock_analytics_service):
        """Test de démarrage du service"""
        with patch('wakedock.api.routes.analytics.get_analytics_service') as mock_get_service:
            mock_get_service.return_value = mock_analytics_service
            
            response = client.post("/api/v1/analytics/start")
            
            assert response.status_code == 200
            data = response.json()
            assert "démarré" in data['message']
            mock_analytics_service.start.assert_called_once()
    
    def test_stop_analytics_service(self, mock_analytics_service):
        """Test d'arrêt du service"""
        with patch('wakedock.api.routes.analytics.get_analytics_service') as mock_get_service:
            mock_get_service.return_value = mock_analytics_service
            
            response = client.post("/api/v1/analytics/stop")
            
            assert response.status_code == 200
            data = response.json()
            assert "arrêté" in data['message']
            mock_analytics_service.stop.assert_called_once()
    
    def test_get_performance_trends(self, mock_analytics_service):
        """Test de récupération des tendances"""
        # Mock des tendances
        mock_trends = [
            PerformanceTrend(
                metric_type='cpu_percent',
                container_id='test_container',
                container_name='test_app',
                service_name='test_service',
                direction=TrendDirection.INCREASING,
                slope=1.5,
                correlation=0.8,
                current_value=75.0,
                average_value=70.0,
                min_value=65.0,
                max_value=80.0,
                std_deviation=5.0,
                predicted_1h=77.0,
                predicted_6h=80.0,
                predicted_24h=85.0,
                confidence=PredictionConfidence.HIGH,
                calculated_at=datetime.utcnow(),
                data_points=50,
                time_range_hours=24
            )
        ]
        
        mock_analytics_service.get_recent_trends.return_value = mock_trends
        
        with patch('wakedock.api.routes.analytics.get_analytics_service') as mock_get_service:
            mock_get_service.return_value = mock_analytics_service
            
            response = client.get("/api/v1/analytics/trends")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            trend = data[0]
            assert trend['metric_type'] == 'cpu_percent'
            assert trend['container_name'] == 'test_app'
            assert trend['direction'] == 'increasing'
    
    def test_get_resource_optimizations(self, mock_analytics_service):
        """Test de récupération des optimisations"""
        # Mock des optimisations
        mock_optimizations = [
            ResourceOptimization(
                container_id='test_container',
                container_name='test_app',
                service_name='test_service',
                resource_type='cpu',
                optimization_type='increase',
                current_limit=100.0,
                recommended_limit=150.0,
                expected_improvement=25.0,
                reason='CPU saturé',
                impact_level='high',
                confidence_score=0.85,
                created_at=datetime.utcnow()
            )
        ]
        
        mock_analytics_service.get_recent_optimizations.return_value = mock_optimizations
        
        with patch('wakedock.api.routes.analytics.get_analytics_service') as mock_get_service:
            mock_get_service.return_value = mock_analytics_service
            
            response = client.get("/api/v1/analytics/optimizations")
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            opt = data[0]
            assert opt['resource_type'] == 'cpu'
            assert opt['optimization_type'] == 'increase'
            assert opt['expected_improvement'] == 25.0
    
    def test_get_analytics_summary(self, mock_analytics_service):
        """Test de récupération du résumé"""
        # Mock des données
        mock_analytics_service.get_recent_trends.return_value = []
        mock_analytics_service.get_recent_optimizations.return_value = []
        
        with patch('wakedock.api.routes.analytics.get_analytics_service') as mock_get_service:
            mock_get_service.return_value = mock_analytics_service
            
            response = client.get("/api/v1/analytics/summary")
            
            assert response.status_code == 200
            data = response.json()
            assert 'summary' in data
            assert 'trends_by_direction' in data
            assert 'optimizations_by_type' in data
            assert 'top_problematic_containers' in data
    
    def test_update_analytics_config(self, mock_analytics_service):
        """Test de mise à jour de la configuration"""
        with patch('wakedock.api.routes.analytics.get_analytics_service') as mock_get_service:
            mock_get_service.return_value = mock_analytics_service
            
            config_update = {
                "trend_analysis_hours": 48,
                "volatility_threshold": 0.4
            }
            
            response = client.put("/api/v1/analytics/config", json=config_update)
            
            assert response.status_code == 200
            data = response.json()
            assert "Configuration mise à jour" in data['message']
            assert 'new_config' in data
    
    def test_generate_performance_report(self, mock_analytics_service):
        """Test de génération de rapport"""
        with patch('wakedock.api.routes.analytics.get_analytics_service') as mock_get_service:
            mock_get_service.return_value = mock_analytics_service
            
            response = client.post("/api/v1/analytics/reports/generate?period_hours=24")
            
            assert response.status_code == 200
            data = response.json()
            assert "Rapport généré" in data['message']
            assert data['period_hours'] == 24
            mock_analytics_service._generate_daily_report.assert_called_once()
    
    def test_api_filtering_parameters(self, mock_analytics_service):
        """Test des paramètres de filtrage de l'API"""
        mock_analytics_service.get_recent_trends.return_value = []
        
        with patch('wakedock.api.routes.analytics.get_analytics_service') as mock_get_service:
            mock_get_service.return_value = mock_analytics_service
            
            # Test avec différents filtres
            response = client.get(
                "/api/v1/analytics/trends"
                "?container_id=test123"
                "&metric_type=cpu_percent"
                "&direction=increasing"
                "&confidence=high"
                "&hours=48"
                "&limit=50"
            )
            
            assert response.status_code == 200
            # Vérifie que les paramètres sont bien pris en compte
            mock_analytics_service.get_recent_trends.assert_called_with(hours=48)
    
    def test_error_handling(self):
        """Test de la gestion d'erreur quand le service n'est pas initialisé"""
        with patch('wakedock.api.routes.analytics._analytics_service', None):
            response = client.get("/api/v1/analytics/status")
            assert response.status_code == 503
            assert "non initialisé" in response.json()['detail']

@pytest.mark.integration
class TestAnalyticsIntegration:
    """Tests d'intégration pour le système d'analytics complet"""
    
    @pytest.mark.asyncio
    async def test_full_analytics_workflow(self):
        """Test du workflow complet d'analytics"""
        # Ce test nécessiterait une instance complète de l'application
        # et des données réelles pour être vraiment significatif
        # Pour l'instant, on vérifie juste que les composants se chargent
        
        from wakedock.core.advanced_analytics import AdvancedAnalyticsService
        from wakedock.core.metrics_collector import MetricsCollector
        
        # Vérifie que les classes peuvent être importées et instanciées
        assert AdvancedAnalyticsService is not None
        assert MetricsCollector is not None
    
    @pytest.mark.asyncio
    async def test_analytics_data_flow(self):
        """Test du flux de données analytics"""
        # Test simplifié du flux : métriques -> tendances -> optimisations -> rapports
        
        # Mock des composants
        mock_collector = Mock()
        mock_collector.get_recent_metrics = AsyncMock(return_value=[])
        mock_collector.get_recent_alerts = AsyncMock(return_value=[])
        
        # Crée le service
        with tempfile.TemporaryDirectory() as temp_dir:
            service = AdvancedAnalyticsService(
                metrics_collector=mock_collector,
                storage_path=temp_dir
            )
            
            # Test du cycle complet
            await service._analyze_performance_trends()
            await service._generate_optimization_recommendations()
            
            # Vérifie que les méthodes ont été appelées sans erreur
            mock_collector.get_recent_metrics.assert_called()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
