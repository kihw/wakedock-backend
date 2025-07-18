"""
Base view class for WakeDock MVC architecture
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from fastapi import Response, status
from pydantic import BaseModel
import json


class BaseView:
    """Base view class for handling API responses"""
    
    @staticmethod
    def success_response(
        data: Any = None,
        message: str = "Success",
        status_code: int = status.HTTP_200_OK,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Create a successful response"""
        response_data = {
            "success": True,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "status_code": status_code
        }
        
        if data is not None:
            response_data["data"] = data
        
        return response_data
    
    @staticmethod
    def error_response(
        message: str,
        details: Optional[Any] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        error_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create an error response"""
        response_data = {
            "success": False,
            "error": {
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "status_code": status_code
            }
        }
        
        if error_code:
            response_data["error"]["code"] = error_code
        
        if details:
            response_data["error"]["details"] = details
        
        return response_data
    
    @staticmethod
    def paginated_response(
        items: List[Any],
        total: int,
        page: int,
        page_size: int,
        message: str = "Success"
    ) -> Dict[str, Any]:
        """Create a paginated response"""
        total_pages = (total + page_size - 1) // page_size
        
        return BaseView.success_response(
            data={
                "items": items,
                "pagination": {
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_previous": page > 1
                }
            },
            message=message
        )
    
    @staticmethod
    def no_content_response(message: str = "No content") -> Dict[str, Any]:
        """Create a no content response"""
        return BaseView.success_response(
            message=message,
            status_code=status.HTTP_204_NO_CONTENT
        )
    
    @staticmethod
    def created_response(
        data: Any,
        message: str = "Resource created successfully"
    ) -> Dict[str, Any]:
        """Create a created response"""
        return BaseView.success_response(
            data=data,
            message=message,
            status_code=status.HTTP_201_CREATED
        )
    
    @staticmethod
    def updated_response(
        data: Any,
        message: str = "Resource updated successfully"
    ) -> Dict[str, Any]:
        """Create an updated response"""
        return BaseView.success_response(
            data=data,
            message=message,
            status_code=status.HTTP_200_OK
        )
    
    @staticmethod
    def deleted_response(message: str = "Resource deleted successfully") -> Dict[str, Any]:
        """Create a deleted response"""
        return BaseView.success_response(
            message=message,
            status_code=status.HTTP_200_OK
        )
    
    @staticmethod
    def validation_error_response(
        message: str = "Validation failed",
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a validation error response"""
        return BaseView.error_response(
            message=message,
            details=details,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="VALIDATION_ERROR"
        )
    
    @staticmethod
    def not_found_response(
        resource: str = "Resource",
        identifier: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a not found response"""
        message = f"{resource} not found"
        if identifier:
            message += f" with ID: {identifier}"
        
        return BaseView.error_response(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND"
        )
    
    @staticmethod
    def unauthorized_response(
        message: str = "Unauthorized access"
    ) -> Dict[str, Any]:
        """Create an unauthorized response"""
        return BaseView.error_response(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="UNAUTHORIZED"
        )
    
    @staticmethod
    def forbidden_response(
        message: str = "Forbidden access"
    ) -> Dict[str, Any]:
        """Create a forbidden response"""
        return BaseView.error_response(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="FORBIDDEN"
        )
    
    @staticmethod
    def internal_server_error_response(
        message: str = "Internal server error"
    ) -> Dict[str, Any]:
        """Create an internal server error response"""
        return BaseView.error_response(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="INTERNAL_SERVER_ERROR"
        )
    
    @staticmethod
    def format_model_data(model: Any, exclude_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Format a model object for API response"""
        exclude_fields = exclude_fields or []
        
        if hasattr(model, '__dict__'):
            data = {}
            for key, value in model.__dict__.items():
                if key.startswith('_') or key in exclude_fields:
                    continue
                
                if isinstance(value, datetime):
                    data[key] = value.isoformat()
                elif hasattr(value, '__dict__'):
                    # Handle nested models
                    data[key] = BaseView.format_model_data(value, exclude_fields)
                else:
                    data[key] = value
            
            return data
        
        return model
    
    @staticmethod
    def format_models_list(
        models: List[Any],
        exclude_fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Format a list of model objects for API response"""
        return [BaseView.format_model_data(model, exclude_fields) for model in models]
