"""
Authentication middleware for FastAPI - MVC Architecture
"""

from datetime import datetime
from typing import Optional, Callable
from fastapi import Request, Response, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from wakedock.core.database import get_db_session
from wakedock.repositories.auth_repository import AuthRepository
from wakedock.models.auth import User, UserSession

import logging
logger = logging.getLogger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Authentication middleware for request/response processing"""
    
    def __init__(self, app, exclude_paths: Optional[list] = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/api/auth/login",
            "/api/auth/register",
            "/api/auth/refresh",
            "/api/auth/reset-password",
            "/api/auth/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico",
            "/health"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and response"""
        try:
            # Skip authentication for excluded paths
            if self._is_excluded_path(request.url.path):
                response = await call_next(request)
                return response
            
            # Extract and validate token
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return self._create_auth_error_response(
                    "Missing or invalid authorization header"
                )
            
            token = auth_header.split(" ")[1]
            
            # Validate token and get user
            async with get_db_session() as db:
                auth_repository = AuthRepository(db)
                user = await self._validate_token_and_get_user(auth_repository, token)
                
                if not user:
                    return self._create_auth_error_response(
                        "Invalid or expired token"
                    )
                
                # Add user to request state
                request.state.current_user = user
                request.state.token = token
                
                # Update user activity
                await self._update_user_activity(auth_repository, user)
                
                # Log request
                await self._log_request(auth_repository, user, request)
            
            # Process request
            response = await call_next(request)
            
            # Add security headers
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
            
            return response
            
        except HTTPException as e:
            return self._create_auth_error_response(e.detail, e.status_code)
        except Exception as e:
            logger.error(f"Authentication middleware error: {str(e)}")
            return self._create_auth_error_response(
                "Internal authentication error",
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _is_excluded_path(self, path: str) -> bool:
        """Check if path should be excluded from authentication"""
        for excluded_path in self.exclude_paths:
            if path.startswith(excluded_path):
                return True
        return False
    
    async def _validate_token_and_get_user(
        self, 
        auth_repository: AuthRepository, 
        token: str
    ) -> Optional[User]:
        """Validate token and return user"""
        try:
            # Verify token
            payload = await auth_repository.verify_token(token)
            if not payload:
                return None
            
            # Get user
            user = await auth_repository.get_by_id(payload['user_id'])
            if not user or not user.is_active:
                return None
            
            # Check if token is blacklisted
            if await auth_repository.is_token_blacklisted(token):
                return None
            
            return user
            
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            return None
    
    async def _update_user_activity(
        self, 
        auth_repository: AuthRepository, 
        user: User
    ) -> None:
        """Update user last activity"""
        try:
            await auth_repository.update_user_activity(user.id)
        except Exception as e:
            logger.error(f"Error updating user activity: {str(e)}")
    
    async def _log_request(
        self, 
        auth_repository: AuthRepository, 
        user: User, 
        request: Request
    ) -> None:
        """Log user request for audit"""
        try:
            await auth_repository.log_user_activity(
                user_id=user.id,
                activity_type="api_request",
                details={
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": str(request.query_params),
                    "user_agent": request.headers.get("User-Agent", ""),
                    "ip_address": self._get_client_ip(request)
                }
            )
        except Exception as e:
            logger.error(f"Error logging request: {str(e)}")
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def _create_auth_error_response(
        self, 
        message: str, 
        status_code: int = status.HTTP_401_UNAUTHORIZED
    ) -> JSONResponse:
        """Create authentication error response"""
        return JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "error": {
                    "code": "AUTHENTICATION_ERROR",
                    "message": message,
                    "timestamp": datetime.now().isoformat()
                }
            }
        )


class RoleBasedAccessMiddleware(BaseHTTPMiddleware):
    """Role-based access control middleware"""
    
    def __init__(self, app, role_permissions: Optional[dict] = None):
        super().__init__(app)
        self.role_permissions = role_permissions or {
            "/api/admin/": ["admin"],
            "/api/users/": ["admin", "manager"],
            "/api/auth/users": ["admin"],
            "/api/auth/stats": ["admin"],
            "/api/auth/roles/": ["admin"],
            "/api/auth/bulk-action": ["admin"]
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request for role-based access"""
        try:
            # Get user from request state (set by AuthenticationMiddleware)
            current_user = getattr(request.state, 'current_user', None)
            
            # Skip if no user (public endpoints)
            if not current_user:
                return await call_next(request)
            
            # Check role permissions
            required_roles = self._get_required_roles(request.url.path)
            if required_roles and not self._user_has_required_role(current_user, required_roles):
                return self._create_access_error_response(
                    "Insufficient permissions for this resource"
                )
            
            # Process request
            response = await call_next(request)
            return response
            
        except Exception as e:
            logger.error(f"Role-based access middleware error: {str(e)}")
            return self._create_access_error_response(
                "Access control error",
                status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _get_required_roles(self, path: str) -> Optional[list]:
        """Get required roles for path"""
        for pattern, roles in self.role_permissions.items():
            if path.startswith(pattern):
                return roles
        return None
    
    def _user_has_required_role(self, user: User, required_roles: list) -> bool:
        """Check if user has required role"""
        user_roles = [role.name for role in user.roles]
        return any(role in user_roles for role in required_roles)
    
    def _create_access_error_response(
        self, 
        message: str, 
        status_code: int = status.HTTP_403_FORBIDDEN
    ) -> JSONResponse:
        """Create access error response"""
        return JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "error": {
                    "code": "ACCESS_DENIED",
                    "message": message,
                    "timestamp": datetime.now().isoformat()
                }
            }
        )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Security headers middleware"""
    
    def __init__(self, app):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response"""
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = {}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply rate limiting"""
        try:
            client_ip = self._get_client_ip(request)
            current_time = datetime.now()
            
            # Clean old entries
            self._clean_old_entries(current_time)
            
            # Check rate limit
            if self._is_rate_limited(client_ip, current_time):
                return self._create_rate_limit_error_response()
            
            # Record request
            self._record_request(client_ip, current_time)
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers
            remaining = self._get_remaining_requests(client_ip, current_time)
            response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(current_time.timestamp()) + 60)
            
            return response
            
        except Exception as e:
            logger.error(f"Rate limit middleware error: {str(e)}")
            return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def _clean_old_entries(self, current_time: datetime) -> None:
        """Clean old rate limit entries"""
        cutoff_time = current_time.timestamp() - 60
        
        for ip in list(self.request_counts.keys()):
            self.request_counts[ip] = [
                timestamp for timestamp in self.request_counts[ip]
                if timestamp > cutoff_time
            ]
            
            if not self.request_counts[ip]:
                del self.request_counts[ip]
    
    def _is_rate_limited(self, client_ip: str, current_time: datetime) -> bool:
        """Check if client is rate limited"""
        if client_ip not in self.request_counts:
            return False
        
        return len(self.request_counts[client_ip]) >= self.requests_per_minute
    
    def _record_request(self, client_ip: str, current_time: datetime) -> None:
        """Record request timestamp"""
        if client_ip not in self.request_counts:
            self.request_counts[client_ip] = []
        
        self.request_counts[client_ip].append(current_time.timestamp())
    
    def _get_remaining_requests(self, client_ip: str, current_time: datetime) -> int:
        """Get remaining requests for client"""
        if client_ip not in self.request_counts:
            return self.requests_per_minute
        
        return max(0, self.requests_per_minute - len(self.request_counts[client_ip]))
    
    def _create_rate_limit_error_response(self) -> JSONResponse:
        """Create rate limit error response"""
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Please try again later.",
                    "timestamp": datetime.now().isoformat()
                }
            }
        )


# Helper functions for middleware setup
def setup_authentication_middleware(app, exclude_paths: Optional[list] = None):
    """Setup authentication middleware"""
    app.add_middleware(AuthenticationMiddleware, exclude_paths=exclude_paths)

def setup_role_based_access_middleware(app, role_permissions: Optional[dict] = None):
    """Setup role-based access middleware"""
    app.add_middleware(RoleBasedAccessMiddleware, role_permissions=role_permissions)

def setup_security_headers_middleware(app):
    """Setup security headers middleware"""
    app.add_middleware(SecurityHeadersMiddleware)

def setup_rate_limit_middleware(app, requests_per_minute: int = 60):
    """Setup rate limit middleware"""
    app.add_middleware(RateLimitMiddleware, requests_per_minute=requests_per_minute)

def setup_all_auth_middleware(
    app, 
    exclude_paths: Optional[list] = None,
    role_permissions: Optional[dict] = None,
    requests_per_minute: int = 60
):
    """Setup all authentication middleware"""
    setup_rate_limit_middleware(app, requests_per_minute)
    setup_security_headers_middleware(app)
    setup_role_based_access_middleware(app, role_permissions)
    setup_authentication_middleware(app, exclude_paths)


# FastAPI dependency for getting current user
from fastapi import Depends

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db_session)
) -> Optional[User]:
    """Get current user from JWT token - FastAPI dependency"""
    try:
        # For now, return a mock user
        # In production, this would validate the JWT token and return the user
        return User(
            id="user_123",
            email="admin@wakedock.com",
            username="admin",
            is_active=True,
            is_admin=True
        )
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        return None
