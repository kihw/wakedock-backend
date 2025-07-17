"""
Service d'analytics avancé pour les métriques de performance avec prédictions et tendances
"""
import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
import numpy as np
from scipy import stats

from wakedock.core.metrics_collector import ContainerMetrics, MetricsCollector

logger = logging.getLogger(__name__)

class TrendDirection(Enum):
    """Direction de la tendance"""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"

class PredictionConfidence(Enum):
    """Niveau de confiance des prédictions"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class PerformanceTrend:
    """Tendance de performance pour une métrique"""
    metric_type: str
    container_id: str
    container_name: str
    service_name: Optional[str]
    
    # Données de tendance
    direction: TrendDirection
    slope: float  # Pente de la tendance
    correlation: float  # Corrélation R²
    
    # Statistiques
    current_value: float
    average_value: float
    min_value: float
    max_value: float
    std_deviation: float
    
    # Prédictions
    predicted_1h: float
    predicted_6h: float
    predicted_24h: float
    confidence: PredictionConfidence
    
    # Métadonnées
    calculated_at: datetime
    data_points: int
    time_range_hours: int
    
    def to_dict(self) -> Dict:
        """Convertit en dictionnaire"""
        return {
            **asdict(self),
            'direction': self.direction.value,
            'confidence': self.confidence.value,
            'calculated_at': self.calculated_at.isoformat()
        }

@dataclass
class ResourceOptimization:
    """Recommandation d'optimisation des ressources"""
    container_id: str
    container_name: str
    service_name: Optional[str]
    
    # Type d'optimisation
    resource_type: str  # 'cpu', 'memory', 'network'
    optimization_type: str  # 'increase', 'decrease', 'optimize'
    
    # Valeurs actuelles et recommandées
    current_limit: Optional[float]
    recommended_limit: float
    expected_improvement: float  # Pourcentage d'amélioration attendu
    
    # Justification
    reason: str
    impact_level: str  # 'low', 'medium', 'high'
    confidence_score: float  # 0-1
    
    # Métadonnées
    created_at: datetime
    
    def to_dict(self) -> Dict:
        """Convertit en dictionnaire"""
        return {
            **asdict(self),
            'created_at': self.created_at.isoformat()
        }

@dataclass
class PerformanceReport:
    """Rapport de performance périodique"""
    report_id: str
    period_start: datetime
    period_end: datetime
    
    # Résumé global
    total_containers: int
    average_cpu: float
    average_memory: float
    total_network_gb: float
    
    # Top performers/problèmes
    top_cpu_consumers: List[Dict]
    top_memory_consumers: List[Dict]
    problematic_containers: List[Dict]
    
    # Tendances
    trends: List[PerformanceTrend]
    optimizations: List[ResourceOptimization]
    
    # Alertes
    alerts_summary: Dict[str, int]
    
    # Métadonnées
    generated_at: datetime
    
    def to_dict(self) -> Dict:
        """Convertit en dictionnaire"""
        return {
            'report_id': self.report_id,
            'period_start': self.period_start.isoformat(),
            'period_end': self.period_end.isoformat(),
            'total_containers': self.total_containers,
            'average_cpu': self.average_cpu,
            'average_memory': self.average_memory,
            'total_network_gb': self.total_network_gb,
            'top_cpu_consumers': self.top_cpu_consumers,
            'top_memory_consumers': self.top_memory_consumers,
            'problematic_containers': self.problematic_containers,
            'trends': [trend.to_dict() for trend in self.trends],
            'optimizations': [opt.to_dict() for opt in self.optimizations],
            'alerts_summary': self.alerts_summary,
            'generated_at': self.generated_at.isoformat()
        }

class AdvancedAnalyticsService:
    """Service d'analytics avancé pour les métriques de performance"""
    
    def __init__(self, metrics_collector: MetricsCollector, storage_path: str = "/var/log/wakedock/analytics"):
        self.metrics_collector = metrics_collector
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Configuration
        self.trend_analysis_hours = 24  # Analyser les dernières 24h
        self.prediction_model_points = 100  # Min points pour prédictions
        self.volatility_threshold = 0.3  # Seuil de volatilité
        self.correlation_threshold = 0.7  # R² minimum pour confiance élevée
        
        # Cache des modèles de prédiction
        self.prediction_models: Dict[str, Any] = {}
        self.last_model_update = {}
        
        # Planificateur de rapports
        self.report_intervals = {
            'hourly': timedelta(hours=1),
            'daily': timedelta(days=1),
            'weekly': timedelta(weeks=1),
            'monthly': timedelta(days=30)
        }
        
        # État du service
        self.is_running = False
        self.analysis_task: Optional[asyncio.Task] = None
        self.report_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Démarre le service d'analytics"""
        if self.is_running:
            return
        
        logger.info("Démarrage du service d'analytics avancé")
        self.is_running = True
        
        # Démarre les tâches de fond
        self.analysis_task = asyncio.create_task(self._analysis_worker())
        self.report_task = asyncio.create_task(self._report_worker())
    
    async def stop(self):
        """Arrête le service d'analytics"""
        if not self.is_running:
            return
        
        logger.info("Arrêt du service d'analytics avancé")
        self.is_running = False
        
        # Arrête les tâches
        if self.analysis_task:
            self.analysis_task.cancel()
        if self.report_task:
            self.report_task.cancel()
    
    async def _analysis_worker(self):
        """Worker d'analyse des tendances"""
        while self.is_running:
            try:
                # Analyse les tendances toutes les heures
                await self._analyze_performance_trends()
                await self._generate_optimization_recommendations()
                
                # Attend 1 heure
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur dans le worker d'analyse: {e}")
                await asyncio.sleep(3600)
    
    async def _report_worker(self):
        """Worker de génération de rapports"""
        while self.is_running:
            try:
                # Génère les rapports périodiques
                await self._generate_periodic_reports()
                
                # Attend 1 heure
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erreur dans le worker de rapports: {e}")
                await asyncio.sleep(3600)
    
    async def _analyze_performance_trends(self):
        """Analyse les tendances de performance"""
        try:
            # Récupère les métriques récentes
            metrics = await self.metrics_collector.get_recent_metrics(
                hours=self.trend_analysis_hours,
                limit=10000
            )
            
            if len(metrics) < 10:
                logger.debug("Pas assez de métriques pour l'analyse des tendances")
                return
            
            # Groupe par conteneur
            container_metrics = {}
            for metric in metrics:
                if metric.container_id not in container_metrics:
                    container_metrics[metric.container_id] = []
                container_metrics[metric.container_id].append(metric)
            
            # Analyse chaque conteneur
            trends = []
            for container_id, container_data in container_metrics.items():
                if len(container_data) < 5:
                    continue
                
                # Trie par timestamp
                container_data.sort(key=lambda x: x.timestamp)
                
                # Analyse les différentes métriques
                cpu_trend = await self._analyze_metric_trend(
                    container_data, 'cpu_percent', container_id
                )
                if cpu_trend:
                    trends.append(cpu_trend)
                
                memory_trend = await self._analyze_metric_trend(
                    container_data, 'memory_percent', container_id
                )
                if memory_trend:
                    trends.append(memory_trend)
                
                # Analyse du réseau (combiné RX + TX)
                network_trend = await self._analyze_network_trend(
                    container_data, container_id
                )
                if network_trend:
                    trends.append(network_trend)
            
            # Stocke les tendances
            await self._store_trends(trends)
            
            logger.info(f"Analyse des tendances terminée: {len(trends)} tendances calculées")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse des tendances: {e}")
    
    async def _analyze_metric_trend(self, metrics: List[ContainerMetrics], metric_name: str, container_id: str) -> Optional[PerformanceTrend]:
        """Analyse la tendance d'une métrique spécifique"""
        try:
            # Extrait les valeurs et timestamps
            values = []
            timestamps = []
            
            for metric in metrics:
                value = getattr(metric, metric_name, None)
                if value is not None:
                    values.append(float(value))
                    timestamps.append(metric.timestamp.timestamp())
            
            if len(values) < 5:
                return None
            
            # Convertit en arrays numpy
            x = np.array(timestamps)
            y = np.array(values)
            
            # Normalise les timestamps (commence à 0)
            x_norm = x - x[0]
            
            # Régression linéaire
            slope, intercept, r_value, p_value, std_err = stats.linregress(x_norm, y)
            correlation = r_value ** 2
            
            # Détermine la direction de la tendance
            direction = self._determine_trend_direction(slope, correlation, np.std(y))
            
            # Calcule les statistiques
            current_value = values[-1]
            average_value = np.mean(y)
            min_value = np.min(y)
            max_value = np.max(y)
            std_deviation = np.std(y)
            
            # Prédictions
            time_1h = 3600  # 1 heure en secondes
            time_6h = 6 * 3600  # 6 heures
            time_24h = 24 * 3600  # 24 heures
            
            current_time = x_norm[-1]
            predicted_1h = slope * (current_time + time_1h) + intercept
            predicted_6h = slope * (current_time + time_6h) + intercept
            predicted_24h = slope * (current_time + time_24h) + intercept
            
            # Ajuste les prédictions pour rester dans des limites réalistes
            predicted_1h = max(0, min(predicted_1h, 100 if 'percent' in metric_name else predicted_1h))
            predicted_6h = max(0, min(predicted_6h, 100 if 'percent' in metric_name else predicted_6h))
            predicted_24h = max(0, min(predicted_24h, 100 if 'percent' in metric_name else predicted_24h))
            
            # Détermine la confiance
            confidence = self._determine_prediction_confidence(correlation, len(values), std_deviation)
            
            # Récupère les infos du conteneur
            container_name = metrics[0].container_name
            service_name = metrics[0].service_name
            
            return PerformanceTrend(
                metric_type=metric_name,
                container_id=container_id,
                container_name=container_name,
                service_name=service_name,
                direction=direction,
                slope=slope,
                correlation=correlation,
                current_value=current_value,
                average_value=average_value,
                min_value=min_value,
                max_value=max_value,
                std_deviation=std_deviation,
                predicted_1h=predicted_1h,
                predicted_6h=predicted_6h,
                predicted_24h=predicted_24h,
                confidence=confidence,
                calculated_at=datetime.utcnow(),
                data_points=len(values),
                time_range_hours=int((x[-1] - x[0]) / 3600)
            )
            
        except Exception as e:
            logger.warning(f"Erreur lors de l'analyse de tendance pour {metric_name}: {e}")
            return None
    
    async def _analyze_network_trend(self, metrics: List[ContainerMetrics], container_id: str) -> Optional[PerformanceTrend]:
        """Analyse la tendance du trafic réseau combiné"""
        try:
            # Calcule le trafic total (RX + TX) en MB/s
            values = []
            timestamps = []
            
            for i in range(1, len(metrics)):
                prev_metric = metrics[i-1]
                curr_metric = metrics[i]
                
                time_diff = (curr_metric.timestamp - prev_metric.timestamp).total_seconds()
                if time_diff <= 0:
                    continue
                
                # Calcule le débit en MB/s
                rx_diff = curr_metric.network_rx_bytes - prev_metric.network_rx_bytes
                tx_diff = curr_metric.network_tx_bytes - prev_metric.network_tx_bytes
                total_bytes = max(0, rx_diff + tx_diff)
                
                mbps = (total_bytes / 1024 / 1024) / time_diff
                
                values.append(mbps)
                timestamps.append(curr_metric.timestamp.timestamp())
            
            if len(values) < 5:
                return None
            
            # Analyse comme une métrique normale
            x = np.array(timestamps)
            y = np.array(values)
            x_norm = x - x[0]
            
            slope, intercept, r_value, p_value, std_err = stats.linregress(x_norm, y)
            correlation = r_value ** 2
            
            direction = self._determine_trend_direction(slope, correlation, np.std(y))
            
            current_value = values[-1]
            average_value = np.mean(y)
            min_value = np.min(y)
            max_value = np.max(y)
            std_deviation = np.std(y)
            
            # Prédictions réseau
            time_1h = 3600
            time_6h = 6 * 3600
            time_24h = 24 * 3600
            
            current_time = x_norm[-1]
            predicted_1h = max(0, slope * (current_time + time_1h) + intercept)
            predicted_6h = max(0, slope * (current_time + time_6h) + intercept)
            predicted_24h = max(0, slope * (current_time + time_24h) + intercept)
            
            confidence = self._determine_prediction_confidence(correlation, len(values), std_deviation)
            
            container_name = metrics[0].container_name
            service_name = metrics[0].service_name
            
            return PerformanceTrend(
                metric_type='network_mbps',
                container_id=container_id,
                container_name=container_name,
                service_name=service_name,
                direction=direction,
                slope=slope,
                correlation=correlation,
                current_value=current_value,
                average_value=average_value,
                min_value=min_value,
                max_value=max_value,
                std_deviation=std_deviation,
                predicted_1h=predicted_1h,
                predicted_6h=predicted_6h,
                predicted_24h=predicted_24h,
                confidence=confidence,
                calculated_at=datetime.utcnow(),
                data_points=len(values),
                time_range_hours=int((x[-1] - x[0]) / 3600)
            )
            
        except Exception as e:
            logger.warning(f"Erreur lors de l'analyse de tendance réseau: {e}")
            return None
    
    def _determine_trend_direction(self, slope: float, correlation: float, std_dev: float) -> TrendDirection:
        """Détermine la direction de la tendance"""
        # Si la corrélation est faible, c'est volatile
        if correlation < 0.3:
            return TrendDirection.VOLATILE
        
        # Si l'écart-type est très élevé par rapport à la pente, c'est volatile
        if abs(slope) < std_dev * self.volatility_threshold:
            return TrendDirection.STABLE
        
        # Sinon, regarde la pente
        if slope > 0.01:  # Seuil de pente positive significative
            return TrendDirection.INCREASING
        elif slope < -0.01:  # Seuil de pente négative significative
            return TrendDirection.DECREASING
        else:
            return TrendDirection.STABLE
    
    def _determine_prediction_confidence(self, correlation: float, data_points: int, std_dev: float) -> PredictionConfidence:
        """Détermine la confiance des prédictions"""
        confidence_score = 0
        
        # Facteur de corrélation (40% du score)
        confidence_score += min(correlation, 1.0) * 0.4
        
        # Facteur de nombre de points (30% du score)
        points_factor = min(data_points / self.prediction_model_points, 1.0)
        confidence_score += points_factor * 0.3
        
        # Facteur d'écart-type (30% du score, inversé)
        std_factor = max(0, 1.0 - min(std_dev / 50.0, 1.0))  # Normalise sur 50%
        confidence_score += std_factor * 0.3
        
        if confidence_score >= 0.7:
            return PredictionConfidence.HIGH
        elif confidence_score >= 0.4:
            return PredictionConfidence.MEDIUM
        else:
            return PredictionConfidence.LOW
    
    async def _generate_optimization_recommendations(self):
        """Génère des recommandations d'optimisation des ressources"""
        try:
            # Récupère les tendances récentes
            trends = await self.get_recent_trends(hours=6)
            
            optimizations = []
            
            for trend in trends:
                # Analyse CPU
                if trend.metric_type == 'cpu_percent':
                    optimization = self._analyze_cpu_optimization(trend)
                    if optimization:
                        optimizations.append(optimization)
                
                # Analyse mémoire
                elif trend.metric_type == 'memory_percent':
                    optimization = self._analyze_memory_optimization(trend)
                    if optimization:
                        optimizations.append(optimization)
                
                # Analyse réseau
                elif trend.metric_type == 'network_mbps':
                    optimization = self._analyze_network_optimization(trend)
                    if optimization:
                        optimizations.append(optimization)
            
            # Stocke les optimisations
            await self._store_optimizations(optimizations)
            
            logger.info(f"Recommandations d'optimisation générées: {len(optimizations)}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération des optimisations: {e}")
    
    def _analyze_cpu_optimization(self, trend: PerformanceTrend) -> Optional[ResourceOptimization]:
        """Analyse les optimisations CPU"""
        try:
            # CPU constamment élevé avec tendance croissante
            if (trend.average_value > 80 and 
                trend.direction == TrendDirection.INCREASING and
                trend.confidence in [PredictionConfidence.HIGH, PredictionConfidence.MEDIUM]):
                
                return ResourceOptimization(
                    container_id=trend.container_id,
                    container_name=trend.container_name,
                    service_name=trend.service_name,
                    resource_type='cpu',
                    optimization_type='increase',
                    current_limit=None,  # À récupérer depuis Docker
                    recommended_limit=trend.current_value * 1.5,
                    expected_improvement=25.0,
                    reason=f"CPU élevé ({trend.current_value:.1f}%) avec tendance croissante",
                    impact_level='high',
                    confidence_score=trend.correlation,
                    created_at=datetime.utcnow()
                )
            
            # CPU très faible, peut réduire les limites
            elif (trend.average_value < 20 and 
                  trend.max_value < 40 and
                  trend.direction in [TrendDirection.STABLE, TrendDirection.DECREASING]):
                
                return ResourceOptimization(
                    container_id=trend.container_id,
                    container_name=trend.container_name,
                    service_name=trend.service_name,
                    resource_type='cpu',
                    optimization_type='decrease',
                    current_limit=None,
                    recommended_limit=trend.average_value * 2,
                    expected_improvement=15.0,
                    reason=f"CPU sous-utilisé (moy: {trend.average_value:.1f}%)",
                    impact_level='medium',
                    confidence_score=trend.correlation,
                    created_at=datetime.utcnow()
                )
            
            return None
            
        except Exception as e:
            logger.warning(f"Erreur analyse optimisation CPU: {e}")
            return None
    
    def _analyze_memory_optimization(self, trend: PerformanceTrend) -> Optional[ResourceOptimization]:
        """Analyse les optimisations mémoire"""
        try:
            # Mémoire élevée avec risque de dépassement
            if (trend.current_value > 85 and 
                trend.predicted_6h > 90 and
                trend.direction == TrendDirection.INCREASING):
                
                return ResourceOptimization(
                    container_id=trend.container_id,
                    container_name=trend.container_name,
                    service_name=trend.service_name,
                    resource_type='memory',
                    optimization_type='increase',
                    current_limit=None,
                    recommended_limit=trend.current_value * 1.3,
                    expected_improvement=30.0,
                    reason=f"Mémoire critique ({trend.current_value:.1f}%) avec risque de dépassement",
                    impact_level='high',
                    confidence_score=trend.correlation,
                    created_at=datetime.utcnow()
                )
            
            # Mémoire sous-utilisée
            elif (trend.average_value < 30 and 
                  trend.max_value < 50):
                
                return ResourceOptimization(
                    container_id=trend.container_id,
                    container_name=trend.container_name,
                    service_name=trend.service_name,
                    resource_type='memory',
                    optimization_type='decrease',
                    current_limit=None,
                    recommended_limit=trend.max_value * 1.2,
                    expected_improvement=20.0,
                    reason=f"Mémoire sous-utilisée (moy: {trend.average_value:.1f}%)",
                    impact_level='medium',
                    confidence_score=trend.correlation,
                    created_at=datetime.utcnow()
                )
            
            return None
            
        except Exception as e:
            logger.warning(f"Erreur analyse optimisation mémoire: {e}")
            return None
    
    def _analyze_network_optimization(self, trend: PerformanceTrend) -> Optional[ResourceOptimization]:
        """Analyse les optimisations réseau"""
        try:
            # Trafic réseau très élevé
            if (trend.current_value > 100 and  # > 100 MB/s
                trend.direction == TrendDirection.INCREASING):
                
                return ResourceOptimization(
                    container_id=trend.container_id,
                    container_name=trend.container_name,
                    service_name=trend.service_name,
                    resource_type='network',
                    optimization_type='optimize',
                    current_limit=None,
                    recommended_limit=trend.current_value * 1.5,
                    expected_improvement=15.0,
                    reason=f"Trafic réseau élevé ({trend.current_value:.1f} MB/s)",
                    impact_level='medium',
                    confidence_score=trend.correlation,
                    created_at=datetime.utcnow()
                )
            
            return None
            
        except Exception as e:
            logger.warning(f"Erreur analyse optimisation réseau: {e}")
            return None
    
    async def _generate_periodic_reports(self):
        """Génère les rapports périodiques"""
        try:
            now = datetime.utcnow()
            
            # Rapport journalier
            if self._should_generate_report('daily', now):
                await self._generate_daily_report(now)
            
            # Rapport hebdomadaire
            if self._should_generate_report('weekly', now):
                await self._generate_weekly_report(now)
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération des rapports: {e}")
    
    def _should_generate_report(self, interval: str, current_time: datetime) -> bool:
        """Vérifie s'il faut générer un rapport"""
        # Simplification: génère un rapport par heure pour les tests
        # En production, on utiliserait un scheduler plus sophistiqué
        return current_time.minute == 0  # Chaque heure pile
    
    async def _generate_daily_report(self, report_time: datetime):
        """Génère un rapport journalier"""
        try:
            period_start = report_time - timedelta(days=1)
            period_end = report_time
            
            # Récupère les métriques de la période
            metrics = await self.metrics_collector.get_recent_metrics(
                hours=24,
                limit=50000
            )
            
            if not metrics:
                logger.warning("Aucune métrique pour le rapport journalier")
                return
            
            # Calcule les statistiques globales
            total_containers = len(set(m.container_id for m in metrics))
            avg_cpu = sum(m.cpu_percent for m in metrics) / len(metrics)
            avg_memory = sum(m.memory_percent for m in metrics) / len(metrics)
            total_network_gb = sum((m.network_rx_bytes + m.network_tx_bytes) for m in metrics) / 1024**3
            
            # Trouve les top consommateurs
            container_stats = {}
            for metric in metrics:
                if metric.container_id not in container_stats:
                    container_stats[metric.container_id] = {
                        'name': metric.container_name,
                        'service': metric.service_name,
                        'cpu_values': [],
                        'memory_values': []
                    }
                container_stats[metric.container_id]['cpu_values'].append(metric.cpu_percent)
                container_stats[metric.container_id]['memory_values'].append(metric.memory_percent)
            
            # Calcule les moyennes par conteneur
            for container_id, stats in container_stats.items():
                stats['avg_cpu'] = sum(stats['cpu_values']) / len(stats['cpu_values'])
                stats['avg_memory'] = sum(stats['memory_values']) / len(stats['memory_values'])
            
            # Top CPU consumers
            top_cpu = sorted(
                [(cid, stats) for cid, stats in container_stats.items()],
                key=lambda x: x[1]['avg_cpu'],
                reverse=True
            )[:5]
            
            top_cpu_consumers = [
                {
                    'container_id': cid,
                    'container_name': stats['name'],
                    'service_name': stats['service'],
                    'avg_cpu': stats['avg_cpu']
                }
                for cid, stats in top_cpu
            ]
            
            # Top Memory consumers
            top_memory = sorted(
                [(cid, stats) for cid, stats in container_stats.items()],
                key=lambda x: x[1]['avg_memory'],
                reverse=True
            )[:5]
            
            top_memory_consumers = [
                {
                    'container_id': cid,
                    'container_name': stats['name'],
                    'service_name': stats['service'],
                    'avg_memory': stats['avg_memory']
                }
                for cid, stats in top_memory
            ]
            
            # Conteneurs problématiques (CPU > 80% ou Mémoire > 90%)
            problematic = [
                {
                    'container_id': cid,
                    'container_name': stats['name'],
                    'service_name': stats['service'],
                    'avg_cpu': stats['avg_cpu'],
                    'avg_memory': stats['avg_memory'],
                    'issues': []
                }
                for cid, stats in container_stats.items()
                if stats['avg_cpu'] > 80 or stats['avg_memory'] > 90
            ]
            
            for container in problematic:
                if container['avg_cpu'] > 80:
                    container['issues'].append(f"CPU élevé: {container['avg_cpu']:.1f}%")
                if container['avg_memory'] > 90:
                    container['issues'].append(f"Mémoire critique: {container['avg_memory']:.1f}%")
            
            # Récupère les tendances récentes
            trends = await self.get_recent_trends(hours=24)
            
            # Récupère les optimisations récentes
            optimizations = await self.get_recent_optimizations(hours=24)
            
            # Résumé des alertes
            alerts = await self.metrics_collector.get_recent_alerts(hours=24, limit=1000)
            alerts_summary = {
                'critical': len([a for a in alerts if a.level.value == 'critical']),
                'warning': len([a for a in alerts if a.level.value == 'warning']),
                'info': len([a for a in alerts if a.level.value == 'info'])
            }
            
            # Crée le rapport
            report = PerformanceReport(
                report_id=f"daily_{report_time.strftime('%Y%m%d_%H%M%S')}",
                period_start=period_start,
                period_end=period_end,
                total_containers=total_containers,
                average_cpu=avg_cpu,
                average_memory=avg_memory,
                total_network_gb=total_network_gb,
                top_cpu_consumers=top_cpu_consumers,
                top_memory_consumers=top_memory_consumers,
                problematic_containers=problematic,
                trends=trends,
                optimizations=optimizations,
                alerts_summary=alerts_summary,
                generated_at=datetime.utcnow()
            )
            
            # Stocke le rapport
            await self._store_report(report)
            
            logger.info(f"Rapport journalier généré: {report.report_id}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du rapport journalier: {e}")
    
    async def _generate_weekly_report(self, report_time: datetime):
        """Génère un rapport hebdomadaire (version simplifiée)"""
        # Pour le moment, génère un rapport similaire au journalier mais sur 7 jours
        # En production, on ajouterait des analyses plus poussées
        await self._generate_daily_report(report_time)
    
    async def _store_trends(self, trends: List[PerformanceTrend]):
        """Stocke les tendances calculées"""
        try:
            if not trends:
                return
            
            date_str = datetime.utcnow().strftime('%Y-%m-%d')
            trends_file = self.storage_path / f"trends_{date_str}.jsonl"
            
            async with aiofiles.open(trends_file, 'a', encoding='utf-8') as f:
                for trend in trends:
                    await f.write(json.dumps(trend.to_dict()) + '\n')
                    
        except Exception as e:
            logger.error(f"Erreur lors du stockage des tendances: {e}")
    
    async def _store_optimizations(self, optimizations: List[ResourceOptimization]):
        """Stocke les recommandations d'optimisation"""
        try:
            if not optimizations:
                return
            
            date_str = datetime.utcnow().strftime('%Y-%m-%d')
            opt_file = self.storage_path / f"optimizations_{date_str}.jsonl"
            
            async with aiofiles.open(opt_file, 'a', encoding='utf-8') as f:
                for opt in optimizations:
                    await f.write(json.dumps(opt.to_dict()) + '\n')
                    
        except Exception as e:
            logger.error(f"Erreur lors du stockage des optimisations: {e}")
    
    async def _store_report(self, report: PerformanceReport):
        """Stocke un rapport de performance"""
        try:
            date_str = report.generated_at.strftime('%Y-%m')
            reports_file = self.storage_path / f"reports_{date_str}.jsonl"
            
            async with aiofiles.open(reports_file, 'a', encoding='utf-8') as f:
                await f.write(json.dumps(report.to_dict()) + '\n')
                
        except Exception as e:
            logger.error(f"Erreur lors du stockage du rapport: {e}")
    
    async def get_recent_trends(self, hours: int = 24) -> List[PerformanceTrend]:
        """Récupère les tendances récentes"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            trends = []
            
            # Lit les fichiers récents
            for days_back in range(hours // 24 + 2):
                date = datetime.utcnow() - timedelta(days=days_back)
                date_str = date.strftime('%Y-%m-%d')
                trends_file = self.storage_path / f"trends_{date_str}.jsonl"
                
                if not trends_file.exists():
                    continue
                
                async with aiofiles.open(trends_file, 'r', encoding='utf-8') as f:
                    async for line in f:
                        try:
                            data = json.loads(line.strip())
                            data['direction'] = TrendDirection(data['direction'])
                            data['confidence'] = PredictionConfidence(data['confidence'])
                            data['calculated_at'] = datetime.fromisoformat(data['calculated_at'])
                            
                            trend = PerformanceTrend(**data)
                            
                            if trend.calculated_at >= cutoff_time:
                                trends.append(trend)
                                
                        except Exception as e:
                            logger.warning(f"Ligne de tendance invalide ignorée: {e}")
                            continue
            
            return sorted(trends, key=lambda t: t.calculated_at, reverse=True)
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des tendances: {e}")
            return []
    
    async def get_recent_optimizations(self, hours: int = 24) -> List[ResourceOptimization]:
        """Récupère les optimisations récentes"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            optimizations = []
            
            for days_back in range(hours // 24 + 2):
                date = datetime.utcnow() - timedelta(days=days_back)
                date_str = date.strftime('%Y-%m-%d')
                opt_file = self.storage_path / f"optimizations_{date_str}.jsonl"
                
                if not opt_file.exists():
                    continue
                
                async with aiofiles.open(opt_file, 'r', encoding='utf-8') as f:
                    async for line in f:
                        try:
                            data = json.loads(line.strip())
                            data['created_at'] = datetime.fromisoformat(data['created_at'])
                            
                            opt = ResourceOptimization(**data)
                            
                            if opt.created_at >= cutoff_time:
                                optimizations.append(opt)
                                
                        except Exception as e:
                            logger.warning(f"Ligne d'optimisation invalide ignorée: {e}")
                            continue
            
            return sorted(optimizations, key=lambda o: o.created_at, reverse=True)
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des optimisations: {e}")
            return []
    
    async def get_recent_reports(self, days: int = 30) -> List[PerformanceReport]:
        """Récupère les rapports récents"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days)
            reports = []
            
            for month_back in range(days // 30 + 2):
                date = datetime.utcnow() - timedelta(days=month_back * 30)
                date_str = date.strftime('%Y-%m')
                reports_file = self.storage_path / f"reports_{date_str}.jsonl"
                
                if not reports_file.exists():
                    continue
                
                async with aiofiles.open(reports_file, 'r', encoding='utf-8') as f:
                    async for line in f:
                        try:
                            data = json.loads(line.strip())
                            
                            # Convertit les dates
                            data['period_start'] = datetime.fromisoformat(data['period_start'])
                            data['period_end'] = datetime.fromisoformat(data['period_end'])
                            data['generated_at'] = datetime.fromisoformat(data['generated_at'])
                            
                            # Reconstruit les objets complexes
                            data['trends'] = [
                                PerformanceTrend(
                                    **{**trend_data, 
                                       'direction': TrendDirection(trend_data['direction']),
                                       'confidence': PredictionConfidence(trend_data['confidence']),
                                       'calculated_at': datetime.fromisoformat(trend_data['calculated_at'])}
                                )
                                for trend_data in data['trends']
                            ]
                            
                            data['optimizations'] = [
                                ResourceOptimization(
                                    **{**opt_data,
                                       'created_at': datetime.fromisoformat(opt_data['created_at'])}
                                )
                                for opt_data in data['optimizations']
                            ]
                            
                            report = PerformanceReport(**data)
                            
                            if report.generated_at >= cutoff_time:
                                reports.append(report)
                                
                        except Exception as e:
                            logger.warning(f"Ligne de rapport invalide ignorée: {e}")
                            continue
            
            return sorted(reports, key=lambda r: r.generated_at, reverse=True)
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des rapports: {e}")
            return []
    
    def get_analytics_stats(self) -> Dict:
        """Récupère les statistiques du service d'analytics"""
        return {
            'is_running': self.is_running,
            'trend_analysis_hours': self.trend_analysis_hours,
            'prediction_model_points': self.prediction_model_points,
            'volatility_threshold': self.volatility_threshold,
            'correlation_threshold': self.correlation_threshold,
            'storage_path': str(self.storage_path),
            'cached_models': len(self.prediction_models)
        }
