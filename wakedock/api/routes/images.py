"""
Routes API pour la gestion des images Docker
"""
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Dict, Any
import docker
from docker.errors import NotFound, APIError, ImageNotFound
from pydantic import BaseModel, Field
from wakedock.core.docker_manager import DockerManager
from wakedock.api.auth.dependencies import get_current_user

router = APIRouter(prefix="/images", tags=["images"])

class ImageResponse(BaseModel):
    """Modèle de réponse pour une image"""
    id: str
    tags: List[str]
    size: int
    created: str
    repository_tags: Optional[List[str]] = None

class ImagePull(BaseModel):
    """Modèle pour télécharger une image"""
    image: str = Field(..., description="Nom de l'image")
    tag: str = Field(default="latest", description="Tag de l'image")

class ImageSearch(BaseModel):
    """Modèle pour rechercher des images"""
    term: str = Field(..., description="Terme de recherche")
    limit: Optional[int] = Field(default=25, description="Limite de résultats")

# Dépendance pour obtenir le gestionnaire Docker
async def get_docker_manager() -> DockerManager:
    return DockerManager()

@router.get("/", response_model=List[ImageResponse])
async def list_images(
    all: bool = False,
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Récupérer la liste de toutes les images Docker
    """
    try:
        images = docker_manager.list_images(all=all)
        return [
            ImageResponse(
                id=image.id,
                tags=image.tags,
                size=image.attrs.get('Size', 0),
                created=image.attrs.get('Created', ''),
                repository_tags=image.attrs.get('RepoTags', [])
            )
            for image in images
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des images: {str(e)}"
        )

@router.get("/{image_id}", response_model=ImageResponse)
async def get_image(
    image_id: str,
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Récupérer les détails d'une image spécifique
    """
    try:
        client = docker_manager.client
        image = client.images.get(image_id)
        
        return ImageResponse(
            id=image.id,
            tags=image.tags,
            size=image.attrs.get('Size', 0),
            created=image.attrs.get('Created', ''),
            repository_tags=image.attrs.get('RepoTags', [])
        )
    except ImageNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image {image_id} non trouvée"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de l'image: {str(e)}"
        )

@router.post("/pull", response_model=ImageResponse, status_code=status.HTTP_201_CREATED)
async def pull_image(
    image_data: ImagePull,
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Télécharger une image Docker
    """
    try:
        image = docker_manager.pull_image(image_data.image, image_data.tag)
        
        return ImageResponse(
            id=image.id,
            tags=image.tags,
            size=image.attrs.get('Size', 0),
            created=image.attrs.get('Created', ''),
            repository_tags=image.attrs.get('RepoTags', [])
        )
    except APIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur lors du téléchargement de l'image: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur interne: {str(e)}"
        )

@router.delete("/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_image(
    image_id: str,
    force: bool = False,
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Supprimer une image Docker
    """
    try:
        client = docker_manager.client
        client.images.remove(image_id, force=force)
    except ImageNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image {image_id} non trouvée"
        )
    except APIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur lors de la suppression: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur interne: {str(e)}"
        )

@router.get("/search/{term}")
async def search_images(
    term: str,
    limit: int = 25,
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Rechercher des images sur Docker Hub
    """
    try:
        client = docker_manager.client
        results = client.images.search(term, limit=limit)
        return {"results": results}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche: {str(e)}"
        )

@router.get("/{image_id}/history")
async def get_image_history(
    image_id: str,
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Récupérer l'historique d'une image
    """
    try:
        client = docker_manager.client
        image = client.images.get(image_id)
        history = image.history()
        return {"history": history}
    except ImageNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image {image_id} non trouvée"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de l'historique: {str(e)}"
        )
