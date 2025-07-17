"""
API Routes pour la personnalisation des tableaux de bord - WakeDock
Endpoints pour la gestion des layouts, widgets et templates
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from wakedock.core.auth import get_current_user
from wakedock.core.dashboard_service import DashboardCustomizationService
from wakedock.core.database import get_db_session
from wakedock.models.user import User

# Création du router
router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard Customization"])

# Modèles Pydantic pour les requêtes/réponses

class WidgetPositionModel(BaseModel):
    x: int = Field(..., ge=0, description="Position X dans la grille")
    y: int = Field(..., ge=0, description="Position Y dans la grille")

class WidgetSizeModel(BaseModel):
    width: int = Field(..., ge=1, le=12, description="Largeur en unités de grille")
    height: int = Field(..., ge=1, le=8, description="Hauteur en unités de grille")

class GridConfigModel(BaseModel):
    columns: int = Field(12, ge=6, le=24, description="Nombre de colonnes")
    rows: int = Field(8, ge=4, le=16, description="Nombre de lignes")
    gap: int = Field(16, ge=8, le=32, description="Espacement entre widgets")
    padding: int = Field(24, ge=16, le=48, description="Padding du conteneur")
    responsive: bool = Field(True, description="Mode responsive activé")

class CreateLayoutRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Nom du layout")
    description: Optional[str] = Field(None, max_length=500, description="Description du layout")
    grid_config: Optional[GridConfigModel] = None
    is_default: bool = Field(False, description="Définir comme layout par défaut")

class UpdateLayoutRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    grid_config: Optional[GridConfigModel] = None
    is_default: Optional[bool] = None

class CreateWidgetRequest(BaseModel):
    widget_type: str = Field(..., description="Type de widget")
    title: Optional[str] = Field(None, max_length=100, description="Titre du widget")
    position: WidgetPositionModel
    size: WidgetSizeModel
    config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Configuration du widget")

class UpdateWidgetRequest(BaseModel):
    position: Optional[WidgetPositionModel] = None
    size: Optional[WidgetSizeModel] = None
    config: Optional[Dict[str, Any]] = None
    title: Optional[str] = Field(None, max_length=100)

class LayoutResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_default: bool
    is_shared: bool
    grid_config: Dict[str, Any]
    widgets: List[Dict[str, Any]]
    created_at: str
    updated_at: str

@router.get("/layouts", response_model=List[LayoutResponse])
async def get_user_layouts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Récupère tous les layouts de l'utilisateur connecté"""
    service = DashboardCustomizationService(db)
    layouts = await service.get_user_layouts(current_user.id)
    return layouts

@router.post("/layouts", response_model=LayoutResponse)
async def create_layout(
    request: CreateLayoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Crée un nouveau layout personnalisé"""
    service = DashboardCustomizationService(db)
    
    grid_config = None
    if request.grid_config:
        grid_config = request.grid_config.dict()
    
    layout = await service.create_layout(
        user_id=current_user.id,
        name=request.name,
        description=request.description or "",
        grid_config=grid_config,
        is_default=request.is_default
    )
    
    if not layout:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible de créer le layout"
        )
    
    return layout

@router.get("/layouts/{layout_id}", response_model=LayoutResponse)
async def get_layout(
    layout_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Récupère un layout spécifique"""
    service = DashboardCustomizationService(db)
    layout = await service.get_layout_by_id(layout_id)
    
    if not layout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Layout non trouvé"
        )
    
    return layout

@router.put("/layouts/{layout_id}", response_model=Dict[str, str])
async def update_layout(
    layout_id: int,
    request: UpdateLayoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Met à jour un layout existant"""
    service = DashboardCustomizationService(db)
    
    grid_config = None
    if request.grid_config:
        grid_config = request.grid_config.dict()
    
    success = await service.update_layout(
        layout_id=layout_id,
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        grid_config=grid_config,
        is_default=request.is_default
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Layout non trouvé ou non autorisé"
        )
    
    return {"message": "Layout mis à jour avec succès"}

@router.delete("/layouts/{layout_id}", response_model=Dict[str, str])
async def delete_layout(
    layout_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Supprime un layout"""
    service = DashboardCustomizationService(db)
    success = await service.delete_layout(layout_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Layout non trouvé ou non autorisé"
        )
    
    return {"message": "Layout supprimé avec succès"}

@router.post("/layouts/{layout_id}/duplicate", response_model=LayoutResponse)
async def duplicate_layout(
    layout_id: int,
    new_name: str = Query(..., min_length=1, max_length=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Duplique un layout existant"""
    service = DashboardCustomizationService(db)
    layout = await service.duplicate_layout(layout_id, current_user.id, new_name)
    
    if not layout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Impossible de dupliquer le layout"
        )
    
    return layout

@router.post("/layouts/{layout_id}/share", response_model=Dict[str, str])
async def toggle_layout_sharing(
    layout_id: int,
    is_shared: bool = Query(..., description="Activer/désactiver le partage"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Active ou désactive le partage d'un layout"""
    service = DashboardCustomizationService(db)
    success = await service.share_layout(layout_id, current_user.id, is_shared)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Layout non trouvé ou non autorisé"
        )
    
    status_msg = "activé" if is_shared else "désactivé"
    return {"message": f"Partage {status_msg} avec succès"}

@router.post("/layouts/{layout_id}/widgets", response_model=Dict[str, Any])
async def add_widget_to_layout(
    layout_id: int,
    request: CreateWidgetRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Ajoute un widget à un layout"""
    service = DashboardCustomizationService(db)
    
    widget = await service.add_widget_to_layout(
        layout_id=layout_id,
        user_id=current_user.id,
        widget_type=request.widget_type,
        position=request.position.dict(),
        size=request.size.dict(),
        title=request.title or "",
        config=request.config
    )
    
    if not widget:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossible d'ajouter le widget"
        )
    
    return widget

@router.put("/widgets/{widget_id}", response_model=Dict[str, str])
async def update_widget(
    widget_id: int,
    request: UpdateWidgetRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Met à jour un widget"""
    service = DashboardCustomizationService(db)
    
    position = request.position.dict() if request.position else None
    size = request.size.dict() if request.size else None
    
    success = await service.update_widget(
        widget_id=widget_id,
        user_id=current_user.id,
        position=position,
        size=size,
        config=request.config,
        title=request.title
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget non trouvé ou non autorisé"
        )
    
    return {"message": "Widget mis à jour avec succès"}

@router.delete("/widgets/{widget_id}", response_model=Dict[str, str])
async def delete_widget(
    widget_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Supprime un widget"""
    service = DashboardCustomizationService(db)
    success = await service.delete_widget(widget_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget non trouvé ou non autorisé"
        )
    
    return {"message": "Widget supprimé avec succès"}

@router.get("/widgets/types", response_model=Dict[str, Dict[str, Any]])
async def get_available_widget_types(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Récupère la liste des types de widgets disponibles"""
    service = DashboardCustomizationService(db)
    widget_types = await service.get_available_widgets()
    return widget_types

@router.get("/widgets/{widget_id}/data")
async def get_widget_data(
    widget_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Récupère les données d'un widget spécifique"""
    # Cette route sera implémentée pour récupérer les données
    # en fonction du type de widget
    return {"message": "Données du widget", "widget_id": widget_id}

@router.get("/templates", response_model=List[Dict[str, Any]])
async def get_dashboard_templates(
    category: Optional[str] = Query(None, description="Filtrer par catégorie"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Récupère les templates de tableau de bord disponibles"""
    # Cette route sera implémentée pour les templates prédéfinis
    templates = [
        {
            "id": 1,
            "name": "Monitoring Standard",
            "description": "Dashboard de monitoring système complet",
            "category": "monitoring",
            "preview_image": "/api/v1/dashboard/templates/1/preview"
        },
        {
            "id": 2,
            "name": "Développement",
            "description": "Dashboard optimisé pour le développement",
            "category": "development", 
            "preview_image": "/api/v1/dashboard/templates/2/preview"
        }
    ]
    
    if category:
        templates = [t for t in templates if t["category"] == category]
    
    return templates

@router.post("/templates/{template_id}/apply", response_model=LayoutResponse)
async def apply_template(
    template_id: int,
    layout_name: str = Query(..., min_length=1, max_length=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """Applique un template pour créer un nouveau layout"""
    # Cette route sera implémentée pour appliquer des templates
    service = DashboardCustomizationService(db)
    
    # Configuration exemple pour un template de monitoring
    if template_id == 1:
        layout = await service.create_layout(
            user_id=current_user.id,
            name=layout_name,
            description="Layout créé à partir du template Monitoring Standard",
            grid_config={
                "columns": 12,
                "rows": 8,
                "gap": 16,
                "padding": 24,
                "responsive": True
            },
            widgets=[
                {
                    "type": "system_metrics",
                    "title": "Métriques Système",
                    "position": {"x": 0, "y": 0},
                    "size": {"width": 4, "height": 3},
                    "config": {"refresh_interval": 5, "chart_type": "line"}
                },
                {
                    "type": "container_list",
                    "title": "Containers",
                    "position": {"x": 4, "y": 0},
                    "size": {"width": 8, "height": 3},
                    "config": {"status_filter": "all", "max_items": 10}
                },
                {
                    "type": "alerts_panel",
                    "title": "Alertes",
                    "position": {"x": 0, "y": 3},
                    "size": {"width": 6, "height": 2},
                    "config": {"severity_filter": "warning"}
                },
                {
                    "type": "network_traffic",
                    "title": "Réseau",
                    "position": {"x": 6, "y": 3},
                    "size": {"width": 6, "height": 2},
                    "config": {"time_range": "1h", "chart_type": "area"}
                }
            ]
        )
        
        if not layout:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible d'appliquer le template"
            )
        
        return layout
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Template non trouvé"
    )
