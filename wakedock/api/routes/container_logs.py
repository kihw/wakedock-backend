"""
Routes WebSocket pour les logs en temps réel des containers
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    WebSocket,
    WebSocketDisconnect,
)

from wakedock.api.auth.dependencies import get_current_user
from wakedock.core.docker_manager import DockerManager

router = APIRouter(prefix="/containers", tags=["container-logs"])
logger = logging.getLogger(__name__)

# Store active WebSocket connections
active_connections: dict[str, list[WebSocket]] = {}

async def get_docker_manager() -> DockerManager:
    return DockerManager()

class ConnectionManager:
    """Gestionnaire des connexions WebSocket pour les logs"""
    
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, container_id: str):
        """Connecter un WebSocket à un container spécifique"""
        await websocket.accept()
        
        if container_id not in self.active_connections:
            self.active_connections[container_id] = []
        
        self.active_connections[container_id].append(websocket)
        logger.info(f"WebSocket connecté pour le container {container_id}")
    
    def disconnect(self, websocket: WebSocket, container_id: str):
        """Déconnecter un WebSocket"""
        if container_id in self.active_connections:
            if websocket in self.active_connections[container_id]:
                self.active_connections[container_id].remove(websocket)
            
            # Nettoyer la liste si elle est vide
            if not self.active_connections[container_id]:
                del self.active_connections[container_id]
        
        logger.info(f"WebSocket déconnecté pour le container {container_id}")
    
    async def send_log(self, message: str, container_id: str):
        """Envoyer un message de log à tous les clients connectés pour un container"""
        if container_id not in self.active_connections:
            return
        
        # Créer le message formaté
        log_message = {
            "timestamp": datetime.now().isoformat(),
            "container_id": container_id,
            "message": message
        }
        
        # Envoyer à tous les clients connectés
        disconnected_connections = []
        
        for connection in self.active_connections[container_id]:
            try:
                await connection.send_text(json.dumps(log_message))
            except Exception as e:
                logger.error(f"Erreur lors de l'envoi du log via WebSocket: {e}")
                disconnected_connections.append(connection)
        
        # Nettoyer les connexions fermées
        for connection in disconnected_connections:
            self.disconnect(connection, container_id)

# Instance globale du gestionnaire de connexions
manager = ConnectionManager()

@router.websocket("/{container_id}/logs/stream")
async def websocket_container_logs(
    websocket: WebSocket,
    container_id: str,
    tail: Optional[int] = 100
):
    """
    WebSocket pour recevoir les logs d'un container en temps réel
    """
    docker_manager = DockerManager()
    
    try:
        # Vérifier que le container existe
        container = docker_manager.get_container(container_id)
        if not container:
            await websocket.close(code=4004, reason="Container non trouvé")
            return
        
        # Connecter le WebSocket
        await manager.connect(websocket, container_id)
        
        try:
            # Envoyer les logs historiques d'abord
            if tail > 0:
                historical_logs = docker_manager.get_container_logs(container_id, tail=tail, follow=False)
                if historical_logs:
                    # Diviser les logs en lignes et les envoyer une par une
                    for line in historical_logs.strip().split('\n'):
                        if line.strip():
                            await manager.send_log(line, container_id)
            
            # Démarrer le streaming des nouveaux logs
            await stream_container_logs(docker_manager, container_id, websocket)
            
        except WebSocketDisconnect:
            manager.disconnect(websocket, container_id)
            logger.info(f"Client déconnecté du streaming des logs pour {container_id}")
        
    except Exception as e:
        logger.error(f"Erreur dans le WebSocket des logs pour {container_id}: {e}")
        if not websocket.client_state.value == 3:  # WebSocket not closed
            await websocket.close(code=4000, reason=f"Erreur serveur: {str(e)}")

async def stream_container_logs(docker_manager: DockerManager, container_id: str, websocket: WebSocket):
    """
    Streamer les logs d'un container en continu
    """
    try:
        container = docker_manager.get_container(container_id)
        if not container:
            return
        
        # Utiliser l'API Docker pour suivre les logs en temps réel
        log_stream = container.logs(stream=True, follow=True, tail=0)
        
        for log_line in log_stream:
            try:
                # Décoder la ligne de log
                if isinstance(log_line, bytes):
                    log_text = log_line.decode('utf-8').strip()
                else:
                    log_text = str(log_line).strip()
                
                if log_text:
                    await manager.send_log(log_text, container_id)
                
                # Petit délai pour éviter de surcharger
                await asyncio.sleep(0.01)
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Erreur lors du traitement d'une ligne de log: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Erreur lors du streaming des logs pour {container_id}: {e}")

@router.get("/{container_id}/logs/download")
async def download_container_logs(
    container_id: str,
    tail: Optional[int] = 1000,
    since: Optional[str] = None,
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Télécharger les logs d'un container sous forme de fichier
    """
    try:
        container = docker_manager.get_container(container_id)
        if not container:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {container_id} non trouvé"
            )
        
        # Paramètres pour récupérer les logs
        log_params = {
            "tail": tail,
            "timestamps": True
        }
        
        if since:
            log_params["since"] = since
        
        logs = container.logs(**log_params)
        
        if isinstance(logs, bytes):
            logs_text = logs.decode('utf-8')
        else:
            logs_text = str(logs)
        
        # Préparer la réponse de téléchargement
        from fastapi.responses import Response
        
        filename = f"container_{container_id}_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        return Response(
            content=logs_text,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du téléchargement des logs: {str(e)}"
        )

@router.post("/{container_id}/logs/clear")
async def clear_container_logs(
    container_id: str,
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Vider les logs d'un container (via redémarrage)
    Note: Docker ne permet pas de vider directement les logs d'un container en cours
    """
    try:
        container = docker_manager.get_container(container_id)
        if not container:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {container_id} non trouvé"
            )
        
        # Pour vider les logs, on doit redémarrer le container
        # C'est la seule méthode supportée par Docker
        was_running = container.status == "running"
        
        if was_running:
            docker_manager.restart_container(container_id)
            message = f"Container {container_id} redémarré pour vider les logs"
        else:
            message = f"Container {container_id} arrêté, les logs seront vidés au prochain démarrage"
        
        return {"message": message}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du vidage des logs: {str(e)}"
        )
