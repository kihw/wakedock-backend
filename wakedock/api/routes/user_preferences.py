"""
API Routes pour les préférences de thème utilisateur
"""
import json
import logging
import os
import tempfile
from datetime import datetime
from typing import Dict

from fastapi import APIRouter, Depends, File, HTTPException, status, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from wakedock.core.auth_middleware import require_authenticated_user
from wakedock.database.database import get_async_session
from wakedock.database.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/users", tags=["user-preferences"])


# Modèles Pydantic pour les préférences de thème
class ThemePreferencesModel(BaseModel):
    """Modèle pour les préférences de thème utilisateur"""
    theme_mode: str = Field(..., description="Mode de thème (light, dark, auto)")
    custom_colors: Dict[str, str] = Field(default_factory=dict, description="Couleurs personnalisées")
    animations_enabled: bool = Field(True, description="Animations activées")
    transitions_enabled: bool = Field(True, description="Transitions activées")


class ThemePreferencesResponse(BaseModel):
    """Modèle de réponse pour les préférences de thème"""
    id: int
    user_id: int
    theme_mode: str
    custom_colors: Dict[str, str]
    animations_enabled: bool
    transitions_enabled: bool
    created_at: datetime
    updated_at: datetime


@router.get("/theme-preferences", response_model=ThemePreferencesResponse)
async def get_user_theme_preferences(
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Récupère les préférences de thème de l'utilisateur connecté
    """
    try:
        # Charge l'utilisateur avec ses préférences
        query = select(User).where(User.id == current_user.id).options(
            selectinload(User.theme_preferences)
        )
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur non trouvé"
            )
        
        # Si l'utilisateur n'a pas de préférences, retourne les valeurs par défaut
        if not hasattr(user, 'theme_preferences') or not user.theme_preferences:
            # Créer des préférences par défaut
            from wakedock.database.models import UserThemePreferences
            
            default_prefs = UserThemePreferences(
                user_id=user.id,
                theme_mode="auto",
                custom_colors={},
                animations_enabled=True,
                transitions_enabled=True
            )
            
            db.add(default_prefs)
            await db.commit()
            await db.refresh(default_prefs)
            
            return ThemePreferencesResponse(
                id=default_prefs.id,
                user_id=default_prefs.user_id,
                theme_mode=default_prefs.theme_mode,
                custom_colors=default_prefs.custom_colors,
                animations_enabled=default_prefs.animations_enabled,
                transitions_enabled=default_prefs.transitions_enabled,
                created_at=default_prefs.created_at,
                updated_at=default_prefs.updated_at
            )
        
        prefs = user.theme_preferences
        return ThemePreferencesResponse(
            id=prefs.id,
            user_id=prefs.user_id,
            theme_mode=prefs.theme_mode,
            custom_colors=prefs.custom_colors,
            animations_enabled=prefs.animations_enabled,
            transitions_enabled=prefs.transitions_enabled,
            created_at=prefs.created_at,
            updated_at=prefs.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des préférences de thème: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.put("/theme-preferences", response_model=ThemePreferencesResponse)
async def update_user_theme_preferences(
    preferences: ThemePreferencesModel,
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Met à jour les préférences de thème de l'utilisateur connecté
    """
    try:
        # Validation du mode de thème
        if preferences.theme_mode not in ["light", "dark", "auto"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mode de thème invalide. Valeurs acceptées: light, dark, auto"
            )
        
        # Charge l'utilisateur avec ses préférences
        query = select(User).where(User.id == current_user.id).options(
            selectinload(User.theme_preferences)
        )
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur non trouvé"
            )
        
        from wakedock.database.models import UserThemePreferences

        # Si l'utilisateur n'a pas de préférences existantes, en créer
        if not hasattr(user, 'theme_preferences') or not user.theme_preferences:
            new_prefs = UserThemePreferences(
                user_id=user.id,
                theme_mode=preferences.theme_mode,
                custom_colors=preferences.custom_colors,
                animations_enabled=preferences.animations_enabled,
                transitions_enabled=preferences.transitions_enabled
            )
            
            db.add(new_prefs)
            await db.commit()
            await db.refresh(new_prefs)
            
            return ThemePreferencesResponse(
                id=new_prefs.id,
                user_id=new_prefs.user_id,
                theme_mode=new_prefs.theme_mode,
                custom_colors=new_prefs.custom_colors,
                animations_enabled=new_prefs.animations_enabled,
                transitions_enabled=new_prefs.transitions_enabled,
                created_at=new_prefs.created_at,
                updated_at=new_prefs.updated_at
            )
        
        # Met à jour les préférences existantes
        prefs = user.theme_preferences
        prefs.theme_mode = preferences.theme_mode
        prefs.custom_colors = preferences.custom_colors
        prefs.animations_enabled = preferences.animations_enabled
        prefs.transitions_enabled = preferences.transitions_enabled
        prefs.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(prefs)
        
        return ThemePreferencesResponse(
            id=prefs.id,
            user_id=prefs.user_id,
            theme_mode=prefs.theme_mode,
            custom_colors=prefs.custom_colors,
            animations_enabled=prefs.animations_enabled,
            transitions_enabled=prefs.transitions_enabled,
            created_at=prefs.created_at,
            updated_at=prefs.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour des préférences de thème: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.delete("/theme-preferences")
async def reset_user_theme_preferences(
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Remet à zéro les préférences de thème de l'utilisateur (valeurs par défaut)
    """
    try:
        from wakedock.database.models import UserThemePreferences

        # Supprime les préférences existantes
        query = delete(UserThemePreferences).where(UserThemePreferences.user_id == current_user.id)
        await db.execute(query)
        await db.commit()
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"message": "Préférences de thème réinitialisées"}
        )
        
    except Exception as e:
        logger.error(f"Erreur lors de la réinitialisation des préférences de thème: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.get("/theme-preferences/export")
async def export_user_theme_preferences(
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Exporte les préférences de thème au format JSON
    """
    try:
        # Récupère les préférences actuelles
        query = select(User).where(User.id == current_user.id).options(
            selectinload(User.theme_preferences)
        )
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur non trouvé"
            )
        
        # Prépare les données d'export
        if hasattr(user, 'theme_preferences') and user.theme_preferences:
            prefs = user.theme_preferences
            export_data = {
                "wakedock_theme_export": True,
                "version": "1.0",
                "exported_at": datetime.utcnow().isoformat(),
                "user_id": user.id,
                "username": user.username,
                "preferences": {
                    "theme_mode": prefs.theme_mode,
                    "custom_colors": prefs.custom_colors,
                    "animations_enabled": prefs.animations_enabled,
                    "transitions_enabled": prefs.transitions_enabled
                }
            }
        else:
            # Préférences par défaut
            export_data = {
                "wakedock_theme_export": True,
                "version": "1.0",
                "exported_at": datetime.utcnow().isoformat(),
                "user_id": user.id,
                "username": user.username,
                "preferences": {
                    "theme_mode": "auto",
                    "custom_colors": {},
                    "animations_enabled": True,
                    "transitions_enabled": True
                }
            }
        
        # Crée un fichier temporaire
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
            json.dump(export_data, tmp_file, indent=2, default=str)
            tmp_file_path = tmp_file.name
        
        # Nom du fichier d'export
        filename = f"wakedock-theme-{user.username}-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        return FileResponse(
            path=tmp_file_path,
            filename=filename,
            media_type='application/json',
            background=lambda: os.unlink(tmp_file_path)  # Supprime le fichier temporaire après envoi
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'export des préférences de thème: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )


@router.post("/theme-preferences/import", response_model=ThemePreferencesResponse)
async def import_user_theme_preferences(
    file: UploadFile = File(...),
    current_user: User = Depends(require_authenticated_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Importe des préférences de thème depuis un fichier JSON
    """
    try:
        # Validation du type de fichier
        if not file.filename or not file.filename.endswith('.json'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le fichier doit être au format JSON"
            )
        
        # Lecture du contenu du fichier
        content = await file.read()
        
        try:
            import_data = json.loads(content.decode('utf-8'))
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Fichier JSON invalide"
            )
        
        # Validation de la structure d'import
        if not isinstance(import_data, dict) or not import_data.get("wakedock_theme_export"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Format d'export WakeDock invalide"
            )
        
        preferences_data = import_data.get("preferences", {})
        
        # Validation des données de préférences
        theme_mode = preferences_data.get("theme_mode", "auto")
        if theme_mode not in ["light", "dark", "auto"]:
            theme_mode = "auto"
        
        custom_colors = preferences_data.get("custom_colors", {})
        if not isinstance(custom_colors, dict):
            custom_colors = {}
        
        animations_enabled = preferences_data.get("animations_enabled", True)
        transitions_enabled = preferences_data.get("transitions_enabled", True)
        
        # Met à jour les préférences
        preferences = ThemePreferencesModel(
            theme_mode=theme_mode,
            custom_colors=custom_colors,
            animations_enabled=bool(animations_enabled),
            transitions_enabled=bool(transitions_enabled)
        )
        
        # Utilise la fonction de mise à jour existante
        return await update_user_theme_preferences(preferences, current_user, db)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'import des préférences de thème: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )
