"""
Routes pour la gestion des conteneurs
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from wakedock.controllers.containers_controller import ContainersController
from wakedock.serializers.containers_serializers import (
    CreateContainerRequest, UpdateContainerRequest, ContainerResponse,
    CreateContainerStackRequest, UpdateContainerStackRequest, ContainerStackResponse
)
from wakedock.core.database import get_db
from wakedock.core.auth import get_current_user
from wakedock.database.models import User

router = APIRouter(prefix="/containers", tags=["containers"])

@router.get("/", response_model=List[ContainerResponse])
async def get_containers(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Récupérer la liste des conteneurs"""
    controller = ContainersController(db)
    return await controller.get_containers(skip=skip, limit=limit)

@router.get("/{container_id}", response_model=ContainerResponse)
async def get_container(
    container_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Récupérer un conteneur spécifique"""
    controller = ContainersController(db)
    container = await controller.get_container_by_id(container_id)
    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conteneur non trouvé"
        )
    return container

@router.post("/", response_model=ContainerResponse)
async def create_container(
    container_data: CreateContainerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Créer un nouveau conteneur"""
    controller = ContainersController(db)
    return await controller.create_container(container_data.dict(), current_user.id)

@router.put("/{container_id}", response_model=ContainerResponse)
async def update_container(
    container_id: int,
    container_data: UpdateContainerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mettre à jour un conteneur"""
    controller = ContainersController(db)
    container = await controller.update_container(container_id, container_data.dict(), current_user.id)
    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conteneur non trouvé"
        )
    return container

@router.delete("/{container_id}")
async def delete_container(
    container_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Supprimer un conteneur"""
    controller = ContainersController(db)
    success = await controller.delete_container(container_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conteneur non trouvé"
        )
    return {"message": "Conteneur supprimé avec succès"}

# Routes pour les stacks de conteneurs
@router.get("/stacks/", response_model=List[ContainerStackResponse])
async def get_container_stacks(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Récupérer la liste des stacks de conteneurs"""
    controller = ContainersController(db)
    return await controller.get_container_stacks(skip=skip, limit=limit)

@router.post("/stacks/", response_model=ContainerStackResponse)
async def create_container_stack(
    stack_data: CreateContainerStackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Créer une nouvelle stack de conteneurs"""
    controller = ContainersController(db)
    return await controller.create_container_stack(stack_data.dict(), current_user.id)

@router.put("/stacks/{stack_id}", response_model=ContainerStackResponse)
async def update_container_stack(
    stack_id: int,
    stack_data: UpdateContainerStackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mettre à jour une stack de conteneurs"""
    controller = ContainersController(db)
    stack = await controller.update_container_stack(stack_id, stack_data.dict(), current_user.id)
    if not stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stack de conteneurs non trouvée"
        )
    return stack

@router.delete("/stacks/{stack_id}")
async def delete_container_stack(
    stack_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Supprimer une stack de conteneurs"""
    controller = ContainersController(db)
    success = await controller.delete_container_stack(stack_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stack de conteneurs non trouvée"
        )
    return {"message": "Stack de conteneurs supprimée avec succès"}

# Actions spéciales pour les conteneurs
@router.post("/{container_id}/start")
async def start_container(
    container_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Démarrer un conteneur"""
    controller = ContainersController(db)
    success = await controller.start_container(container_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conteneur non trouvé"
        )
    return {"message": "Conteneur démarré avec succès"}

@router.post("/{container_id}/stop")
async def stop_container(
    container_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Arrêter un conteneur"""
    controller = ContainersController(db)
    success = await controller.stop_container(container_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conteneur non trouvé"
        )
    return {"message": "Conteneur arrêté avec succès"}

@router.post("/{container_id}/restart")
async def restart_container(
    container_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Redémarrer un conteneur"""
    controller = ContainersController(db)
    success = await controller.restart_container(container_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conteneur non trouvé"
        )
    return {"message": "Conteneur redémarré avec succès"}
