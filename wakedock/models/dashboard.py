"""
Modèles de base de données pour la personnalisation des tableaux de bord - WakeDock
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, Integer, String, Text, JSON, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

from wakedock.models.base import Base

class DashboardLayout(Base):
    """Modèle pour les layouts de tableau de bord personnalisés"""
    __tablename__ = "dashboard_layouts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    grid_config = Column(JSON, nullable=False, default={})
    is_default = Column(Boolean, default=False, nullable=False)
    is_shared = Column(Boolean, default=False, nullable=False)
    share_token = Column(String(64), nullable=True, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relations
    user = relationship("User", back_populates="dashboard_layouts")
    widgets = relationship("DashboardWidget", back_populates="layout", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<DashboardLayout(id={self.id}, name='{self.name}', user_id={self.user_id})>"

class DashboardWidget(Base):
    """Modèle pour les widgets de tableau de bord"""
    __tablename__ = "dashboard_widgets"
    
    id = Column(Integer, primary_key=True, index=True)
    layout_id = Column(Integer, ForeignKey("dashboard_layouts.id"), nullable=False, index=True)
    widget_type = Column(String(50), nullable=False)
    title = Column(String(100), nullable=True)
    position = Column(JSON, nullable=False, default={})  # {"x": 0, "y": 0}
    size = Column(JSON, nullable=False, default={})      # {"width": 2, "height": 2}
    config = Column(JSON, nullable=False, default={})    # Configuration spécifique au widget
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relations
    layout = relationship("DashboardLayout", back_populates="widgets")
    
    def __repr__(self):
        return f"<DashboardWidget(id={self.id}, type='{self.widget_type}', layout_id={self.layout_id})>"

class DashboardTemplate(Base):
    """Modèle pour les templates de tableau de bord prédéfinis"""
    __tablename__ = "dashboard_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=False)  # monitoring, development, operations, etc.
    layout_config = Column(JSON, nullable=False, default={})
    widgets_config = Column(JSON, nullable=False, default=[])
    is_public = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    usage_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relations
    creator = relationship("User", foreign_keys=[created_by])
    
    def __repr__(self):
        return f"<DashboardTemplate(id={self.id}, name='{self.name}', category='{self.category}')>"

class WidgetDataSource(Base):
    """Modèle pour les sources de données des widgets"""
    __tablename__ = "widget_data_sources"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    source_type = Column(String(50), nullable=False)  # api, database, file, etc.
    connection_config = Column(JSON, nullable=False, default={})
    refresh_interval = Column(Integer, default=30, nullable=False)  # secondes
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<WidgetDataSource(id={self.id}, name='{self.name}', type='{self.source_type}')>"

class UserDashboardPreferences(Base):
    """Modèle pour les préférences utilisateur globales du tableau de bord"""
    __tablename__ = "user_dashboard_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    auto_refresh_interval = Column(Integer, default=30, nullable=False)  # secondes
    show_grid = Column(Boolean, default=True, nullable=False)
    snap_to_grid = Column(Boolean, default=True, nullable=False)
    compact_mode = Column(Boolean, default=False, nullable=False)
    default_widget_size = Column(JSON, nullable=False, default={"width": 2, "height": 2})
    notification_settings = Column(JSON, nullable=False, default={})
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relations
    user = relationship("User", back_populates="dashboard_preferences")
    
    def __repr__(self):
        return f"<UserDashboardPreferences(id={self.id}, user_id={self.user_id})>"
