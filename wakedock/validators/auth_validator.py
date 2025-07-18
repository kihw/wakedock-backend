"""
Authentication validators for user data validation
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from wakedock.validators.base_validator import BaseValidator, ValidationError
from wakedock.core.logging import get_logger

logger = get_logger(__name__)


class AuthValidator(BaseValidator):
    """Validator for authentication operations"""
    
    def __init__(self):
        super().__init__()
        self.validation_rules = {
            'username': {
                'min_length': 3,
                'max_length': 50,
                'pattern': r'^[a-zA-Z0-9_.-]+$',
                'forbidden': ['admin', 'root', 'system', 'null', 'undefined']
            },
            'email': {
                'pattern': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
                'max_length': 254
            },
            'password': {
                'min_length': 8,
                'max_length': 128,
                'require_uppercase': True,
                'require_lowercase': True,
                'require_digit': True,
                'require_special': True,
                'forbidden_patterns': ['password', '123456', 'qwerty']
            },
            'name': {
                'min_length': 1,
                'max_length': 100,
                'pattern': r'^[a-zA-Z\s\'-]+$'
            },
            'roles': {
                'valid_roles': ['admin', 'user', 'services_admin', 'viewer', 'operator']
            }
        }
    
    async def validate_credentials(self, username: str, password: str) -> Dict[str, Any]:
        """Validate login credentials"""
        errors = []
        
        try:
            # Validate username
            if not username:
                errors.append("Username is required")
            elif not isinstance(username, str):
                errors.append("Username must be a string")
            else:
                username_errors = self._validate_username(username, required=True)
                errors.extend(username_errors)
            
            # Validate password
            if not password:
                errors.append("Password is required")
            elif not isinstance(password, str):
                errors.append("Password must be a string")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error validating credentials: {str(e)}")
            return {
                'valid': False,
                'errors': ['Validation failed']
            }
    
    async def validate_registration(self, username: str, email: str, password: str,
                                  first_name: str = None, last_name: str = None,
                                  roles: List[str] = None) -> Dict[str, Any]:
        """Validate user registration data"""
        errors = []
        
        try:
            # Validate username
            username_errors = self._validate_username(username, required=True)
            errors.extend(username_errors)
            
            # Validate email
            email_errors = self._validate_email(email, required=True)
            errors.extend(email_errors)
            
            # Validate password
            password_errors = self._validate_password(password, required=True)
            errors.extend(password_errors)
            
            # Validate first name
            if first_name is not None:
                first_name_errors = self._validate_name(first_name, "First name")
                errors.extend(first_name_errors)
            
            # Validate last name
            if last_name is not None:
                last_name_errors = self._validate_name(last_name, "Last name")
                errors.extend(last_name_errors)
            
            # Validate roles
            if roles is not None:
                roles_errors = self._validate_roles(roles)
                errors.extend(roles_errors)
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error validating registration: {str(e)}")
            return {
                'valid': False,
                'errors': ['Validation failed']
            }
    
    async def validate_profile_update(self, user_id: str, first_name: str = None,
                                    last_name: str = None, email: str = None) -> Dict[str, Any]:
        """Validate profile update data"""
        errors = []
        
        try:
            # Validate user ID
            if not user_id:
                errors.append("User ID is required")
            elif not isinstance(user_id, str):
                errors.append("User ID must be a string")
            
            # Validate first name
            if first_name is not None:
                first_name_errors = self._validate_name(first_name, "First name")
                errors.extend(first_name_errors)
            
            # Validate last name
            if last_name is not None:
                last_name_errors = self._validate_name(last_name, "Last name")
                errors.extend(last_name_errors)
            
            # Validate email
            if email is not None:
                email_errors = self._validate_email(email, required=False)
                errors.extend(email_errors)
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error validating profile update: {str(e)}")
            return {
                'valid': False,
                'errors': ['Validation failed']
            }
    
    async def validate_password_change(self, user_id: str, current_password: str,
                                     new_password: str) -> Dict[str, Any]:
        """Validate password change data"""
        errors = []
        
        try:
            # Validate user ID
            if not user_id:
                errors.append("User ID is required")
            elif not isinstance(user_id, str):
                errors.append("User ID must be a string")
            
            # Validate current password
            if not current_password:
                errors.append("Current password is required")
            elif not isinstance(current_password, str):
                errors.append("Current password must be a string")
            
            # Validate new password
            new_password_errors = self._validate_password(new_password, required=True)
            errors.extend(new_password_errors)
            
            # Check if new password is different from current
            if current_password and new_password and current_password == new_password:
                errors.append("New password must be different from current password")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error validating password change: {str(e)}")
            return {
                'valid': False,
                'errors': ['Validation failed']
            }
    
    async def validate_role_assignment(self, user_id: str, roles: List[str]) -> Dict[str, Any]:
        """Validate role assignment"""
        errors = []
        
        try:
            # Validate user ID
            if not user_id:
                errors.append("User ID is required")
            elif not isinstance(user_id, str):
                errors.append("User ID must be a string")
            
            # Validate roles
            roles_errors = self._validate_roles(roles)
            errors.extend(roles_errors)
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error validating role assignment: {str(e)}")
            return {
                'valid': False,
                'errors': ['Validation failed']
            }
    
    def _validate_username(self, username: str, required: bool = False) -> List[str]:
        """Validate username"""
        errors = []
        rules = self.validation_rules['username']
        
        if not username:
            if required:
                errors.append("Username is required")
            return errors
        
        if not isinstance(username, str):
            errors.append("Username must be a string")
            return errors
        
        # Length validation
        if len(username) < rules['min_length']:
            errors.append(f"Username must be at least {rules['min_length']} characters")
        
        if len(username) > rules['max_length']:
            errors.append(f"Username must be no more than {rules['max_length']} characters")
        
        # Pattern validation
        if not re.match(rules['pattern'], username):
            errors.append("Username can only contain letters, numbers, dots, hyphens, and underscores")
        
        # Forbidden usernames
        if username.lower() in rules['forbidden']:
            errors.append("This username is not allowed")
        
        return errors
    
    def _validate_email(self, email: str, required: bool = False) -> List[str]:
        """Validate email address"""
        errors = []
        rules = self.validation_rules['email']
        
        if not email:
            if required:
                errors.append("Email is required")
            return errors
        
        if not isinstance(email, str):
            errors.append("Email must be a string")
            return errors
        
        # Length validation
        if len(email) > rules['max_length']:
            errors.append(f"Email must be no more than {rules['max_length']} characters")
        
        # Pattern validation
        if not re.match(rules['pattern'], email):
            errors.append("Email format is invalid")
        
        return errors
    
    def _validate_password(self, password: str, required: bool = False) -> List[str]:
        """Validate password"""
        errors = []
        rules = self.validation_rules['password']
        
        if not password:
            if required:
                errors.append("Password is required")
            return errors
        
        if not isinstance(password, str):
            errors.append("Password must be a string")
            return errors
        
        # Length validation
        if len(password) < rules['min_length']:
            errors.append(f"Password must be at least {rules['min_length']} characters")
        
        if len(password) > rules['max_length']:
            errors.append(f"Password must be no more than {rules['max_length']} characters")
        
        # Complexity validation
        if rules['require_uppercase'] and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        if rules['require_lowercase'] and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        if rules['require_digit'] and not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")
        
        if rules['require_special'] and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")
        
        # Forbidden patterns
        password_lower = password.lower()
        for pattern in rules['forbidden_patterns']:
            if pattern in password_lower:
                errors.append(f"Password cannot contain '{pattern}'")
        
        return errors
    
    def _validate_name(self, name: str, field_name: str) -> List[str]:
        """Validate name fields (first name, last name)"""
        errors = []
        rules = self.validation_rules['name']
        
        if not name:
            return errors  # Names are optional
        
        if not isinstance(name, str):
            errors.append(f"{field_name} must be a string")
            return errors
        
        # Length validation
        if len(name) < rules['min_length']:
            errors.append(f"{field_name} must be at least {rules['min_length']} character")
        
        if len(name) > rules['max_length']:
            errors.append(f"{field_name} must be no more than {rules['max_length']} characters")
        
        # Pattern validation
        if not re.match(rules['pattern'], name):
            errors.append(f"{field_name} can only contain letters, spaces, hyphens, and apostrophes")
        
        return errors
    
    def _validate_roles(self, roles: List[str]) -> List[str]:
        """Validate roles"""
        errors = []
        rules = self.validation_rules['roles']
        
        if not roles:
            return errors  # Roles are optional
        
        if not isinstance(roles, list):
            errors.append("Roles must be a list")
            return errors
        
        for role in roles:
            if not isinstance(role, str):
                errors.append("Each role must be a string")
                continue
            
            if role not in rules['valid_roles']:
                errors.append(f"Invalid role: {role}. Valid roles are: {', '.join(rules['valid_roles'])}")
        
        return errors
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """Validate authentication token format"""
        errors = []
        
        try:
            if not token:
                errors.append("Token is required")
            elif not isinstance(token, str):
                errors.append("Token must be a string")
            elif len(token) < 10:
                errors.append("Invalid token format")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error validating token: {str(e)}")
            return {
                'valid': False,
                'errors': ['Token validation failed']
            }
    
    async def validate_user_search(self, query: str = None, role: str = None,
                                 is_active: bool = None, limit: int = None,
                                 offset: int = None) -> Dict[str, Any]:
        """Validate user search parameters"""
        errors = []
        
        try:
            # Validate query
            if query is not None:
                if not isinstance(query, str):
                    errors.append("Query must be a string")
                elif len(query) > 255:
                    errors.append("Query must be no more than 255 characters")
            
            # Validate role
            if role is not None:
                if not isinstance(role, str):
                    errors.append("Role must be a string")
                elif role not in self.validation_rules['roles']['valid_roles']:
                    errors.append(f"Invalid role: {role}")
            
            # Validate is_active
            if is_active is not None and not isinstance(is_active, bool):
                errors.append("is_active must be a boolean")
            
            # Validate limit
            if limit is not None:
                if not isinstance(limit, int):
                    errors.append("Limit must be an integer")
                elif limit < 1 or limit > 1000:
                    errors.append("Limit must be between 1 and 1000")
            
            # Validate offset
            if offset is not None:
                if not isinstance(offset, int):
                    errors.append("Offset must be an integer")
                elif offset < 0:
                    errors.append("Offset must be non-negative")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error validating user search: {str(e)}")
            return {
                'valid': False,
                'errors': ['Search validation failed']
            }
    
    async def validate_bulk_action(self, user_ids: List[str], action: str) -> Dict[str, Any]:
        """Validate bulk user actions"""
        errors = []
        
        try:
            # Validate user IDs
            if not user_ids:
                errors.append("User IDs are required")
            elif not isinstance(user_ids, list):
                errors.append("User IDs must be a list")
            else:
                for user_id in user_ids:
                    if not isinstance(user_id, str):
                        errors.append("Each user ID must be a string")
                        break
                
                if len(user_ids) > 100:
                    errors.append("Cannot perform bulk action on more than 100 users at once")
            
            # Validate action
            valid_actions = ['activate', 'deactivate', 'delete', 'assign_role', 'remove_role']
            if not action:
                errors.append("Action is required")
            elif not isinstance(action, str):
                errors.append("Action must be a string")
            elif action not in valid_actions:
                errors.append(f"Invalid action: {action}. Valid actions are: {', '.join(valid_actions)}")
            
            return {
                'valid': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error validating bulk action: {str(e)}")
            return {
                'valid': False,
                'errors': ['Bulk action validation failed']
            }
