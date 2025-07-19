"""
Authentication controller for user management and authentication
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, status

from wakedock.controllers.base_controller import BaseController
from wakedock.repositories.auth_repository import AuthRepository
from wakedock.validators.auth_validator import AuthValidator
from wakedock.services.auth_service import AuthService
from wakedock.database.models import User
from wakedock.core.logging import get_logger
from wakedock.core.exceptions import WakeDockException

logger = get_logger(__name__)


class AuthController(BaseController[User]):
    """Controller for authentication operations"""
    
    def __init__(self, auth_repository: AuthRepository, auth_validator: AuthValidator, auth_service: AuthService):
        super().__init__(auth_repository, auth_validator)
        self.auth_service = auth_service
    
    async def authenticate(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate user and return token"""
        try:
            # Validate credentials
            validation_result = await self.validator.validate_credentials(username, password)
            if not validation_result['valid']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=validation_result['errors']
                )
            
            # Pre-authentication hook
            await self._pre_authenticate(username)
            
            # Authenticate user
            user = await self.repository.authenticate_user(username, password)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )
            
            # Generate token
            token = await self.repository.generate_token(user)
            
            # Post-authentication hook
            await self._post_authenticate(user, token)
            
            # Log successful authentication
            logger.info(f"User '{username}' authenticated successfully")
            
            return {
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'roles': [role.name for role in user.roles] if user.roles else [],
                    'permissions': [
                        permission.name 
                        for role in user.roles 
                        for permission in role.permissions
                    ] if user.roles else []
                },
                'token': token,
                'expires_at': (datetime.utcnow() + timedelta(hours=24)).isoformat()
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication error for user '{username}': {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication failed"
            )
    
    async def register(self, username: str, email: str, password: str, 
                      first_name: str = None, last_name: str = None,
                      roles: List[str] = None) -> Dict[str, Any]:
        """Register new user"""
        try:
            # Validate registration data
            validation_result = await self.validator.validate_registration(
                username, email, password, first_name, last_name, roles
            )
            if not validation_result['valid']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=validation_result['errors']
                )
            
            # Pre-registration hook
            await self._pre_register(username, email)
            
            # Create user
            user = await self.repository.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                roles=roles or ['user']  # Default role
            )
            
            # Post-registration hook
            await self._post_register(user)
            
            # Log successful registration
            logger.info(f"User '{username}' registered successfully")
            
            return {
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'roles': [role.name for role in user.roles] if user.roles else [],
                    'created_at': user.created_at.isoformat()
                },
                'message': 'User registered successfully'
            }
            
        except HTTPException:
            raise
        except WakeDockException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Registration error for user '{username}': {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed"
            )
    
    async def refresh_token(self, token: str) -> Dict[str, Any]:
        """Refresh authentication token"""
        try:
            # Verify current token
            payload = await self.repository.verify_token(token)
            if not payload:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
            
            # Get user
            user = await self.repository.get_by_id(payload['user_id'])
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or inactive"
                )
            
            # Generate new token
            new_token = await self.repository.generate_token(user)
            
            # Revoke old token
            await self.repository.revoke_session(token)
            
            logger.info(f"Token refreshed for user '{user.username}'")
            
            return {
                'token': new_token,
                'expires_at': (datetime.utcnow() + timedelta(hours=24)).isoformat()
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Token refresh error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token refresh failed"
            )
    
    async def logout(self, token: str) -> Dict[str, Any]:
        """Logout user and revoke token"""
        try:
            # Revoke token
            success = await self.repository.revoke_session(token)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid token"
                )
            
            logger.info("User logged out successfully")
            
            return {
                'message': 'Logged out successfully'
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Logout failed"
            )
    
    async def get_current_user(self, token: str) -> Dict[str, Any]:
        """Get current user information"""
        try:
            # Verify token
            payload = await self.repository.verify_token(token)
            if not payload:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
            
            # Get user
            user = await self.repository.get_by_id(payload['user_id'])
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or inactive"
                )
            
            return {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'roles': [role.name for role in user.roles] if user.roles else [],
                'permissions': [
                    permission.name 
                    for role in user.roles 
                    for permission in role.permissions
                ] if user.roles else [],
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'created_at': user.created_at.isoformat()
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Get current user error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get user information"
            )
    
    async def update_profile(self, user_id: str, first_name: str = None, 
                           last_name: str = None, email: str = None) -> Dict[str, Any]:
        """Update user profile"""
        try:
            # Validate update data
            validation_result = await self.validator.validate_profile_update(
                user_id, first_name, last_name, email
            )
            if not validation_result['valid']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=validation_result['errors']
                )
            
            # Get user
            user = await self.repository.get_by_id(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Update user
            update_data = {}
            if first_name is not None:
                update_data['first_name'] = first_name
            if last_name is not None:
                update_data['last_name'] = last_name
            if email is not None:
                update_data['email'] = email
            
            if update_data:
                user = await self.repository.update(user_id, update_data)
            
            logger.info(f"Profile updated for user '{user.username}'")
            
            return {
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'updated_at': user.updated_at.isoformat()
                },
                'message': 'Profile updated successfully'
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Profile update error for user '{user_id}': {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Profile update failed"
            )
    
    async def change_password(self, user_id: str, current_password: str, 
                            new_password: str) -> Dict[str, Any]:
        """Change user password"""
        try:
            # Validate password change
            validation_result = await self.validator.validate_password_change(
                user_id, current_password, new_password
            )
            if not validation_result['valid']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=validation_result['errors']
                )
            
            # Get user
            user = await self.repository.get_by_id(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Verify current password
            if not self.repository._verify_password(current_password, user.password_hash):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is incorrect"
                )
            
            # Update password
            success = await self.repository.update_password(user_id, new_password)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Password update failed"
                )
            
            # Revoke all sessions to force re-authentication
            await self.repository.revoke_all_user_sessions(user_id)
            
            logger.info(f"Password changed for user '{user.username}'")
            
            return {
                'message': 'Password changed successfully',
                'note': 'All sessions have been revoked. Please login again.'
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Password change error for user '{user_id}': {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password change failed"
            )
    
    async def get_users(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get users list (admin only)"""
        try:
            users = await self.repository.get_active_users(limit, offset)
            total_count = await self.repository.count()
            
            return {
                'users': [
                    {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'is_active': user.is_active,
                        'roles': [role.name for role in user.roles] if user.roles else [],
                        'last_login': user.last_login.isoformat() if user.last_login else None,
                        'created_at': user.created_at.isoformat()
                    }
                    for user in users
                ],
                'total_count': total_count,
                'limit': limit,
                'offset': offset
            }
            
        except Exception as e:
            logger.error(f"Get users error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get users"
            )
    
    async def get_auth_stats(self) -> Dict[str, Any]:
        """Get authentication statistics"""
        try:
            stats = await self.repository.get_auth_stats()
            return stats
            
        except Exception as e:
            logger.error(f"Get auth stats error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get authentication statistics"
            )
    
    # Pre/Post hooks
    async def _pre_authenticate(self, username: str):
        """Pre-authentication hook"""
        logger.debug(f"Pre-authentication hook for user '{username}'")
    
    async def _post_authenticate(self, user: User, token: str):
        """Post-authentication hook"""
        logger.debug(f"Post-authentication hook for user '{user.username}'")
    
    async def _pre_register(self, username: str, email: str):
        """Pre-registration hook"""
        logger.debug(f"Pre-registration hook for user '{username}'")
    
    async def _post_register(self, user: User):
        """Post-registration hook"""
        logger.debug(f"Post-registration hook for user '{user.username}'")
