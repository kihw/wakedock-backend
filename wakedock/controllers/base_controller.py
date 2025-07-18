"""
Base controller class for WakeDock MVC architecture
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar, Generic
from fastapi import HTTPException, status
from wakedock.repositories.base_repository import BaseRepository

# Type variable for model classes
ModelType = TypeVar('ModelType')


class BaseController(ABC, Generic[ModelType]):
    """Base controller class with common business logic operations"""
    
    def __init__(self, repository: BaseRepository[ModelType]):
        self.repository = repository
    
    async def get_all(self, skip: int = 0, limit: int = 100, **filters) -> List[ModelType]:
        """Get all records with optional filtering and pagination"""
        try:
            return await self.repository.get_all(skip=skip, limit=limit, **filters)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve records: {str(e)}"
            )
    
    async def get_by_id(self, id: str) -> ModelType:
        """Get a record by its ID"""
        try:
            record = await self.repository.get_by_id(id)
            if not record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Record with ID {id} not found"
                )
            return record
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve record: {str(e)}"
            )
    
    async def create(self, data: Dict[str, Any]) -> ModelType:
        """Create a new record"""
        try:
            # Validate data before creation
            await self.validate_create_data(data)
            
            # Perform business logic validation
            await self.pre_create_hook(data)
            
            # Create the record
            record = await self.repository.create(data)
            
            # Perform post-creation actions
            await self.post_create_hook(record)
            
            return record
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create record: {str(e)}"
            )
    
    async def update(self, id: str, data: Dict[str, Any]) -> ModelType:
        """Update a record by its ID"""
        try:
            # Check if record exists
            existing_record = await self.repository.get_by_id(id)
            if not existing_record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Record with ID {id} not found"
                )
            
            # Validate data before update
            await self.validate_update_data(id, data)
            
            # Perform business logic validation
            await self.pre_update_hook(id, data)
            
            # Update the record
            updated_record = await self.repository.update(id, data)
            
            # Perform post-update actions
            await self.post_update_hook(updated_record)
            
            return updated_record
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update record: {str(e)}"
            )
    
    async def delete(self, id: str) -> bool:
        """Delete a record by its ID"""
        try:
            # Check if record exists
            existing_record = await self.repository.get_by_id(id)
            if not existing_record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Record with ID {id} not found"
                )
            
            # Perform business logic validation
            await self.pre_delete_hook(id)
            
            # Delete the record
            deleted = await self.repository.delete(id)
            
            # Perform post-delete actions
            if deleted:
                await self.post_delete_hook(id)
            
            return deleted
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete record: {str(e)}"
            )
    
    async def count(self, **filters) -> int:
        """Count records with optional filtering"""
        try:
            return await self.repository.count(**filters)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to count records: {str(e)}"
            )
    
    async def exists(self, id: str) -> bool:
        """Check if a record exists by its ID"""
        try:
            return await self.repository.exists(id)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to check record existence: {str(e)}"
            )
    
    # Validation hooks (to be implemented by subclasses)
    async def validate_create_data(self, data: Dict[str, Any]) -> None:
        """Validate data before creating a record"""
        pass
    
    async def validate_update_data(self, id: str, data: Dict[str, Any]) -> None:
        """Validate data before updating a record"""
        pass
    
    # Business logic hooks (to be implemented by subclasses)
    async def pre_create_hook(self, data: Dict[str, Any]) -> None:
        """Hook called before creating a record"""
        pass
    
    async def post_create_hook(self, record: ModelType) -> None:
        """Hook called after creating a record"""
        pass
    
    async def pre_update_hook(self, id: str, data: Dict[str, Any]) -> None:
        """Hook called before updating a record"""
        pass
    
    async def post_update_hook(self, record: ModelType) -> None:
        """Hook called after updating a record"""
        pass
    
    async def pre_delete_hook(self, id: str) -> None:
        """Hook called before deleting a record"""
        pass
    
    async def post_delete_hook(self, id: str) -> None:
        """Hook called after deleting a record"""
        pass
