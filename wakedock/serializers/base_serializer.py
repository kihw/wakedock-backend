"""
Base serializer for WakeDock
"""

from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, Field
from datetime import datetime


class BaseSerializer(BaseModel):
    """Base serializer for all WakeDock serializers"""
    
    class Config:
        # Allow extra fields for flexibility
        extra = "allow"
        # Use enum values instead of names
        use_enum_values = True
        # Allow population by field name
        validate_by_name = True
        # JSON schema extra configuration
        json_schema_extra = {
            "example": {}
        }


class PaginatedResponse(BaseModel):
    """Base paginated response"""
    
    items: list = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")
    
    class Config:
        extra = "allow"


class BaseResponse(BaseModel):
    """Base response model"""
    
    success: bool = Field(True, description="Whether the operation was successful")
    message: Optional[str] = Field(None, description="Response message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    
    class Config:
        extra = "allow"


class ErrorResponse(BaseResponse):
    """Error response model"""
    
    success: bool = Field(False, description="Always false for errors")
    error_code: Optional[str] = Field(None, description="Error code")
    error_details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    
    class Config:
        extra = "allow"


class SuccessResponse(BaseResponse):
    """Success response model"""
    
    data: Optional[Any] = Field(None, description="Response data")
    
    class Config:
        extra = "allow"
