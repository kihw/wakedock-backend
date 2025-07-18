"""
Base validator classes for WakeDock MVC architecture
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Callable
import re
from datetime import datetime
from email_validator import validate_email, EmailNotValidError


class ValidationError(Exception):
    """Custom validation error exception"""
    
    def __init__(self, message: str, field: str = None, code: str = None):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(self.message)


class BaseValidator(ABC):
    """Base validator class with common validation methods"""
    
    def __init__(self, strict: bool = False):
        self.strict = strict
        self.errors = []
    
    def validate(self, data: Any, rules: Dict[str, Any] = None) -> bool:
        """Validate data against rules"""
        self.errors = []
        
        try:
            if rules:
                self._validate_with_rules(data, rules)
            else:
                self._validate_data(data)
            
            return len(self.errors) == 0
        except Exception as e:
            if self.strict:
                raise ValidationError(f"Validation failed: {str(e)}")
            self.errors.append(str(e))
            return False
    
    def _validate_with_rules(self, data: Any, rules: Dict[str, Any]) -> None:
        """Validate data with specific rules"""
        for field, field_rules in rules.items():
            try:
                self._validate_field(data, field, field_rules)
            except ValidationError as e:
                self.errors.append(f"{field}: {e.message}")
    
    def _validate_field(self, data: Any, field: str, rules: Dict[str, Any]) -> None:
        """Validate a single field"""
        value = data.get(field) if isinstance(data, dict) else getattr(data, field, None)
        
        # Required validation
        if rules.get('required', False) and (value is None or value == ''):
            raise ValidationError(f"Field '{field}' is required", field, "REQUIRED")
        
        # Skip other validations if value is None and not required
        if value is None and not rules.get('required', False):
            return
        
        # Type validation
        if 'type' in rules:
            self._validate_type(value, rules['type'], field)
        
        # String validations
        if isinstance(value, str):
            if 'min_length' in rules:
                self._validate_min_length(value, rules['min_length'], field)
            if 'max_length' in rules:
                self._validate_max_length(value, rules['max_length'], field)
            if 'pattern' in rules:
                self._validate_pattern(value, rules['pattern'], field)
            if 'email' in rules and rules['email']:
                self._validate_email(value, field)
        
        # Numeric validations
        if isinstance(value, (int, float)):
            if 'min_value' in rules:
                self._validate_min_value(value, rules['min_value'], field)
            if 'max_value' in rules:
                self._validate_max_value(value, rules['max_value'], field)
        
        # List validations
        if isinstance(value, list):
            if 'min_items' in rules:
                self._validate_min_items(value, rules['min_items'], field)
            if 'max_items' in rules:
                self._validate_max_items(value, rules['max_items'], field)
            if 'unique_items' in rules and rules['unique_items']:
                self._validate_unique_items(value, field)
        
        # Custom validation
        if 'custom' in rules:
            self._validate_custom(value, rules['custom'], field)
        
        # Enum validation
        if 'choices' in rules:
            self._validate_choices(value, rules['choices'], field)
    
    @abstractmethod
    def _validate_data(self, data: Any) -> None:
        """Abstract method for custom validation logic"""
        pass
    
    def _validate_type(self, value: Any, expected_type: type, field: str) -> None:
        """Validate value type"""
        if not isinstance(value, expected_type):
            raise ValidationError(
                f"Field '{field}' must be of type {expected_type.__name__}",
                field,
                "TYPE_ERROR"
            )
    
    def _validate_min_length(self, value: str, min_length: int, field: str) -> None:
        """Validate minimum string length"""
        if len(value) < min_length:
            raise ValidationError(
                f"Field '{field}' must be at least {min_length} characters long",
                field,
                "MIN_LENGTH"
            )
    
    def _validate_max_length(self, value: str, max_length: int, field: str) -> None:
        """Validate maximum string length"""
        if len(value) > max_length:
            raise ValidationError(
                f"Field '{field}' must be at most {max_length} characters long",
                field,
                "MAX_LENGTH"
            )
    
    def _validate_pattern(self, value: str, pattern: str, field: str) -> None:
        """Validate string pattern"""
        if not re.match(pattern, value):
            raise ValidationError(
                f"Field '{field}' does not match required pattern",
                field,
                "PATTERN_MISMATCH"
            )
    
    def _validate_email(self, value: str, field: str) -> None:
        """Validate email format"""
        try:
            validate_email(value)
        except EmailNotValidError:
            raise ValidationError(
                f"Field '{field}' must be a valid email address",
                field,
                "INVALID_EMAIL"
            )
    
    def _validate_min_value(self, value: Union[int, float], min_value: Union[int, float], field: str) -> None:
        """Validate minimum numeric value"""
        if value < min_value:
            raise ValidationError(
                f"Field '{field}' must be at least {min_value}",
                field,
                "MIN_VALUE"
            )
    
    def _validate_max_value(self, value: Union[int, float], max_value: Union[int, float], field: str) -> None:
        """Validate maximum numeric value"""
        if value > max_value:
            raise ValidationError(
                f"Field '{field}' must be at most {max_value}",
                field,
                "MAX_VALUE"
            )
    
    def _validate_min_items(self, value: List[Any], min_items: int, field: str) -> None:
        """Validate minimum list length"""
        if len(value) < min_items:
            raise ValidationError(
                f"Field '{field}' must have at least {min_items} items",
                field,
                "MIN_ITEMS"
            )
    
    def _validate_max_items(self, value: List[Any], max_items: int, field: str) -> None:
        """Validate maximum list length"""
        if len(value) > max_items:
            raise ValidationError(
                f"Field '{field}' must have at most {max_items} items",
                field,
                "MAX_ITEMS"
            )
    
    def _validate_unique_items(self, value: List[Any], field: str) -> None:
        """Validate unique items in list"""
        if len(value) != len(set(value)):
            raise ValidationError(
                f"Field '{field}' must contain unique items",
                field,
                "UNIQUE_ITEMS"
            )
    
    def _validate_custom(self, value: Any, custom_func: Callable, field: str) -> None:
        """Validate with custom function"""
        try:
            if not custom_func(value):
                raise ValidationError(
                    f"Field '{field}' failed custom validation",
                    field,
                    "CUSTOM_VALIDATION"
                )
        except Exception as e:
            raise ValidationError(
                f"Field '{field}' custom validation error: {str(e)}",
                field,
                "CUSTOM_VALIDATION_ERROR"
            )
    
    def _validate_choices(self, value: Any, choices: List[Any], field: str) -> None:
        """Validate value is in choices"""
        if value not in choices:
            raise ValidationError(
                f"Field '{field}' must be one of {choices}",
                field,
                "INVALID_CHOICE"
            )
    
    def get_errors(self) -> List[str]:
        """Get validation errors"""
        return self.errors
    
    def has_errors(self) -> bool:
        """Check if there are validation errors"""
        return len(self.errors) > 0
    
    def clear_errors(self) -> None:
        """Clear validation errors"""
        self.errors = []
    
    def add_error(self, error: str) -> None:
        """Add validation error"""
        self.errors.append(error)
    
    def get_errors_dict(self) -> Dict[str, List[str]]:
        """Get errors as a dictionary grouped by field"""
        errors_dict = {}
        for error in self.errors:
            if ':' in error:
                field, message = error.split(':', 1)
                field = field.strip()
                message = message.strip()
                if field not in errors_dict:
                    errors_dict[field] = []
                errors_dict[field].append(message)
            else:
                if 'general' not in errors_dict:
                    errors_dict['general'] = []
                errors_dict['general'].append(error)
        return errors_dict


class DataValidator(BaseValidator):
    """Generic data validator"""
    
    def _validate_data(self, data: Any) -> None:
        """Basic data validation"""
        if data is None:
            raise ValidationError("Data cannot be None")
        
        if isinstance(data, dict) and not data:
            raise ValidationError("Data cannot be empty")


class ModelValidator(BaseValidator):
    """Model-specific validator"""
    
    def __init__(self, model_class: type, strict: bool = False):
        super().__init__(strict)
        self.model_class = model_class
    
    def _validate_data(self, data: Any) -> None:
        """Validate model data"""
        if not isinstance(data, (dict, self.model_class)):
            raise ValidationError(f"Data must be a dict or {self.model_class.__name__} instance")
        
        # Additional model-specific validation can be added here
        pass


class CompositeValidator(BaseValidator):
    """Validator that combines multiple validators"""
    
    def __init__(self, validators: List[BaseValidator], strict: bool = False):
        super().__init__(strict)
        self.validators = validators
    
    def _validate_data(self, data: Any) -> None:
        """Validate data using all validators"""
        for validator in self.validators:
            if not validator.validate(data):
                self.errors.extend(validator.get_errors())
    
    def validate(self, data: Any, rules: Dict[str, Any] = None) -> bool:
        """Validate data using all validators"""
        self.errors = []
        
        for validator in self.validators:
            if not validator.validate(data, rules):
                self.errors.extend(validator.get_errors())
        
        return len(self.errors) == 0
