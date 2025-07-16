"""
Service d'indexation pour la recherche rapide dans les logs
"""
import asyncio
import logging
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path
import aiosqlite
from dataclasses import dataclass

from wakedock.core.log_collector import LogEntry, LogLevel

logger = logging.getLogger(__name__)

@dataclass
class LogIndex:
    """Index d'un log pour la recherche"""
    id: int
    container_id: str
    container_name: str
    service_name: Optional[str]
    timestamp: datetime
    level: LogLevel
    message_hash: str
    file_path: str
    line_number: int
    
class LogSearchService:
    """Service de recherche indexée dans les logs"""
    
    def __init__(self, storage_path: str = "/var/log/wakedock", db_path: str = None):
        self.storage_path = Path(storage_path)
        self.db_path = db_path or str(self.storage_path / "logs_index.db")
        
        # Configuration de l'indexation
        self.index_batch_size = 1000
        self.reindex_interval = 3600  # 1 heure
        
        # État du service
        self.is_running = False
        self.indexing_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Démarre le service d'indexation"""
        if self.is_running:
            return
            
        logger.info("Démarrage du service d'indexation des logs")
        self.is_running = True
        
        # Initialise la base de données
        await self._init_database()
        
        # Démarre la tâche d'indexation continue
        self.indexing_task = asyncio.create_task(self._indexing_worker())
        
        # Indexation initiale
        await self._reindex_all()
    
    async def stop(self):
        """Arrête le service d'indexation"""
        if not self.is_running:
            return
            
        logger.info("Arrêt du service d'indexation des logs")
        self.is_running = False
        
        if self.indexing_task:
            self.indexing_task.cancel()
    
    async def _init_database(self):
        """Initialise la base de données SQLite pour l'index"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS log_index (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    container_id TEXT NOT NULL,
                    container_name TEXT NOT NULL,
                    service_name TEXT,
                    timestamp DATETIME NOT NULL,
                    level TEXT NOT NULL,
                    message_hash TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    line_number INTEGER NOT NULL,
                    indexed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(file_path, line_number)
                )
            """)
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS log_search_index (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    log_id INTEGER NOT NULL,
                    term TEXT NOT NULL,
                    frequency INTEGER DEFAULT 1,
                    FOREIGN KEY (log_id) REFERENCES log_index (id) ON DELETE CASCADE
                )
            """)
            
            # Index pour améliorer les performances
            await db.execute("CREATE INDEX IF NOT EXISTS idx_container_id ON log_index (container_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON log_index (timestamp)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_level ON log_index (level)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_service_name ON log_index (service_name)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_search_term ON log_search_index (term)")
            
            await db.commit()
    
    async def _indexing_worker(self):
        """Worker qui effectue l'indexation continue"""
        while self.is_running:
            try:
                await asyncio.sleep(self.reindex_interval)
                await self._incremental_index()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur dans l'indexing worker: {e}")
    
    async def _reindex_all(self):
        """Réindexe tous les fichiers de logs"""
        logger.info("Démarrage de la réindexation complète")
        
        # Nettoie l'index existant
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM log_search_index")
            await db.execute("DELETE FROM log_index")
            await db.commit()
        
        # Indexe tous les fichiers
        log_files = list(self.storage_path.glob("containers/*.jsonl"))
        for log_file in log_files:
            await self._index_file(log_file)
        
        logger.info(f"Réindexation complète terminée: {len(log_files)} fichiers")
    
    async def _incremental_index(self):
        """Indexation incrémentale des nouveaux logs"""
        logger.debug("Démarrage de l'indexation incrémentale")
        
        # Trouve les fichiers modifiés récemment
        cutoff_time = datetime.utcnow() - timedelta(hours=2)
        
        log_files = []
        for log_file in self.storage_path.glob("containers/*.jsonl"):
            if datetime.fromtimestamp(log_file.stat().st_mtime) > cutoff_time:
                log_files.append(log_file)
        
        # Indexe les fichiers modifiés
        for log_file in log_files:
            await self._index_file(log_file, incremental=True)
        
        if log_files:
            logger.debug(f"Indexation incrémentale terminée: {len(log_files)} fichiers")
    
    async def _index_file(self, log_file: Path, incremental: bool = False):
        """Indexe un fichier de logs"""
        try:
            # Récupère la dernière ligne indexée pour ce fichier
            last_line = 0
            if incremental:
                async with aiosqlite.connect(self.db_path) as db:
                    cursor = await db.execute(
                        "SELECT MAX(line_number) FROM log_index WHERE file_path = ?",
                        (str(log_file),)
                    )
                    result = await cursor.fetchone()
                    if result and result[0]:
                        last_line = result[0]
            
            # Lit et indexe les nouvelles lignes
            batch = []
            current_line = 0
            
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    current_line += 1
                    
                    # Skip les lignes déjà indexées
                    if current_line <= last_line:
                        continue
                    
                    try:
                        log_data = json.loads(line.strip())
                        log_entry = LogEntry.from_dict(log_data)
                        
                        # Ajoute au batch
                        batch.append((log_entry, current_line))
                        
                        # Flush le batch si plein
                        if len(batch) >= self.index_batch_size:
                            await self._index_batch(batch, str(log_file))
                            batch.clear()
                            
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        logger.warning(f"Ligne de log invalide ignorée: {e}")
                        continue
            
            # Flush le dernier batch
            if batch:
                await self._index_batch(batch, str(log_file))
            
            logger.debug(f"Indexation du fichier {log_file}: {current_line - last_line} nouvelles lignes")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'indexation du fichier {log_file}: {e}")
    
    async def _index_batch(self, batch: List[Tuple[LogEntry, int]], file_path: str):
        """Indexe un batch de logs"""
        async with aiosqlite.connect(self.db_path) as db:
            # Insère les entrées dans l'index principal
            log_entries = []
            search_entries = []
            
            for log_entry, line_number in batch:
                # Hash du message pour déduplication
                import hashlib
                message_hash = hashlib.md5(log_entry.message.encode()).hexdigest()
                
                log_entries.append((
                    log_entry.container_id,
                    log_entry.container_name,
                    log_entry.service_name,
                    log_entry.timestamp.isoformat(),
                    log_entry.level.value,
                    message_hash,
                    file_path,
                    line_number
                ))
            
            # Insère en batch
            await db.executemany("""
                INSERT OR REPLACE INTO log_index 
                (container_id, container_name, service_name, timestamp, level, message_hash, file_path, line_number)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, log_entries)
            
            await db.commit()
            
            # Récupère les IDs des logs insérés pour l'index de recherche
            for i, (log_entry, line_number) in enumerate(batch):
                cursor = await db.execute(
                    "SELECT id FROM log_index WHERE file_path = ? AND line_number = ?",
                    (file_path, line_number)
                )
                result = await cursor.fetchone()
                if result:
                    log_id = result[0]
                    
                    # Extrait les termes de recherche
                    terms = self._extract_search_terms(log_entry.message)
                    for term in terms:
                        search_entries.append((log_id, term))
            
            # Insère les termes de recherche
            if search_entries:
                await db.executemany("""
                    INSERT OR IGNORE INTO log_search_index (log_id, term)
                    VALUES (?, ?)
                """, search_entries)
                
                await db.commit()
    
    def _extract_search_terms(self, message: str) -> Set[str]:
        """Extrait les termes de recherche d'un message"""
        import re
        
        # Normalise le message
        message = message.lower()
        
        # Extrait les mots (minimum 3 caractères)
        words = set(re.findall(r'\b\w{3,}\b', message))
        
        # Filtre les mots courants (stop words)
        stop_words = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'who', 'boy', 'did', 'come', 'from', 'into', 'like', 'make', 'many', 'over', 'such', 'take', 'than', 'them', 'time', 'very', 'when', 'with'
        }
        
        return words - stop_words
    
    async def search_logs(self, 
                         query: str,
                         container_id: Optional[str] = None,
                         service_name: Optional[str] = None,
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None,
                         level: Optional[LogLevel] = None,
                         limit: int = 1000) -> List[Dict]:
        """Recherche dans les logs indexés"""
        
        # Construit la requête SQL
        sql_parts = []
        params = []
        
        # Recherche par terme
        if query:
            query_terms = self._extract_search_terms(query)
            if query_terms:
                # Utilise l'index de recherche pour la performance
                sql_parts.append("""
                    li.id IN (
                        SELECT DISTINCT lsi.log_id 
                        FROM log_search_index lsi 
                        WHERE lsi.term IN ({})
                    )
                """.format(','.join('?' * len(query_terms))))
                params.extend(query_terms)
        
        # Filtres additionnels
        if container_id:
            sql_parts.append("li.container_id = ?")
            params.append(container_id)
        
        if service_name:
            sql_parts.append("li.service_name = ?")
            params.append(service_name)
        
        if start_time:
            sql_parts.append("li.timestamp >= ?")
            params.append(start_time.isoformat())
        
        if end_time:
            sql_parts.append("li.timestamp <= ?")
            params.append(end_time.isoformat())
        
        if level:
            sql_parts.append("li.level = ?")
            params.append(level.value)
        
        # Construit la requête finale
        where_clause = " AND ".join(sql_parts) if sql_parts else "1=1"
        
        sql = f"""
            SELECT li.container_id, li.container_name, li.service_name, 
                   li.timestamp, li.level, li.file_path, li.line_number
            FROM log_index li
            WHERE {where_clause}
            ORDER BY li.timestamp DESC
            LIMIT ?
        """
        params.append(limit)
        
        # Exécute la requête
        results = []
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
            
            for row in rows:
                container_id, container_name, service_name, timestamp, level, file_path, line_number = row
                
                # Lit le log original depuis le fichier
                try:
                    log_content = await self._read_log_line(file_path, line_number)
                    if log_content:
                        results.append({
                            'container_id': container_id,
                            'container_name': container_name,
                            'service_name': service_name,
                            'timestamp': timestamp,
                            'level': level,
                            'message': log_content.get('message', ''),
                            'metadata': log_content.get('metadata', {}),
                            'file_path': file_path,
                            'line_number': line_number
                        })
                except Exception as e:
                    logger.warning(f"Erreur lors de la lecture du log {file_path}:{line_number}: {e}")
        
        return results
    
    async def _read_log_line(self, file_path: str, line_number: int) -> Optional[Dict]:
        """Lit une ligne spécifique d'un fichier de log"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f, 1):
                    if i == line_number:
                        return json.loads(line.strip())
            return None
        except Exception as e:
            logger.warning(f"Erreur lors de la lecture de {file_path}:{line_number}: {e}")
            return None
    
    async def get_log_statistics(self, 
                               container_id: Optional[str] = None,
                               start_time: Optional[datetime] = None,
                               end_time: Optional[datetime] = None) -> Dict:
        """Récupère les statistiques des logs"""
        
        # Construit les filtres
        where_parts = []
        params = []
        
        if container_id:
            where_parts.append("container_id = ?")
            params.append(container_id)
        
        if start_time:
            where_parts.append("timestamp >= ?")
            params.append(start_time.isoformat())
        
        if end_time:
            where_parts.append("timestamp <= ?")
            params.append(end_time.isoformat())
        
        where_clause = " AND ".join(where_parts) if where_parts else "1=1"
        
        # Récupère les statistiques
        async with aiosqlite.connect(self.db_path) as db:
            # Nombre total de logs
            cursor = await db.execute(
                f"SELECT COUNT(*) FROM log_index WHERE {where_clause}",
                params
            )
            total_logs = (await cursor.fetchone())[0]
            
            # Répartition par niveau
            cursor = await db.execute(
                f"SELECT level, COUNT(*) FROM log_index WHERE {where_clause} GROUP BY level",
                params
            )
            level_distribution = dict(await cursor.fetchall())
            
            # Répartition par conteneur
            cursor = await db.execute(
                f"SELECT container_name, COUNT(*) FROM log_index WHERE {where_clause} GROUP BY container_name ORDER BY COUNT(*) DESC LIMIT 10",
                params
            )
            container_distribution = dict(await cursor.fetchall())
            
            # Répartition par service
            cursor = await db.execute(
                f"SELECT service_name, COUNT(*) FROM log_index WHERE {where_clause} AND service_name IS NOT NULL GROUP BY service_name ORDER BY COUNT(*) DESC LIMIT 10",
                params
            )
            service_distribution = dict(await cursor.fetchall())
            
            # Timeline (logs par heure)
            cursor = await db.execute(
                f"""
                SELECT strftime('%Y-%m-%d %H:00:00', timestamp) as hour, COUNT(*)
                FROM log_index 
                WHERE {where_clause}
                GROUP BY hour 
                ORDER BY hour DESC 
                LIMIT 24
                """,
                params
            )
            timeline = dict(await cursor.fetchall())
        
        return {
            'total_logs': total_logs,
            'level_distribution': level_distribution,
            'container_distribution': container_distribution,
            'service_distribution': service_distribution,
            'timeline': timeline
        }
    
    async def get_index_stats(self) -> Dict:
        """Récupère les statistiques de l'index"""
        async with aiosqlite.connect(self.db_path) as db:
            # Nombre total d'entrées indexées
            cursor = await db.execute("SELECT COUNT(*) FROM log_index")
            total_indexed = (await cursor.fetchone())[0]
            
            # Nombre de termes de recherche
            cursor = await db.execute("SELECT COUNT(DISTINCT term) FROM log_search_index")
            unique_terms = (await cursor.fetchone())[0]
            
            # Taille de la base de données
            db_size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
            
            return {
                'total_indexed_logs': total_indexed,
                'unique_search_terms': unique_terms,
                'database_size_bytes': db_size,
                'is_running': self.is_running
            }
