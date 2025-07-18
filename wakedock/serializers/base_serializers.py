"""
Base serializer classes for WakeDock MVC architecture
"""

from typing import Any, Dict, List, Optional, Generic, TypeVar
from datetime import datetime
from pydantic import BaseModel, Field, validator, root_validator


class BaseSerializer(BaseModel):
    """Base serializer class with common fields and validation"""
    
    class Config:
        # Allow arbitrary types for complex objects
        arbitrary_types_allowed = True
        # Use enum values instead of enum objects
        use_enum_values = True
        # Allow population by field name and alias
        allow_population_by_field_name = True
        # Validate assignment when setting attributes
        validate_assignment = True
        # Generate JSON schema
        schema_extra = {
            "example": {}
        }


class BaseCreateSerializer(BaseSerializer):
    """Base serializer for create operations"""
    pass


class BaseUpdateSerializer(BaseSerializer):
    """Base serializer for update operations"""
    pass


class BaseResponseSerializer(BaseSerializer):
    """Base serializer for API responses"""
    
    id: str = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    
    class Config(BaseSerializer.Config):
        # Use alias for field names
        allow_population_by_field_name = True


class PaginationMetaSerializer(BaseSerializer):
    """Serializer for pagination metadata"""
    
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_previous: bool = Field(..., description="Whether there is a previous page")


class PaginatedResponseSerializer(BaseSerializer, Generic[TypeVar('T')]):
    """Generic serializer for paginated responses"""
    
    items: List[Any] = Field(..., description="List of items")
    pagination: PaginationMetaSerializer = Field(..., description="Pagination metadata")


class ApiResponseSerializer(BaseSerializer):
    """Base serializer for API responses"""
    
    success: bool = Field(..., description="Whether the request was successful")
    message: str = Field(..., description="Response message")
    timestamp: datetime = Field(..., description="Response timestamp")
    status_code: int = Field(..., description="HTTP status code")
    data: Optional[Any] = Field(None, description="Response data")


class ApiErrorSerializer(BaseSerializer):
    """Serializer for API error responses"""
    
    success: bool = Field(False, description="Whether the request was successful")
    error: Dict[str, Any] = Field(..., description="Error details")
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "success": False,
                "error": {
                    "message": "Error message",
                    "code": "ERROR_CODE",
                    "details": {},
                    "timestamp": "2023-01-01T00:00:00Z",
                    "status_code": 400
                }
            }
        }


class HealthCheckSerializer(BaseSerializer):
    """Serializer for health check responses"""
    
    status: str = Field(..., description="Health status")
    timestamp: datetime = Field(..., description="Check timestamp")
    version: str = Field(..., description="Application version")
    database: str = Field(..., description="Database status")
    docker: str = Field(..., description="Docker status")
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2023-01-01T00:00:00Z",
                "version": "1.0.0",
                "database": "connected",
                "docker": "running"
            }
        }


class FilterSerializer(BaseSerializer):
    """Base serializer for filtering parameters"""
    
    search: Optional[str] = Field(None, description="Search query")
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: Optional[str] = Field("asc", description="Sort order (asc/desc)")
    
    @validator('sort_order')
    def validate_sort_order(cls, v):
        if v not in ['asc', 'desc']:
            raise ValueError('sort_order must be either "asc" or "desc"')
        return v


class PaginationSerializer(BaseSerializer):
    """Serializer for pagination parameters"""
    
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(10, ge=1, le=100, description="Number of items per page")
    
    @validator('page_size')
    def validate_page_size(cls, v):
        if v > 100:
            raise ValueError('page_size cannot exceed 100')
        return v


class ActionSerializer(BaseSerializer):
    """Base serializer for action requests"""
    
    action: str = Field(..., description="Action to perform")
    options: Optional[Dict[str, Any]] = Field(None, description="Action options")
    
    @validator('action')
    def validate_action(cls, v):
        if not v.strip():
            raise ValueError('action cannot be empty')
        return v.strip().lower()


class BulkActionSerializer(BaseSerializer):
    """Serializer for bulk action requests"""
    
    ids: List[str] = Field(..., description="List of IDs to perform action on")
    action: str = Field(..., description="Action to perform")
    options: Optional[Dict[str, Any]] = Field(None, description="Action options")
    
    @validator('ids')
    def validate_ids(cls, v):
        if not v:
            raise ValueError('ids cannot be empty')
        return v
    
    @validator('action')
    def validate_action(cls, v):
        if not v.strip():
            raise ValueError('action cannot be empty')
        return v.strip().lower()


class StatusSerializer(BaseSerializer):
    """Serializer for status responses"""
    
    status: str = Field(..., description="Current status")
    details: Optional[Dict[str, Any]] = Field(None, description="Status details")
    last_updated: datetime = Field(..., description="Last update timestamp")
    
    class Config(BaseSerializer.Config):
        schema_extra = {
            "example": {
                "status": "running",
                "details": {
                    "cpu_usage": 25.5,
                    "memory_usage": 512
                },
                "last_updated": "2023-01-01T00:00:00Z"
            }
        }
