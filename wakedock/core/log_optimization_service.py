"""
Service d'optimisation et indexation avancée pour les logs centralisés
Version 0.2.5 - Performance et stockage optimisés
"""
import asyncio
import logging
import lz4.frame
import gzip
import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any
from pathlib import Path
import aiofiles
import aiosqlite
from dataclasses import dataclass, asdict
from collections import defaultdict
import time

from wakedock.core.log_collector import LogEntry, LogLevel

logger = logging.getLogger(__name__)

@dataclass
class LogIndexEntry:
    """Entrée d'index pour recherche rapide"""
    log_id: str
    timestamp: datetime
    container_id: str
    level: str
    message_hash: str
    search_terms: Set[str]
    file_path: str
    compressed_size: int

@dataclass
class CompressionStats:
    """Statistiques de compression"""
    original_size: int
    compressed_size: int
    compression_ratio: float
    files_compressed: int
    time_taken: float

@dataclass
class SearchIndex:
    """Index de recherche optimisé"""
    term_to_logs: Dict[str, Set[str]]  # terme -> set de log_ids
    log_metadata: Dict[str, LogIndexEntry]  # log_id -> metadata
    container_index: Dict[str, Set[str]]  # container_id -> set de log_ids
    level_index: Dict[str, Set[str]]  # level -> set de log_ids
    time_buckets: Dict[str, Set[str]]  # bucket temporel -> set de log_ids

class LogOptimizationService:
    """Service d'optimisation et indexation des logs"""
    
    def __init__(self, storage_path: str = "/var/log/wakedock"):
        self.storage_path = Path(storage_path)
        self.index_path = self.storage_path / "indexes"
        self.compressed_path = self.storage_path / "compressed"
        self.db_path = self.index_path / "search_index.db"
        
        # Configuration
        self.compression_threshold_mb = 10  # Compresser les fichiers > 10MB
        self.max_search_terms_per_log = 50
        self.time_bucket_hours = 1  # Bucketing par heure
        self.retention_days = 30
        
        # Index en mémoire pour recherches rapides
        self.search_index = SearchIndex(
            term_to_logs={},
            log_metadata={},
            container_index={},
            level_index={},
            time_buckets={}
        )
        
        # Cache pour recherches fréquentes
        self.search_cache: Dict[str, Tuple[List[Dict], float]] = {}
        self.cache_ttl_seconds = 300  # 5 minutes
        
        # Statistiques
        self.stats = {
            "total_indexed_logs": 0,
            "unique_search_terms": 0,
            "database_size_bytes": 0,
            "compression_stats": CompressionStats(0, 0, 0.0, 0, 0.0),
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        # Tasks d'arrière-plan
        self.background_tasks: Set[asyncio.Task] = set()
        self.is_running = False
    
    async def start(self):
        """Démarre le service d'optimisation"""
        logger.info("Démarrage du service d'optimisation des logs")
        
        # Créer les répertoires nécessaires
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.index_path.mkdir(parents=True, exist_ok=True)
        self.compressed_path.mkdir(parents=True, exist_ok=True)
        
        # Initialiser la base de données
        await self._init_database()
        
        # Charger l'index existant
        await self._load_search_index()
        
        # Démarrer les tâches d'arrière-plan
        self.is_running = True
        
        # Compression automatique
        compression_task = asyncio.create_task(self._auto_compression_worker())
        self.background_tasks.add(compression_task)
        
        # Nettoyage du cache
        cache_cleanup_task = asyncio.create_task(self._cache_cleanup_worker())
        self.background_tasks.add(cache_cleanup_task)
        
        # Rotation et archivage
        rotation_task = asyncio.create_task(self._log_rotation_worker())
        self.background_tasks.add(rotation_task)
        
        logger.info("Service d'optimisation des logs démarré")
    
    async def stop(self):
        """Arrête le service d'optimisation"""
        logger.info("Arrêt du service d'optimisation des logs")
        
        self.is_running = False
        
        # Annuler toutes les tâches d'arrière-plan
        for task in self.background_tasks:
            task.cancel()
        
        # Attendre que toutes les tâches se terminent
        if self.background_tasks:
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
        
        self.background_tasks.clear()
        logger.info("Service d'optimisation des logs arrêté")
    
    async def _init_database(self):
        """Initialise la base de données SQLite pour l'indexation"""
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS log_index (
                    log_id TEXT PRIMARY KEY,
                    timestamp REAL,
                    container_id TEXT,
                    level TEXT,
                    message_hash TEXT,
                    search_terms TEXT,
                    file_path TEXT,
                    compressed_size INTEGER
                )
            ''')
            
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp ON log_index(timestamp)
            ''')
            
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_container ON log_index(container_id)
            ''')
            
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_level ON log_index(level)
            ''')
            
            # Table pour les termes de recherche (full-text search)
            await db.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS search_terms 
                USING fts5(log_id, terms, content='log_index', content_rowid='rowid')
            ''')
            
            await db.commit()
    
    async def _load_search_index(self):
        """Charge l'index de recherche depuis la base de données"""
        logger.info("Chargement de l'index de recherche")
        
        async with aiosqlite.connect(str(self.db_path)) as db:
            # Charger les métadonnées des logs
            async with db.execute('SELECT * FROM log_index ORDER BY timestamp DESC LIMIT 100000') as cursor:
                async for row in cursor:
                    log_id, timestamp, container_id, level, message_hash, search_terms_str, file_path, compressed_size = row
                    
                    search_terms = set(json.loads(search_terms_str))
                    
                    entry = LogIndexEntry(
                        log_id=log_id,
                        timestamp=datetime.fromtimestamp(timestamp),
                        container_id=container_id,
                        level=level,
                        message_hash=message_hash,
                        search_terms=search_terms,
                        file_path=file_path,
                        compressed_size=compressed_size
                    )
                    
                    # Ajouter à l'index en mémoire
                    self.search_index.log_metadata[log_id] = entry
                    
                    # Index par termes
                    for term in search_terms:
                        if term not in self.search_index.term_to_logs:
                            self.search_index.term_to_logs[term] = set()
                        self.search_index.term_to_logs[term].add(log_id)
                    
                    # Index par conteneur
                    if container_id not in self.search_index.container_index:
                        self.search_index.container_index[container_id] = set()
                    self.search_index.container_index[container_id].add(log_id)
                    
                    # Index par niveau
                    if level not in self.search_index.level_index:
                        self.search_index.level_index[level] = set()
                    self.search_index.level_index[level].add(log_id)
                    
                    # Index temporel (bucketing par heure)
                    time_bucket = entry.timestamp.replace(minute=0, second=0, microsecond=0).isoformat()
                    if time_bucket not in self.search_index.time_buckets:
                        self.search_index.time_buckets[time_bucket] = set()
                    self.search_index.time_buckets[time_bucket].add(log_id)
        
        # Mettre à jour les statistiques
        self.stats["total_indexed_logs"] = len(self.search_index.log_metadata)
        self.stats["unique_search_terms"] = len(self.search_index.term_to_logs)
        
        if self.db_path.exists():
            self.stats["database_size_bytes"] = self.db_path.stat().st_size
        
        logger.info(f"Index chargé: {self.stats['total_indexed_logs']} logs, {self.stats['unique_search_terms']} termes")
    
    async def index_log_entry(self, log_entry: LogEntry) -> str:
        """Indexe une nouvelle entrée de log"""
        # Générer un ID unique
        log_id = hashlib.md5(
            f"{log_entry.timestamp.isoformat()}{log_entry.container_id}{log_entry.message}".encode()
        ).hexdigest()
        
        # Hash du message pour détecter les doublons
        message_hash = hashlib.sha256(log_entry.message.encode()).hexdigest()[:16]
        
        # Extraire les termes de recherche
        search_terms = self._extract_search_terms(log_entry.message)
        
        # Créer l'entrée d'index
        index_entry = LogIndexEntry(
            log_id=log_id,
            timestamp=log_entry.timestamp,
            container_id=log_entry.container_id,
            level=log_entry.level.value,
            message_hash=message_hash,
            search_terms=search_terms,
            file_path="",  # À définir lors du stockage
            compressed_size=0
        )
        
        # Ajouter à l'index en mémoire
        self.search_index.log_metadata[log_id] = index_entry
        
        # Mettre à jour les index
        for term in search_terms:
            if term not in self.search_index.term_to_logs:
                self.search_index.term_to_logs[term] = set()
            self.search_index.term_to_logs[term].add(log_id)
        
        # Index par conteneur
        if log_entry.container_id not in self.search_index.container_index:
            self.search_index.container_index[log_entry.container_id] = set()
        self.search_index.container_index[log_entry.container_id].add(log_id)
        
        # Index par niveau
        if index_entry.level not in self.search_index.level_index:
            self.search_index.level_index[index_entry.level] = set()
        self.search_index.level_index[index_entry.level].add(log_id)
        
        # Index temporel
        time_bucket = log_entry.timestamp.replace(minute=0, second=0, microsecond=0).isoformat()
        if time_bucket not in self.search_index.time_buckets:
            self.search_index.time_buckets[time_bucket] = set()
        self.search_index.time_buckets[time_bucket].add(log_id)
        
        # Sauvegarder en base de données (en batch pour performance)
        await self._save_to_database(index_entry)
        
        # Mettre à jour les statistiques
        self.stats["total_indexed_logs"] = len(self.search_index.log_metadata)
        self.stats["unique_search_terms"] = len(self.search_index.term_to_logs)
        
        return log_id
    
    def _extract_search_terms(self, message: str) -> Set[str]:
        """Extrait les termes de recherche d'un message"""
        import re
        
        # Nettoyer et normaliser le message
        cleaned = re.sub(r'[^\w\s\-\.]', ' ', message.lower())
        
        # Extraire les mots (minimum 3 caractères)
        words = [word for word in cleaned.split() if len(word) >= 3]
        
        # Limiter le nombre de termes pour éviter l'explosion de l'index
        if len(words) > self.max_search_terms_per_log:
            words = words[:self.max_search_terms_per_log]
        
        return set(words)
    
    async def _save_to_database(self, entry: LogIndexEntry):
        """Sauvegarde une entrée d'index en base de données"""
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute('''
                INSERT OR REPLACE INTO log_index 
                (log_id, timestamp, container_id, level, message_hash, search_terms, file_path, compressed_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entry.log_id,
                entry.timestamp.timestamp(),
                entry.container_id,
                entry.level,
                entry.message_hash,
                json.dumps(list(entry.search_terms)),
                entry.file_path,
                entry.compressed_size
            ))
            
            # Ajouter aux termes de recherche FTS
            await db.execute('''
                INSERT OR REPLACE INTO search_terms (log_id, terms)
                VALUES (?, ?)
            ''', (entry.log_id, ' '.join(entry.search_terms)))
            
            await db.commit()
    
    async def search_logs_optimized(
        self,
        query: Optional[str] = None,
        container_id: Optional[str] = None,
        level: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> Tuple[List[str], float]:
        """Recherche optimisée avec cache et indexation"""
        start_time_search = time.time()
        
        # Créer une clé de cache
        cache_key = hashlib.md5(
            f"{query}{container_id}{level}{start_time}{end_time}{limit}".encode()
        ).hexdigest()
        
        # Vérifier le cache
        if cache_key in self.search_cache:
            cached_result, cached_time = self.search_cache[cache_key]
            if time.time() - cached_time < self.cache_ttl_seconds:
                self.stats["cache_hits"] += 1
                return cached_result, time.time() - start_time_search
        
        self.stats["cache_misses"] += 1
        
        # Recherche dans l'index
        matching_log_ids = set(self.search_index.log_metadata.keys())
        
        # Filtrer par termes de recherche
        if query:
            query_terms = self._extract_search_terms(query)
            query_matches = set()
            
            for term in query_terms:
                if term in self.search_index.term_to_logs:
                    if not query_matches:
                        query_matches = self.search_index.term_to_logs[term].copy()
                    else:
                        query_matches &= self.search_index.term_to_logs[term]
            
            if query_terms and query_matches:
                matching_log_ids &= query_matches
            elif query_terms:
                matching_log_ids = set()  # Aucun terme trouvé
        
        # Filtrer par conteneur
        if container_id and container_id in self.search_index.container_index:
            matching_log_ids &= self.search_index.container_index[container_id]
        elif container_id:
            matching_log_ids = set()
        
        # Filtrer par niveau
        if level and level in self.search_index.level_index:
            matching_log_ids &= self.search_index.level_index[level]
        elif level:
            matching_log_ids = set()
        
        # Filtrer par temps (utiliser les buckets pour performance)
        if start_time or end_time:
            time_matches = set()
            
            for time_bucket, log_ids in self.search_index.time_buckets.items():
                bucket_time = datetime.fromisoformat(time_bucket)
                
                include_bucket = True
                if start_time and bucket_time < start_time - timedelta(hours=1):
                    include_bucket = False
                if end_time and bucket_time > end_time + timedelta(hours=1):
                    include_bucket = False
                
                if include_bucket:
                    time_matches.update(log_ids)
            
            if time_matches:
                matching_log_ids &= time_matches
            else:
                matching_log_ids = set()
        
        # Trier par timestamp (plus récent en premier)
        sorted_log_ids = sorted(
            matching_log_ids,
            key=lambda log_id: self.search_index.log_metadata[log_id].timestamp,
            reverse=True
        )
        
        # Appliquer la limite
        result_log_ids = sorted_log_ids[:limit]
        
        search_time = time.time() - start_time_search
        
        # Mettre en cache
        self.search_cache[cache_key] = (result_log_ids, time.time())
        
        return result_log_ids, search_time
    
    async def compress_log_file(self, file_path: Path, compression_type: str = "lz4") -> CompressionStats:
        """Compresse un fichier de logs"""
        start_time = time.time()
        
        if not file_path.exists():
            raise FileNotFoundError(f"Fichier non trouvé: {file_path}")
        
        original_size = file_path.stat().st_size
        
        # Lire le contenu original
        async with aiofiles.open(file_path, 'rb') as f:
            original_data = await f.read()
        
        # Compresser selon le type
        if compression_type == "lz4":
            compressed_data = lz4.frame.compress(original_data)
            extension = ".lz4"
        elif compression_type == "gzip":
            compressed_data = gzip.compress(original_data)
            extension = ".gz"
        else:
            raise ValueError(f"Type de compression non supporté: {compression_type}")
        
        # Écrire le fichier compressé
        compressed_path = self.compressed_path / f"{file_path.name}{extension}"
        async with aiofiles.open(compressed_path, 'wb') as f:
            await f.write(compressed_data)
        
        compressed_size = len(compressed_data)
        compression_ratio = (1 - compressed_size / original_size) * 100
        time_taken = time.time() - start_time
        
        # Supprimer le fichier original après compression réussie
        file_path.unlink()
        
        stats = CompressionStats(
            original_size=original_size,
            compressed_size=compressed_size,
            compression_ratio=compression_ratio,
            files_compressed=1,
            time_taken=time_taken
        )
        
        logger.info(f"Fichier compressé: {file_path.name} ({compression_ratio:.1f}% de réduction)")
        
        return stats
    
    async def _auto_compression_worker(self):
        """Worker de compression automatique en arrière-plan"""
        while self.is_running:
            try:
                # Rechercher les fichiers à compresser
                log_files = list(self.storage_path.glob("*.log"))
                
                for log_file in log_files:
                    if not self.is_running:
                        break
                    
                    # Vérifier la taille du fichier
                    file_size_mb = log_file.stat().st_size / (1024 * 1024)
                    
                    if file_size_mb > self.compression_threshold_mb:
                        try:
                            await self.compress_log_file(log_file, "lz4")
                            
                            # Mettre à jour les statistiques
                            self.stats["compression_stats"].files_compressed += 1
                            
                        except Exception as e:
                            logger.error(f"Erreur lors de la compression de {log_file}: {e}")
                
                # Attendre avant la prochaine vérification
                await asyncio.sleep(300)  # 5 minutes
                
            except Exception as e:
                logger.error(f"Erreur dans le worker de compression: {e}")
                await asyncio.sleep(60)
    
    async def _cache_cleanup_worker(self):
        """Worker de nettoyage du cache"""
        while self.is_running:
            try:
                current_time = time.time()
                expired_keys = []
                
                for cache_key, (_, cached_time) in self.search_cache.items():
                    if current_time - cached_time > self.cache_ttl_seconds:
                        expired_keys.append(cache_key)
                
                for key in expired_keys:
                    del self.search_cache[key]
                
                if expired_keys:
                    logger.debug(f"Cache nettoyé: {len(expired_keys)} entrées expirées supprimées")
                
                await asyncio.sleep(self.cache_ttl_seconds)
                
            except Exception as e:
                logger.error(f"Erreur dans le worker de nettoyage du cache: {e}")
                await asyncio.sleep(60)
    
    async def _log_rotation_worker(self):
        """Worker de rotation et archivage des logs"""
        while self.is_running:
            try:
                cutoff_date = datetime.now() - timedelta(days=self.retention_days)
                
                # Nettoyer l'index des logs anciens
                old_log_ids = []
                for log_id, entry in self.search_index.log_metadata.items():
                    if entry.timestamp < cutoff_date:
                        old_log_ids.append(log_id)
                
                # Supprimer de l'index en mémoire
                for log_id in old_log_ids:
                    entry = self.search_index.log_metadata[log_id]
                    
                    # Supprimer des index
                    for term in entry.search_terms:
                        if term in self.search_index.term_to_logs:
                            self.search_index.term_to_logs[term].discard(log_id)
                            if not self.search_index.term_to_logs[term]:
                                del self.search_index.term_to_logs[term]
                    
                    if entry.container_id in self.search_index.container_index:
                        self.search_index.container_index[entry.container_id].discard(log_id)
                    
                    if entry.level in self.search_index.level_index:
                        self.search_index.level_index[entry.level].discard(log_id)
                    
                    # Supprimer des buckets temporels
                    time_bucket = entry.timestamp.replace(minute=0, second=0, microsecond=0).isoformat()
                    if time_bucket in self.search_index.time_buckets:
                        self.search_index.time_buckets[time_bucket].discard(log_id)
                        if not self.search_index.time_buckets[time_bucket]:
                            del self.search_index.time_buckets[time_bucket]
                    
                    del self.search_index.log_metadata[log_id]
                
                # Supprimer de la base de données
                if old_log_ids:
                    async with aiosqlite.connect(str(self.db_path)) as db:
                        placeholders = ','.join(['?' for _ in old_log_ids])
                        await db.execute(f'DELETE FROM log_index WHERE log_id IN ({placeholders})', old_log_ids)
                        await db.execute(f'DELETE FROM search_terms WHERE log_id IN ({placeholders})', old_log_ids)
                        await db.commit()
                    
                    logger.info(f"Rotation: {len(old_log_ids)} logs anciens supprimés")
                
                # Attendre avant la prochaine rotation
                await asyncio.sleep(3600)  # 1 heure
                
            except Exception as e:
                logger.error(f"Erreur dans le worker de rotation: {e}")
                await asyncio.sleep(300)
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques d'optimisation"""
        # Calculer la taille de la base de données
        if self.db_path.exists():
            self.stats["database_size_bytes"] = self.db_path.stat().st_size
        
        return {
            **self.stats,
            "is_running": self.is_running,
            "cache_size": len(self.search_cache),
            "compression_ratio": self.stats["compression_stats"].compression_ratio,
            "cache_hit_ratio": (
                self.stats["cache_hits"] / (self.stats["cache_hits"] + self.stats["cache_misses"])
                if (self.stats["cache_hits"] + self.stats["cache_misses"]) > 0 else 0
            )
        }
