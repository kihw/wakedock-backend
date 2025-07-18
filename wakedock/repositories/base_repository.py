"""
Base repository class for WakeDock MVC architecture
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError

# Type variable for model classes
ModelType = TypeVar('ModelType')


class BaseRepository(ABC, Generic[ModelType]):
    """Base repository class with common CRUD operations"""
    
    def __init__(self, session: AsyncSession, model: Type[ModelType]):
        self.session = session
        self.model = model
    
    async def get_all(self, skip: int = 0, limit: int = 100, **filters) -> List[ModelType]:
        """Get all records with optional filtering and pagination"""
        query = select(self.model)
        
        # Apply filters
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.where(getattr(self.model, key) == value)
        
        # Apply pagination
        query = query.offset(skip).limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()
    
    async def get_by_id(self, id: str) -> Optional[ModelType]:
        """Get a record by its ID"""
        query = select(self.model).where(self.model.id == id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
    
    async def create(self, data: Dict[str, Any]) -> ModelType:
        """Create a new record"""
        try:
            instance = self.model(**data)
            self.session.add(instance)
            await self.session.commit()
            await self.session.refresh(instance)
            return instance
        except IntegrityError as e:
            await self.session.rollback()
            raise ValueError(f"Failed to create record: {str(e)}")
    
    async def update(self, id: str, data: Dict[str, Any]) -> Optional[ModelType]:
        """Update a record by its ID"""
        try:
            query = update(self.model).where(self.model.id == id).values(**data)
            result = await self.session.execute(query)
            await self.session.commit()
            
            if result.rowcount == 0:
                return None
            
            return await self.get_by_id(id)
        except IntegrityError as e:
            await self.session.rollback()
            raise ValueError(f"Failed to update record: {str(e)}")
    
    async def delete(self, id: str) -> bool:
        """Delete a record by its ID"""
        try:
            query = delete(self.model).where(self.model.id == id)
            result = await self.session.execute(query)
            await self.session.commit()
            return result.rowcount > 0
        except Exception as e:
            await self.session.rollback()
            raise ValueError(f"Failed to delete record: {str(e)}")
    
    async def count(self, **filters) -> int:
        """Count records with optional filtering"""
        query = select(func.count(self.model.id))
        
        # Apply filters
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.where(getattr(self.model, key) == value)
        
        result = await self.session.execute(query)
        return result.scalar()
    
    async def exists(self, id: str) -> bool:
        """Check if a record exists by its ID"""
        query = select(func.count(self.model.id)).where(self.model.id == id)
        result = await self.session.execute(query)
        return result.scalar() > 0
    
    async def get_or_create(self, defaults: Dict[str, Any], **lookup) -> tuple[ModelType, bool]:
        """Get a record or create it if it doesn't exist"""
        # Try to get existing record
        query = select(self.model)
        for key, value in lookup.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)
        
        result = await self.session.execute(query)
        instance = result.scalar_one_or_none()
        
        if instance:
            return instance, False
        
        # Create new record
        create_data = {**lookup, **defaults}
        instance = await self.create(create_data)
        return instance, True
    
    async def bulk_create(self, data_list: List[Dict[str, Any]]) -> List[ModelType]:
        """Create multiple records"""
        try:
            instances = [self.model(**data) for data in data_list]
            self.session.add_all(instances)
            await self.session.commit()
            
            # Refresh all instances
            for instance in instances:
                await self.session.refresh(instance)
            
            return instances
        except IntegrityError as e:
            await self.session.rollback()
            raise ValueError(f"Failed to create records: {str(e)}")
    
    async def bulk_update(self, updates: List[Dict[str, Any]]) -> int:
        """Update multiple records"""
        try:
            updated_count = 0
            for update_data in updates:
                if 'id' not in update_data:
                    continue
                
                record_id = update_data.pop('id')
                query = update(self.model).where(self.model.id == record_id).values(**update_data)
                result = await self.session.execute(query)
                updated_count += result.rowcount
            
            await self.session.commit()
            return updated_count
        except IntegrityError as e:
            await self.session.rollback()
            raise ValueError(f"Failed to update records: {str(e)}")
