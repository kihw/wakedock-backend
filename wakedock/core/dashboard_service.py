"""
Service de personnalisation des tableaux de bord - WakeDock
Gestion des layouts, widgets et configurations personnalisées
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from wakedock.core.base_service import BaseService
from wakedock.models.dashboard import DashboardLayout, DashboardWidget

logger = logging.getLogger(__name__)

class DashboardCustomizationService(BaseService):
    """Service pour la personnalisation des tableaux de bord"""
    
    def __init__(self, db_session: AsyncSession):
        super().__init__()
        self.db = db_session
        self.widget_types = self._get_available_widget_types()
        
    def _get_available_widget_types(self) -> Dict[str, Dict[str, Any]]:
        """Retourne les types de widgets disponibles avec leurs configurations"""
        return {
            "system_metrics": {
                "name": "Métriques Système",
                "description": "CPU, Mémoire, Disque",
                "category": "monitoring",
                "size": {"width": 2, "height": 2},
                "configurable": ["refresh_interval", "chart_type"],
                "data_sources": ["cpu", "memory", "disk"]
            },
            "container_list": {
                "name": "Liste des Containers",
                "description": "Aperçu des containers Docker",
                "category": "containers",
                "size": {"width": 4, "height": 3},
                "configurable": ["status_filter", "max_items", "sort_by"],
                "data_sources": ["docker_api"]
            },
            "alerts_panel": {
                "name": "Panneau d'Alertes",
                "description": "Alertes système critiques",
                "category": "monitoring",
                "size": {"width": 3, "height": 2},
                "configurable": ["severity_filter", "auto_refresh"],
                "data_sources": ["alerts_service"]
            },
            "network_traffic": {
                "name": "Trafic Réseau",
                "description": "Monitoring réseau en temps réel",
                "category": "monitoring",
                "size": {"width": 3, "height": 2},
                "configurable": ["time_range", "chart_type"],
                "data_sources": ["network_metrics"]
            },
            "quick_actions": {
                "name": "Actions Rapides",
                "description": "Boutons d'actions fréquentes",
                "category": "controls",
                "size": {"width": 2, "height": 1},
                "configurable": ["button_actions", "layout"],
                "data_sources": ["user_config"]
            },
            "logs_viewer": {
                "name": "Visualiseur de Logs",
                "description": "Logs récents en temps réel",
                "category": "monitoring",
                "size": {"width": 4, "height": 2},
                "configurable": ["log_level", "max_lines", "auto_scroll"],
                "data_sources": ["docker_logs"]
            },
            "custom_metric": {
                "name": "Métrique Personnalisée",
                "description": "Métrique définie par l'utilisateur",
                "category": "custom",
                "size": {"width": 2, "height": 2},
                "configurable": ["metric_query", "chart_type", "thresholds"],
                "data_sources": ["custom_query"]
            }
        }
    
    async def get_user_layouts(self, user_id: int) -> List[Dict[str, Any]]:
        """Récupère tous les layouts d'un utilisateur"""
        try:
            query = (
                select(DashboardLayout)
                .options(selectinload(DashboardLayout.widgets))
                .where(DashboardLayout.user_id == user_id)
                .order_by(DashboardLayout.created_at.desc())
            )
            
            result = await self.db.execute(query)
            layouts = result.scalars().all()
            
            return [
                {
                    "id": layout.id,
                    "name": layout.name,
                    "description": layout.description,
                    "is_default": layout.is_default,
                    "is_shared": layout.is_shared,
                    "grid_config": layout.grid_config,
                    "widgets": [
                        {
                            "id": widget.id,
                            "type": widget.widget_type,
                            "position": widget.position,
                            "size": widget.size,
                            "config": widget.config,
                            "title": widget.title
                        }
                        for widget in layout.widgets
                    ],
                    "created_at": layout.created_at.isoformat(),
                    "updated_at": layout.updated_at.isoformat()
                }
                for layout in layouts
            ]
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des layouts: {e}")
            return []
    
    async def create_layout(
        self, 
        user_id: int, 
        name: str, 
        description: str = "",
        grid_config: Optional[Dict[str, Any]] = None,
        widgets: Optional[List[Dict[str, Any]]] = None,
        is_default: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Crée un nouveau layout pour un utilisateur"""
        try:
            # Si c'est le layout par défaut, désactiver les autres
            if is_default:
                await self.db.execute(
                    update(DashboardLayout)
                    .where(DashboardLayout.user_id == user_id)
                    .values(is_default=False)
                )
            
            # Configuration de grille par défaut
            if grid_config is None:
                grid_config = {
                    "columns": 12,
                    "rows": 8,
                    "gap": 16,
                    "padding": 24,
                    "responsive": True
                }
            
            # Créer le layout
            layout = DashboardLayout(
                user_id=user_id,
                name=name,
                description=description,
                grid_config=grid_config,
                is_default=is_default,
                is_shared=False
            )
            
            self.db.add(layout)
            await self.db.flush()  # Pour obtenir l'ID
            
            # Ajouter les widgets si fournis
            if widgets:
                for widget_data in widgets:
                    widget = DashboardWidget(
                        layout_id=layout.id,
                        widget_type=widget_data.get("type"),
                        title=widget_data.get("title", ""),
                        position=widget_data.get("position", {"x": 0, "y": 0}),
                        size=widget_data.get("size", {"width": 2, "height": 2}),
                        config=widget_data.get("config", {})
                    )
                    self.db.add(widget)
            
            await self.db.commit()
            
            # Retourner le layout créé
            return await self.get_layout_by_id(layout.id)
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Erreur lors de la création du layout: {e}")
            return None
    
    async def get_layout_by_id(self, layout_id: int) -> Optional[Dict[str, Any]]:
        """Récupère un layout par son ID"""
        try:
            query = (
                select(DashboardLayout)
                .options(selectinload(DashboardLayout.widgets))
                .where(DashboardLayout.id == layout_id)
            )
            
            result = await self.db.execute(query)
            layout = result.scalar_one_or_none()
            
            if not layout:
                return None
            
            return {
                "id": layout.id,
                "name": layout.name,
                "description": layout.description,
                "is_default": layout.is_default,
                "is_shared": layout.is_shared,
                "grid_config": layout.grid_config,
                "widgets": [
                    {
                        "id": widget.id,
                        "type": widget.widget_type,
                        "position": widget.position,
                        "size": widget.size,
                        "config": widget.config,
                        "title": widget.title
                    }
                    for widget in layout.widgets
                ],
                "created_at": layout.created_at.isoformat(),
                "updated_at": layout.updated_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du layout {layout_id}: {e}")
            return None
    
    async def update_layout(
        self,
        layout_id: int,
        user_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        grid_config: Optional[Dict[str, Any]] = None,
        is_default: Optional[bool] = None
    ) -> bool:
        """Met à jour un layout existant"""
        try:
            # Vérifier que le layout appartient à l'utilisateur
            query = select(DashboardLayout).where(
                DashboardLayout.id == layout_id,
                DashboardLayout.user_id == user_id
            )
            result = await self.db.execute(query)
            layout = result.scalar_one_or_none()
            
            if not layout:
                return False
            
            # Si on définit comme défaut, désactiver les autres
            if is_default:
                await self.db.execute(
                    update(DashboardLayout)
                    .where(DashboardLayout.user_id == user_id)
                    .values(is_default=False)
                )
            
            # Mettre à jour les champs fournis
            update_data = {}
            if name is not None:
                update_data["name"] = name
            if description is not None:
                update_data["description"] = description
            if grid_config is not None:
                update_data["grid_config"] = grid_config
            if is_default is not None:
                update_data["is_default"] = is_default
            
            if update_data:
                update_data["updated_at"] = datetime.utcnow()
                await self.db.execute(
                    update(DashboardLayout)
                    .where(DashboardLayout.id == layout_id)
                    .values(**update_data)
                )
                await self.db.commit()
            
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Erreur lors de la mise à jour du layout {layout_id}: {e}")
            return False
    
    async def delete_layout(self, layout_id: int, user_id: int) -> bool:
        """Supprime un layout"""
        try:
            # Vérifier que le layout appartient à l'utilisateur
            query = select(DashboardLayout).where(
                DashboardLayout.id == layout_id,
                DashboardLayout.user_id == user_id
            )
            result = await self.db.execute(query)
            layout = result.scalar_one_or_none()
            
            if not layout:
                return False
            
            # Supprimer le layout (cascade supprimera les widgets)
            await self.db.execute(
                delete(DashboardLayout).where(DashboardLayout.id == layout_id)
            )
            await self.db.commit()
            
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Erreur lors de la suppression du layout {layout_id}: {e}")
            return False
    
    async def add_widget_to_layout(
        self,
        layout_id: int,
        user_id: int,
        widget_type: str,
        position: Dict[str, int],
        size: Dict[str, int],
        title: str = "",
        config: Dict[str, Any] = None
    ) -> Optional[Dict[str, Any]]:
        """Ajoute un widget à un layout"""
        try:
            # Vérifier que le layout appartient à l'utilisateur
            query = select(DashboardLayout).where(
                DashboardLayout.id == layout_id,
                DashboardLayout.user_id == user_id
            )
            result = await self.db.execute(query)
            layout = result.scalar_one_or_none()
            
            if not layout:
                return None
            
            # Vérifier que le type de widget est valide
            if widget_type not in self.widget_types:
                logger.error(f"Type de widget invalide: {widget_type}")
                return None
            
            # Configuration par défaut si non fournie
            if config is None:
                config = {}
            
            # Créer le widget
            widget = DashboardWidget(
                layout_id=layout_id,
                widget_type=widget_type,
                title=title or self.widget_types[widget_type]["name"],
                position=position,
                size=size,
                config=config
            )
            
            self.db.add(widget)
            await self.db.commit()
            
            return {
                "id": widget.id,
                "type": widget.widget_type,
                "position": widget.position,
                "size": widget.size,
                "config": widget.config,
                "title": widget.title
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Erreur lors de l'ajout du widget: {e}")
            return None
    
    async def update_widget(
        self,
        widget_id: int,
        user_id: int,
        position: Optional[Dict[str, int]] = None,
        size: Optional[Dict[str, int]] = None,
        config: Optional[Dict[str, Any]] = None,
        title: Optional[str] = None
    ) -> bool:
        """Met à jour un widget"""
        try:
            # Vérifier que le widget appartient à l'utilisateur
            query = (
                select(DashboardWidget)
                .join(DashboardLayout)
                .where(
                    DashboardWidget.id == widget_id,
                    DashboardLayout.user_id == user_id
                )
            )
            result = await self.db.execute(query)
            widget = result.scalar_one_or_none()
            
            if not widget:
                return False
            
            # Mettre à jour les champs fournis
            update_data = {}
            if position is not None:
                update_data["position"] = position
            if size is not None:
                update_data["size"] = size
            if config is not None:
                update_data["config"] = config
            if title is not None:
                update_data["title"] = title
            
            if update_data:
                await self.db.execute(
                    update(DashboardWidget)
                    .where(DashboardWidget.id == widget_id)
                    .values(**update_data)
                )
                await self.db.commit()
            
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Erreur lors de la mise à jour du widget {widget_id}: {e}")
            return False
    
    async def delete_widget(self, widget_id: int, user_id: int) -> bool:
        """Supprime un widget"""
        try:
            # Vérifier que le widget appartient à l'utilisateur
            query = (
                select(DashboardWidget)
                .join(DashboardLayout)
                .where(
                    DashboardWidget.id == widget_id,
                    DashboardLayout.user_id == user_id
                )
            )
            result = await self.db.execute(query)
            widget = result.scalar_one_or_none()
            
            if not widget:
                return False
            
            # Supprimer le widget
            await self.db.execute(
                delete(DashboardWidget).where(DashboardWidget.id == widget_id)
            )
            await self.db.commit()
            
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Erreur lors de la suppression du widget {widget_id}: {e}")
            return False
    
    async def get_available_widgets(self) -> Dict[str, Dict[str, Any]]:
        """Retourne la liste des types de widgets disponibles"""
        return self.widget_types
    
    async def share_layout(self, layout_id: int, user_id: int, is_shared: bool = True) -> bool:
        """Active/désactive le partage d'un layout"""
        try:
            # Vérifier que le layout appartient à l'utilisateur
            query = select(DashboardLayout).where(
                DashboardLayout.id == layout_id,
                DashboardLayout.user_id == user_id
            )
            result = await self.db.execute(query)
            layout = result.scalar_one_or_none()
            
            if not layout:
                return False
            
            # Mettre à jour le statut de partage
            await self.db.execute(
                update(DashboardLayout)
                .where(DashboardLayout.id == layout_id)
                .values(is_shared=is_shared, updated_at=datetime.utcnow())
            )
            await self.db.commit()
            
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Erreur lors du partage du layout {layout_id}: {e}")
            return False
    
    async def duplicate_layout(
        self, 
        layout_id: int, 
        user_id: int, 
        new_name: str
    ) -> Optional[Dict[str, Any]]:
        """Duplique un layout existant"""
        try:
            # Récupérer le layout original
            original_layout = await self.get_layout_by_id(layout_id)
            if not original_layout:
                return None
            
            # Créer une copie
            new_layout = await self.create_layout(
                user_id=user_id,
                name=new_name,
                description=f"Copie de {original_layout['name']}",
                grid_config=original_layout["grid_config"],
                widgets=original_layout["widgets"],
                is_default=False
            )
            
            return new_layout
            
        except Exception as e:
            logger.error(f"Erreur lors de la duplication du layout {layout_id}: {e}")
            return None
