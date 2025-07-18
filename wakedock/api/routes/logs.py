"""
Routes API pour la gestion des logs
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from wakedock.api.auth.dependencies import get_current_user
from wakedock.core.docker_manager import DockerManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/logs", tags=["logs"])

# Modèles Pydantic

class LogEntry(BaseModel):
    """Entrée de log"""
    timestamp: datetime
    level: str
    message: str
    container_id: Optional[str] = None
    container_name: Optional[str] = None
    service: Optional[str] = None
    source: str = "application"
    metadata: Dict[str, Any] = Field(default_factory=dict)

class LogFilter(BaseModel):
    """Filtres pour les logs"""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    level: Optional[str] = None
    service: Optional[str] = None
    container_id: Optional[str] = None
    search_text: Optional[str] = None
    limit: int = Field(default=1000, ge=1, le=10000)

class LogExportRequest(BaseModel):
    """Requête d'export de logs"""
    filters: LogFilter
    format: str = Field(default="json", regex="^(json|csv|txt)$")
    include_metadata: bool = True

class ContainerLogRequest(BaseModel):
    """Requête de logs de conteneur"""
    container_id: str
    since: Optional[str] = None
    until: Optional[str] = None
    timestamps: bool = True
    tail: Optional[int] = None
    follow: bool = False

class LogStats(BaseModel):
    """Statistiques des logs"""
    total_entries: int
    error_count: int
    warning_count: int
    info_count: int
    debug_count: int
    time_range: Dict[str, Optional[datetime]]
    services: List[str]
    containers: List[str]

class LogLevel(BaseModel):
    """Configuration des niveaux de log"""
    level: str = Field(..., regex="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    services: List[str] = Field(default=[])
    expires_at: Optional[datetime] = None

# Dépendances

def get_docker_manager() -> DockerManager:
    """Dépendance pour obtenir le gestionnaire Docker"""
    return DockerManager()

# Classes utilitaires

class LogManager:
    """Gestionnaire des logs de l'application"""
    
    def __init__(self, log_dir: str = "/var/log/wakedock"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def get_log_files(self) -> List[Path]:
        """Récupère tous les fichiers de log"""
        return list(self.log_dir.glob("*.log"))
    
    def parse_log_entry(self, line: str) -> Optional[LogEntry]:
        """Parse une ligne de log"""
        try:
            # Format: 2024-01-15 10:30:45 [INFO] [service] message
            parts = line.strip().split(" ", 4)
            if len(parts) >= 4:
                timestamp_str = f"{parts[0]} {parts[1]}"
                timestamp = datetime.fromisoformat(timestamp_str)
                level = parts[2].strip("[]")
                service = parts[3].strip("[]") if len(parts) > 4 else None
                message = parts[4] if len(parts) > 4 else parts[3]
                
                return LogEntry(
                    timestamp=timestamp,
                    level=level,
                    message=message,
                    service=service,
                    source="application"
                )
        except Exception:
            pass
        
        return None
    
    def filter_logs(self, logs: List[LogEntry], filters: LogFilter) -> List[LogEntry]:
        """Filtre les logs selon les critères"""
        filtered = logs
        
        if filters.start_time:
            filtered = [log for log in filtered if log.timestamp >= filters.start_time]
        
        if filters.end_time:
            filtered = [log for log in filtered if log.timestamp <= filters.end_time]
        
        if filters.level:
            filtered = [log for log in filtered if log.level == filters.level]
        
        if filters.service:
            filtered = [log for log in filtered if log.service == filters.service]
        
        if filters.container_id:
            filtered = [log for log in filtered if log.container_id == filters.container_id]
        
        if filters.search_text:
            search_lower = filters.search_text.lower()
            filtered = [
                log for log in filtered 
                if search_lower in log.message.lower()
            ]
        
        # Limiter le nombre de résultats
        return filtered[-filters.limit:]
    
    def get_log_stats(self, logs: List[LogEntry]) -> LogStats:
        """Calcule les statistiques des logs"""
        if not logs:
            return LogStats(
                total_entries=0,
                error_count=0,
                warning_count=0,
                info_count=0,
                debug_count=0,
                time_range={"start": None, "end": None},
                services=[],
                containers=[]
            )
        
        level_counts = {}
        services = set()
        containers = set()
        
        for log in logs:
            level_counts[log.level] = level_counts.get(log.level, 0) + 1
            if log.service:
                services.add(log.service)
            if log.container_id:
                containers.add(log.container_id)
        
        return LogStats(
            total_entries=len(logs),
            error_count=level_counts.get("ERROR", 0),
            warning_count=level_counts.get("WARNING", 0),
            info_count=level_counts.get("INFO", 0),
            debug_count=level_counts.get("DEBUG", 0),
            time_range={
                "start": min(log.timestamp for log in logs),
                "end": max(log.timestamp for log in logs)
            },
            services=list(services),
            containers=list(containers)
        )

# Instance globale
log_manager = LogManager()

# Routes

@router.get("/", response_model=List[LogEntry])
async def get_logs(
    start_time: Optional[datetime] = Query(None, description="Heure de début"),
    end_time: Optional[datetime] = Query(None, description="Heure de fin"),
    level: Optional[str] = Query(None, description="Niveau de log"),
    service: Optional[str] = Query(None, description="Service"),
    container_id: Optional[str] = Query(None, description="ID du conteneur"),
    search_text: Optional[str] = Query(None, description="Texte à rechercher"),
    limit: int = Query(1000, ge=1, le=10000, description="Nombre limite de logs"),
    current_user = Depends(get_current_user)
):
    """
    Récupère les logs de l'application
    """
    try:
        filters = LogFilter(
            start_time=start_time,
            end_time=end_time,
            level=level,
            service=service,
            container_id=container_id,
            search_text=search_text,
            limit=limit
        )
        
        # Lire tous les fichiers de log
        all_logs = []
        for log_file in log_manager.get_log_files():
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        entry = log_manager.parse_log_entry(line)
                        if entry:
                            all_logs.append(entry)
            except Exception as e:
                logger.warning(f"Erreur lors de la lecture du fichier {log_file}: {e}")
        
        # Trier par timestamp
        all_logs.sort(key=lambda x: x.timestamp)
        
        # Filtrer
        filtered_logs = log_manager.filter_logs(all_logs, filters)
        
        return filtered_logs
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de récupération: {str(e)}"
        )

@router.get("/stats", response_model=LogStats)
async def get_log_stats(
    start_time: Optional[datetime] = Query(None, description="Heure de début"),
    end_time: Optional[datetime] = Query(None, description="Heure de fin"),
    current_user = Depends(get_current_user)
):
    """
    Récupère les statistiques des logs
    """
    try:
        filters = LogFilter(
            start_time=start_time,
            end_time=end_time,
            limit=100000  # Large limit pour les stats
        )
        
        # Lire tous les logs
        all_logs = []
        for log_file in log_manager.get_log_files():
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        entry = log_manager.parse_log_entry(line)
                        if entry:
                            all_logs.append(entry)
            except Exception as e:
                logger.warning(f"Erreur lors de la lecture du fichier {log_file}: {e}")
        
        # Filtrer
        filtered_logs = log_manager.filter_logs(all_logs, filters)
        
        # Calculer les stats
        stats = log_manager.get_log_stats(filtered_logs)
        
        return stats
        
    except Exception as e:
        logger.error(f"Erreur lors du calcul des statistiques: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de calcul: {str(e)}"
        )

@router.post("/export")
async def export_logs(
    request: LogExportRequest,
    current_user = Depends(get_current_user)
):
    """
    Exporte les logs dans différents formats
    """
    try:
        # Récupérer les logs filtrés
        all_logs = []
        for log_file in log_manager.get_log_files():
            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        entry = log_manager.parse_log_entry(line)
                        if entry:
                            all_logs.append(entry)
            except Exception as e:
                logger.warning(f"Erreur lors de la lecture du fichier {log_file}: {e}")
        
        # Filtrer
        filtered_logs = log_manager.filter_logs(all_logs, request.filters)
        
        # Générer le contenu selon le format
        if request.format == "json":
            content = json.dumps([
                {
                    "timestamp": log.timestamp.isoformat(),
                    "level": log.level,
                    "message": log.message,
                    "service": log.service,
                    "container_id": log.container_id,
                    **(log.metadata if request.include_metadata else {})
                }
                for log in filtered_logs
            ], indent=2)
            media_type = "application/json"
            filename = f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
        elif request.format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # En-têtes
            headers = ["timestamp", "level", "message", "service", "container_id"]
            if request.include_metadata:
                headers.append("metadata")
            writer.writerow(headers)
            
            # Données
            for log in filtered_logs:
                row = [
                    log.timestamp.isoformat(),
                    log.level,
                    log.message,
                    log.service or "",
                    log.container_id or ""
                ]
                if request.include_metadata:
                    row.append(json.dumps(log.metadata))
                writer.writerow(row)
            
            content = output.getvalue()
            media_type = "text/csv"
            filename = f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
        else:  # txt
            lines = []
            for log in filtered_logs:
                line = f"{log.timestamp.isoformat()} [{log.level}] {log.message}"
                if log.service:
                    line += f" (service: {log.service})"
                if log.container_id:
                    line += f" (container: {log.container_id})"
                lines.append(line)
            
            content = "\n".join(lines)
            media_type = "text/plain"
            filename = f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        # Retourner le fichier
        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de l'export des logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur d'export: {str(e)}"
        )

@router.post("/containers/logs")
async def get_container_logs(
    request: ContainerLogRequest,
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Récupère les logs d'un conteneur Docker
    """
    try:
        # Vérifier que le conteneur existe
        container_info = docker_manager.get_container_info(request.container_id)
        if not container_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conteneur {request.container_id} non trouvé"
            )
        
        # Paramètres pour docker logs
        params = {
            'timestamps': request.timestamps,
            'since': request.since,
            'until': request.until
        }
        
        if request.tail:
            params['tail'] = request.tail
        
        # Récupérer les logs
        logs = docker_manager.get_container_logs(request.container_id, **params)
        
        if request.follow:
            # Stream des logs en temps réel
            async def log_stream() -> AsyncGenerator[str, None]:
                try:
                    for line in logs:
                        if isinstance(line, bytes):
                            line = line.decode('utf-8', errors='ignore')
                        yield f"data: {json.dumps({'log': line.strip()})}\n\n"
                        await asyncio.sleep(0.1)  # Petite pause pour éviter la surcharge
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
            return StreamingResponse(
                log_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive"
                }
            )
        else:
            # Logs statiques
            log_lines = []
            for line in logs:
                if isinstance(line, bytes):
                    line = line.decode('utf-8', errors='ignore')
                log_lines.append(line.strip())
            
            return {
                "container_id": request.container_id,
                "container_name": container_info.get('name', ''),
                "logs": log_lines,
                "total_lines": len(log_lines)
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des logs du conteneur {request.container_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de récupération: {str(e)}"
        )

@router.get("/containers/{container_id}/logs/stream")
async def stream_container_logs(
    container_id: str,
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Stream des logs d'un conteneur en temps réel
    """
    try:
        # Vérifier que le conteneur existe
        container_info = docker_manager.get_container_info(container_id)
        if not container_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conteneur {container_id} non trouvé"
            )
        
        async def log_stream() -> AsyncGenerator[str, None]:
            try:
                logs = docker_manager.get_container_logs(
                    container_id,
                    follow=True,
                    timestamps=True
                )
                
                for line in logs:
                    if isinstance(line, bytes):
                        line = line.decode('utf-8', errors='ignore')
                    
                    yield f"data: {json.dumps({
                        'timestamp': datetime.now().isoformat(),
                        'container_id': container_id,
                        'log': line.strip()
                    })}\n\n"
                    
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(
            log_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors du streaming des logs du conteneur {container_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de streaming: {str(e)}"
        )

@router.post("/level", status_code=status.HTTP_200_OK)
async def set_log_level(
    log_level: LogLevel,
    current_user = Depends(get_current_user)
):
    """
    Configure le niveau de log dynamiquement
    """
    try:
        # Configurer le niveau de log pour les services spécifiés
        if log_level.services:
            for service in log_level.services:
                service_logger = logging.getLogger(f"wakedock.{service}")
                service_logger.setLevel(getattr(logging, log_level.level))
        else:
            # Configurer le niveau global
            root_logger = logging.getLogger("wakedock")
            root_logger.setLevel(getattr(logging, log_level.level))
        
        # Programmer la restauration si nécessaire
        if log_level.expires_at:
            # Ici, on pourrait utiliser une tâche asynchrone pour restaurer le niveau
            # Pour l'instant, on se contente de logger l'information
            logger.info(f"Niveau de log {log_level.level} configuré jusqu'à {log_level.expires_at}")
        
        return {
            "message": f"Niveau de log configuré à {log_level.level}",
            "services": log_level.services or ["global"],
            "expires_at": log_level.expires_at
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la configuration du niveau de log: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de configuration: {str(e)}"
        )

@router.delete("/", status_code=status.HTTP_200_OK)
async def clear_logs(
    older_than_days: int = Query(30, ge=1, description="Supprimer les logs plus anciens que X jours"),
    current_user = Depends(get_current_user)
):
    """
    Supprime les anciens logs
    """
    try:
        cutoff_date = datetime.now() - timedelta(days=older_than_days)
        deleted_files = []
        
        for log_file in log_manager.get_log_files():
            try:
                # Vérifier la date du fichier
                file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if file_mtime < cutoff_date:
                    log_file.unlink()
                    deleted_files.append(str(log_file))
            except Exception as e:
                logger.warning(f"Erreur lors de la suppression du fichier {log_file}: {e}")
        
        return {
            "message": f"Logs supprimés (plus anciens que {older_than_days} jours)",
            "deleted_files": deleted_files,
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la suppression des logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de suppression: {str(e)}"
        )
