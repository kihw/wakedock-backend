"""
API routes pour la gestion des rôles et permissions (RBAC)
Version 0.3.3
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from wakedock.core.auth_middleware import (
    require_admin_permission,
    require_audit_access,
    require_user_management,
)
from wakedock.core.rbac_service import get_rbac_service
from wakedock.database.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rbac", tags=["RBAC"])


# ========== Modèles de données ==========

class RoleCreate(BaseModel):
    """Modèle pour la création d'un rôle"""
    name: str = Field(..., min_length=3, max_length=50, description="Nom du rôle")
    description: str = Field(..., min_length=1, max_length=500, description="Description du rôle")
    permissions: List[str] = Field(default=[], description="Liste des permissions")


class RoleUpdate(BaseModel):
    """Modèle pour la mise à jour d'un rôle"""
    name: Optional[str] = Field(None, min_length=3, max_length=50, description="Nom du rôle")
    description: Optional[str] = Field(None, min_length=1, max_length=500, description="Description du rôle")
    permissions: Optional[List[str]] = Field(None, description="Liste des permissions")
    is_active: Optional[bool] = Field(None, description="Statut actif/inactif")


class UserRoleAssignment(BaseModel):
    """Modèle pour l'assignation de rôle à un utilisateur"""
    user_id: int = Field(..., description="ID de l'utilisateur")
    role_id: int = Field(..., description="ID du rôle")
    expires_at: Optional[datetime] = Field(None, description="Date d'expiration (optionnel)")


class RoleResponse(BaseModel):
    """Modèle de réponse pour un rôle"""
    id: int
    name: str
    description: str
    is_system_role: bool
    is_active: bool
    permissions: List[str]
    user_count: int
    created_at: str
    updated_at: str


class PermissionResponse(BaseModel):
    """Modèle de réponse pour une permission"""
    id: int
    name: str
    description: str
    category: str
    module: Optional[str] = None


class AuditLogResponse(BaseModel):
    """Modèle de réponse pour un log d'audit"""
    id: int
    user_id: Optional[int]
    username: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: str
    success: bool
    error_message: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: str


# ========== Routes pour les rôles ==========

@router.get("/roles", response_model=List[RoleResponse])
async def get_all_roles(current_user: User = Depends(require_user_management())):
    """
    Récupère tous les rôles avec leurs permissions
    """
    try:
        rbac_service = get_rbac_service()
        roles = await rbac_service.get_all_roles()
        return roles
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des rôles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des rôles"
        )


@router.post("/roles", response_model=RoleResponse)
async def create_role(
    role_data: RoleCreate,
    request: Request,
    current_user: User = Depends(require_admin_permission())
):
    """
    Crée un nouveau rôle personnalisé
    """
    try:
        rbac_service = get_rbac_service()
        
        # Créer le rôle
        role = await rbac_service.create_role(
            name=role_data.name,
            description=role_data.description,
            permissions=role_data.permissions,
            created_by_id=current_user.id
        )
        
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un rôle avec ce nom existe déjà"
            )
        
        # Récupérer le rôle complet
        roles = await rbac_service.get_all_roles()
        created_role = next((r for r in roles if r["id"] == role.id), None)
        
        if not created_role:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la récupération du rôle créé"
            )
        
        return created_role
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la création du rôle: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la création du rôle"
        )


@router.get("/roles/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: int,
    current_user: User = Depends(require_user_management())
):
    """
    Récupère un rôle spécifique par son ID
    """
    try:
        rbac_service = get_rbac_service()
        roles = await rbac_service.get_all_roles()
        
        role = next((r for r in roles if r["id"] == role_id), None)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rôle non trouvé"
            )
        
        return role
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du rôle: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération du rôle"
        )


# ========== Routes pour les permissions ==========

@router.get("/permissions")
async def get_all_permissions(current_user: User = Depends(require_user_management())):
    """
    Récupère toutes les permissions organisées par catégorie
    """
    try:
        rbac_service = get_rbac_service()
        permissions = await rbac_service.get_all_permissions()
        return permissions
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des permissions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des permissions"
        )


@router.get("/permissions/categories")
async def get_permission_categories(current_user: User = Depends(require_user_management())):
    """
    Récupère les catégories de permissions
    """
    try:
        rbac_service = get_rbac_service()
        return rbac_service.permission_categories
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des catégories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des catégories"
        )


# ========== Routes pour l'assignation des rôles ==========

@router.post("/users/{user_id}/roles/{role_id}")
async def assign_role_to_user(
    user_id: int,
    role_id: int,
    expires_at: Optional[datetime] = Query(None),
    current_user: User = Depends(require_admin_permission())
):
    """
    Assigne un rôle à un utilisateur
    """
    try:
        rbac_service = get_rbac_service()
        
        success = await rbac_service.assign_role_to_user(
            user_id=user_id,
            role_id=role_id,
            assigned_by_id=current_user.id,
            expires_at=expires_at
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible d'assigner le rôle (utilisateur ou rôle non trouvé)"
            )
        
        return {"message": "Rôle assigné avec succès"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'assignation du rôle: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'assignation du rôle"
        )


@router.delete("/users/{user_id}/roles/{role_id}")
async def remove_role_from_user(
    user_id: int,
    role_id: int,
    current_user: User = Depends(require_admin_permission())
):
    """
    Retire un rôle d'un utilisateur
    """
    try:
        rbac_service = get_rbac_service()
        
        success = await rbac_service.remove_role_from_user(
            user_id=user_id,
            role_id=role_id,
            removed_by_id=current_user.id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Association utilisateur-rôle non trouvée"
            )
        
        return {"message": "Rôle retiré avec succès"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la suppression du rôle: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la suppression du rôle"
        )


@router.get("/users/{user_id}/permissions")
async def get_user_permissions(
    user_id: int,
    current_user: User = Depends(require_user_management())
):
    """
    Récupère toutes les permissions d'un utilisateur
    """
    try:
        rbac_service = get_rbac_service()
        
        # Vérifier que l'utilisateur peut consulter les permissions
        if current_user.id != user_id and not current_user.is_superuser:
            # Vérifier si l'utilisateur a la permission de gestion des utilisateurs
            if not await rbac_service.check_user_permission(current_user.id, "users.read"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Vous ne pouvez consulter que vos propres permissions"
                )
        
        permissions = await rbac_service.get_user_permissions(user_id)
        return {"user_id": user_id, "permissions": permissions}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des permissions utilisateur: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des permissions"
        )


@router.get("/users/{user_id}/permissions/{permission}")
async def check_user_permission(
    user_id: int,
    permission: str,
    current_user: User = Depends(require_user_management())
):
    """
    Vérifie si un utilisateur a une permission spécifique
    """
    try:
        rbac_service = get_rbac_service()
        
        # Vérifier que l'utilisateur peut consulter les permissions
        if current_user.id != user_id and not current_user.is_superuser:
            if not await rbac_service.check_user_permission(current_user.id, "users.read"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Vous ne pouvez consulter que vos propres permissions"
                )
        
        has_permission = await rbac_service.check_user_permission(user_id, permission)
        return {
            "user_id": user_id,
            "permission": permission,
            "has_permission": has_permission
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la vérification de permission"
        )


# ========== Routes pour l'audit ==========

@router.get("/audit/logs")
async def get_audit_logs(
    user_id: Optional[int] = Query(None, description="Filtrer par utilisateur"),
    action: Optional[str] = Query(None, description="Filtrer par action"),
    start_date: Optional[datetime] = Query(None, description="Date de début"),
    end_date: Optional[datetime] = Query(None, description="Date de fin"),
    page: int = Query(1, ge=1, description="Numéro de page"),
    per_page: int = Query(50, ge=1, le=100, description="Nombre d'éléments par page"),
    current_user: User = Depends(require_audit_access())
):
    """
    Récupère les logs d'audit avec filtres et pagination
    """
    try:
        rbac_service = get_rbac_service()
        
        result = await rbac_service.get_audit_logs(
            user_id=user_id,
            action=action,
            start_date=start_date,
            end_date=end_date,
            page=page,
            per_page=per_page
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des logs d'audit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des logs d'audit"
        )


@router.get("/audit/actions")
async def get_audit_actions(current_user: User = Depends(require_audit_access())):
    """
    Récupère la liste des actions disponibles pour les filtres d'audit
    """
    try:
        # Actions communes d'audit
        actions = [
            "login", "logout", "access_granted", "access_denied",
            "assign_role", "remove_role", "create_role", "update_role", "delete_role",
            "create_user", "update_user", "delete_user",
            "container_create", "container_start", "container_stop", "container_delete",
            "image_pull", "image_push", "image_delete",
            "config_change", "system_backup", "system_restore"
        ]
        
        return {"actions": sorted(actions)}
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des actions d'audit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des actions d'audit"
        )


# ========== Routes de maintenance ==========

@router.post("/maintenance/cleanup-expired-roles")
async def cleanup_expired_role_assignments(current_user: User = Depends(require_admin_permission())):
    """
    Nettoie les assignations de rôles expirées
    """
    try:
        rbac_service = get_rbac_service()
        count = await rbac_service.cleanup_expired_role_assignments()
        
        return {
            "message": f"Nettoyage terminé",
            "expired_assignments_removed": count
        }
        
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des rôles expirés: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du nettoyage des rôles expirés"
        )


@router.post("/maintenance/initialize-defaults")
async def initialize_default_roles_and_permissions(current_user: User = Depends(require_admin_permission())):
    """
    Initialise les rôles et permissions par défaut
    """
    try:
        rbac_service = get_rbac_service()
        await rbac_service.initialize_default_roles_and_permissions()
        
        return {"message": "Rôles et permissions par défaut initialisés avec succès"}
        
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation RBAC: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'initialisation RBAC"
        )


# ========== Routes d'information ==========

@router.get("/info")
async def get_rbac_info(current_user: User = Depends(require_user_management())):
    """
    Récupère les informations générales sur le système RBAC
    """
    try:
        rbac_service = get_rbac_service()
        
        roles = await rbac_service.get_all_roles()
        permissions = await rbac_service.get_all_permissions()
        
        total_permissions = sum(len(perms) for perms in permissions.values())
        system_roles = [r for r in roles if r["is_system_role"]]
        custom_roles = [r for r in roles if not r["is_system_role"]]
        
        return {
            "summary": {
                "total_roles": len(roles),
                "system_roles": len(system_roles),
                "custom_roles": len(custom_roles),
                "total_permissions": total_permissions,
                "permission_categories": len(permissions)
            },
            "default_roles": rbac_service.default_roles.keys(),
            "permission_categories": rbac_service.permission_categories
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des informations RBAC: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des informations RBAC"
        )
