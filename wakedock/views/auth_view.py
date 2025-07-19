"""
Authentication view for API response formatting
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from wakedock.views.base_view import BaseView
from wakedock.database.models import User, Role, Permission, UserSession
from wakedock.core.logging import get_logger

logger = get_logger(__name__)


class AuthView(BaseView):
    """View for authentication responses"""
    
    def __init__(self):
        super().__init__()
    
    async def login_response(self, user: User, token: str, expires_at: datetime) -> Dict[str, Any]:
        """Format login response"""
        try:
            return await self.success_response(
                data={
                    'user': self._format_user(user),
                    'token': token,
                    'expires_at': expires_at.isoformat(),
                    'permissions': self._get_user_permissions(user)
                },
                message="Login successful"
            )
        except Exception as e:
            logger.error(f"Error formatting login response: {str(e)}")
            return await self.error_response(
                error="Failed to format login response",
                status_code=500
            )
    
    async def register_response(self, user: User) -> Dict[str, Any]:
        """Format registration response"""
        try:
            return await self.success_response(
                data={
                    'user': self._format_user(user),
                    'message': 'Registration successful'
                },
                message="User registered successfully"
            )
        except Exception as e:
            logger.error(f"Error formatting registration response: {str(e)}")
            return await self.error_response(
                error="Failed to format registration response",
                status_code=500
            )
    
    async def user_profile_response(self, user: User) -> Dict[str, Any]:
        """Format user profile response"""
        try:
            return await self.success_response(
                data={
                    'user': self._format_user_profile(user),
                    'permissions': self._get_user_permissions(user),
                    'roles': self._format_user_roles(user)
                },
                message="Profile retrieved successfully"
            )
        except Exception as e:
            logger.error(f"Error formatting profile response: {str(e)}")
            return await self.error_response(
                error="Failed to format profile response",
                status_code=500
            )
    
    async def token_refresh_response(self, token: str, expires_at: datetime) -> Dict[str, Any]:
        """Format token refresh response"""
        try:
            return await self.success_response(
                data={
                    'token': token,
                    'expires_at': expires_at.isoformat()
                },
                message="Token refreshed successfully"
            )
        except Exception as e:
            logger.error(f"Error formatting token refresh response: {str(e)}")
            return await self.error_response(
                error="Failed to format token refresh response",
                status_code=500
            )
    
    async def logout_response(self) -> Dict[str, Any]:
        """Format logout response"""
        try:
            return await self.success_response(
                data={},
                message="Logout successful"
            )
        except Exception as e:
            logger.error(f"Error formatting logout response: {str(e)}")
            return await self.error_response(
                error="Failed to format logout response",
                status_code=500
            )
    
    async def password_change_response(self) -> Dict[str, Any]:
        """Format password change response"""
        try:
            return await self.success_response(
                data={
                    'message': 'Password changed successfully',
                    'note': 'All sessions have been revoked. Please login again.'
                },
                message="Password changed successfully"
            )
        except Exception as e:
            logger.error(f"Error formatting password change response: {str(e)}")
            return await self.error_response(
                error="Failed to format password change response",
                status_code=500
            )
    
    async def profile_update_response(self, user: User) -> Dict[str, Any]:
        """Format profile update response"""
        try:
            return await self.success_response(
                data={
                    'user': self._format_user_profile(user),
                    'message': 'Profile updated successfully'
                },
                message="Profile updated successfully"
            )
        except Exception as e:
            logger.error(f"Error formatting profile update response: {str(e)}")
            return await self.error_response(
                error="Failed to format profile update response",
                status_code=500
            )
    
    async def users_list_response(self, users: List[User], total_count: int, 
                                 limit: int, offset: int) -> Dict[str, Any]:
        """Format users list response"""
        try:
            return await self.paginated_response(
                data=[self._format_user_summary(user) for user in users],
                total_count=total_count,
                limit=limit,
                offset=offset,
                message="Users retrieved successfully"
            )
        except Exception as e:
            logger.error(f"Error formatting users list response: {str(e)}")
            return await self.error_response(
                error="Failed to format users list response",
                status_code=500
            )
    
    async def user_detail_response(self, user: User) -> Dict[str, Any]:
        """Format user detail response"""
        try:
            return await self.success_response(
                data={
                    'user': self._format_user_detail(user),
                    'permissions': self._get_user_permissions(user),
                    'roles': self._format_user_roles(user),
                    'sessions': self._format_user_sessions(user)
                },
                message="User details retrieved successfully"
            )
        except Exception as e:
            logger.error(f"Error formatting user detail response: {str(e)}")
            return await self.error_response(
                error="Failed to format user detail response",
                status_code=500
            )
    
    async def password_reset_request_response(self, email: str) -> Dict[str, Any]:
        """Format password reset request response"""
        try:
            return await self.success_response(
                data={
                    'message': 'Password reset email sent',
                    'email': email
                },
                message="Password reset email sent successfully"
            )
        except Exception as e:
            logger.error(f"Error formatting password reset request response: {str(e)}")
            return await self.error_response(
                error="Failed to format password reset request response",
                status_code=500
            )
    
    async def password_reset_response(self) -> Dict[str, Any]:
        """Format password reset response"""
        try:
            return await self.success_response(
                data={
                    'message': 'Password reset successful',
                    'note': 'Please login with your new password'
                },
                message="Password reset successful"
            )
        except Exception as e:
            logger.error(f"Error formatting password reset response: {str(e)}")
            return await self.error_response(
                error="Failed to format password reset response",
                status_code=500
            )
    
    async def auth_stats_response(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Format authentication statistics response"""
        try:
            return await self.success_response(
                data={
                    'statistics': stats,
                    'generated_at': datetime.utcnow().isoformat()
                },
                message="Authentication statistics retrieved successfully"
            )
        except Exception as e:
            logger.error(f"Error formatting auth stats response: {str(e)}")
            return await self.error_response(
                error="Failed to format auth stats response",
                status_code=500
            )
    
    async def security_metrics_response(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Format security metrics response"""
        try:
            return await self.success_response(
                data={
                    'metrics': metrics,
                    'generated_at': datetime.utcnow().isoformat()
                },
                message="Security metrics retrieved successfully"
            )
        except Exception as e:
            logger.error(f"Error formatting security metrics response: {str(e)}")
            return await self.error_response(
                error="Failed to format security metrics response",
                status_code=500
            )
    
    async def bulk_user_action_response(self, action: str, user_ids: List[str], 
                                      results: Dict[str, Any]) -> Dict[str, Any]:
        """Format bulk user action response"""
        try:
            return await self.success_response(
                data={
                    'action': action,
                    'user_ids': user_ids,
                    'results': results,
                    'summary': {
                        'total': len(user_ids),
                        'successful': results.get('successful', 0),
                        'failed': results.get('failed', 0)
                    }
                },
                message=f"Bulk action '{action}' completed"
            )
        except Exception as e:
            logger.error(f"Error formatting bulk user action response: {str(e)}")
            return await self.error_response(
                error="Failed to format bulk user action response",
                status_code=500
            )
    
    async def role_assignment_response(self, user: User, roles: List[str]) -> Dict[str, Any]:
        """Format role assignment response"""
        try:
            return await self.success_response(
                data={
                    'user': self._format_user_summary(user),
                    'assigned_roles': roles,
                    'current_roles': [role.name for role in user.roles] if user.roles else []
                },
                message="Roles assigned successfully"
            )
        except Exception as e:
            logger.error(f"Error formatting role assignment response: {str(e)}")
            return await self.error_response(
                error="Failed to format role assignment response",
                status_code=500
            )
    
    async def authentication_error_response(self, error: str, code: str = "AUTH_ERROR") -> Dict[str, Any]:
        """Format authentication error response"""
        try:
            return await self.error_response(
                error=error,
                error_code=code,
                status_code=401
            )
        except Exception as e:
            logger.error(f"Error formatting authentication error response: {str(e)}")
            return await self.error_response(
                error="Authentication failed",
                status_code=401
            )
    
    async def authorization_error_response(self, error: str = "Insufficient permissions") -> Dict[str, Any]:
        """Format authorization error response"""
        try:
            return await self.error_response(
                error=error,
                error_code="INSUFFICIENT_PERMISSIONS",
                status_code=403
            )
        except Exception as e:
            logger.error(f"Error formatting authorization error response: {str(e)}")
            return await self.error_response(
                error="Access denied",
                status_code=403
            )
    
    async def validation_error_response(self, errors: List[str]) -> Dict[str, Any]:
        """Format validation error response"""
        try:
            return await self.error_response(
                error="Validation failed",
                error_code="VALIDATION_ERROR",
                details=errors,
                status_code=400
            )
        except Exception as e:
            logger.error(f"Error formatting validation error response: {str(e)}")
            return await self.error_response(
                error="Validation failed",
                status_code=400
            )
    
    # Helper methods for formatting
    def _format_user(self, user: User) -> Dict[str, Any]:
        """Format user for API response"""
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'created_at': user.created_at.isoformat() if user.created_at else None
        }
    
    def _format_user_profile(self, user: User) -> Dict[str, Any]:
        """Format user profile for API response"""
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'updated_at': user.updated_at.isoformat() if user.updated_at else None
        }
    
    def _format_user_summary(self, user: User) -> Dict[str, Any]:
        """Format user summary for list responses"""
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'roles': [role.name for role in user.roles] if user.roles else [],
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'created_at': user.created_at.isoformat() if user.created_at else None
        }
    
    def _format_user_detail(self, user: User) -> Dict[str, Any]:
        """Format detailed user information"""
        return {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_active': user.is_active,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'updated_at': user.updated_at.isoformat() if user.updated_at else None,
            'login_count': getattr(user, 'login_count', 0),
            'last_ip': getattr(user, 'last_ip', None)
        }
    
    def _format_user_roles(self, user: User) -> List[Dict[str, Any]]:
        """Format user roles"""
        if not user.roles:
            return []
        
        return [
            {
                'id': role.id,
                'name': role.name,
                'description': role.description,
                'permissions': [perm.name for perm in role.permissions] if role.permissions else []
            }
            for role in user.roles
        ]
    
    def _format_user_sessions(self, user: User) -> List[Dict[str, Any]]:
        """Format user sessions"""
        if not hasattr(user, 'sessions') or not user.sessions:
            return []
        
        return [
            {
                'id': session.id,
                'created_at': session.created_at.isoformat() if session.created_at else None,
                'expires_at': session.expires_at.isoformat() if session.expires_at else None,
                'is_active': session.is_active,
                'last_activity': session.updated_at.isoformat() if session.updated_at else None
            }
            for session in user.sessions
            if session.is_active
        ]
    
    def _get_user_permissions(self, user: User) -> List[str]:
        """Get user permissions"""
        if not user.roles:
            return []
        
        permissions = set()
        for role in user.roles:
            if role.permissions:
                for permission in role.permissions:
                    permissions.add(permission.name)
        
        return sorted(list(permissions))
    
    def _format_role(self, role: Role) -> Dict[str, Any]:
        """Format role for API response"""
        return {
            'id': role.id,
            'name': role.name,
            'description': role.description,
            'permissions': [perm.name for perm in role.permissions] if role.permissions else [],
            'created_at': role.created_at.isoformat() if role.created_at else None
        }
    
    def _format_permission(self, permission: Permission) -> Dict[str, Any]:
        """Format permission for API response"""
        return {
            'id': permission.id,
            'name': permission.name,
            'description': permission.description,
            'resource': permission.resource,
            'action': permission.action,
            'created_at': permission.created_at.isoformat() if permission.created_at else None
        }
