"""
Routes pour l'authentification et la gestion des utilisateurs
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from wakedock.controllers.authentication_controller import AuthenticationController
from wakedock.serializers.authentication_serializers import (
    RegisterRequest, LoginRequest, UserResponse, TokenResponse,
    CreateRoleRequest, UpdateRoleRequest, RoleResponse
)
from wakedock.core.database import get_db
from wakedock.core.auth import get_current_user
from wakedock.database.models import User

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """Enregistrer un nouvel utilisateur"""
    controller = AuthenticationController(db)
    return await controller.register_user(user_data.dict())

@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Connexion utilisateur"""
    controller = AuthenticationController(db)
    return await controller.login_user(credentials.dict())

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Récupérer les informations de l'utilisateur connecté"""
    return current_user

@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mettre à jour les informations de l'utilisateur connecté"""
    controller = AuthenticationController(db)
    return await controller.update_user(current_user.id, user_data)

@router.get("/users/", response_model=List[UserResponse])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Récupérer la liste des utilisateurs (admin uniquement)"""
    controller = AuthenticationController(db)
    return await controller.get_users(skip=skip, limit=limit)

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Récupérer un utilisateur spécifique"""
    controller = AuthenticationController(db)
    user = await controller.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )
    return user

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Supprimer un utilisateur"""
    controller = AuthenticationController(db)
    success = await controller.delete_user(user_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur non trouvé"
        )
    return {"message": "Utilisateur supprimé avec succès"}

# Routes pour les rôles
@router.get("/roles/", response_model=List[RoleResponse])
async def get_roles(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Récupérer la liste des rôles"""
    controller = AuthenticationController(db)
    return await controller.get_roles(skip=skip, limit=limit)

@router.post("/roles/", response_model=RoleResponse)
async def create_role(
    role_data: CreateRoleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Créer un nouveau rôle"""
    controller = AuthenticationController(db)
    return await controller.create_role(role_data.dict(), current_user.id)

@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    role_data: UpdateRoleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mettre à jour un rôle"""
    controller = AuthenticationController(db)
    role = await controller.update_role(role_id, role_data.dict(), current_user.id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rôle non trouvé"
        )
    return role

@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Supprimer un rôle"""
    controller = AuthenticationController(db)
    success = await controller.delete_role(role_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rôle non trouvé"
        )
    return {"message": "Rôle supprimé avec succès"}

# Routes pour la gestion des permissions
@router.post("/users/{user_id}/roles/{role_id}")
async def assign_role_to_user(
    user_id: int,
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Assigner un rôle à un utilisateur"""
    controller = AuthenticationController(db)
    success = await controller.assign_role_to_user(user_id, role_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible d'assigner le rôle"
        )
    return {"message": "Rôle assigné avec succès"}

@router.delete("/users/{user_id}/roles/{role_id}")
async def remove_role_from_user(
    user_id: int,
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retirer un rôle d'un utilisateur"""
    controller = AuthenticationController(db)
    success = await controller.remove_role_from_user(user_id, role_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de retirer le rôle"
        )
    return {"message": "Rôle retiré avec succès"}
