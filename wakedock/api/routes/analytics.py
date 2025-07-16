"""
Routes API pour les analytics avancés et métriques de performance
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field
from enum import Enum

from wakedock.core.advanced_analytics import (
    AdvancedAnalyticsService, 
    PerformanceTrend, 
    ResourceOptimization, 
    PerformanceReport,
    TrendDirection,
    PredictionConfidence
)
from wakedock.core.metrics_collector import MetricsCollector
from wakedock.core.docker_manager import DockerManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["Analytics"])

# Models Pydantic pour les responses
class TrendDirectionResponse(str, Enum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"

class PredictionConfidenceResponse(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class PerformanceTrendResponse(BaseModel):
    metric_type: str
    container_id: str
    container_name: str
    service_name: Optional[str]
    direction: TrendDirectionResponse
    slope: float
    correlation: float
    current_value: float
    average_value: float
    min_value: float
    max_value: float
    std_deviation: float
    predicted_1h: float
    predicted_6h: float
    predicted_24h: float
    confidence: PredictionConfidenceResponse
    calculated_at: datetime
    data_points: int
    time_range_hours: int

class ResourceOptimizationResponse(BaseModel):
    container_id: str
    container_name: str
    service_name: Optional[str]
    resource_type: str
    optimization_type: str
    current_limit: Optional[float]
    recommended_limit: float
    expected_improvement: float
    reason: str
    impact_level: str
    confidence_score: float
    created_at: datetime

class PerformanceReportResponse(BaseModel):
    report_id: str
    period_start: datetime
    period_end: datetime
    total_containers: int
    average_cpu: float
    average_memory: float
    total_network_gb: float
    top_cpu_consumers: List[Dict]
    top_memory_consumers: List[Dict]
    problematic_containers: List[Dict]
    trends: List[PerformanceTrendResponse]
    optimizations: List[ResourceOptimizationResponse]
    alerts_summary: Dict[str, int]
    generated_at: datetime

class AnalyticsStatsResponse(BaseModel):
    is_running: bool
    trend_analysis_hours: int
    prediction_model_points: int
    volatility_threshold: float
    correlation_threshold: float
    storage_path: str
    cached_models: int

class TrendQuery(BaseModel):
    container_id: Optional[str] = None
    metric_type: Optional[str] = None
    direction: Optional[TrendDirectionResponse] = None
    confidence: Optional[PredictionConfidenceResponse] = None
    hours: int = Field(default=24, ge=1, le=168)  # 1h à 7j

class OptimizationQuery(BaseModel):
    container_id: Optional[str] = None
    resource_type: Optional[str] = None
    optimization_type: Optional[str] = None
    impact_level: Optional[str] = None
    hours: int = Field(default=24, ge=1, le=168)

class AnalyticsConfigUpdate(BaseModel):
    trend_analysis_hours: Optional[int] = Field(None, ge=1, le=168)
    prediction_model_points: Optional[int] = Field(None, ge=10, le=1000)
    volatility_threshold: Optional[float] = Field(None, ge=0.1, le=1.0)
    correlation_threshold: Optional[float] = Field(None, ge=0.1, le=1.0)

# Dépendances globales
_analytics_service: Optional[AdvancedAnalyticsService] = None

async def get_analytics_service() -> AdvancedAnalyticsService:
    """Récupère l'instance du service d'analytics"""
    global _analytics_service
    if _analytics_service is None:
        raise HTTPException(
            status_code=503, 
            detail="Service d'analytics non initialisé"
        )
    return _analytics_service

async def initialize_analytics_service(metrics_collector: MetricsCollector):
    """Initialise le service d'analytics (appelé au démarrage)"""
    global _analytics_service
    _analytics_service = AdvancedAnalyticsService(metrics_collector)
    await _analytics_service.start()

async def cleanup_analytics_service():
    """Nettoie le service d'analytics (appelé à l'arrêt)"""
    global _analytics_service
    if _analytics_service:
        await _analytics_service.stop()

@router.get("/status", response_model=AnalyticsStatsResponse)
async def get_analytics_status(
    analytics: AdvancedAnalyticsService = Depends(get_analytics_service)
):
    """Récupère le statut du service d'analytics"""
    try:
        stats = analytics.get_analytics_stats()
        return AnalyticsStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/start")
async def start_analytics_service(
    analytics: AdvancedAnalyticsService = Depends(get_analytics_service)
):
    """Démarre le service d'analytics"""
    try:
        await analytics.start()
        return {"message": "Service d'analytics démarré", "status": "running"}
    except Exception as e:
        logger.error(f"Erreur lors du démarrage du service analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop")
async def stop_analytics_service(
    analytics: AdvancedAnalyticsService = Depends(get_analytics_service)
):
    """Arrête le service d'analytics"""
    try:
        await analytics.stop()
        return {"message": "Service d'analytics arrêté", "status": "stopped"}
    except Exception as e:
        logger.error(f"Erreur lors de l'arrêt du service analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trends", response_model=List[PerformanceTrendResponse])
async def get_performance_trends(
    container_id: Optional[str] = Query(None, description="ID du conteneur à filtrer"),
    metric_type: Optional[str] = Query(None, description="Type de métrique (cpu_percent, memory_percent, network_mbps)"),
    direction: Optional[TrendDirectionResponse] = Query(None, description="Direction de la tendance"),
    confidence: Optional[PredictionConfidenceResponse] = Query(None, description="Niveau de confiance"),
    hours: int = Query(24, ge=1, le=168, description="Nombre d'heures à récupérer"),
    limit: int = Query(100, ge=1, le=1000, description="Nombre maximum de résultats"),
    analytics: AdvancedAnalyticsService = Depends(get_analytics_service)
):
    """Récupère les tendances de performance avec filtres optionnels"""
    try:
        trends = await analytics.get_recent_trends(hours=hours)
        
        # Applique les filtres
        filtered_trends = trends
        
        if container_id:
            filtered_trends = [t for t in filtered_trends if t.container_id == container_id]
        
        if metric_type:
            filtered_trends = [t for t in filtered_trends if t.metric_type == metric_type]
        
        if direction:
            filtered_trends = [t for t in filtered_trends if t.direction.value == direction.value]
        
        if confidence:
            filtered_trends = [t for t in filtered_trends if t.confidence.value == confidence.value]
        
        # Limite les résultats
        filtered_trends = filtered_trends[:limit]
        
        # Convertit en response models
        return [
            PerformanceTrendResponse(
                metric_type=trend.metric_type,
                container_id=trend.container_id,
                container_name=trend.container_name,
                service_name=trend.service_name,
                direction=TrendDirectionResponse(trend.direction.value),
                slope=trend.slope,
                correlation=trend.correlation,
                current_value=trend.current_value,
                average_value=trend.average_value,
                min_value=trend.min_value,
                max_value=trend.max_value,
                std_deviation=trend.std_deviation,
                predicted_1h=trend.predicted_1h,
                predicted_6h=trend.predicted_6h,
                predicted_24h=trend.predicted_24h,
                confidence=PredictionConfidenceResponse(trend.confidence.value),
                calculated_at=trend.calculated_at,
                data_points=trend.data_points,
                time_range_hours=trend.time_range_hours
            )
            for trend in filtered_trends
        ]
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des tendances: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/trends/{container_id}", response_model=List[PerformanceTrendResponse])
async def get_container_trends(
    container_id: str,
    metric_type: Optional[str] = Query(None, description="Type de métrique spécifique"),
    hours: int = Query(24, ge=1, le=168),
    analytics: AdvancedAnalyticsService = Depends(get_analytics_service)
):
    """Récupère toutes les tendances pour un conteneur spécifique"""
    try:
        trends = await analytics.get_recent_trends(hours=hours)
        container_trends = [t for t in trends if t.container_id == container_id]
        
        if metric_type:
            container_trends = [t for t in container_trends if t.metric_type == metric_type]
        
        return [
            PerformanceTrendResponse(
                metric_type=trend.metric_type,
                container_id=trend.container_id,
                container_name=trend.container_name,
                service_name=trend.service_name,
                direction=TrendDirectionResponse(trend.direction.value),
                slope=trend.slope,
                correlation=trend.correlation,
                current_value=trend.current_value,
                average_value=trend.average_value,
                min_value=trend.min_value,
                max_value=trend.max_value,
                std_deviation=trend.std_deviation,
                predicted_1h=trend.predicted_1h,
                predicted_6h=trend.predicted_6h,
                predicted_24h=trend.predicted_24h,
                confidence=PredictionConfidenceResponse(trend.confidence.value),
                calculated_at=trend.calculated_at,
                data_points=trend.data_points,
                time_range_hours=trend.time_range_hours
            )
            for trend in container_trends
        ]
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des tendances du conteneur: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/optimizations", response_model=List[ResourceOptimizationResponse])
async def get_resource_optimizations(
    container_id: Optional[str] = Query(None, description="ID du conteneur à filtrer"),
    resource_type: Optional[str] = Query(None, description="Type de ressource (cpu, memory, network)"),
    optimization_type: Optional[str] = Query(None, description="Type d'optimisation (increase, decrease, optimize)"),
    impact_level: Optional[str] = Query(None, description="Niveau d'impact (low, medium, high)"),
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(100, ge=1, le=1000),
    analytics: AdvancedAnalyticsService = Depends(get_analytics_service)
):
    """Récupère les recommandations d'optimisation des ressources"""
    try:
        optimizations = await analytics.get_recent_optimizations(hours=hours)
        
        # Applique les filtres
        filtered_opts = optimizations
        
        if container_id:
            filtered_opts = [o for o in filtered_opts if o.container_id == container_id]
        
        if resource_type:
            filtered_opts = [o for o in filtered_opts if o.resource_type == resource_type]
        
        if optimization_type:
            filtered_opts = [o for o in filtered_opts if o.optimization_type == optimization_type]
        
        if impact_level:
            filtered_opts = [o for o in filtered_opts if o.impact_level == impact_level]
        
        # Limite les résultats
        filtered_opts = filtered_opts[:limit]
        
        return [
            ResourceOptimizationResponse(
                container_id=opt.container_id,
                container_name=opt.container_name,
                service_name=opt.service_name,
                resource_type=opt.resource_type,
                optimization_type=opt.optimization_type,
                current_limit=opt.current_limit,
                recommended_limit=opt.recommended_limit,
                expected_improvement=opt.expected_improvement,
                reason=opt.reason,
                impact_level=opt.impact_level,
                confidence_score=opt.confidence_score,
                created_at=opt.created_at
            )
            for opt in filtered_opts
        ]
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des optimisations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/optimizations/{container_id}", response_model=List[ResourceOptimizationResponse])
async def get_container_optimizations(
    container_id: str,
    resource_type: Optional[str] = Query(None),
    hours: int = Query(24, ge=1, le=168),
    analytics: AdvancedAnalyticsService = Depends(get_analytics_service)
):
    """Récupère toutes les optimisations pour un conteneur spécifique"""
    try:
        optimizations = await analytics.get_recent_optimizations(hours=hours)
        container_opts = [o for o in optimizations if o.container_id == container_id]
        
        if resource_type:
            container_opts = [o for o in container_opts if o.resource_type == resource_type]
        
        return [
            ResourceOptimizationResponse(
                container_id=opt.container_id,
                container_name=opt.container_name,
                service_name=opt.service_name,
                resource_type=opt.resource_type,
                optimization_type=opt.optimization_type,
                current_limit=opt.current_limit,
                recommended_limit=opt.recommended_limit,
                expected_improvement=opt.expected_improvement,
                reason=opt.reason,
                impact_level=opt.impact_level,
                confidence_score=opt.confidence_score,
                created_at=opt.created_at
            )
            for opt in container_opts
        ]
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des optimisations du conteneur: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports", response_model=List[PerformanceReportResponse])
async def get_performance_reports(
    days: int = Query(7, ge=1, le=90, description="Nombre de jours à récupérer"),
    limit: int = Query(50, ge=1, le=200),
    analytics: AdvancedAnalyticsService = Depends(get_analytics_service)
):
    """Récupère les rapports de performance générés"""
    try:
        reports = await analytics.get_recent_reports(days=days)
        reports = reports[:limit]
        
        response_reports = []
        for report in reports:
            # Convertit les tendances
            trends = [
                PerformanceTrendResponse(
                    metric_type=trend.metric_type,
                    container_id=trend.container_id,
                    container_name=trend.container_name,
                    service_name=trend.service_name,
                    direction=TrendDirectionResponse(trend.direction.value),
                    slope=trend.slope,
                    correlation=trend.correlation,
                    current_value=trend.current_value,
                    average_value=trend.average_value,
                    min_value=trend.min_value,
                    max_value=trend.max_value,
                    std_deviation=trend.std_deviation,
                    predicted_1h=trend.predicted_1h,
                    predicted_6h=trend.predicted_6h,
                    predicted_24h=trend.predicted_24h,
                    confidence=PredictionConfidenceResponse(trend.confidence.value),
                    calculated_at=trend.calculated_at,
                    data_points=trend.data_points,
                    time_range_hours=trend.time_range_hours
                )
                for trend in report.trends
            ]
            
            # Convertit les optimisations
            optimizations = [
                ResourceOptimizationResponse(
                    container_id=opt.container_id,
                    container_name=opt.container_name,
                    service_name=opt.service_name,
                    resource_type=opt.resource_type,
                    optimization_type=opt.optimization_type,
                    current_limit=opt.current_limit,
                    recommended_limit=opt.recommended_limit,
                    expected_improvement=opt.expected_improvement,
                    reason=opt.reason,
                    impact_level=opt.impact_level,
                    confidence_score=opt.confidence_score,
                    created_at=opt.created_at
                )
                for opt in report.optimizations
            ]
            
            response_reports.append(PerformanceReportResponse(
                report_id=report.report_id,
                period_start=report.period_start,
                period_end=report.period_end,
                total_containers=report.total_containers,
                average_cpu=report.average_cpu,
                average_memory=report.average_memory,
                total_network_gb=report.total_network_gb,
                top_cpu_consumers=report.top_cpu_consumers,
                top_memory_consumers=report.top_memory_consumers,
                problematic_containers=report.problematic_containers,
                trends=trends,
                optimizations=optimizations,
                alerts_summary=report.alerts_summary,
                generated_at=report.generated_at
            ))
        
        return response_reports
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des rapports: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/{report_id}", response_model=PerformanceReportResponse)
async def get_performance_report(
    report_id: str,
    analytics: AdvancedAnalyticsService = Depends(get_analytics_service)
):
    """Récupère un rapport de performance spécifique"""
    try:
        reports = await analytics.get_recent_reports(days=90)  # Cherche dans les 3 derniers mois
        
        report = next((r for r in reports if r.report_id == report_id), None)
        if not report:
            raise HTTPException(status_code=404, detail="Rapport non trouvé")
        
        # Convertit les tendances
        trends = [
            PerformanceTrendResponse(
                metric_type=trend.metric_type,
                container_id=trend.container_id,
                container_name=trend.container_name,
                service_name=trend.service_name,
                direction=TrendDirectionResponse(trend.direction.value),
                slope=trend.slope,
                correlation=trend.correlation,
                current_value=trend.current_value,
                average_value=trend.average_value,
                min_value=trend.min_value,
                max_value=trend.max_value,
                std_deviation=trend.std_deviation,
                predicted_1h=trend.predicted_1h,
                predicted_6h=trend.predicted_6h,
                predicted_24h=trend.predicted_24h,
                confidence=PredictionConfidenceResponse(trend.confidence.value),
                calculated_at=trend.calculated_at,
                data_points=trend.data_points,
                time_range_hours=trend.time_range_hours
            )
            for trend in report.trends
        ]
        
        # Convertit les optimisations
        optimizations = [
            ResourceOptimizationResponse(
                container_id=opt.container_id,
                container_name=opt.container_name,
                service_name=opt.service_name,
                resource_type=opt.resource_type,
                optimization_type=opt.optimization_type,
                current_limit=opt.current_limit,
                recommended_limit=opt.recommended_limit,
                expected_improvement=opt.expected_improvement,
                reason=opt.reason,
                impact_level=opt.impact_level,
                confidence_score=opt.confidence_score,
                created_at=opt.created_at
            )
            for opt in report.optimizations
        ]
        
        return PerformanceReportResponse(
            report_id=report.report_id,
            period_start=report.period_start,
            period_end=report.period_end,
            total_containers=report.total_containers,
            average_cpu=report.average_cpu,
            average_memory=report.average_memory,
            total_network_gb=report.total_network_gb,
            top_cpu_consumers=report.top_cpu_consumers,
            top_memory_consumers=report.top_memory_consumers,
            problematic_containers=report.problematic_containers,
            trends=trends,
            optimizations=optimizations,
            alerts_summary=report.alerts_summary,
            generated_at=report.generated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du rapport: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reports/generate")
async def generate_performance_report(
    background_tasks: BackgroundTasks,
    period_hours: int = Query(24, ge=1, le=168, description="Période du rapport en heures"),
    analytics: AdvancedAnalyticsService = Depends(get_analytics_service)
):
    """Génère un nouveau rapport de performance"""
    try:
        # Lance la génération en arrière-plan
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=period_hours)
        
        # Pour l'instant, on génère synchrone, mais on pourrait l'optimiser
        if period_hours <= 24:
            await analytics._generate_daily_report(end_time)
        else:
            await analytics._generate_weekly_report(end_time)
        
        return {
            "message": "Rapport généré avec succès",
            "period_start": start_time.isoformat(),
            "period_end": end_time.isoformat(),
            "period_hours": period_hours
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération du rapport: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/summary")
async def get_analytics_summary(
    hours: int = Query(24, ge=1, le=168),
    analytics: AdvancedAnalyticsService = Depends(get_analytics_service)
):
    """Récupère un résumé des analytics pour le dashboard"""
    try:
        # Récupère les données récentes
        trends = await analytics.get_recent_trends(hours=hours)
        optimizations = await analytics.get_recent_optimizations(hours=hours)
        
        # Calcule les statistiques de résumé
        trends_by_direction = {}
        for trend in trends:
            direction = trend.direction.value
            if direction not in trends_by_direction:
                trends_by_direction[direction] = 0
            trends_by_direction[direction] += 1
        
        trends_by_confidence = {}
        for trend in trends:
            confidence = trend.confidence.value
            if confidence not in trends_by_confidence:
                trends_by_confidence[confidence] = 0
            trends_by_confidence[confidence] += 1
        
        optimizations_by_type = {}
        for opt in optimizations:
            opt_type = opt.optimization_type
            if opt_type not in optimizations_by_type:
                optimizations_by_type[opt_type] = 0
            optimizations_by_type[opt_type] += 1
        
        optimizations_by_impact = {}
        for opt in optimizations:
            impact = opt.impact_level
            if impact not in optimizations_by_impact:
                optimizations_by_impact[impact] = 0
            optimizations_by_impact[impact] += 1
        
        # Conteneurs les plus problématiques
        container_issues = {}
        for trend in trends:
            if trend.direction == TrendDirection.INCREASING and trend.current_value > 80:
                container_id = trend.container_id
                if container_id not in container_issues:
                    container_issues[container_id] = {
                        'container_name': trend.container_name,
                        'service_name': trend.service_name,
                        'issues': []
                    }
                container_issues[container_id]['issues'].append({
                    'metric': trend.metric_type,
                    'current_value': trend.current_value,
                    'predicted_24h': trend.predicted_24h
                })
        
        # Top 5 des conteneurs problématiques
        top_problematic = sorted(
            [(cid, data) for cid, data in container_issues.items()],
            key=lambda x: len(x[1]['issues']),
            reverse=True
        )[:5]
        
        return {
            'period_hours': hours,
            'summary': {
                'total_trends': len(trends),
                'total_optimizations': len(optimizations),
                'unique_containers': len(set(t.container_id for t in trends))
            },
            'trends_by_direction': trends_by_direction,
            'trends_by_confidence': trends_by_confidence,
            'optimizations_by_type': optimizations_by_type,
            'optimizations_by_impact': optimizations_by_impact,
            'top_problematic_containers': [
                {
                    'container_id': cid,
                    'container_name': data['container_name'],
                    'service_name': data['service_name'],
                    'issues_count': len(data['issues']),
                    'issues': data['issues']
                }
                for cid, data in top_problematic
            ],
            'generated_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la génération du résumé analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/config")
async def update_analytics_config(
    config: AnalyticsConfigUpdate,
    analytics: AdvancedAnalyticsService = Depends(get_analytics_service)
):
    """Met à jour la configuration du service d'analytics"""
    try:
        # Met à jour les paramètres de configuration
        if config.trend_analysis_hours is not None:
            analytics.trend_analysis_hours = config.trend_analysis_hours
        
        if config.prediction_model_points is not None:
            analytics.prediction_model_points = config.prediction_model_points
        
        if config.volatility_threshold is not None:
            analytics.volatility_threshold = config.volatility_threshold
        
        if config.correlation_threshold is not None:
            analytics.correlation_threshold = config.correlation_threshold
        
        return {
            "message": "Configuration mise à jour",
            "new_config": analytics.get_analytics_stats()
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Fonctions utilitaires pour l'intégration
def convert_trend_to_response(trend: PerformanceTrend) -> PerformanceTrendResponse:
    """Convertit un PerformanceTrend en PerformanceTrendResponse"""
    return PerformanceTrendResponse(
        metric_type=trend.metric_type,
        container_id=trend.container_id,
        container_name=trend.container_name,
        service_name=trend.service_name,
        direction=TrendDirectionResponse(trend.direction.value),
        slope=trend.slope,
        correlation=trend.correlation,
        current_value=trend.current_value,
        average_value=trend.average_value,
        min_value=trend.min_value,
        max_value=trend.max_value,
        std_deviation=trend.std_deviation,
        predicted_1h=trend.predicted_1h,
        predicted_6h=trend.predicted_6h,
        predicted_24h=trend.predicted_24h,
        confidence=PredictionConfidenceResponse(trend.confidence.value),
        calculated_at=trend.calculated_at,
        data_points=trend.data_points,
        time_range_hours=trend.time_range_hours
    )

def convert_optimization_to_response(opt: ResourceOptimization) -> ResourceOptimizationResponse:
    """Convertit un ResourceOptimization en ResourceOptimizationResponse"""
    return ResourceOptimizationResponse(
        container_id=opt.container_id,
        container_name=opt.container_name,
        service_name=opt.service_name,
        resource_type=opt.resource_type,
        optimization_type=opt.optimization_type,
        current_limit=opt.current_limit,
        recommended_limit=opt.recommended_limit,
        expected_improvement=opt.expected_improvement,
        reason=opt.reason,
        impact_level=opt.impact_level,
        confidence_score=opt.confidence_score,
        created_at=opt.created_at
    )
