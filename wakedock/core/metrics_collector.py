"""
Collecteur de métriques pour le monitoring temps réel des conteneurs Docker
"""
import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, AsyncGenerator, NamedTuple
from dataclasses import dataclass, asdict
from enum import Enum
import aiofiles
from pathlib import Path

from wakedock.core.docker_manager import DockerManager

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """Types de métriques collectées"""
    CPU_PERCENT = "cpu_percent"
    MEMORY_USAGE = "memory_usage"
    MEMORY_PERCENT = "memory_percent"
    MEMORY_LIMIT = "memory_limit"
    NETWORK_RX = "network_rx"
    NETWORK_TX = "network_tx"
    BLOCK_READ = "block_read"
    BLOCK_WRITE = "block_write"
    PIDS = "pids"

class AlertLevel(Enum):
    """Niveaux d'alerte"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class ContainerMetrics:
    """Métriques d'un conteneur à un instant donné"""
    container_id: str
    container_name: str
    service_name: Optional[str]
    timestamp: datetime
    
    # Métriques CPU
    cpu_percent: float
    cpu_usage: int  # En nanosecondes
    cpu_system_usage: int
    
    # Métriques mémoire
    memory_usage: int  # En bytes
    memory_limit: int  # En bytes
    memory_percent: float
    memory_cache: int
    
    # Métriques réseau
    network_rx_bytes: int
    network_tx_bytes: int
    network_rx_packets: int
    network_tx_packets: int
    
    # Métriques I/O
    block_read_bytes: int
    block_write_bytes: int
    
    # Autres métriques
    pids: int
    
    def to_dict(self) -> Dict:
        """Convertit en dictionnaire pour sérialisation"""
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ContainerMetrics':
        """Crée depuis un dictionnaire"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

@dataclass
class Alert:
    """Alerte de monitoring"""
    container_id: str
    container_name: str
    service_name: Optional[str]
    timestamp: datetime
    level: AlertLevel
    metric_type: MetricType
    value: float
    threshold: float
    message: str
    
    def to_dict(self) -> Dict:
        """Convertit en dictionnaire"""
        return {
            **asdict(self),
            'timestamp': self.timestamp.isoformat(),
            'level': self.level.value,
            'metric_type': self.metric_type.value
        }

@dataclass
class ThresholdConfig:
    """Configuration des seuils d'alerte"""
    metric_type: MetricType
    warning_threshold: float
    critical_threshold: float
    enabled: bool = True

class MetricsCollector:
    """Collecteur de métriques pour les conteneurs Docker"""
    
    def __init__(self, docker_manager: DockerManager, storage_path: str = "/var/log/wakedock/metrics"):
        self.docker_manager = docker_manager
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.collection_interval = 5  # secondes
        self.retention_days = 7  # jours
        self.max_file_size = 50 * 1024 * 1024  # 50MB
        
        # État du collecteur
        self.is_running = False
        self.monitored_containers: Dict[str, str] = {}  # id -> name
        self.collection_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        
        # Configuration des seuils par défaut
        self.thresholds: Dict[MetricType, ThresholdConfig] = {
            MetricType.CPU_PERCENT: ThresholdConfig(
                MetricType.CPU_PERCENT, 
                warning_threshold=70.0, 
                critical_threshold=90.0
            ),
            MetricType.MEMORY_PERCENT: ThresholdConfig(
                MetricType.MEMORY_PERCENT, 
                warning_threshold=80.0, 
                critical_threshold=95.0
            ),
            MetricType.NETWORK_RX: ThresholdConfig(
                MetricType.NETWORK_RX, 
                warning_threshold=100*1024*1024,  # 100MB/s
                critical_threshold=500*1024*1024   # 500MB/s
            ),
            MetricType.NETWORK_TX: ThresholdConfig(
                MetricType.NETWORK_TX, 
                warning_threshold=100*1024*1024,
                critical_threshold=500*1024*1024
            )
        }
        
        # Callbacks pour les alertes
        self.alert_callbacks: List[callable] = []
        
        # Cache pour les calculs de dérivées
        self.previous_metrics: Dict[str, ContainerMetrics] = {}
    
    async def start(self):
        """Démarre la collecte de métriques"""
        if self.is_running:
            return
        
        logger.info("Démarrage du collecteur de métriques")
        self.is_running = True
        
        # Découvre les conteneurs en cours d'exécution
        await self._discover_containers()
        
        # Démarre les tâches de fond
        self.collection_task = asyncio.create_task(self._collection_worker())
        self.cleanup_task = asyncio.create_task(self._cleanup_worker())
    
    async def stop(self):
        """Arrête la collecte de métriques"""
        if not self.is_running:
            return
        
        logger.info("Arrêt du collecteur de métriques")
        self.is_running = False
        
        # Arrête les tâches
        if self.collection_task:
            self.collection_task.cancel()
        if self.cleanup_task:
            self.cleanup_task.cancel()
        
        # Nettoie l'état
        self.monitored_containers.clear()
        self.previous_metrics.clear()
    
    async def _discover_containers(self):
        """Découvre les conteneurs en cours d'exécution"""
        try:
            containers = self.docker_manager.list_containers(all=False)
            for container in containers:
                info = self.docker_manager.get_container_info(container.id)
                if info:
                    name = info.get('name', container.id[:12])
                    self.monitored_containers[container.id] = name
                    logger.debug(f"Conteneur ajouté au monitoring: {name}")
        except Exception as e:
            logger.error(f"Erreur lors de la découverte des conteneurs: {e}")
    
    async def _collection_worker(self):
        """Worker principal de collecte de métriques"""
        while self.is_running:
            try:
                start_time = datetime.utcnow()
                
                # Met à jour la liste des conteneurs
                await self._discover_containers()
                
                # Collecte les métriques de chaque conteneur
                for container_id, container_name in list(self.monitored_containers.items()):
                    try:
                        metrics = await self._collect_container_metrics(container_id, container_name)
                        if metrics:
                            await self._store_metrics(metrics)
                            await self._check_thresholds(metrics)
                    except Exception as e:
                        logger.warning(f"Erreur lors de la collecte pour {container_name}: {e}")
                        # Retire le conteneur s'il n'existe plus
                        if "not found" in str(e).lower():
                            del self.monitored_containers[container_id]
                
                # Calcule le temps d'attente pour maintenir l'intervalle
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                sleep_time = max(0, self.collection_interval - elapsed)
                await asyncio.sleep(sleep_time)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur dans le worker de collecte: {e}")
                await asyncio.sleep(self.collection_interval)
    
    async def _collect_container_metrics(self, container_id: str, container_name: str) -> Optional[ContainerMetrics]:
        """Collecte les métriques d'un conteneur spécifique"""
        try:
            # Récupère les stats Docker
            stats = self.docker_manager.get_container_stats(container_id, stream=False)
            if not stats:
                return None
            
            # Récupère les infos du conteneur
            info = self.docker_manager.get_container_info(container_id)
            service_name = None
            if info:
                labels = info.get('labels', {})
                service_name = labels.get('com.docker.compose.service')
            
            timestamp = datetime.utcnow()
            
            # Parse les métriques CPU
            cpu_stats = stats.get('cpu_stats', {})
            precpu_stats = stats.get('precpu_stats', {})
            
            cpu_usage = cpu_stats.get('cpu_usage', {}).get('total_usage', 0)
            system_usage = cpu_stats.get('system_cpu_usage', 0)
            
            # Calcule le pourcentage CPU
            cpu_percent = self._calculate_cpu_percent(cpu_stats, precpu_stats)
            
            # Parse les métriques mémoire
            memory_stats = stats.get('memory_stats', {})
            memory_usage = memory_stats.get('usage', 0)
            memory_limit = memory_stats.get('limit', 0)
            memory_cache = memory_stats.get('stats', {}).get('cache', 0)
            memory_percent = (memory_usage / memory_limit * 100) if memory_limit > 0 else 0
            
            # Parse les métriques réseau
            networks = stats.get('networks', {})
            network_rx_bytes = 0
            network_tx_bytes = 0
            network_rx_packets = 0
            network_tx_packets = 0
            
            for network_data in networks.values():
                network_rx_bytes += network_data.get('rx_bytes', 0)
                network_tx_bytes += network_data.get('tx_bytes', 0)
                network_rx_packets += network_data.get('rx_packets', 0)
                network_tx_packets += network_data.get('tx_packets', 0)
            
            # Parse les métriques I/O
            blkio_stats = stats.get('blkio_stats', {})
            io_service_bytes = blkio_stats.get('io_service_bytes_recursive', [])
            
            block_read_bytes = 0
            block_write_bytes = 0
            
            for io_stat in io_service_bytes:
                if io_stat.get('op') == 'read':
                    block_read_bytes += io_stat.get('value', 0)
                elif io_stat.get('op') == 'write':
                    block_write_bytes += io_stat.get('value', 0)
            
            # Parse les PIDs
            pids_stats = stats.get('pids_stats', {})
            pids = pids_stats.get('current', 0)
            
            return ContainerMetrics(
                container_id=container_id,
                container_name=container_name,
                service_name=service_name,
                timestamp=timestamp,
                cpu_percent=cpu_percent,
                cpu_usage=cpu_usage,
                cpu_system_usage=system_usage,
                memory_usage=memory_usage,
                memory_limit=memory_limit,
                memory_percent=memory_percent,
                memory_cache=memory_cache,
                network_rx_bytes=network_rx_bytes,
                network_tx_bytes=network_tx_bytes,
                network_rx_packets=network_rx_packets,
                network_tx_packets=network_tx_packets,
                block_read_bytes=block_read_bytes,
                block_write_bytes=block_write_bytes,
                pids=pids
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de la collecte des métriques pour {container_name}: {e}")
            return None
    
    def _calculate_cpu_percent(self, cpu_stats: Dict, precpu_stats: Dict) -> float:
        """Calcule le pourcentage d'utilisation CPU"""
        try:
            cpu_usage = cpu_stats.get('cpu_usage', {}).get('total_usage', 0)
            precpu_usage = precpu_stats.get('cpu_usage', {}).get('total_usage', 0)
            
            system_usage = cpu_stats.get('system_cpu_usage', 0)
            presystem_usage = precpu_stats.get('system_cpu_usage', 0)
            
            online_cpus = cpu_stats.get('online_cpus', 1)
            if online_cpus == 0:
                online_cpus = len(cpu_stats.get('cpu_usage', {}).get('percpu_usage', [1]))
            
            cpu_delta = cpu_usage - precpu_usage
            system_delta = system_usage - presystem_usage
            
            if system_delta > 0 and cpu_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * online_cpus * 100
                return min(cpu_percent, 100.0 * online_cpus)
            
            return 0.0
            
        except Exception as e:
            logger.warning(f"Erreur lors du calcul du CPU: {e}")
            return 0.0
    
    async def _store_metrics(self, metrics: ContainerMetrics):
        """Stocke les métriques dans un fichier"""
        try:
            # Organise par jour
            date_str = metrics.timestamp.strftime('%Y-%m-%d')
            metrics_file = self.storage_path / f"metrics_{date_str}.jsonl"
            
            # Écrit les métriques
            async with aiofiles.open(metrics_file, 'a', encoding='utf-8') as f:
                await f.write(json.dumps(metrics.to_dict()) + '\n')
                
        except Exception as e:
            logger.error(f"Erreur lors du stockage des métriques: {e}")
    
    async def _check_thresholds(self, metrics: ContainerMetrics):
        """Vérifie les seuils et génère des alertes si nécessaire"""
        try:
            alerts = []
            
            # Vérifie CPU
            cpu_config = self.thresholds.get(MetricType.CPU_PERCENT)
            if cpu_config and cpu_config.enabled:
                if metrics.cpu_percent >= cpu_config.critical_threshold:
                    alerts.append(Alert(
                        container_id=metrics.container_id,
                        container_name=metrics.container_name,
                        service_name=metrics.service_name,
                        timestamp=metrics.timestamp,
                        level=AlertLevel.CRITICAL,
                        metric_type=MetricType.CPU_PERCENT,
                        value=metrics.cpu_percent,
                        threshold=cpu_config.critical_threshold,
                        message=f"CPU critique: {metrics.cpu_percent:.1f}% (seuil: {cpu_config.critical_threshold}%)"
                    ))
                elif metrics.cpu_percent >= cpu_config.warning_threshold:
                    alerts.append(Alert(
                        container_id=metrics.container_id,
                        container_name=metrics.container_name,
                        service_name=metrics.service_name,
                        timestamp=metrics.timestamp,
                        level=AlertLevel.WARNING,
                        metric_type=MetricType.CPU_PERCENT,
                        value=metrics.cpu_percent,
                        threshold=cpu_config.warning_threshold,
                        message=f"CPU élevé: {metrics.cpu_percent:.1f}% (seuil: {cpu_config.warning_threshold}%)"
                    ))
            
            # Vérifie mémoire
            memory_config = self.thresholds.get(MetricType.MEMORY_PERCENT)
            if memory_config and memory_config.enabled:
                if metrics.memory_percent >= memory_config.critical_threshold:
                    alerts.append(Alert(
                        container_id=metrics.container_id,
                        container_name=metrics.container_name,
                        service_name=metrics.service_name,
                        timestamp=metrics.timestamp,
                        level=AlertLevel.CRITICAL,
                        metric_type=MetricType.MEMORY_PERCENT,
                        value=metrics.memory_percent,
                        threshold=memory_config.critical_threshold,
                        message=f"Mémoire critique: {metrics.memory_percent:.1f}% (seuil: {memory_config.critical_threshold}%)"
                    ))
                elif metrics.memory_percent >= memory_config.warning_threshold:
                    alerts.append(Alert(
                        container_id=metrics.container_id,
                        container_name=metrics.container_name,
                        service_name=metrics.service_name,
                        timestamp=metrics.timestamp,
                        level=AlertLevel.WARNING,
                        metric_type=MetricType.MEMORY_PERCENT,
                        value=metrics.memory_percent,
                        threshold=memory_config.warning_threshold,
                        message=f"Mémoire élevée: {metrics.memory_percent:.1f}% (seuil: {memory_config.warning_threshold}%)"
                    ))
            
            # Calcule les taux de réseau si on a des métriques précédentes
            previous = self.previous_metrics.get(metrics.container_id)
            if previous:
                time_delta = (metrics.timestamp - previous.timestamp).total_seconds()
                if time_delta > 0:
                    # Taux de réception réseau
                    rx_rate = (metrics.network_rx_bytes - previous.network_rx_bytes) / time_delta
                    tx_rate = (metrics.network_tx_bytes - previous.network_tx_bytes) / time_delta
                    
                    # Vérifie les seuils réseau
                    for metric_type, rate in [(MetricType.NETWORK_RX, rx_rate), (MetricType.NETWORK_TX, tx_rate)]:
                        config = self.thresholds.get(metric_type)
                        if config and config.enabled:
                            if rate >= config.critical_threshold:
                                alerts.append(Alert(
                                    container_id=metrics.container_id,
                                    container_name=metrics.container_name,
                                    service_name=metrics.service_name,
                                    timestamp=metrics.timestamp,
                                    level=AlertLevel.CRITICAL,
                                    metric_type=metric_type,
                                    value=rate,
                                    threshold=config.critical_threshold,
                                    message=f"Trafic réseau critique: {rate/1024/1024:.1f} MB/s"
                                ))
                            elif rate >= config.warning_threshold:
                                alerts.append(Alert(
                                    container_id=metrics.container_id,
                                    container_name=metrics.container_name,
                                    service_name=metrics.service_name,
                                    timestamp=metrics.timestamp,
                                    level=AlertLevel.WARNING,
                                    metric_type=metric_type,
                                    value=rate,
                                    threshold=config.warning_threshold,
                                    message=f"Trafic réseau élevé: {rate/1024/1024:.1f} MB/s"
                                ))
            
            # Stocke les métriques actuelles pour la prochaine fois
            self.previous_metrics[metrics.container_id] = metrics
            
            # Traite les alertes
            for alert in alerts:
                await self._process_alert(alert)
                
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des seuils: {e}")
    
    async def _process_alert(self, alert: Alert):
        """Traite une alerte"""
        try:
            # Log l'alerte
            level_map = {
                AlertLevel.INFO: logging.INFO,
                AlertLevel.WARNING: logging.WARNING,
                AlertLevel.CRITICAL: logging.ERROR
            }
            logger.log(level_map[alert.level], f"ALERTE {alert.level.value.upper()}: {alert.message}")
            
            # Stocke l'alerte
            await self._store_alert(alert)
            
            # Appelle les callbacks
            for callback in self.alert_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(alert)
                    else:
                        callback(alert)
                except Exception as e:
                    logger.error(f"Erreur dans le callback d'alerte: {e}")
                    
        except Exception as e:
            logger.error(f"Erreur lors du traitement de l'alerte: {e}")
    
    async def _store_alert(self, alert: Alert):
        """Stocke une alerte"""
        try:
            date_str = alert.timestamp.strftime('%Y-%m-%d')
            alerts_file = self.storage_path / f"alerts_{date_str}.jsonl"
            
            async with aiofiles.open(alerts_file, 'a', encoding='utf-8') as f:
                await f.write(json.dumps(alert.to_dict()) + '\n')
                
        except Exception as e:
            logger.error(f"Erreur lors du stockage de l'alerte: {e}")
    
    async def _cleanup_worker(self):
        """Worker de nettoyage des anciens fichiers"""
        while self.is_running:
            try:
                # Nettoie une fois par jour
                await asyncio.sleep(24 * 3600)
                await self._cleanup_old_files()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur dans le worker de nettoyage: {e}")
    
    async def _cleanup_old_files(self):
        """Nettoie les anciens fichiers de métriques"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
            
            for file_path in self.storage_path.glob("*.jsonl"):
                try:
                    file_date = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_date < cutoff_date:
                        file_path.unlink()
                        logger.info(f"Fichier de métriques supprimé: {file_path}")
                except Exception as e:
                    logger.warning(f"Erreur lors de la suppression de {file_path}: {e}")
                    
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage: {e}")
    
    def add_alert_callback(self, callback: callable):
        """Ajoute un callback pour les alertes"""
        self.alert_callbacks.append(callback)
    
    def remove_alert_callback(self, callback: callable):
        """Retire un callback d'alerte"""
        if callback in self.alert_callbacks:
            self.alert_callbacks.remove(callback)
    
    def update_threshold(self, metric_type: MetricType, warning: float, critical: float, enabled: bool = True):
        """Met à jour un seuil d'alerte"""
        self.thresholds[metric_type] = ThresholdConfig(
            metric_type=metric_type,
            warning_threshold=warning,
            critical_threshold=critical,
            enabled=enabled
        )
    
    async def get_recent_metrics(self, 
                                container_id: Optional[str] = None,
                                hours: int = 1,
                                limit: int = 1000) -> List[ContainerMetrics]:
        """Récupère les métriques récentes"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            metrics = []
            
            # Lit les fichiers de métriques récents
            for days_back in range(hours // 24 + 2):
                date = datetime.utcnow() - timedelta(days=days_back)
                date_str = date.strftime('%Y-%m-%d')
                metrics_file = self.storage_path / f"metrics_{date_str}.jsonl"
                
                if not metrics_file.exists():
                    continue
                
                async with aiofiles.open(metrics_file, 'r', encoding='utf-8') as f:
                    async for line in f:
                        try:
                            data = json.loads(line.strip())
                            metric = ContainerMetrics.from_dict(data)
                            
                            if metric.timestamp < cutoff_time:
                                continue
                            
                            if container_id and metric.container_id != container_id:
                                continue
                            
                            metrics.append(metric)
                            
                            if len(metrics) >= limit:
                                break
                                
                        except Exception as e:
                            logger.warning(f"Ligne de métrique invalide ignorée: {e}")
                            continue
                
                if len(metrics) >= limit:
                    break
            
            # Trie par timestamp
            metrics.sort(key=lambda m: m.timestamp, reverse=True)
            return metrics[:limit]
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des métriques: {e}")
            return []
    
    async def get_recent_alerts(self, 
                               container_id: Optional[str] = None,
                               hours: int = 24,
                               limit: int = 100) -> List[Alert]:
        """Récupère les alertes récentes"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            alerts = []
            
            # Lit les fichiers d'alertes récents
            for days_back in range(hours // 24 + 2):
                date = datetime.utcnow() - timedelta(days=days_back)
                date_str = date.strftime('%Y-%m-%d')
                alerts_file = self.storage_path / f"alerts_{date_str}.jsonl"
                
                if not alerts_file.exists():
                    continue
                
                async with aiofiles.open(alerts_file, 'r', encoding='utf-8') as f:
                    async for line in f:
                        try:
                            data = json.loads(line.strip())
                            data['level'] = AlertLevel(data['level'])
                            data['metric_type'] = MetricType(data['metric_type'])
                            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
                            
                            alert = Alert(**data)
                            
                            if alert.timestamp < cutoff_time:
                                continue
                            
                            if container_id and alert.container_id != container_id:
                                continue
                            
                            alerts.append(alert)
                            
                            if len(alerts) >= limit:
                                break
                                
                        except Exception as e:
                            logger.warning(f"Ligne d'alerte invalide ignorée: {e}")
                            continue
                
                if len(alerts) >= limit:
                    break
            
            # Trie par timestamp
            alerts.sort(key=lambda a: a.timestamp, reverse=True)
            return alerts[:limit]
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des alertes: {e}")
            return []
    
    def get_stats(self) -> Dict:
        """Récupère les statistiques du collecteur"""
        return {
            'is_running': self.is_running,
            'monitored_containers': len(self.monitored_containers),
            'collection_interval': self.collection_interval,
            'retention_days': self.retention_days,
            'storage_path': str(self.storage_path),
            'thresholds': {
                metric_type.value: {
                    'warning': config.warning_threshold,
                    'critical': config.critical_threshold,
                    'enabled': config.enabled
                }
                for metric_type, config in self.thresholds.items()
            }
        }
