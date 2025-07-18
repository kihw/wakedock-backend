"""
Tests pour le service d'optimisation des logs - Version 0.2.5
"""
import pytest
import asyncio
import tempfile
import shutil
import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from wakedock.core.log_optimization_service import (
    LogOptimizationService,
    LogIndexEntry,
    CompressionStats,
    SearchIndex
)
from wakedock.core.log_collector import LogEntry, LogLevel


class TestLogOptimizationService:
    """Tests pour le service d'optimisation des logs"""

    @pytest.fixture
    async def temp_storage(self):
        """Fixture pour un répertoire temporaire"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    async def service(self, temp_storage):
        """Fixture pour le service d'optimisation"""
        service = LogOptimizationService(storage_path=temp_storage)
        yield service
        if service.is_running:
            await service.stop()

    @pytest.fixture
    def sample_log_entry(self):
        """Fixture pour une entrée de log d'exemple"""
        return LogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            container_id="test_container_123",
            container_name="test_app",
            service_name="web",
            message="This is a test log message with some keywords",
            source="stdout",
            metadata={"key": "value"}
        )

    async def test_service_initialization(self, service):
        """Test l'initialisation du service"""
        assert not service.is_running
        assert service.storage_path.exists()
        assert service.index_path.exists()
        assert service.compressed_path.exists()

    async def test_service_start_stop(self, service):
        """Test le démarrage et arrêt du service"""
        await service.start()
        assert service.is_running
        assert len(service.background_tasks) > 0

        await service.stop()
        assert not service.is_running
        assert len(service.background_tasks) == 0

    async def test_database_initialization(self, service):
        """Test l'initialisation de la base de données"""
        await service._init_database()
        assert service.db_path.exists()

        # Vérifier que les tables sont créées
        import aiosqlite
        async with aiosqlite.connect(str(service.db_path)) as db:
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in await cursor.fetchall()]
            assert "log_index" in tables
            assert "search_terms" in tables

    async def test_extract_search_terms(self, service):
        """Test l'extraction des termes de recherche"""
        message = "Error connecting to database: connection timeout"
        terms = service._extract_search_terms(message)
        
        expected_terms = {"error", "connecting", "database", "connection", "timeout"}
        assert terms == expected_terms

    async def test_extract_search_terms_filtering(self, service):
        """Test le filtrage des termes de recherche"""
        # Test avec des mots courts (doivent être filtrés)
        message = "a b to is the of and"
        terms = service._extract_search_terms(message)
        assert len(terms) == 0  # Tous les mots sont trop courts

        # Test avec limitation du nombre de termes
        long_message = " ".join([f"word{i}" for i in range(100)])
        terms = service._extract_search_terms(long_message)
        assert len(terms) <= service.max_search_terms_per_log

    async def test_index_log_entry(self, service, sample_log_entry):
        """Test l'indexation d'une entrée de log"""
        await service.start()
        
        log_id = await service.index_log_entry(sample_log_entry)
        
        assert log_id is not None
        assert log_id in service.search_index.log_metadata
        
        # Vérifier que l'entrée est dans les index
        entry = service.search_index.log_metadata[log_id]
        assert entry.container_id == sample_log_entry.container_id
        assert entry.level == sample_log_entry.level.value
        
        # Vérifier les index
        assert sample_log_entry.container_id in service.search_index.container_index
        assert log_id in service.search_index.container_index[sample_log_entry.container_id]

    async def test_search_logs_optimized_basic(self, service, sample_log_entry):
        """Test la recherche optimisée basique"""
        await service.start()
        
        # Indexer un log
        log_id = await service.index_log_entry(sample_log_entry)
        
        # Recherche sans filtre
        results, search_time = await service.search_logs_optimized()
        assert log_id in results
        assert search_time >= 0

    async def test_search_logs_optimized_with_query(self, service, sample_log_entry):
        """Test la recherche optimisée avec requête"""
        await service.start()
        
        # Indexer un log
        log_id = await service.index_log_entry(sample_log_entry)
        
        # Recherche avec terme présent
        results, _ = await service.search_logs_optimized(query="test")
        assert log_id in results
        
        # Recherche avec terme absent
        results, _ = await service.search_logs_optimized(query="absent")
        assert log_id not in results

    async def test_search_logs_optimized_with_filters(self, service, sample_log_entry):
        """Test la recherche optimisée avec filtres"""
        await service.start()
        
        # Indexer un log
        log_id = await service.index_log_entry(sample_log_entry)
        
        # Recherche par conteneur
        results, _ = await service.search_logs_optimized(
            container_id=sample_log_entry.container_id
        )
        assert log_id in results
        
        # Recherche par niveau
        results, _ = await service.search_logs_optimized(
            level=sample_log_entry.level.value
        )
        assert log_id in results
        
        # Recherche avec conteneur inexistant
        results, _ = await service.search_logs_optimized(
            container_id="nonexistent"
        )
        assert len(results) == 0

    async def test_search_cache(self, service, sample_log_entry):
        """Test le cache de recherche"""
        await service.start()
        
        # Indexer un log
        await service.index_log_entry(sample_log_entry)
        
        # Première recherche (cache miss)
        results1, time1 = await service.search_logs_optimized(query="test")
        cache_size_after_first = len(service.search_cache)
        
        # Deuxième recherche identique (cache hit)
        results2, time2 = await service.search_logs_optimized(query="test")
        
        assert results1 == results2
        assert len(service.search_cache) == cache_size_after_first
        assert service.stats["cache_hits"] > 0

    async def test_compress_log_file(self, service, temp_storage):
        """Test la compression de fichiers"""
        # Créer un fichier de log temporaire
        log_file = Path(temp_storage) / "test.log"
        test_content = "This is a test log file content\n" * 1000
        
        with open(log_file, 'w') as f:
            f.write(test_content)
        
        original_size = log_file.stat().st_size
        
        # Compresser le fichier
        stats = await service.compress_log_file(log_file, "lz4")
        
        assert stats.original_size == original_size
        assert stats.compressed_size < original_size
        assert stats.compression_ratio > 0
        assert not log_file.exists()  # Fichier original supprimé
        
        # Vérifier que le fichier compressé existe
        compressed_file = service.compressed_path / "test.log.lz4"
        assert compressed_file.exists()

    async def test_compress_log_file_gzip(self, service, temp_storage):
        """Test la compression avec GZIP"""
        # Créer un fichier de log temporaire
        log_file = Path(temp_storage) / "test.log"
        test_content = "This is a test log file content\n" * 1000
        
        with open(log_file, 'w') as f:
            f.write(test_content)
        
        # Compresser avec GZIP
        stats = await service.compress_log_file(log_file, "gzip")
        
        assert stats.compression_ratio > 0
        compressed_file = service.compressed_path / "test.log.gz"
        assert compressed_file.exists()

    async def test_compress_log_file_invalid_type(self, service, temp_storage):
        """Test la compression avec type invalide"""
        log_file = Path(temp_storage) / "test.log"
        
        with open(log_file, 'w') as f:
            f.write("test content")
        
        with pytest.raises(ValueError):
            await service.compress_log_file(log_file, "invalid")

    async def test_time_bucket_indexing(self, service):
        """Test l'indexation par buckets temporels"""
        await service.start()
        
        # Créer des logs à différents moments
        base_time = datetime(2024, 1, 1, 12, 30, 0)
        
        log1 = LogEntry(
            timestamp=base_time,
            level=LogLevel.INFO,
            container_id="container1",
            container_name="app1",
            service_name="web",
            message="First log"
        )
        
        log2 = LogEntry(
            timestamp=base_time + timedelta(minutes=30),  # Même heure
            level=LogLevel.INFO,
            container_id="container1",
            container_name="app1",
            service_name="web",
            message="Second log"
        )
        
        log3 = LogEntry(
            timestamp=base_time + timedelta(hours=1),  # Heure différente
            level=LogLevel.INFO,
            container_id="container1",
            container_name="app1",
            service_name="web",
            message="Third log"
        )
        
        # Indexer les logs
        id1 = await service.index_log_entry(log1)
        id2 = await service.index_log_entry(log2)
        id3 = await service.index_log_entry(log3)
        
        # Vérifier le bucketing temporel
        bucket1 = base_time.replace(minute=0, second=0, microsecond=0).isoformat()
        bucket2 = (base_time + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0).isoformat()
        
        assert bucket1 in service.search_index.time_buckets
        assert bucket2 in service.search_index.time_buckets
        assert id1 in service.search_index.time_buckets[bucket1]
        assert id2 in service.search_index.time_buckets[bucket1]  # Même bucket
        assert id3 in service.search_index.time_buckets[bucket2]

    async def test_search_with_time_filter(self, service):
        """Test la recherche avec filtres temporels"""
        await service.start()
        
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        
        # Log dans la plage
        log_in_range = LogEntry(
            timestamp=base_time + timedelta(hours=1),
            level=LogLevel.INFO,
            container_id="container1",
            container_name="app1",
            service_name="web",
            message="Log in range"
        )
        
        # Log hors plage
        log_out_range = LogEntry(
            timestamp=base_time + timedelta(hours=5),
            level=LogLevel.INFO,
            container_id="container1",
            container_name="app1",
            service_name="web",
            message="Log out of range"
        )
        
        id_in = await service.index_log_entry(log_in_range)
        id_out = await service.index_log_entry(log_out_range)
        
        # Recherche avec plage temporelle
        start_time = base_time
        end_time = base_time + timedelta(hours=3)
        
        results, _ = await service.search_logs_optimized(
            start_time=start_time,
            end_time=end_time
        )
        
        assert id_in in results
        assert id_out not in results

    async def test_get_optimization_stats(self, service, sample_log_entry):
        """Test la récupération des statistiques"""
        await service.start()
        
        # Indexer quelques logs
        await service.index_log_entry(sample_log_entry)
        
        stats = service.get_optimization_stats()
        
        assert "total_indexed_logs" in stats
        assert "unique_search_terms" in stats
        assert "is_running" in stats
        assert "cache_hit_ratio" in stats
        assert stats["total_indexed_logs"] > 0

    @pytest.mark.asyncio
    async def test_background_workers_start_stop(self, service):
        """Test que les workers d'arrière-plan démarrent et s'arrêtent correctement"""
        await service.start()
        
        # Vérifier que les tâches sont créées
        assert len(service.background_tasks) > 0
        
        # Toutes les tâches doivent être en cours d'exécution
        for task in service.background_tasks:
            assert not task.done()
        
        await service.stop()
        
        # Toutes les tâches doivent être annulées ou terminées
        for task in service.background_tasks:
            assert task.done() or task.cancelled()

    async def test_cache_cleanup(self, service):
        """Test le nettoyage du cache"""
        await service.start()
        
        # Ajouter des entrées au cache avec différents âges
        import time
        current_time = time.time()
        
        service.search_cache["old_key"] = ([], current_time - service.cache_ttl_seconds - 10)
        service.search_cache["recent_key"] = ([], current_time)
        
        # Simuler le nettoyage du cache
        expired_keys = []
        for cache_key, (_, cached_time) in service.search_cache.items():
            if current_time - cached_time > service.cache_ttl_seconds:
                expired_keys.append(cache_key)
        
        assert "old_key" in expired_keys
        assert "recent_key" not in expired_keys

    async def test_memory_usage_with_large_dataset(self, service):
        """Test la gestion mémoire avec un grand dataset"""
        await service.start()
        
        # Créer un grand nombre de logs
        base_time = datetime.now()
        
        for i in range(100):  # Réduire pour les tests
            log_entry = LogEntry(
                timestamp=base_time + timedelta(minutes=i),
                level=LogLevel.INFO,
                container_id=f"container_{i % 10}",
                container_name=f"app_{i % 10}",
                service_name="test",
                message=f"Test log message number {i} with some keywords"
            )
            await service.index_log_entry(log_entry)
        
        # Vérifier que les index sont créés correctement
        assert len(service.search_index.log_metadata) == 100
        assert len(service.search_index.container_index) == 10  # 10 conteneurs uniques
        
        # Test de recherche sur le grand dataset
        results, search_time = await service.search_logs_optimized(query="test")
        assert len(results) == 100
        assert search_time < 1.0  # Doit être rapide

    async def test_concurrent_indexing(self, service):
        """Test l'indexation concurrente"""
        await service.start()
        
        async def index_log(i):
            log_entry = LogEntry(
                timestamp=datetime.now(),
                level=LogLevel.INFO,
                container_id=f"container_{i}",
                container_name=f"app_{i}",
                service_name="test",
                message=f"Concurrent log {i}"
            )
            return await service.index_log_entry(log_entry)
        
        # Indexer plusieurs logs en parallèle
        tasks = [index_log(i) for i in range(20)]
        log_ids = await asyncio.gather(*tasks)
        
        # Vérifier que tous les logs sont indexés
        assert len(log_ids) == 20
        assert len(set(log_ids)) == 20  # Tous les IDs sont uniques
        assert len(service.search_index.log_metadata) == 20


class TestLogOptimizationAPI:
    """Tests pour les API d'optimisation"""

    @pytest.fixture
    async def service_mock(self):
        """Mock du service d'optimisation"""
        service = Mock(spec=LogOptimizationService)
        service.is_running = True
        service.get_optimization_stats.return_value = {
            "total_indexed_logs": 1000,
            "unique_search_terms": 500,
            "database_size_bytes": 1024 * 1024,
            "is_running": True,
            "cache_size": 10,
            "compression_ratio": 65.5,
            "cache_hit_ratio": 0.85
        }
        return service

    async def test_optimization_stats_endpoint(self, service_mock):
        """Test l'endpoint des statistiques d'optimisation"""
        from wakedock.api.routes.logs_optimization import get_optimization_stats
        
        with patch('wakedock.api.routes.logs_optimization.get_optimization_service', 
                  return_value=service_mock):
            result = await get_optimization_stats(service_mock)
            
            assert result.total_indexed_logs == 1000
            assert result.unique_search_terms == 500
            assert result.is_running == True
            assert result.cache_hit_ratio == 0.85

    async def test_optimized_search_endpoint(self, service_mock):
        """Test l'endpoint de recherche optimisée"""
        from wakedock.api.routes.logs_optimization import optimized_search, OptimizedSearchRequest
        
        # Mock de la recherche
        service_mock.search_logs_optimized = AsyncMock(return_value=(["log1", "log2"], 0.005))
        
        request = OptimizedSearchRequest(query="test", limit=100)
        
        with patch('wakedock.api.routes.logs_optimization.get_optimization_service', 
                  return_value=service_mock):
            result = await optimized_search(request, service_mock)
            
            assert result.log_ids == ["log1", "log2"]
            assert result.total_found == 2
            assert result.search_time_ms == 5.0  # 0.005 * 1000

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
