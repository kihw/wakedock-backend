"""
API routes pour l'optimisation et performance des logs - Version 0.2.5
"""
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from wakedock.core.dependencies import get_log_optimization_service
from wakedock.core.log_optimization_service import LogOptimizationService

logger = logging.getLogger(__name__)

# Router pour les endpoints d'optimisation des logs
router = APIRouter(prefix="/logs-optimization")

# Modèles Pydantic pour les réponses

class OptimizationStatsResponse(BaseModel):
    """Réponse pour les statistiques d'optimisation"""
    storage_stats: Dict[str, Any]
    compression_stats: Dict[str, Any]
    indexing_stats: Dict[str, Any]
    cache_stats: Dict[str, Any]
    performance_metrics: Dict[str, Any]

class OptimizedSearchResponse(BaseModel):
    """Réponse pour la recherche optimisée"""
    logs: List[Dict[str, Any]]
    total_count: int
    search_time_ms: float
    cache_hit: bool
    metadata: Dict[str, Any]

class CompressionRequest(BaseModel):
    """Requête pour compression de logs"""
    container_ids: Optional[List[str]] = None
    date_range: Optional[Dict[str, datetime]] = None
    compression_type: Optional[str] = Field(default="lz4", regex="^(lz4|gzip)$")
    min_age_hours: Optional[int] = Field(default=24, ge=1)

class IndexRebuildRequest(BaseModel):
    """Requête pour reconstruction d'index"""
    container_ids: Optional[List[str]] = None
    full_rebuild: bool = Field(default=False)
    preserve_cache: bool = Field(default=True)

class SearchRequest(BaseModel):
    """Requête pour recherche optimisée"""
    query: str = Field(..., min_length=1)
    container_ids: Optional[List[str]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    log_level: Optional[str] = None
    limit: int = Field(default=100, le=1000, ge=1)
    offset: int = Field(default=0, ge=0)
    use_cache: bool = Field(default=True)

class MaintenanceRequest(BaseModel):
    """Requête pour maintenance"""
    operation: str = Field(..., regex="^(cleanup|optimize|rebuild|purge)$")
    parameters: Optional[Dict[str, Any]] = None

class PerformanceAnalysisResponse(BaseModel):
    """Réponse pour analyse de performance"""
    storage_analysis: Dict[str, Any]
    search_performance: Dict[str, Any]
    compression_efficiency: Dict[str, Any]
    recommendations: List[Dict[str, Any]]

@router.get("/stats", response_model=OptimizationStatsResponse)
async def get_optimization_stats(
    service: LogOptimizationService = Depends(get_log_optimization_service)
):
    """Récupère les statistiques d'optimisation"""
    try:
        stats = service.get_optimization_stats()
        return OptimizationStatsResponse(**stats)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats d'optimisation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search", response_model=OptimizedSearchResponse)
async def search_logs_optimized(
    request: SearchRequest,
    service: LogOptimizationService = Depends(get_log_optimization_service)
):
    """Recherche optimisée dans les logs"""
    try:
        start_time = time.time()
        
        search_options = {
            "container_ids": request.container_ids,
            "start_date": request.start_date,
            "end_date": request.end_date,
            "log_level": request.log_level,
            "limit": request.limit,
            "offset": request.offset,
            "use_cache": request.use_cache
        }
        
        results = await service.search_logs_optimized(
            query=request.query,
            **search_options
        )
        
        search_time = (time.time() - start_time) * 1000
        
        return OptimizedSearchResponse(
            logs=results.get("logs", []),
            total_count=results.get("total_count", 0),
            search_time_ms=search_time,
            cache_hit=results.get("cache_hit", False),
            metadata=results.get("metadata", {})
        )
    except Exception as e:
        logger.error(f"Erreur lors de la recherche optimisée: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/compress")
async def compress_logs(
    request: CompressionRequest,
    background_tasks: BackgroundTasks,
    service: LogOptimizationService = Depends(get_log_optimization_service)
):
    """Lance la compression de logs en arrière-plan"""
    try:
        # Configuration de compression
        compression_config = {
            "container_ids": request.container_ids,
            "compression_type": request.compression_type,
            "min_age_hours": request.min_age_hours
        }
        
        if request.date_range:
            compression_config["date_range"] = request.date_range
        
        # Lance la compression en arrière-plan
        background_tasks.add_task(
            service.compress_logs_batch,
            **compression_config
        )
        
        return {
            "message": "Compression lancée en arrière-plan",
            "config": compression_config
        }
    except Exception as e:
        logger.error(f"Erreur lors du lancement de la compression: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/compression/status")
async def get_compression_status(
    service: LogOptimizationService = Depends(get_log_optimization_service)
):
    """Récupère le statut des opérations de compression"""
    try:
        status = service.get_compression_status()
        return {
            "active_operations": status.get("active_operations", []),
            "completed_operations": status.get("completed_operations", []),
            "compression_queue": status.get("queue_size", 0),
            "total_compressed": status.get("total_compressed", 0),
            "storage_saved": status.get("storage_saved", 0)
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut de compression: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/index/rebuild")
async def rebuild_search_index(
    request: IndexRebuildRequest,
    background_tasks: BackgroundTasks,
    service: LogOptimizationService = Depends(get_log_optimization_service)
):
    """Reconstruit l'index de recherche"""
    try:
        rebuild_config = {
            "container_ids": request.container_ids,
            "full_rebuild": request.full_rebuild,
            "preserve_cache": request.preserve_cache
        }
        
        background_tasks.add_task(
            service.rebuild_search_index,
            **rebuild_config
        )
        
        return {
            "message": "Reconstruction d'index lancée",
            "config": rebuild_config
        }
    except Exception as e:
        logger.error(f"Erreur lors de la reconstruction d'index: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/index/status")
async def get_index_status(
    service: LogOptimizationService = Depends(get_log_optimization_service)
):
    """Récupère le statut de l'index de recherche"""
    try:
        status = service.get_index_status()
        return {
            "index_size": status.get("index_size", 0),
            "indexed_logs": status.get("indexed_logs", 0),
            "last_update": status.get("last_update"),
            "index_health": status.get("health", "unknown"),
            "fragmentation": status.get("fragmentation", 0)
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut d'index: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/cache/clear")
async def clear_search_cache(
    service: LogOptimizationService = Depends(get_log_optimization_service)
):
    """Vide le cache de recherche"""
    try:
        cleared_entries = await service.clear_search_cache()
        return {
            "message": "Cache vidé avec succès",
            "cleared_entries": cleared_entries
        }
    except Exception as e:
        logger.error(f"Erreur lors du vidage du cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cache/stats")
async def get_cache_stats(
    service: LogOptimizationService = Depends(get_log_optimization_service)
):
    """Récupère les statistiques du cache"""
    try:
        stats = service.get_cache_stats()
        return {
            "cache_size": stats.get("size", 0),
            "hit_rate": stats.get("hit_rate", 0.0),
            "entries_count": stats.get("entries", 0),
            "memory_usage": stats.get("memory_usage", 0),
            "evictions": stats.get("evictions", 0)
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats de cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/maintenance")
async def run_maintenance(
    request: MaintenanceRequest,
    background_tasks: BackgroundTasks,
    service: LogOptimizationService = Depends(get_log_optimization_service)
):
    """Lance une opération de maintenance"""
    try:
        operation = request.operation
        parameters = request.parameters or {}
        
        if operation == "cleanup":
            background_tasks.add_task(service.cleanup_old_logs, **parameters)
        elif operation == "optimize":
            background_tasks.add_task(service.optimize_storage, **parameters)
        elif operation == "rebuild":
            background_tasks.add_task(service.rebuild_search_index, **parameters)
        elif operation == "purge":
            background_tasks.add_task(service.purge_compressed_logs, **parameters)
        
        return {
            "message": f"Opération '{operation}' lancée en arrière-plan",
            "operation": operation,
            "parameters": parameters
        }
    except Exception as e:
        logger.error(f"Erreur lors du lancement de la maintenance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance/analysis", response_model=PerformanceAnalysisResponse)
async def get_performance_analysis(
    service: LogOptimizationService = Depends(get_log_optimization_service)
):
    """Analyse les performances du système de logs"""
    try:
        analysis = await service.analyze_performance()
        return PerformanceAnalysisResponse(**analysis)
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse de performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/storage/usage")
async def get_storage_usage(
    service: LogOptimizationService = Depends(get_log_optimization_service)
):
    """Récupère l'utilisation du stockage"""
    try:
        usage = service.get_storage_usage()
        return {
            "total_size": usage.get("total_size", 0),
            "compressed_size": usage.get("compressed_size", 0),
            "uncompressed_size": usage.get("uncompressed_size", 0),
            "compression_ratio": usage.get("compression_ratio", 0.0),
            "index_size": usage.get("index_size", 0),
            "cache_size": usage.get("cache_size", 0),
            "breakdown_by_container": usage.get("breakdown", {})
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'utilisation du stockage: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommendations")
async def get_optimization_recommendations(
    service: LogOptimizationService = Depends(get_log_optimization_service)
):
    """Récupère les recommandations d'optimisation"""
    try:
        recommendations = await service.get_optimization_recommendations()
        return {
            "recommendations": recommendations,
            "priority_actions": [r for r in recommendations if r.get("priority") == "high"],
            "potential_savings": sum(r.get("potential_savings", 0) for r in recommendations)
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des recommandations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def get_optimization_health(
    service: LogOptimizationService = Depends(get_log_optimization_service)
):
    """Récupère l'état de santé du système d'optimisation"""
    try:
        health = service.get_health_status()
        return {
            "status": health.get("status", "unknown"),
            "services": health.get("services", {}),
            "last_maintenance": health.get("last_maintenance"),
            "issues": health.get("issues", []),
            "uptime": health.get("uptime", 0)
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'état de santé: {e}")
        raise HTTPException(status_code=500, detail=str(e))
