"""
Middleware for services operations
"""

import time
import logging
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint

from wakedock.middleware.base_middleware import BaseMiddleware
from wakedock.core.logging import get_logger
from wakedock.core.exceptions import WakeDockException
from wakedock.models.stack import StackStatus, StackType

logger = get_logger(__name__)


class ServicesRequestMiddleware(BaseMiddleware):
    """Middleware for services request processing"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.request_count = 0
        self.error_count = 0
        self.start_time = datetime.now()
        
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process services requests"""
        
        # Check if this is a services-related request
        if not self._is_services_request(request):
            return await call_next(request)
        
        # Increment request counter
        self.request_count += 1
        
        # Start timing
        start_time = time.time()
        
        # Add request ID if not present
        if not hasattr(request.state, 'request_id'):
            request.state.request_id = self._generate_request_id()
        
        # Log request
        await self._log_request(request)
        
        # Add services-specific headers
        request.state.services_context = {
            'request_id': request.state.request_id,
            'timestamp': datetime.now(),
            'user_agent': request.headers.get('user-agent', ''),
            'ip_address': self._get_client_ip(request)
        }
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Add response headers
            response.headers['X-Request-ID'] = request.state.request_id
            response.headers['X-Processing-Time'] = str(processing_time)
            response.headers['X-Service-Context'] = 'services'
            
            # Log response
            await self._log_response(request, response, processing_time)
            
            return response
            
        except Exception as e:
            # Increment error counter
            self.error_count += 1
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Log error
            await self._log_error(request, e, processing_time)
            
            # Re-raise the exception
            raise
    
    def _is_services_request(self, request: Request) -> bool:
        """Check if request is services-related"""
        path = request.url.path
        return (
            path.startswith('/api/services') or
            path.startswith('/api/stacks') or
            path.startswith('/api/docker/services')
        )
    
    async def _log_request(self, request: Request):
        """Log incoming request"""
        logger.info(
            f"Services request: {request.method} {request.url.path}",
            extra={
                'request_id': request.state.request_id,
                'method': request.method,
                'path': request.url.path,
                'query_params': dict(request.query_params),
                'user_agent': request.headers.get('user-agent', ''),
                'ip_address': self._get_client_ip(request)
            }
        )
    
    async def _log_response(self, request: Request, response: Response, processing_time: float):
        """Log outgoing response"""
        logger.info(
            f"Services response: {response.status_code} in {processing_time:.4f}s",
            extra={
                'request_id': request.state.request_id,
                'status_code': response.status_code,
                'processing_time': processing_time,
                'method': request.method,
                'path': request.url.path
            }
        )
    
    async def _log_error(self, request: Request, error: Exception, processing_time: float):
        """Log error"""
        logger.error(
            f"Services error: {str(error)} in {processing_time:.4f}s",
            extra={
                'request_id': request.state.request_id,
                'error_type': type(error).__name__,
                'error_message': str(error),
                'processing_time': processing_time,
                'method': request.method,
                'path': request.url.path
            },
            exc_info=True
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get middleware statistics"""
        uptime = datetime.now() - self.start_time
        return {
            'middleware': 'ServicesRequestMiddleware',
            'uptime': str(uptime),
            'request_count': self.request_count,
            'error_count': self.error_count,
            'error_rate': self.error_count / max(self.request_count, 1) * 100,
            'start_time': self.start_time.isoformat()
        }


class ServicesAuthMiddleware(BaseMiddleware):
    """Middleware for services authentication and authorization"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.auth_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_timeout = 300  # 5 minutes
        
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Check authentication for services requests"""
        
        # Check if this is a services-related request
        if not self._is_services_request(request):
            return await call_next(request)
        
        # Check if authentication is required
        if not self._requires_auth(request):
            return await call_next(request)
        
        # Get authentication token
        token = self._get_auth_token(request)
        if not token:
            return self._create_auth_error_response("Authentication required")
        
        # Validate token
        try:
            user_info = await self._validate_token(token)
            if not user_info:
                return self._create_auth_error_response("Invalid authentication token")
            
            # Check permissions
            if not await self._check_permissions(user_info, request):
                return self._create_auth_error_response("Insufficient permissions")
            
            # Add user info to request state
            request.state.user = user_info
            
            return await call_next(request)
            
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return self._create_auth_error_response("Authentication failed")
    
    def _is_services_request(self, request: Request) -> bool:
        """Check if request is services-related"""
        path = request.url.path
        return (
            path.startswith('/api/services') or
            path.startswith('/api/stacks') or
            path.startswith('/api/docker/services')
        )
    
    def _requires_auth(self, request: Request) -> bool:
        """Check if request requires authentication"""
        # GET requests to read-only endpoints might not require auth
        if request.method == 'GET' and request.url.path.endswith('/health'):
            return False
        
        # All other services requests require authentication
        return True
    
    def _get_auth_token(self, request: Request) -> Optional[str]:
        """Extract authentication token from request"""
        # Try Authorization header first
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            return auth_header[7:]  # Remove 'Bearer ' prefix
        
        # Try query parameter
        return request.query_params.get('token')
    
    async def _validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate authentication token"""
        # Check cache first
        if token in self.auth_cache:
            cached_info = self.auth_cache[token]
            if time.time() - cached_info['timestamp'] < self.cache_timeout:
                return cached_info['user_info']
        
        # Validate token (implement your token validation logic here)
        # For now, we'll use a simple validation
        if token == 'admin-token':
            user_info = {
                'user_id': 'admin',
                'username': 'admin',
                'roles': ['admin', 'services_admin'],
                'permissions': ['services:read', 'services:write', 'services:admin']
            }
            
            # Cache the result
            self.auth_cache[token] = {
                'user_info': user_info,
                'timestamp': time.time()
            }
            
            return user_info
        
        return None
    
    async def _check_permissions(self, user_info: Dict[str, Any], request: Request) -> bool:
        """Check if user has required permissions"""
        permissions = user_info.get('permissions', [])
        
        # Admin users have all permissions
        if 'services:admin' in permissions:
            return True
        
        # Check specific permissions based on request method
        if request.method == 'GET':
            return 'services:read' in permissions
        elif request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return 'services:write' in permissions
        
        return False
    
    def _create_auth_error_response(self, message: str) -> Response:
        """Create authentication error response"""
        return Response(
            content=f'{{"error": "{message}", "code": "AUTHENTICATION_ERROR"}}',
            status_code=401,
            media_type='application/json'
        )


class ServicesRateLimitMiddleware(BaseMiddleware):
    """Middleware for services rate limiting"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.request_counts: Dict[str, Dict[str, Any]] = {}
        self.rate_limit = 100  # requests per minute
        self.window_size = 60  # 1 minute
        
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Apply rate limiting to services requests"""
        
        # Check if this is a services-related request
        if not self._is_services_request(request):
            return await call_next(request)
        
        # Get client identifier
        client_id = self._get_client_id(request)
        
        # Check rate limit
        if not await self._check_rate_limit(client_id):
            return self._create_rate_limit_error_response()
        
        # Process request
        return await call_next(request)
    
    def _is_services_request(self, request: Request) -> bool:
        """Check if request is services-related"""
        path = request.url.path
        return (
            path.startswith('/api/services') or
            path.startswith('/api/stacks') or
            path.startswith('/api/docker/services')
        )
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        # Use IP address as client ID
        return self._get_client_ip(request)
    
    async def _check_rate_limit(self, client_id: str) -> bool:
        """Check if client is within rate limit"""
        current_time = time.time()
        
        # Clean up old entries
        self._cleanup_old_entries(current_time)
        
        # Get client's request count
        if client_id not in self.request_counts:
            self.request_counts[client_id] = {
                'count': 0,
                'window_start': current_time
            }
        
        client_data = self.request_counts[client_id]
        
        # Check if we're in a new window
        if current_time - client_data['window_start'] >= self.window_size:
            client_data['count'] = 0
            client_data['window_start'] = current_time
        
        # Check rate limit
        if client_data['count'] >= self.rate_limit:
            return False
        
        # Increment count
        client_data['count'] += 1
        return True
    
    def _cleanup_old_entries(self, current_time: float):
        """Clean up old rate limit entries"""
        expired_clients = []
        
        for client_id, data in self.request_counts.items():
            if current_time - data['window_start'] > self.window_size * 2:
                expired_clients.append(client_id)
        
        for client_id in expired_clients:
            del self.request_counts[client_id]
    
    def _create_rate_limit_error_response(self) -> Response:
        """Create rate limit error response"""
        return Response(
            content='{"error": "Rate limit exceeded", "code": "RATE_LIMIT_EXCEEDED"}',
            status_code=429,
            media_type='application/json',
            headers={'Retry-After': str(self.window_size)}
        )


class ServicesMetricsMiddleware(BaseMiddleware):
    """Middleware for services metrics collection"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.metrics: Dict[str, Any] = {
            'request_count': 0,
            'error_count': 0,
            'response_times': [],
            'status_codes': {},
            'endpoints': {},
            'start_time': datetime.now()
        }
        
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Collect metrics for services requests"""
        
        # Check if this is a services-related request
        if not self._is_services_request(request):
            return await call_next(request)
        
        # Start timing
        start_time = time.time()
        
        # Increment request count
        self.metrics['request_count'] += 1
        
        # Track endpoint usage
        endpoint = f"{request.method} {request.url.path}"
        if endpoint not in self.metrics['endpoints']:
            self.metrics['endpoints'][endpoint] = {
                'count': 0,
                'avg_response_time': 0,
                'errors': 0
            }
        
        self.metrics['endpoints'][endpoint]['count'] += 1
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate response time
            response_time = time.time() - start_time
            
            # Track response time
            self.metrics['response_times'].append(response_time)
            
            # Keep only last 1000 response times
            if len(self.metrics['response_times']) > 1000:
                self.metrics['response_times'] = self.metrics['response_times'][-1000:]
            
            # Track status codes
            status_code = response.status_code
            if status_code not in self.metrics['status_codes']:
                self.metrics['status_codes'][status_code] = 0
            self.metrics['status_codes'][status_code] += 1
            
            # Update endpoint metrics
            endpoint_metrics = self.metrics['endpoints'][endpoint]
            endpoint_metrics['avg_response_time'] = (
                (endpoint_metrics['avg_response_time'] * (endpoint_metrics['count'] - 1) + response_time) /
                endpoint_metrics['count']
            )
            
            # Add metrics headers
            response.headers['X-Request-Count'] = str(self.metrics['request_count'])
            response.headers['X-Response-Time'] = f"{response_time:.4f}"
            
            return response
            
        except Exception as e:
            # Increment error count
            self.metrics['error_count'] += 1
            self.metrics['endpoints'][endpoint]['errors'] += 1
            
            # Re-raise the exception
            raise
    
    def _is_services_request(self, request: Request) -> bool:
        """Check if request is services-related"""
        path = request.url.path
        return (
            path.startswith('/api/services') or
            path.startswith('/api/stacks') or
            path.startswith('/api/docker/services')
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get collected metrics"""
        response_times = self.metrics['response_times']
        
        return {
            'request_count': self.metrics['request_count'],
            'error_count': self.metrics['error_count'],
            'error_rate': self.metrics['error_count'] / max(self.metrics['request_count'], 1) * 100,
            'avg_response_time': sum(response_times) / len(response_times) if response_times else 0,
            'min_response_time': min(response_times) if response_times else 0,
            'max_response_time': max(response_times) if response_times else 0,
            'status_codes': self.metrics['status_codes'],
            'endpoints': self.metrics['endpoints'],
            'uptime': str(datetime.now() - self.metrics['start_time']),
            'start_time': self.metrics['start_time'].isoformat()
        }


class ServicesValidationMiddleware(BaseMiddleware):
    """Middleware for services request validation"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.validation_rules = {
            'service_name': r'^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?$',
            'max_name_length': 63,
            'required_fields': ['name', 'type'],
            'valid_types': ['compose', 'dockerfile', 'image'],
            'valid_statuses': ['running', 'stopped', 'paused', 'restarting', 'dead']
        }
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Validate services requests"""
        
        # Check if this is a services-related request
        if not self._is_services_request(request):
            return await call_next(request)
        
        # Only validate POST, PUT, PATCH requests
        if request.method not in ['POST', 'PUT', 'PATCH']:
            return await call_next(request)
        
        # Validate request
        validation_result = await self._validate_request(request)
        if not validation_result['valid']:
            return self._create_validation_error_response(validation_result['errors'])
        
        # Process request
        return await call_next(request)
    
    def _is_services_request(self, request: Request) -> bool:
        """Check if request is services-related"""
        path = request.url.path
        return (
            path.startswith('/api/services') or
            path.startswith('/api/stacks') or
            path.startswith('/api/docker/services')
        )
    
    async def _validate_request(self, request: Request) -> Dict[str, Any]:
        """Validate request data"""
        errors = []
        
        try:
            # Get request body
            body = await request.body()
            if not body:
                return {'valid': True, 'errors': []}
            
            # Parse JSON
            import json
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return {'valid': False, 'errors': ['Invalid JSON format']}
            
            # Validate based on request type
            if request.method == 'POST':
                errors.extend(self._validate_creation_data(data))
            elif request.method in ['PUT', 'PATCH']:
                errors.extend(self._validate_update_data(data))
            
            return {'valid': len(errors) == 0, 'errors': errors}
            
        except Exception as e:
            logger.error(f"Request validation error: {str(e)}")
            return {'valid': False, 'errors': ['Request validation failed']}
    
    def _validate_creation_data(self, data: Dict[str, Any]) -> List[str]:
        """Validate service creation data"""
        errors = []
        
        # Check required fields
        for field in self.validation_rules['required_fields']:
            if field not in data:
                errors.append(f"Field '{field}' is required")
        
        # Validate service name
        if 'name' in data:
            errors.extend(self._validate_service_name(data['name']))
        
        # Validate service type
        if 'type' in data:
            errors.extend(self._validate_service_type(data['type']))
        
        return errors
    
    def _validate_update_data(self, data: Dict[str, Any]) -> List[str]:
        """Validate service update data"""
        errors = []
        
        # Validate service name if provided
        if 'name' in data:
            errors.extend(self._validate_service_name(data['name']))
        
        # Validate service type if provided
        if 'type' in data:
            errors.extend(self._validate_service_type(data['type']))
        
        return errors
    
    def _validate_service_name(self, name: str) -> List[str]:
        """Validate service name"""
        errors = []
        
        if not isinstance(name, str):
            errors.append("Service name must be a string")
            return errors
        
        if len(name) > self.validation_rules['max_name_length']:
            errors.append(f"Service name must be less than {self.validation_rules['max_name_length']} characters")
        
        import re
        if not re.match(self.validation_rules['service_name'], name):
            errors.append("Service name must start and end with alphanumeric characters")
        
        return errors
    
    def _validate_service_type(self, service_type: str) -> List[str]:
        """Validate service type"""
        errors = []
        
        if not isinstance(service_type, str):
            errors.append("Service type must be a string")
            return errors
        
        if service_type not in self.validation_rules['valid_types']:
            errors.append(f"Service type must be one of: {self.validation_rules['valid_types']}")
        
        return errors
    
    def _create_validation_error_response(self, errors: List[str]) -> Response:
        """Create validation error response"""
        return Response(
            content=json.dumps({
                'error': 'Validation failed',
                'code': 'VALIDATION_ERROR',
                'details': errors
            }),
            status_code=400,
            media_type='application/json'
        )
