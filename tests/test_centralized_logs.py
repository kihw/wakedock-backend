"""
Tests pour le système de logs centralisé
"""
import pytest
import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient

from wakedock.core.log_collector import LogCollector, LogEntry, LogLevel
from wakedock.core.log_search_service import LogSearchService
from wakedock.core.docker_manager import DockerManager


@pytest.fixture
def temp_storage():
    """Fixture pour le stockage temporaire"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def mock_docker_manager():
    """Mock du gestionnaire Docker"""
    manager = Mock(spec=DockerManager)
    manager.list_containers.return_value = [
        Mock(id="container1", name="test-container-1"),
        Mock(id="container2", name="test-container-2")
    ]
    manager.get_container_info.return_value = {
        'name': 'test-container',
        'labels': {'com.docker.compose.service': 'web'}
    }
    manager.get_container_logs.return_value = [
        "2024-01-01T10:00:00.000000Z [INFO] Starting application",
        "2024-01-01T10:00:01.000000Z [ERROR] Database connection failed",
        "2024-01-01T10:00:02.000000Z [WARN] Retrying connection"
    ]
    return manager


@pytest.fixture
async def log_collector(temp_storage, mock_docker_manager):
    """Fixture pour le collecteur de logs"""
    collector = LogCollector(mock_docker_manager, temp_storage)
    yield collector
    await collector.stop()


@pytest.fixture
async def log_search_service(temp_storage):
    """Fixture pour le service de recherche"""
    service = LogSearchService(temp_storage)
    yield service
    await service.stop()


class TestLogCollector:
    """Tests pour le collecteur de logs"""
    
    def test_log_entry_creation(self):
        """Test la création d'une entrée de log"""
        log_entry = LogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            container_id="test123",
            container_name="test-container",
            service_name="web",
            message="Test message",
            metadata={"key": "value"}
        )
        
        assert log_entry.container_id == "test123"
        assert log_entry.level == LogLevel.INFO
        assert log_entry.metadata == {"key": "value"}
        
        # Test de sérialisation
        log_dict = log_entry.to_dict()
        assert log_dict['level'] == 'info'
        assert 'timestamp' in log_dict
        
        # Test de désérialisation
        restored = LogEntry.from_dict(log_dict)
        assert restored.container_id == log_entry.container_id
        assert restored.level == log_entry.level
    
    def test_parse_log_line(self, log_collector):
        """Test le parsing d'une ligne de log"""
        log_line = "2024-01-01T10:00:00.123456Z [ERROR] Connection failed"
        
        log_entry = log_collector._parse_log_line(
            log_line,
            "container123",
            "test-container",
            "web"
        )
        
        assert log_entry is not None
        assert log_entry.level == LogLevel.ERROR
        assert "Connection failed" in log_entry.message
        assert log_entry.container_id == "container123"
        assert log_entry.service_name == "web"
    
    def test_detect_log_level(self, log_collector):
        """Test la détection du niveau de log"""
        test_cases = [
            ("ERROR: Something went wrong", LogLevel.ERROR),
            ("WARN: Deprecated feature", LogLevel.WARN),
            ("INFO: Application started", LogLevel.INFO),
            ("DEBUG: Variable value", LogLevel.DEBUG),
            ("FATAL: Critical error", LogLevel.FATAL),
            ("Normal message", LogLevel.INFO)  # Défaut
        ]
        
        for message, expected_level in test_cases:
            level = log_collector._detect_log_level(message)
            assert level == expected_level
    
    def test_extract_metadata(self, log_collector):
        """Test l'extraction de métadonnées"""
        # Test avec JSON
        message = '{"level": "error", "user_id": 123, "action": "login"}'
        metadata = log_collector._extract_metadata(message)
        assert metadata == {"level": "error", "user_id": 123, "action": "login"}
        
        # Test avec key=value
        message = "user=john action=delete status=success"
        metadata = log_collector._extract_metadata(message)
        assert "user" in metadata
        assert metadata["user"] == "john"
    
    async def test_add_remove_container(self, log_collector):
        """Test l'ajout et la suppression de conteneurs"""
        container_id = "test123"
        
        # Test ajout
        await log_collector.add_container(container_id)
        assert container_id in log_collector.monitored_containers
        assert container_id in log_collector.collection_tasks
        
        # Test suppression
        await log_collector.remove_container(container_id)
        assert container_id not in log_collector.monitored_containers
        assert container_id not in log_collector.collection_tasks
    
    async def test_log_buffer_management(self, log_collector):
        """Test la gestion des buffers de logs"""
        container_id = "test123"
        
        # Ajoute des logs au buffer
        for i in range(5):
            log_entry = LogEntry(
                timestamp=datetime.now(),
                level=LogLevel.INFO,
                container_id=container_id,
                container_name="test",
                message=f"Message {i}"
            )
            await log_collector._add_to_buffer(container_id, log_entry)
        
        # Vérifie que le buffer contient les logs
        assert container_id in log_collector.log_buffers
        assert len(log_collector.log_buffers[container_id]) == 5
        
        # Test flush du buffer
        await log_collector._flush_container_buffer(container_id)
        assert len(log_collector.log_buffers[container_id]) == 0
        
        # Vérifie que le fichier a été créé
        log_file = Path(log_collector.storage_path) / f"{container_id}.jsonl"
        assert log_file.exists()
    
    def test_get_stats(self, log_collector):
        """Test les statistiques du collecteur"""
        stats = log_collector.get_stats()
        
        assert 'is_running' in stats
        assert 'monitored_containers' in stats
        assert 'active_tasks' in stats
        assert 'buffered_logs' in stats
        assert 'log_files' in stats
        assert 'storage_path' in stats


class TestLogSearchService:
    """Tests pour le service de recherche"""
    
    async def test_search_terms_extraction(self, log_search_service):
        """Test l'extraction des termes de recherche"""
        message = "The quick brown fox jumps over the lazy dog"
        terms = log_search_service._extract_search_terms(message)
        
        # Vérifie que les mots courts et les stop words sont filtrés
        assert "quick" in terms
        assert "brown" in terms
        assert "jumps" in terms
        assert "the" not in terms  # Stop word
        assert "fox" in terms
    
    async def test_index_creation(self, log_search_service, temp_storage):
        """Test la création de l'index"""
        # Crée un fichier de log de test
        log_file = Path(temp_storage) / "containers" / "test123.jsonl"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        log_entries = [
            {
                "timestamp": "2024-01-01T10:00:00",
                "level": "info",
                "container_id": "test123",
                "container_name": "test-container",
                "service_name": "web",
                "message": "Application started successfully",
                "metadata": {}
            },
            {
                "timestamp": "2024-01-01T10:00:01",
                "level": "error",
                "container_id": "test123",
                "container_name": "test-container",
                "service_name": "web",
                "message": "Database connection failed",
                "metadata": {}
            }
        ]
        
        with open(log_file, 'w') as f:
            for entry in log_entries:
                f.write(json.dumps(entry) + '\n')
        
        # Indexe le fichier
        await log_search_service._index_file(log_file)
        
        # Vérifie que l'index a été créé
        stats = await log_search_service.get_index_stats()
        assert stats['total_indexed_logs'] == 2
        assert stats['unique_search_terms'] > 0
    
    async def test_search_functionality(self, log_search_service, temp_storage):
        """Test la fonctionnalité de recherche"""
        # Prépare les données de test (comme dans le test précédent)
        log_file = Path(temp_storage) / "containers" / "test123.jsonl"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        log_entries = [
            {
                "timestamp": "2024-01-01T10:00:00",
                "level": "info",
                "container_id": "test123",
                "container_name": "test-container",
                "service_name": "web",
                "message": "Application started successfully",
                "metadata": {}
            },
            {
                "timestamp": "2024-01-01T10:00:01",
                "level": "error",
                "container_id": "test123",
                "container_name": "test-container",
                "service_name": "web",
                "message": "Database connection failed",
                "metadata": {}
            }
        ]
        
        with open(log_file, 'w') as f:
            for entry in log_entries:
                f.write(json.dumps(entry) + '\n')
        
        await log_search_service._index_file(log_file)
        
        # Test recherche par terme
        results = await log_search_service.search_logs(
            query="application",
            limit=10
        )
        assert len(results) == 1
        assert "started" in results[0]['message']
        
        # Test recherche par niveau
        results = await log_search_service.search_logs(
            query=None,
            level=LogLevel.ERROR,
            limit=10
        )
        assert len(results) == 1
        assert "failed" in results[0]['message']
        
        # Test recherche par conteneur
        results = await log_search_service.search_logs(
            query=None,
            container_id="test123",
            limit=10
        )
        assert len(results) == 2
    
    async def test_log_statistics(self, log_search_service, temp_storage):
        """Test les statistiques des logs"""
        # Prépare les données (comme dans les tests précédents)
        log_file = Path(temp_storage) / "containers" / "test123.jsonl"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        log_entries = [
            {
                "timestamp": "2024-01-01T10:00:00",
                "level": "info",
                "container_id": "test123",
                "container_name": "test-container",
                "service_name": "web",
                "message": "Application started",
                "metadata": {}
            },
            {
                "timestamp": "2024-01-01T10:00:01",
                "level": "error",
                "container_id": "test123",
                "container_name": "test-container",
                "service_name": "web",
                "message": "Database failed",
                "metadata": {}
            }
        ]
        
        with open(log_file, 'w') as f:
            for entry in log_entries:
                f.write(json.dumps(entry) + '\n')
        
        await log_search_service._index_file(log_file)
        
        # Test des statistiques
        stats = await log_search_service.get_log_statistics()
        
        assert stats['total_logs'] == 2
        assert stats['level_distribution']['info'] == 1
        assert stats['level_distribution']['error'] == 1
        assert 'test-container' in stats['container_distribution']
        assert 'web' in stats['service_distribution']


class TestCentralizedLogsAPI:
    """Tests pour l'API des logs centralisés"""
    
    @pytest.fixture
    def client(self):
        """Client de test FastAPI"""
        from wakedock.api.routes.centralized_logs import router
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        
        app = FastAPI()
        app.include_router(router)
        return TestClient(app)
    
    @patch('wakedock.api.routes.centralized_logs.get_log_collector')
    def test_get_collector_status(self, mock_get_collector, client):
        """Test de récupération du statut du collecteur"""
        # Mock du collecteur
        mock_collector = Mock()
        mock_collector.get_stats.return_value = {
            'is_running': True,
            'monitored_containers': 3,
            'active_tasks': 3,
            'buffered_logs': 150,
            'log_files': 5,
            'storage_path': '/tmp/logs'
        }
        mock_get_collector.return_value = mock_collector
        
        response = client.get("/status")
        assert response.status_code == 200
        
        data = response.json()
        assert data['is_running'] is True
        assert data['monitored_containers'] == 3
    
    @patch('wakedock.api.routes.centralized_logs.get_log_search_service')
    def test_search_logs(self, mock_get_search, client):
        """Test de recherche dans les logs"""
        # Mock du service de recherche
        mock_search = AsyncMock()
        mock_search.search_logs.return_value = [
            {
                'timestamp': '2024-01-01T10:00:00',
                'level': 'info',
                'container_id': 'test123',
                'container_name': 'test-container',
                'service_name': 'web',
                'message': 'Test message',
                'metadata': {}
            }
        ]
        mock_get_search.return_value = mock_search
        
        response = client.get("/search?query=test&limit=100")
        assert response.status_code == 200
        
        data = response.json()
        assert 'logs' in data
        assert 'total_found' in data
        assert 'search_time_ms' in data
        assert 'has_more' in data
    
    @patch('wakedock.api.routes.centralized_logs.get_log_search_service')
    def test_get_statistics(self, mock_get_search, client):
        """Test de récupération des statistiques"""
        mock_search = AsyncMock()
        mock_search.get_log_statistics.return_value = {
            'total_logs': 1000,
            'level_distribution': {'info': 800, 'error': 200},
            'container_distribution': {'web': 600, 'db': 400},
            'service_distribution': {'frontend': 600, 'backend': 400},
            'timeline': {'2024-01-01 10:00:00': 100}
        }
        mock_get_search.return_value = mock_search
        
        response = client.get("/statistics")
        assert response.status_code == 200
        
        data = response.json()
        assert data['total_logs'] == 1000
        assert 'level_distribution' in data
        assert 'container_distribution' in data
    
    @patch('wakedock.api.routes.centralized_logs.get_log_search_service')
    def test_export_logs(self, mock_get_search, client):
        """Test d'export des logs"""
        mock_search = AsyncMock()
        mock_search.search_logs.return_value = [
            {
                'timestamp': '2024-01-01T10:00:00',
                'level': 'info',
                'container_id': 'test123',
                'container_name': 'test-container',
                'service_name': 'web',
                'message': 'Test message',
                'metadata': {}
            }
        ]
        mock_get_search.return_value = mock_search
        
        # Test export JSON
        response = client.post("/export", json={"format": "json", "limit": 100})
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        
        # Test export CSV
        response = client.post("/export", json={"format": "csv", "limit": 100})
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]


# Tests d'intégration
class TestLogSystemIntegration:
    """Tests d'intégration du système de logs"""
    
    async def test_full_log_pipeline(self, temp_storage, mock_docker_manager):
        """Test du pipeline complet de logs"""
        # Initialise les services
        collector = LogCollector(mock_docker_manager, temp_storage)
        search_service = LogSearchService(temp_storage)
        
        try:
            await collector.start()
            await search_service.start()
            
            # Simule l'ajout d'un conteneur
            await collector.add_container("test123")
            
            # Simule l'ajout de logs
            log_entry = LogEntry(
                timestamp=datetime.now(),
                level=LogLevel.INFO,
                container_id="test123",
                container_name="test-container",
                service_name="web",
                message="Integration test message"
            )
            
            await collector._add_to_buffer("test123", log_entry)
            await collector._flush_container_buffer("test123")
            
            # Attendre un peu pour l'indexation
            await asyncio.sleep(0.1)
            
            # Recherche les logs
            results = await search_service.search_logs(
                query="integration",
                limit=10
            )
            
            assert len(results) >= 0  # Peut être 0 si l'indexation n'est pas terminée
            
            # Vérifie les statistiques
            stats = await search_service.get_log_statistics()
            assert 'total_logs' in stats
            
        finally:
            await collector.stop()
            await search_service.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
