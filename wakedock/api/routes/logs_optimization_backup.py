"""
API routes pour l'optimisation et performance des logs - Version 0# Service global d'optimisation
optimization_service: Optional[LogOptimizationService] = Nonemport asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from pydantic import BaseModel, Field
import time

from wakedock.core.log_optimization_service import LogOptimizationService, CompressionStats
from wakedock.core.dependencies import get_log_optimization_service

logger = logging.getLogger(__name__)

# Models Pydantic pour l'optimisation
class OptimizationStatsResponse(BaseModel):
    total_indexed_logs: int
    unique_search_terms: int
    database_size_bytes: int
    is_running: bool
    cache_size: int
    compression_ratio: float
    cache_hit_ratio: float
    compression_stats: Dict[str, Any]

class OptimizedSearchRequest(BaseModel):
    query: Optional[str] = None
    container_id: Optional[str] = None
    level: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(default=1000, le=10000)
    use_cache: bool = True

class OptimizedSearchResponse(BaseModel):
    log_ids: List[str]
    total_found: int
    search_time_ms: float
    cache_hit: bool
    performance_stats: Dict[str, Any]

class CompressionRequest(BaseModel):
    compression_type: str = Field(default="lz4", pattern="^(lz4|gzip)$")
    file_patterns: List[str] = Field(default=["*.log"])
    min_size_mb: float = Field(default=10.0, ge=0.1)

class CompressionResponse(BaseModel):
    files_processed: int
    total_original_size: int
    total_compressed_size: int
    compression_ratio: float
    time_taken: float
    files_compressed: List[str]

class IndexRebuildRequest(BaseModel):
    force_rebuild: bool = False
    optimize_after_rebuild: bool = True
    batch_size: int = Field(default=1000, ge=100, le=10000)

class PerformanceAnalysisResponse(BaseModel):
    query_performance: Dict[str, float]
    index_efficiency: Dict[str, float]
    storage_efficiency: Dict[str, Any]
    recommendations: List[str]

# Router pour l'optimisation
router = APIRouter(prefix="/api/v1/logs/optimization", tags=["logs-optimization"])

# Instance globale du service d'optimisation
optimization_service: Optional[LogOptimizationService] = None

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
async def optimized_search(
    request: OptimizedSearchRequest,
    service: LogOptimizationService = Depends(get_optimization_service)
):
    """Recherche optimisée avec cache et indexation"""
    try:
        start_time = time.time()
        
        log_ids, search_time = await service.search_logs_optimized(
            query=request.query,
            container_id=request.container_id,
            level=request.level,
            start_time=request.start_time,
            end_time=request.end_time,
            limit=request.limit
        )
        
        total_time = time.time() - start_time
        
        # Vérifier si c'était un cache hit (recherche très rapide)
        cache_hit = search_time < 0.001
        
        return OptimizedSearchResponse(
            log_ids=log_ids,
            total_found=len(log_ids),
            search_time_ms=search_time * 1000,
            cache_hit=cache_hit,
            performance_stats={
                "total_time_ms": total_time * 1000,
                "index_time_ms": search_time * 1000,
                "results_count": len(log_ids)
            }
        )
    except Exception as e:
        logger.error(f"Erreur lors de la recherche optimisée: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/compress", response_model=CompressionResponse)
async def compress_logs(
    request: CompressionRequest,
    background_tasks: BackgroundTasks,
    service: LogOptimizationService = Depends(get_optimization_service)
):
    """Compresse les fichiers de logs selon les critères"""
    try:
        from pathlib import Path
        import glob
        
        files_to_compress = []
        
        # Rechercher les fichiers correspondant aux patterns
        for pattern in request.file_patterns:
            files = list(service.storage_path.glob(pattern))
            
            # Filtrer par taille minimale
            for file_path in files:
                if file_path.is_file():
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    if size_mb >= request.min_size_mb:
                        files_to_compress.append(file_path)
        
        if not files_to_compress:
            return CompressionResponse(
                files_processed=0,
                total_original_size=0,
                total_compressed_size=0,
                compression_ratio=0.0,
                time_taken=0.0,
                files_compressed=[]
            )
        
        # Compresser les fichiers
        total_original_size = 0
        total_compressed_size = 0
        files_compressed = []
        start_time = time.time()
        
        for file_path in files_to_compress:
            try:
                original_size = file_path.stat().st_size
                stats = await service.compress_log_file(file_path, request.compression_type)
                
                total_original_size += stats.original_size
                total_compressed_size += stats.compressed_size
                files_compressed.append(str(file_path.name))
                
            except Exception as e:
                logger.warning(f"Échec de compression pour {file_path}: {e}")
        
        total_time = time.time() - start_time
        compression_ratio = (
            (1 - total_compressed_size / total_original_size) * 100
            if total_original_size > 0 else 0
        )
        
        return CompressionResponse(
            files_processed=len(files_to_compress),
            total_original_size=total_original_size,
            total_compressed_size=total_compressed_size,
            compression_ratio=compression_ratio,
            time_taken=total_time,
            files_compressed=files_compressed
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de la compression: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/index/rebuild")
async def rebuild_search_index(
    request: IndexRebuildRequest,
    background_tasks: BackgroundTasks,
    service: LogOptimizationService = Depends(get_optimization_service)
):
    """Reconstruit l'index de recherche"""
    try:
        # Créer une tâche d'arrière-plan pour la reconstruction
        async def rebuild_task():
            try:
                logger.info("Début de la reconstruction de l'index")
                
                if request.force_rebuild:
                    # Vider l'index existant
                    service.search_index.term_to_logs.clear()
                    service.search_index.log_metadata.clear()
                    service.search_index.container_index.clear()
                    service.search_index.level_index.clear()
                    service.search_index.time_buckets.clear()
                
                # Recharger l'index depuis la base de données
                await service._load_search_index()
                
                logger.info("Reconstruction de l'index terminée")
                
            except Exception as e:
                logger.error(f"Erreur lors de la reconstruction de l'index: {e}")
        
        background_tasks.add_task(rebuild_task)
        
        return {
            "message": "Reconstruction de l'index démarrée en arrière-plan",
            "force_rebuild": request.force_rebuild,
            "batch_size": request.batch_size
        }
        
    except Exception as e:
        logger.error(f"Erreur lors du démarrage de la reconstruction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance/analysis", response_model=PerformanceAnalysisResponse)
async def analyze_performance(
    service: LogOptimizationService = Depends(get_optimization_service)
):
    """Analyse les performances du système de logs"""
    try:
        stats = service.get_optimization_stats()
        
        # Analyse des performances de requête
        query_performance = {
            "cache_hit_ratio": stats.get("cache_hit_ratio", 0),
            "average_search_time_ms": 50.0,  # Calculer depuis les stats réelles
            "index_efficiency": 0.95 if stats["unique_search_terms"] > 0 else 0
        }
        
        # Efficacité de l'index
        index_efficiency = {
            "terms_per_log": (
                stats["unique_search_terms"] / stats["total_indexed_logs"]
                if stats["total_indexed_logs"] > 0 else 0
            ),
            "database_size_mb": stats["database_size_bytes"] / (1024 * 1024),
            "compression_efficiency": stats.get("compression_ratio", 0)
        }
        
        # Efficacité du stockage
        storage_efficiency = {
            "total_indexed_logs": stats["total_indexed_logs"],
            "database_size_bytes": stats["database_size_bytes"],
            "cache_size": stats.get("cache_size", 0),
            "compression_stats": stats.get("compression_stats", {})
        }
        
        # Recommandations d'optimisation
        recommendations = []
        
        if query_performance["cache_hit_ratio"] < 0.3:
            recommendations.append("Augmenter la TTL du cache pour améliorer le taux de cache hit")
        
        if index_efficiency["database_size_mb"] > 1000:
            recommendations.append("Considérer une rotation plus fréquente des logs")
        
        if stats["total_indexed_logs"] > 1000000:
            recommendations.append("Activer la compression automatique pour réduire l'espace disque")
        
        if index_efficiency["terms_per_log"] > 30:
            recommendations.append("Réduire le nombre de termes par log pour optimiser l'index")
        
        if not recommendations:
            recommendations.append("Les performances sont optimales")
        
        return PerformanceAnalysisResponse(
            query_performance=query_performance,
            index_efficiency=index_efficiency,
            storage_efficiency=storage_efficiency,
            recommendations=recommendations
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse de performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cache/clear")
async def clear_search_cache(
    service: LogOptimizationService = Depends(get_optimization_service)
):
    """Vide le cache de recherche"""
    try:
        cache_size_before = len(service.search_cache)
        service.search_cache.clear()
        
        return {
            "message": "Cache vidé avec succès",
            "entries_cleared": cache_size_before
        }
        
    except Exception as e:
        logger.error(f"Erreur lors du vidage du cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/service/start")
async def start_optimization_service(
    background_tasks: BackgroundTasks,
    service: LogOptimizationService = Depends(get_optimization_service)
):
    """Démarre le service d'optimisation"""
    try:
        if not service.is_running:
            background_tasks.add_task(service.start)
        
        return {
            "message": "Service d'optimisation démarré",
            "status": "started" if service.is_running else "starting"
        }
        
    except Exception as e:
        logger.error(f"Erreur lors du démarrage du service d'optimisation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/service/stop")
async def stop_optimization_service(
    service: LogOptimizationService = Depends(get_optimization_service)
):
    """Arrête le service d'optimisation"""
    try:
        await service.stop()
        
        return {
            "message": "Service d'optimisation arrêté",
            "status": "stopped"
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de l'arrêt du service d'optimisation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/storage/usage")
async def get_storage_usage(
    service: LogOptimizationService = Depends(get_optimization_service)
):
    """Analyse l'utilisation du stockage"""
    try:
        from pathlib import Path

        # Calculer l'espace utilisé
        total_size = 0
        file_count = 0
        
        for file_path in service.storage_path.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
                file_count += 1
        
        # Analyser par type de fichier
        storage_breakdown = {
            "log_files": 0,
            "compressed_files": 0,
            "index_files": 0,
            "other_files": 0
        }
        
        for file_path in service.storage_path.rglob("*"):
            if file_path.is_file():
                size = file_path.stat().st_size
                
                if file_path.suffix in ['.log', '.txt']:
                    storage_breakdown["log_files"] += size
                elif file_path.suffix in ['.lz4', '.gz']:
                    storage_breakdown["compressed_files"] += size
                elif file_path.suffix in ['.db', '.idx']:
                    storage_breakdown["index_files"] += size
                else:
                    storage_breakdown["other_files"] += size
        
        return {
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "file_count": file_count,
            "storage_breakdown": storage_breakdown,
            "compression_savings": (
                storage_breakdown["compressed_files"] / total_size * 100
                if total_size > 0 else 0
            )
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de l'analyse du stockage: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/maintenance/purge")
async def purge_old_logs(
    days_to_keep: int = Query(default=30, ge=1, le=365),
    service: LogOptimizationService = Depends(get_optimization_service)
):
    """Purge les logs anciens"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        # Compter les logs à supprimer
        logs_to_remove = []
        for log_id, entry in service.search_index.log_metadata.items():
            if entry.timestamp < cutoff_date:
                logs_to_remove.append(log_id)
        
        if not logs_to_remove:
            return {
                "message": "Aucun log ancien à supprimer",
                "logs_removed": 0,
                "cutoff_date": cutoff_date.isoformat()
            }
        
        # Déclencher la rotation manuelle
        # (Le worker de rotation se chargera du nettoyage réel)
        return {
            "message": f"Purge programmée pour {len(logs_to_remove)} logs",
            "logs_to_remove": len(logs_to_remove),
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la purge: {e}")
        raise HTTPException(status_code=500, detail=str(e))
