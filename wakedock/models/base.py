"""
Base classes and utilities for WakeDock models
"""

from sqlalchemy import Column, Integer, DateTime, String, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, Any, Dict
import uuid

from wakedock.database.base import Base  # Use the single Base instance

class BaseModel(Base):
    """Base model class with common fields and methods"""
    
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update model from dictionary"""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    @classmethod
    def create_from_dict(cls, data: Dict[str, Any]) -> 'BaseModel':
        """Create model instance from dictionary"""
        instance = cls()
        instance.update_from_dict(data)
        return instance


class AuditableModel(BaseModel):
    """Base model with audit fields"""
    
    __abstract__ = True
    
    created_by = Column(String(255), nullable=True)
    updated_by = Column(String(255), nullable=True)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    
    def soft_delete(self, user_id: Optional[str] = None) -> None:
        """Soft delete by marking as inactive"""
        self.is_active = False
        self.updated_by = user_id
        self.updated_at = datetime.utcnow()


class TimestampMixin:
    """Mixin for timestamp fields"""
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UUIDMixin:
    """Mixin for UUID fields"""
    
    uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, index=True)


class SoftDeleteMixin:
    """Mixin for soft delete functionality"""
    
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(String(255), nullable=True)
    
    def soft_delete(self, user_id: Optional[str] = None) -> None:
        """Mark as deleted"""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
        self.deleted_by = user_id


class MetadataMixin:
    """Mixin for metadata fields"""
    
    metadata_json = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)  # JSON array as text
    description = Column(Text, nullable=True)
    
    def set_metadata(self, data: Dict[str, Any]) -> None:
        """Set metadata as JSON string"""
        import json
        self.metadata_json = json.dumps(data)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary"""
        import json
        if self.metadata_json:
            return json.loads(self.metadata_json)
        return {}
    
    def set_tags(self, tags: list) -> None:
        """Set tags as JSON string"""
        import json
        self.tags = json.dumps(tags)
    
    def get_tags(self) -> list:
        """Get tags as list"""
        import json
        if self.tags:
            return json.loads(self.tags)
        return []
