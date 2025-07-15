"""
Routes API pour la gestion des containers Docker
"""
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Optional, Dict, Any
import docker
from docker.errors import NotFound, APIError
from pydantic import BaseModel, Field
from wakedock.core.docker_manager import DockerManager
from wakedock.core.validation import ValidationError
from wakedock.api.auth.dependencies import get_current_user

router = APIRouter(prefix="/containers", tags=["containers"])

class ContainerCreate(BaseModel):
    """Modèle pour la création d'un container"""
    name: str = Field(..., description="Nom du container")
    image: str = Field(..., description="Image Docker à utiliser")
    environment: Optional[Dict[str, str]] = Field(default={}, description="Variables d'environnement")
    ports: Optional[Dict[str, int]] = Field(default={}, description="Mapping des ports (container_port: host_port)")
    volumes: Optional[Dict[str, str]] = Field(default={}, description="Volumes montés (host_path: container_path)")
    command: Optional[str] = Field(default=None, description="Commande à exécuter")
    working_dir: Optional[str] = Field(default=None, description="Répertoire de travail")
    restart_policy: Optional[str] = Field(default="no", description="Politique de redémarrage")

class ContainerResponse(BaseModel):
    """Modèle de réponse pour un container"""
    id: str
    name: str
    image: str
    status: str
    state: str
    created: str
    ports: Optional[Dict[str, Any]] = None
    environment: Optional[Dict[str, str]] = None
    volumes: Optional[List[Dict[str, str]]] = None

class ContainerUpdate(BaseModel):
    """Modèle pour la mise à jour d'un container"""
    name: Optional[str] = None
    environment: Optional[Dict[str, str]] = None

# Dépendance pour obtenir le gestionnaire Docker
async def get_docker_manager() -> DockerManager:
    return DockerManager()

@router.get("/", response_model=List[ContainerResponse])
async def list_containers(
    all: bool = False,
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Récupérer la liste de tous les containers
    """
    try:
        containers = docker_manager.list_containers(all=all)
        return [
            ContainerResponse(
                id=container.id,
                name=container.name.lstrip('/'),
                image=container.image.tags[0] if container.image.tags else container.image.id,
                status=container.status,
                state=container.attrs['State']['Status'],
                created=container.attrs['Created'],
                ports=container.ports,
                environment=dict(env.split('=', 1) for env in container.attrs['Config']['Env'] if '=' in env) if container.attrs['Config']['Env'] else {}
            )
            for container in containers
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des containers: {str(e)}"
        )

@router.get("/{container_id}", response_model=ContainerResponse)
async def get_container(
    container_id: str,
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Récupérer les détails d'un container spécifique
    """
    try:
        container = docker_manager.get_container(container_id)
        if not container:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Container {container_id} non trouvé"
            )
        
        return ContainerResponse(
            id=container.id,
            name=container.name.lstrip('/'),
            image=container.image.tags[0] if container.image.tags else container.image.id,
            status=container.status,
            state=container.attrs['State']['Status'],
            created=container.attrs['Created'],
            ports=container.ports,
            environment=dict(env.split('=', 1) for env in container.attrs['Config']['Env'] if '=' in env) if container.attrs['Config']['Env'] else {},
            volumes=[
                {"source": mount['Source'], "destination": mount['Destination'], "mode": mount['Mode']}
                for mount in container.attrs['Mounts']
            ] if container.attrs['Mounts'] else []
        )
    except NotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} non trouvé"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération du container: {str(e)}"
        )

@router.post("/", response_model=ContainerResponse, status_code=status.HTTP_201_CREATED)
async def create_container(
    container_data: ContainerCreate,
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Créer un nouveau container
    """
    try:
        container = docker_manager.create_container(
            name=container_data.name,
            image=container_data.image,
            environment=container_data.environment,
            ports=container_data.ports,
            volumes=container_data.volumes,
            command=container_data.command,
            working_dir=container_data.working_dir,
            restart_policy=container_data.restart_policy
        )
        
        return ContainerResponse(
            id=container.id,
            name=container.name.lstrip('/'),
            image=container.image.tags[0] if container.image.tags else container.image.id,
            status=container.status,
            state=container.attrs['State']['Status'],
            created=container.attrs['Created'],
            ports=container.ports,
            environment=container_data.environment
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Configuration invalide: {str(e)}"
        )
    except APIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erreur lors de la création du container: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur interne: {str(e)}"
        )

@router.put("/{container_id}", response_model=ContainerResponse)
async def update_container(
    container_id: str,
    container_data: ContainerUpdate,
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Mettre à jour un container (redémarrage nécessaire pour certains changements)
    """
    try:
        container = docker_manager.update_container(container_id, container_data.dict(exclude_unset=True))
        
        return ContainerResponse(
            id=container.id,
            name=container.name.lstrip('/'),
            image=container.image.tags[0] if container.image.tags else container.image.id,
            status=container.status,
            state=container.attrs['State']['Status'],
            created=container.attrs['Created'],
            ports=container.ports,
            environment=dict(env.split('=', 1) for env in container.attrs['Config']['Env'] if '=' in env) if container.attrs['Config']['Env'] else {}
        )
    except NotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} non trouvé"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la mise à jour: {str(e)}"
        )

@router.delete("/{container_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_container(
    container_id: str,
    force: bool = False,
    docker_manager: DockerManager = Depends(get_docker_manager),
    current_user = Depends(get_current_user)
):
    """
    Supprimer un container
    """
    try:
        docker_manager.remove_container(container_id, force=force)
    except NotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Container {container_id} non trouvé"
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
