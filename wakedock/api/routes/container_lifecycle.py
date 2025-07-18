"""
Routes API pour la gestion du cycle de vie des containers
"""
from typing import Optional

from docker.errors import APIError, NotFound
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from wakedock.api.auth.dependencies import get_current_user
from wakedock.core.docker_manager import DockerManager

router = APIRouter(prefix="/containers", tags=["container-lifecycle"])

class ContainerAction(BaseModel):
    """Modèle pour les actions sur les containers"""
    timeout: Optional[int] = 10

class LogsRequest(BaseModel):
    """Modèle pour la demande de logs"""
    tail: Optional[int] = 100
    follow: Optional[bool] = False
    timestamps: Optional[bool] = True

# Dépendance pour obtenir le gestionnaire Docker
async def get_docker_manager() -> DockerManager:
    return DockerManager()

@router.post("/{container_id}/start", status_code=status.HTTP_200_OK)
async def start_container(
    container_id: str,
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Démarrer un container
    """
    try:
        docker_manager.start_container(container_id)
        return {"message": f"Container {container_id} démarré avec succès"}
    except NotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} non trouvé"
        )
    except APIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur lors du démarrage: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur interne: {str(e)}"
        )

@router.post("/{container_id}/stop", status_code=status.HTTP_200_OK)
async def stop_container(
    container_id: str,
    action_data: ContainerAction = ContainerAction(),
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Arrêter un container
    """
    try:
        docker_manager.stop_container(container_id, timeout=action_data.timeout)
        return {"message": f"Container {container_id} arrêté avec succès"}
    except NotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} non trouvé"
        )
    except APIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur lors de l'arrêt: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur interne: {str(e)}"
        )

@router.post("/{container_id}/restart", status_code=status.HTTP_200_OK)
async def restart_container(
    container_id: str,
    action_data: ContainerAction = ContainerAction(),
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Redémarrer un container
    """
    try:
        docker_manager.restart_container(container_id, timeout=action_data.timeout)
        return {"message": f"Container {container_id} redémarré avec succès"}
    except NotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} non trouvé"
        )
    except APIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur lors du redémarrage: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur interne: {str(e)}"
        )

@router.get("/{container_id}/logs")
async def get_container_logs(
    container_id: str,
    tail: int = 100,
    follow: bool = False,
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Récupérer les logs d'un container
    """
    try:
        logs = docker_manager.get_container_logs(
            container_id, 
            tail=tail, 
            follow=follow
        )
        return {"logs": logs}
    except NotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} non trouvé"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des logs: {str(e)}"
        )

@router.get("/{container_id}/stats")
async def get_container_stats(
    container_id: str,
    stream: bool = False,
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Récupérer les statistiques d'un container
    """
    try:
        container = docker_manager.get_container(container_id)
        if not container:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {container_id} non trouvé"
            )
        
        stats = container.stats(stream=False)
        return {"stats": stats}
    except NotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} non trouvé"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des stats: {str(e)}"
        )
