"""
Service de collecte de logs centralisé pour les conteneurs Docker
"""
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, AsyncGenerator, Set
from pathlib import Path
import aiofiles
from dataclasses import dataclass, asdict
from enum import Enum

from wakedock.core.docker_manager import DockerManager

logger = logging.getLogger(__name__)

class LogLevel(Enum):
    """Niveaux de logs supportés"""
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"

@dataclass
class LogEntry:
    """Entrée de log structurée"""
    timestamp: datetime
    level: LogLevel
    container_id: str
    container_name: str
    service_name: Optional[str]
    message: str
    source: str = "stdout"
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict:
        """Convertit l'entrée en dictionnaire"""
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat(),
            'level': self.level.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'LogEntry':
        """Crée une entrée depuis un dictionnaire"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        data['level'] = LogLevel(data['level'])
        return cls(**data)

class LogCollector:
    """Collecteur de logs pour les conteneurs Docker"""
    
    def __init__(self, docker_manager: DockerManager, storage_path: str = "/var/log/wakedock/containers"):
        self.docker_manager = docker_manager
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # État du collecteur
        self.is_running = False
        self.monitored_containers: Set[str] = set()
        self.collection_tasks: Dict[str, asyncio.Task] = {}
        
        # Configuration
        self.max_log_size = 100 * 1024 * 1024  # 100MB par fichier
        self.rotation_count = 5  # Garder 5 fichiers rotés
        self.buffer_size = 1000  # Buffer de 1000 logs en mémoire
        self.flush_interval = 10  # Flush toutes les 10 secondes
        
        # Buffers en mémoire
        self.log_buffers: Dict[str, List[LogEntry]] = {}
        
        # Tâches de fond
        self.flush_task: Optional[asyncio.Task] = None
        self.rotation_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Démarre la collecte de logs"""
        if self.is_running:
            return
        
        logger.info("Démarrage du collecteur de logs")
        self.is_running = True
        
        # Démarre les tâches de fond
        self.flush_task = asyncio.create_task(self._flush_worker())
        self.rotation_task = asyncio.create_task(self._rotation_worker())
        
        # Découvre et surveille les conteneurs existants
        await self._discover_containers()
    
    async def stop(self):
        """Arrête la collecte de logs"""
        if not self.is_running:
            return
        
        logger.info("Arrêt du collecteur de logs")
        self.is_running = False
        
        # Arrête toutes les tâches de collecte
        for task in self.collection_tasks.values():
            task.cancel()
        
        # Arrête les tâches de fond
        if self.flush_task:
            self.flush_task.cancel()
        if self.rotation_task:
            self.rotation_task.cancel()
        
        # Flush final des buffers
        await self._flush_all_buffers()
        
        # Nettoie l'état
        self.collection_tasks.clear()
        self.monitored_containers.clear()
        self.log_buffers.clear()
    
    async def add_container(self, container_id: str):
        """Ajoute un conteneur à surveiller"""
        if container_id in self.monitored_containers:
            return
        
        logger.info(f"Ajout de la surveillance du conteneur {container_id}")
        self.monitored_containers.add(container_id)
        
        # Démarre la collecte pour ce conteneur
        task = asyncio.create_task(self._collect_container_logs(container_id))
        self.collection_tasks[container_id] = task
    
    async def remove_container(self, container_id: str):
        """Retire un conteneur de la surveillance"""
        if container_id not in self.monitored_containers:
            return
        
        logger.info(f"Retrait de la surveillance du conteneur {container_id}")
        self.monitored_containers.remove(container_id)
        
        # Arrête la tâche de collecte
        if container_id in self.collection_tasks:
            self.collection_tasks[container_id].cancel()
            del self.collection_tasks[container_id]
        
        # Flush final du buffer
        if container_id in self.log_buffers:
            await self._flush_container_buffer(container_id)
    
    async def _discover_containers(self):
        """Découvre les conteneurs en cours d'exécution"""
        try:
            containers = self.docker_manager.list_containers(all=False)
            for container in containers:
                await self.add_container(container.id)
        except Exception as e:
            logger.error(f"Erreur lors de la découverte des conteneurs: {e}")
    
    async def _collect_container_logs(self, container_id: str):
        """Collecte les logs d'un conteneur spécifique"""
        try:
            container_info = self.docker_manager.get_container_info(container_id)
            if not container_info:
                logger.warning(f"Conteneur {container_id} non trouvé")
                return
            
            container_name = container_info.get('name', container_id[:12])
            service_name = container_info.get('labels', {}).get('com.docker.compose.service')
            
            logger.info(f"Démarrage de la collecte de logs pour {container_name}")
            
            # Stream les logs en continu
            logs_stream = self.docker_manager.get_container_logs(
                container_id,
                follow=True,
                timestamps=True,
                since='1h'  # Dernière heure pour éviter l'overload initial
            )
            
            for log_line in logs_stream:
                if not self.is_running or container_id not in self.monitored_containers:
                    break
                
                try:
                    # Parse la ligne de log
                    log_entry = self._parse_log_line(
                        log_line, 
                        container_id, 
                        container_name, 
                        service_name
                    )
                    
                    if log_entry:
                        # Ajoute au buffer
                        await self._add_to_buffer(container_id, log_entry)
                        
                except Exception as e:
                    logger.warning(f"Erreur lors du parsing du log {container_id}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Erreur lors de la collecte des logs du conteneur {container_id}: {e}")
        finally:
            # Nettoie les ressources
            if container_id in self.monitored_containers:
                self.monitored_containers.remove(container_id)
            if container_id in self.collection_tasks:
                del self.collection_tasks[container_id]
    
    def _parse_log_line(self, log_line: str, container_id: str, container_name: str, service_name: Optional[str]) -> Optional[LogEntry]:
        """Parse une ligne de log Docker"""
        try:
            # Décode les bytes si nécessaire
            if isinstance(log_line, bytes):
                log_line = log_line.decode('utf-8', errors='ignore')
            
            # Parse le timestamp Docker (format: 2025-07-16T10:30:45.123456789Z message)
            parts = log_line.strip().split(' ', 1)
            if len(parts) < 2:
                return None
            
            timestamp_str, message = parts
            
            # Parse le timestamp
            try:
                # Enlève le Z final et les nanosecondes excessives
                if timestamp_str.endswith('Z'):
                    timestamp_str = timestamp_str[:-1]
                if '.' in timestamp_str:
                    base, microseconds = timestamp_str.split('.')
                    # Limite aux microsecondes (6 chiffres)
                    microseconds = microseconds[:6].ljust(6, '0')
                    timestamp_str = f"{base}.{microseconds}"
                
                timestamp = datetime.fromisoformat(timestamp_str)
            except ValueError:
                # Fallback: utilise le timestamp actuel
                timestamp = datetime.utcnow()
            
            # Détecte le niveau de log depuis le message
            level = self._detect_log_level(message)
            
            # Extrait les métadonnées du message si possible
            metadata = self._extract_metadata(message)
            
            return LogEntry(
                timestamp=timestamp,
                level=level,
                container_id=container_id,
                container_name=container_name,
                service_name=service_name,
                message=message.strip(),
                metadata=metadata
            )
            
        except Exception as e:
            logger.warning(f"Erreur lors du parsing de la ligne de log: {e}")
            return None
    
    def _detect_log_level(self, message: str) -> LogLevel:
        """Détecte le niveau de log depuis le message"""
        message_lower = message.lower()
        
        if any(keyword in message_lower for keyword in ['fatal', 'panic', 'critical']):
            return LogLevel.FATAL
        elif any(keyword in message_lower for keyword in ['error', 'err', 'exception', 'failed']):
            return LogLevel.ERROR
        elif any(keyword in message_lower for keyword in ['warn', 'warning', 'deprecated']):
            return LogLevel.WARN
        elif any(keyword in message_lower for keyword in ['info', 'information']):
            return LogLevel.INFO
        elif any(keyword in message_lower for keyword in ['debug', 'dbg']):
            return LogLevel.DEBUG
        elif any(keyword in message_lower for keyword in ['trace']):
            return LogLevel.TRACE
        else:
            return LogLevel.INFO  # Défaut
    
    def _extract_metadata(self, message: str) -> Dict:
        """Extrait les métadonnées depuis le message"""
        metadata = {}
        
        # Détecte les formats JSON dans le message
        try:
            if message.strip().startswith('{') and message.strip().endswith('}'):
                parsed = json.loads(message)
                if isinstance(parsed, dict):
                    return parsed
        except json.JSONDecodeError:
            pass
        
        # Détecte les formats key=value
        import re
        kv_pattern = r'(\w+)=([^\s]+)'
        matches = re.findall(kv_pattern, message)
        for key, value in matches:
            metadata[key] = value
        
        return metadata
    
    async def _add_to_buffer(self, container_id: str, log_entry: LogEntry):
        """Ajoute une entrée au buffer"""
        if container_id not in self.log_buffers:
            self.log_buffers[container_id] = []
        
        self.log_buffers[container_id].append(log_entry)
        
        # Flush si le buffer est plein
        if len(self.log_buffers[container_id]) >= self.buffer_size:
            await self._flush_container_buffer(container_id)
    
    async def _flush_worker(self):
        """Worker qui flush les buffers périodiquement"""
        while self.is_running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self._flush_all_buffers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur dans le flush worker: {e}")
    
    async def _flush_all_buffers(self):
        """Flush tous les buffers vers le stockage"""
        for container_id in list(self.log_buffers.keys()):
            await self._flush_container_buffer(container_id)
    
    async def _flush_container_buffer(self, container_id: str):
        """Flush le buffer d'un conteneur vers le fichier"""
        if container_id not in self.log_buffers or not self.log_buffers[container_id]:
            return
        
        try:
            log_file = self.storage_path / f"{container_id}.jsonl"
            
            # Écrit les logs en mode append
            async with aiofiles.open(log_file, 'a', encoding='utf-8') as f:
                for log_entry in self.log_buffers[container_id]:
                    await f.write(json.dumps(log_entry.to_dict()) + '\n')
            
            # Vide le buffer
            log_count = len(self.log_buffers[container_id])
            self.log_buffers[container_id].clear()
            
            logger.debug(f"Flush de {log_count} logs pour {container_id}")
            
        except Exception as e:
            logger.error(f"Erreur lors du flush du buffer {container_id}: {e}")
    
    async def _rotation_worker(self):
        """Worker qui effectue la rotation des logs"""
        while self.is_running:
            try:
                # Vérifie toutes les heures
                await asyncio.sleep(3600)
                await self._rotate_logs()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur dans le rotation worker: {e}")
    
    async def _rotate_logs(self):
        """Effectue la rotation des logs volumineux"""
        for log_file in self.storage_path.glob("*.jsonl"):
            try:
                if log_file.stat().st_size > self.max_log_size:
                    await self._rotate_log_file(log_file)
            except Exception as e:
                logger.error(f"Erreur lors de la rotation de {log_file}: {e}")
    
    async def _rotate_log_file(self, log_file: Path):
        """Effectue la rotation d'un fichier de log"""
        base_name = log_file.stem
        
        # Déplace les anciens fichiers rotés
        for i in range(self.rotation_count - 1, 0, -1):
            old_file = self.storage_path / f"{base_name}.{i}.jsonl"
            new_file = self.storage_path / f"{base_name}.{i + 1}.jsonl"
            
            if old_file.exists():
                if new_file.exists():
                    new_file.unlink()
                old_file.rename(new_file)
        
        # Déplace le fichier actuel vers .1
        rotated_file = self.storage_path / f"{base_name}.1.jsonl"
        if rotated_file.exists():
            rotated_file.unlink()
        log_file.rename(rotated_file)
        
        logger.info(f"Rotation du fichier de log {log_file}")
    
    async def get_logs(self, 
                      container_id: Optional[str] = None,
                      start_time: Optional[datetime] = None,
                      end_time: Optional[datetime] = None,
                      level: Optional[LogLevel] = None,
                      limit: int = 1000) -> AsyncGenerator[LogEntry, None]:
        """Récupère les logs avec filtrage"""
        
        # Détermine les fichiers à lire
        files_to_read = []
        if container_id:
            # Fichiers pour un conteneur spécifique
            base_pattern = f"{container_id}*.jsonl"
            files_to_read = list(self.storage_path.glob(base_pattern))
        else:
            # Tous les fichiers de logs
            files_to_read = list(self.storage_path.glob("*.jsonl"))
        
        # Trie les fichiers par date de modification (plus récents en premier)
        files_to_read.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        count = 0
        for log_file in files_to_read:
            if count >= limit:
                break
                
            try:
                # Lit le fichier ligne par ligne (en reverse pour avoir les plus récents)
                async with aiofiles.open(log_file, 'r', encoding='utf-8') as f:
                    lines = await f.readlines()
                    
                for line in reversed(lines):
                    if count >= limit:
                        break
                    
                    try:
                        log_data = json.loads(line.strip())
                        log_entry = LogEntry.from_dict(log_data)
                        
                        # Applique les filtres
                        if start_time and log_entry.timestamp < start_time:
                            continue
                        if end_time and log_entry.timestamp > end_time:
                            continue
                        if level and log_entry.level != level:
                            continue
                        
                        yield log_entry
                        count += 1
                        
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        logger.warning(f"Ligne de log invalide ignorée: {e}")
                        continue
                        
            except Exception as e:
                logger.error(f"Erreur lors de la lecture du fichier {log_file}: {e}")
                continue
    
    async def search_logs(self, 
                         query: str,
                         container_id: Optional[str] = None,
                         start_time: Optional[datetime] = None,
                         end_time: Optional[datetime] = None,
                         limit: int = 1000) -> AsyncGenerator[LogEntry, None]:
        """Recherche dans les logs avec requête texte"""
        query_lower = query.lower()
        count = 0
        
        async for log_entry in self.get_logs(container_id, start_time, end_time, limit=limit * 2):
            if count >= limit:
                break
            
            # Recherche dans le message
            if query_lower in log_entry.message.lower():
                yield log_entry
                count += 1
                continue
            
            # Recherche dans les métadonnées
            for key, value in log_entry.metadata.items():
                if query_lower in str(value).lower():
                    yield log_entry
                    count += 1
                    break
    
    def get_stats(self) -> Dict:
        """Retourne les statistiques du collecteur"""
        return {
            'is_running': self.is_running,
            'monitored_containers': len(self.monitored_containers),
            'active_tasks': len(self.collection_tasks),
            'buffered_logs': sum(len(buffer) for buffer in self.log_buffers.values()),
            'log_files': len(list(self.storage_path.glob("*.jsonl"))),
            'storage_path': str(self.storage_path)
        }
