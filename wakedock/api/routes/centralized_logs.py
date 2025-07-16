"""
API routes pour le système de logs centralisé avec recherche avancée
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import json
import io
import csv

from wakedock.core.log_collector import LogCollector, LogLevel, LogEntry
from wakedock.core.log_search_service import LogSearchService
from wakedock.core.docker_manager import DockerManager

logger = logging.getLogger(__name__)

# Models Pydantic
class LogEntryResponse(BaseModel):
    timestamp: datetime
    level: str
    container_id: str
    container_name: str
    service_name: Optional[str] = None
    message: str
    source: str = "stdout"
    metadata: Dict[str, Any] = {}

class LogSearchRequest(BaseModel):
    query: Optional[str] = None
    container_id: Optional[str] = None
    service_name: Optional[str] = None
    level: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(default=1000, le=10000)

class LogSearchResponse(BaseModel):
    logs: List[LogEntryResponse]
    total_found: int
    search_time_ms: int
    has_more: bool

class LogStatisticsResponse(BaseModel):
    total_logs: int
    level_distribution: Dict[str, int]
    container_distribution: Dict[str, int]
    service_distribution: Dict[str, int]
    timeline: Dict[str, int]

class LogCollectorStatus(BaseModel):
    is_running: bool
    monitored_containers: int
    active_tasks: int
    buffered_logs: int
    log_files: int
    storage_path: str

class LogIndexStatus(BaseModel):
    total_indexed_logs: int
    unique_search_terms: int
    database_size_bytes: int
    is_running: bool

class ExportRequest(BaseModel):
    format: str = Field(default="json", pattern="^(json|csv|txt)$")
    container_id: Optional[str] = None
    service_name: Optional[str] = None
    level: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = Field(default=10000, le=50000)

# Router
router = APIRouter(prefix="/api/v1/logs", tags=["logs"])

# Instances globales (à injecter via dependency injection en production)
log_collector: Optional[LogCollector] = None
log_search_service: Optional[LogSearchService] = None
docker_manager: Optional[DockerManager] = None

async def get_log_collector() -> LogCollector:
    """Dependency pour obtenir le collecteur de logs"""
    global log_collector
    if not log_collector:
        global docker_manager
        if not docker_manager:
            docker_manager = DockerManager()
        log_collector = LogCollector(docker_manager)
        await log_collector.start()
    return log_collector

async def get_log_search_service() -> LogSearchService:
    """Dependency pour obtenir le service de recherche"""
    global log_search_service
    if not log_search_service:
        log_search_service = LogSearchService()
        await log_search_service.start()
    return log_search_service

@router.get("/status", response_model=LogCollectorStatus)
async def get_log_collector_status(
    collector: LogCollector = Depends(get_log_collector)
):
    """Récupère le statut du collecteur de logs"""
    try:
        stats = collector.get_stats()
        return LogCollectorStatus(**stats)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/collector/start")
async def start_log_collector(
    background_tasks: BackgroundTasks,
    collector: LogCollector = Depends(get_log_collector)
):
    """Démarre le collecteur de logs"""
    try:
        if not collector.is_running:
            background_tasks.add_task(collector.start)
        return {"message": "Collecteur de logs démarré", "status": "started"}
    except Exception as e:
        logger.error(f"Erreur lors du démarrage du collecteur: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/collector/stop")
async def stop_log_collector(
    collector: LogCollector = Depends(get_log_collector)
):
    """Arrête le collecteur de logs"""
    try:
        await collector.stop()
        return {"message": "Collecteur de logs arrêté", "status": "stopped"}
    except Exception as e:
        logger.error(f"Erreur lors de l'arrêt du collecteur: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/collector/containers/{container_id}/add")
async def add_container_monitoring(
    container_id: str,
    collector: LogCollector = Depends(get_log_collector)
):
    """Ajoute un conteneur à la surveillance"""
    try:
        await collector.add_container(container_id)
        return {"message": f"Conteneur {container_id} ajouté à la surveillance"}
    except Exception as e:
        logger.error(f"Erreur lors de l'ajout du conteneur: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/collector/containers/{container_id}")
async def remove_container_monitoring(
    container_id: str,
    collector: LogCollector = Depends(get_log_collector)
):
    """Retire un conteneur de la surveillance"""
    try:
        await collector.remove_container(container_id)
        return {"message": f"Conteneur {container_id} retiré de la surveillance"}
    except Exception as e:
        logger.error(f"Erreur lors du retrait du conteneur: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search", response_model=LogSearchResponse)
async def search_logs(
    query: Optional[str] = Query(None, description="Terme de recherche"),
    container_id: Optional[str] = Query(None, description="ID du conteneur"),
    service_name: Optional[str] = Query(None, description="Nom du service"),
    level: Optional[str] = Query(None, description="Niveau de log"),
    start_time: Optional[datetime] = Query(None, description="Date de début"),
    end_time: Optional[datetime] = Query(None, description="Date de fin"),
    limit: int = Query(1000, le=10000, description="Limite de résultats"),
    search_service: LogSearchService = Depends(get_log_search_service)
):
    """Recherche dans les logs avec filtrage avancé"""
    try:
        start_search = datetime.now()
        
        # Convertit le niveau en enum si fourni
        log_level = None
        if level:
            try:
                log_level = LogLevel(level.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Niveau de log invalide: {level}")
        
        # Effectue la recherche
        results = await search_service.search_logs(
            query=query,
            container_id=container_id,
            service_name=service_name,
            start_time=start_time,
            end_time=end_time,
            level=log_level,
            limit=limit + 1  # +1 pour détecter s'il y a plus de résultats
        )
        
        # Convertit les résultats
        logs = []
        for result in results[:limit]:  # Limite au nombre demandé
            logs.append(LogEntryResponse(
                timestamp=datetime.fromisoformat(result['timestamp']),
                level=result['level'],
                container_id=result['container_id'],
                container_name=result['container_name'],
                service_name=result['service_name'],
                message=result['message'],
                metadata=result['metadata']
            ))
        
        search_time_ms = int((datetime.now() - start_search).total_seconds() * 1000)
        has_more = len(results) > limit
        
        return LogSearchResponse(
            logs=logs,
            total_found=len(results),
            search_time_ms=search_time_ms,
            has_more=has_more
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la recherche: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search", response_model=LogSearchResponse)
async def search_logs_post(
    request: LogSearchRequest,
    search_service: LogSearchService = Depends(get_log_search_service)
):
    """Recherche dans les logs avec requête POST (pour requêtes complexes)"""
    try:
        start_search = datetime.now()
        
        # Convertit le niveau en enum si fourni
        log_level = None
        if request.level:
            try:
                log_level = LogLevel(request.level.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Niveau de log invalide: {request.level}")
        
        # Effectue la recherche
        results = await search_service.search_logs(
            query=request.query,
            container_id=request.container_id,
            service_name=request.service_name,
            start_time=request.start_time,
            end_time=request.end_time,
            level=log_level,
            limit=request.limit + 1
        )
        
        # Convertit les résultats
        logs = []
        for result in results[:request.limit]:
            logs.append(LogEntryResponse(
                timestamp=datetime.fromisoformat(result['timestamp']),
                level=result['level'],
                container_id=result['container_id'],
                container_name=result['container_name'],
                service_name=result['service_name'],
                message=result['message'],
                metadata=result['metadata']
            ))
        
        search_time_ms = int((datetime.now() - start_search).total_seconds() * 1000)
        has_more = len(results) > request.limit
        
        return LogSearchResponse(
            logs=logs,
            total_found=len(results),
            search_time_ms=search_time_ms,
            has_more=has_more
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la recherche POST: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stream")
async def stream_logs(
    container_id: Optional[str] = Query(None, description="ID du conteneur"),
    level: Optional[str] = Query(None, description="Niveau de log minimum"),
    follow: bool = Query(True, description="Suivre les nouveaux logs"),
    collector: LogCollector = Depends(get_log_collector)
):
    """Stream en temps réel des logs"""
    
    async def generate_logs():
        """Générateur de logs en streaming"""
        try:
            # Convertit le niveau en enum si fourni
            min_level = None
            if level:
                try:
                    min_level = LogLevel(level.lower())
                except ValueError:
                    yield f"data: {json.dumps({'error': f'Niveau de log invalide: {level}'})}\n\n"
                    return
            
            # Stream les logs existants d'abord
            async for log_entry in collector.get_logs(
                container_id=container_id,
                limit=100  # Derniers 100 logs
            ):
                # Filtre par niveau si spécifié
                if min_level and log_entry.level.value < min_level.value:
                    continue
                
                log_data = {
                    'timestamp': log_entry.timestamp.isoformat(),
                    'level': log_entry.level.value,
                    'container_id': log_entry.container_id,
                    'container_name': log_entry.container_name,
                    'service_name': log_entry.service_name,
                    'message': log_entry.message,
                    'metadata': log_entry.metadata
                }
                
                yield f"data: {json.dumps(log_data)}\n\n"
            
            # Si follow=True, continue à streamer les nouveaux logs
            if follow:
                # Cette partie nécessiterait une implémentation de queue en temps réel
                # Pour l'instant, on simule avec un polling
                last_check = datetime.utcnow()
                while True:
                    await asyncio.sleep(1)  # Check chaque seconde
                    
                    # Récupère les nouveaux logs depuis la dernière vérification
                    async for log_entry in collector.get_logs(
                        container_id=container_id,
                        start_time=last_check,
                        limit=50
                    ):
                        if min_level and log_entry.level.value < min_level.value:
                            continue
                        
                        log_data = {
                            'timestamp': log_entry.timestamp.isoformat(),
                            'level': log_entry.level.value,
                            'container_id': log_entry.container_id,
                            'container_name': log_entry.container_name,
                            'service_name': log_entry.service_name,
                            'message': log_entry.message,
                            'metadata': log_entry.metadata
                        }
                        
                        yield f"data: {json.dumps(log_data)}\n\n"
                    
                    last_check = datetime.utcnow()
                    
        except Exception as e:
            logger.error(f"Erreur dans le streaming: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_logs(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control"
        }
    )

@router.get("/statistics", response_model=LogStatisticsResponse)
async def get_log_statistics(
    container_id: Optional[str] = Query(None, description="ID du conteneur"),
    start_time: Optional[datetime] = Query(None, description="Date de début"),
    end_time: Optional[datetime] = Query(None, description="Date de fin"),
    search_service: LogSearchService = Depends(get_log_search_service)
):
    """Récupère les statistiques des logs"""
    try:
        stats = await search_service.get_log_statistics(
            container_id=container_id,
            start_time=start_time,
            end_time=end_time
        )
        
        return LogStatisticsResponse(**stats)
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/index/status", response_model=LogIndexStatus)
async def get_index_status(
    search_service: LogSearchService = Depends(get_log_search_service)
):
    """Récupère le statut de l'index de recherche"""
    try:
        stats = await search_service.get_index_stats()
        return LogIndexStatus(**stats)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut de l'index: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/index/rebuild")
async def rebuild_search_index(
    background_tasks: BackgroundTasks,
    search_service: LogSearchService = Depends(get_log_search_service)
):
    """Reconstruit l'index de recherche"""
    try:
        background_tasks.add_task(search_service._reindex_all)
        return {"message": "Reconstruction de l'index en cours", "status": "started"}
    except Exception as e:
        logger.error(f"Erreur lors de la reconstruction de l'index: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/export")
async def export_logs(
    request: ExportRequest,
    search_service: LogSearchService = Depends(get_log_search_service)
):
    """Exporte les logs dans différents formats"""
    try:
        # Convertit le niveau en enum si fourni
        log_level = None
        if request.level:
            try:
                log_level = LogLevel(request.level.lower())
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Niveau de log invalide: {request.level}")
        
        # Récupère les logs
        results = await search_service.search_logs(
            query=None,  # Pas de recherche textuelle pour l'export
            container_id=request.container_id,
            service_name=request.service_name,
            start_time=request.start_time,
            end_time=request.end_time,
            level=log_level,
            limit=request.limit
        )
        
        # Génère le contenu selon le format
        if request.format == "json":
            content = json.dumps(results, indent=2, default=str)
            media_type = "application/json"
            filename = f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
        elif request.format == "csv":
            output = io.StringIO()
            if results:
                fieldnames = ['timestamp', 'level', 'container_name', 'service_name', 'message']
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                
                for result in results:
                    writer.writerow({
                        'timestamp': result['timestamp'],
                        'level': result['level'],
                        'container_name': result['container_name'],
                        'service_name': result['service_name'] or '',
                        'message': result['message']
                    })
            
            content = output.getvalue()
            media_type = "text/csv"
            filename = f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
        elif request.format == "txt":
            lines = []
            for result in results:
                line = f"[{result['timestamp']}] [{result['level'].upper()}] {result['container_name']}: {result['message']}"
                lines.append(line)
            
            content = "\n".join(lines)
            media_type = "text/plain"
            filename = f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        else:
            raise HTTPException(status_code=400, detail=f"Format d'export non supporté: {request.format}")
        
        # Retourne le fichier
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'export: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/containers/{container_id}/logs")
async def get_container_logs(
    container_id: str,
    lines: int = Query(100, le=1000, description="Nombre de lignes"),
    follow: bool = Query(False, description="Suivre les nouveaux logs"),
    since: Optional[str] = Query(None, description="Timestamp de début"),
    collector: LogCollector = Depends(get_log_collector)
):
    """Récupère les logs d'un conteneur spécifique"""
    try:
        # Parse le timestamp si fourni
        start_time = None
        if since:
            try:
                start_time = datetime.fromisoformat(since)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Format de timestamp invalide: {since}")
        
        # Récupère les logs
        logs = []
        async for log_entry in collector.get_logs(
            container_id=container_id,
            start_time=start_time,
            limit=lines
        ):
            logs.append(LogEntryResponse(
                timestamp=log_entry.timestamp,
                level=log_entry.level.value,
                container_id=log_entry.container_id,
                container_name=log_entry.container_name,
                service_name=log_entry.service_name,
                message=log_entry.message,
                source=log_entry.source,
                metadata=log_entry.metadata
            ))
        
        return {
            "container_id": container_id,
            "logs": logs,
            "total": len(logs)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des logs du conteneur: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/logs")
async def cleanup_old_logs(
    days: int = Query(30, ge=1, le=365, description="Supprimer les logs plus anciens que X jours"),
    dry_run: bool = Query(True, description="Mode simulation")
):
    """Nettoie les anciens logs"""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        if dry_run:
            # Mode simulation - compte les logs qui seraient supprimés
            # Cette fonctionnalité nécessiterait d'être implémentée dans le collector
            return {
                "message": f"Mode simulation: logs antérieurs au {cutoff_date.isoformat()} seraient supprimés",
                "dry_run": True,
                "cutoff_date": cutoff_date.isoformat()
            }
        else:
            # Suppression réelle
            # Cette fonctionnalité nécessiterait d'être implémentée dans le collector
            return {
                "message": f"Suppression des logs antérieurs au {cutoff_date.isoformat()}",
                "dry_run": False,
                "cutoff_date": cutoff_date.isoformat()
            }
            
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage: {e}")
        raise HTTPException(status_code=500, detail=str(e))
