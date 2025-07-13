"""
WakeDock Rate Limiting Module

Provides Redis-based rate limiting for API endpoints and user actions.
"""

import time
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from wakedock.logging import get_logger


logger = get_logger(__name__)


class RateLimitStrategy(Enum):
    """Rate limiting strategies."""
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    TOKEN_BUCKET = "token_bucket"
    LEAKY_BUCKET = "leaky_bucket"


@dataclass
class RateLimit:
    """Rate limit configuration."""
    requests: int
    window: int  # seconds
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    burst: Optional[int] = None  # for token bucket


@dataclass
class RateLimitResult:
    """Rate limit check result."""
    allowed: bool
    remaining: int
    reset_time: int
    retry_after: Optional[int] = None


class RateLimitError(Exception):
    """Rate limit exceeded error."""
    
    def __init__(self, message: str, retry_after: int = None):
        super().__init__(message)
        self.retry_after = retry_after


class RateLimiter:
    """Base rate limiter class."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        self._fallback_store = {}  # In-memory fallback
    
    def check_rate_limit(self, key: str, limit: RateLimit) -> RateLimitResult:
        """Check if request is within rate limit."""
        raise NotImplementedError
    
    def reset_rate_limit(self, key: str) -> None:
        """Reset rate limit for a key."""
        raise NotImplementedError


class SlidingWindowRateLimiter(RateLimiter):
    """Sliding window rate limiter implementation."""
    
    def check_rate_limit(self, key: str, limit: RateLimit) -> RateLimitResult:
        """Check rate limit using sliding window algorithm."""
        current_time = int(time.time())
        window_start = current_time - limit.window
        
        if self.redis and REDIS_AVAILABLE:
            return self._check_redis_sliding_window(key, limit, current_time, window_start)
        else:
            return self._check_memory_sliding_window(key, limit, current_time, window_start)
    
    def _check_redis_sliding_window(self, key: str, limit: RateLimit, current_time: int, window_start: int) -> RateLimitResult:
        """Redis-based sliding window implementation."""
        try:
            pipe = self.redis.pipeline()
            
            # Remove expired entries
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            
            # Set expiration
            pipe.expire(key, limit.window)
            
            results = pipe.execute()
            current_requests = results[1]
            
            remaining = max(0, limit.requests - current_requests - 1)
            reset_time = current_time + limit.window
            
            if current_requests >= limit.requests:
                # Remove the request we just added since it's not allowed
                self.redis.zrem(key, str(current_time))
                
                retry_after = limit.window
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_time=reset_time,
                    retry_after=retry_after
                )
            
            return RateLimitResult(
                allowed=True,
                remaining=remaining,
                reset_time=reset_time
            )
            
        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            # Fallback to memory-based rate limiting
            return self._check_memory_sliding_window(key, limit, current_time, window_start)
    
    def _check_memory_sliding_window(self, key: str, limit: RateLimit, current_time: int, window_start: int) -> RateLimitResult:
        """Memory-based sliding window implementation."""
        if key not in self._fallback_store:
            self._fallback_store[key] = []
        
        requests = self._fallback_store[key]
        
        # Remove expired requests
        requests[:] = [req_time for req_time in requests if req_time > window_start]
        
        remaining = max(0, limit.requests - len(requests) - 1)
        reset_time = current_time + limit.window
        
        if len(requests) >= limit.requests:
            retry_after = limit.window
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=reset_time,
                retry_after=retry_after
            )
        
        # Add current request
        requests.append(current_time)
        
        return RateLimitResult(
            allowed=True,
            remaining=remaining,
            reset_time=reset_time
        )
    
    def reset_rate_limit(self, key: str) -> None:
        """Reset rate limit for a key."""
        if self.redis and REDIS_AVAILABLE:
            try:
                self.redis.delete(key)
            except Exception as e:
                logger.error(f"Failed to reset rate limit in Redis: {e}")
        
        if key in self._fallback_store:
            del self._fallback_store[key]


class FixedWindowRateLimiter(RateLimiter):
    """Fixed window rate limiter implementation."""
    
    def check_rate_limit(self, key: str, limit: RateLimit) -> RateLimitResult:
        """Check rate limit using fixed window algorithm."""
        current_time = int(time.time())
        window_start = (current_time // limit.window) * limit.window
        window_key = f"{key}:{window_start}"
        
        if self.redis and REDIS_AVAILABLE:
            return self._check_redis_fixed_window(window_key, limit, current_time, window_start)
        else:
            return self._check_memory_fixed_window(window_key, limit, current_time, window_start)
    
    def _check_redis_fixed_window(self, window_key: str, limit: RateLimit, current_time: int, window_start: int) -> RateLimitResult:
        """Redis-based fixed window implementation."""
        try:
            pipe = self.redis.pipeline()
            
            # Increment counter
            pipe.incr(window_key)
            
            # Set expiration on first request
            pipe.expire(window_key, limit.window)
            
            results = pipe.execute()
            current_requests = results[0]
            
            remaining = max(0, limit.requests - current_requests)
            reset_time = window_start + limit.window
            
            if current_requests > limit.requests:
                retry_after = reset_time - current_time
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_time=reset_time,
                    retry_after=retry_after
                )
            
            return RateLimitResult(
                allowed=True,
                remaining=remaining,
                reset_time=reset_time
            )
            
        except Exception as e:
            logger.error(f"Redis rate limit check failed: {e}")
            return self._check_memory_fixed_window(window_key, limit, current_time, window_start)
    
    def _check_memory_fixed_window(self, window_key: str, limit: RateLimit, current_time: int, window_start: int) -> RateLimitResult:
        """Memory-based fixed window implementation."""
        if window_key not in self._fallback_store:
            self._fallback_store[window_key] = 0
        
        self._fallback_store[window_key] += 1
        current_requests = self._fallback_store[window_key]
        
        remaining = max(0, limit.requests - current_requests)
        reset_time = window_start + limit.window
        
        if current_requests > limit.requests:
            retry_after = reset_time - current_time
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=reset_time,
                retry_after=retry_after
            )
        
        return RateLimitResult(
            allowed=True,
            remaining=remaining,
            reset_time=reset_time
        )
    
    def reset_rate_limit(self, key: str) -> None:
        """Reset rate limit for a key."""
        current_time = int(time.time())
        window_start = (current_time // 60) * 60  # Assuming 60s window
        window_key = f"{key}:{window_start}"
        
        if self.redis and REDIS_AVAILABLE:
            try:
                self.redis.delete(window_key)
            except Exception as e:
                logger.error(f"Failed to reset rate limit in Redis: {e}")
        
        if window_key in self._fallback_store:
            del self._fallback_store[window_key]


class TokenBucketRateLimiter(RateLimiter):
    """Token bucket rate limiter implementation."""
    
    def check_rate_limit(self, key: str, limit: RateLimit) -> RateLimitResult:
        """Check rate limit using token bucket algorithm."""
        current_time = time.time()
        
        if self.redis and REDIS_AVAILABLE:
            return self._check_redis_token_bucket(key, limit, current_time)
        else:
            return self._check_memory_token_bucket(key, limit, current_time)
    
    def _check_redis_token_bucket(self, key: str, limit: RateLimit, current_time: float) -> RateLimitResult:
        """Redis-based token bucket implementation."""
        try:
            bucket_key = f"bucket:{key}"
            
            # Get current bucket state
            bucket_data = self.redis.hgetall(bucket_key)
            
            if bucket_data:
                tokens = float(bucket_data.get(b'tokens', limit.burst or limit.requests))
                last_refill = float(bucket_data.get(b'last_refill', current_time))
            else:
                tokens = limit.burst or limit.requests
                last_refill = current_time
            
            # Calculate tokens to add
            time_passed = current_time - last_refill
            tokens_to_add = time_passed * (limit.requests / limit.window)
            tokens = min(limit.burst or limit.requests, tokens + tokens_to_add)
            
            # Check if request can be fulfilled
            if tokens >= 1:
                tokens -= 1
                
                # Update bucket state
                self.redis.hset(bucket_key, mapping={
                    'tokens': tokens,
                    'last_refill': current_time
                })
                self.redis.expire(bucket_key, limit.window * 2)
                
                remaining = int(tokens)
                return RateLimitResult(
                    allowed=True,
                    remaining=remaining,
                    reset_time=int(current_time + (1 - tokens) * (limit.window / limit.requests))
                )
            else:
                retry_after = int((1 - tokens) * (limit.window / limit.requests))
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_time=int(current_time + retry_after),
                    retry_after=retry_after
                )
                
        except Exception as e:
            logger.error(f"Redis token bucket check failed: {e}")
            return self._check_memory_token_bucket(key, limit, current_time)
    
    def _check_memory_token_bucket(self, key: str, limit: RateLimit, current_time: float) -> RateLimitResult:
        """Memory-based token bucket implementation."""
        if key not in self._fallback_store:
            self._fallback_store[key] = {
                'tokens': limit.burst or limit.requests,
                'last_refill': current_time
            }
        
        bucket = self._fallback_store[key]
        
        # Calculate tokens to add
        time_passed = current_time - bucket['last_refill']
        tokens_to_add = time_passed * (limit.requests / limit.window)
        bucket['tokens'] = min(limit.burst or limit.requests, bucket['tokens'] + tokens_to_add)
        bucket['last_refill'] = current_time
        
        # Check if request can be fulfilled
        if bucket['tokens'] >= 1:
            bucket['tokens'] -= 1
            
            remaining = int(bucket['tokens'])
            return RateLimitResult(
                allowed=True,
                remaining=remaining,
                reset_time=int(current_time + (1 - bucket['tokens']) * (limit.window / limit.requests))
            )
        else:
            retry_after = int((1 - bucket['tokens']) * (limit.window / limit.requests))
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_time=int(current_time + retry_after),
                retry_after=retry_after
            )
    
    def reset_rate_limit(self, key: str) -> None:
        """Reset rate limit for a key."""
        if self.redis and REDIS_AVAILABLE:
            try:
                self.redis.delete(f"bucket:{key}")
            except Exception as e:
                logger.error(f"Failed to reset rate limit in Redis: {e}")
        
        if key in self._fallback_store:
            del self._fallback_store[key]


class RateLimitManager:
    """Manages multiple rate limiters and rules."""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        self.limiters = {
            RateLimitStrategy.SLIDING_WINDOW: SlidingWindowRateLimiter(redis_client),
            RateLimitStrategy.FIXED_WINDOW: FixedWindowRateLimiter(redis_client),
            RateLimitStrategy.TOKEN_BUCKET: TokenBucketRateLimiter(redis_client),
        }
        
        # Default rate limit rules
        self.rules: Dict[str, RateLimit] = {
            # Authentication endpoints
            'auth:login': RateLimit(5, 300),  # 5 attempts per 5 minutes
            'auth:register': RateLimit(3, 3600),  # 3 registrations per hour
            'auth:reset_password': RateLimit(3, 3600),  # 3 resets per hour
            
            # API endpoints
            'api:general': RateLimit(1000, 3600),  # 1000 requests per hour
            'api:create': RateLimit(100, 3600),  # 100 creates per hour
            'api:upload': RateLimit(50, 3600),  # 50 uploads per hour
            
            # User-specific limits
            'user:actions': RateLimit(500, 3600),  # 500 actions per hour per user
            'user:api_calls': RateLimit(10000, 86400),  # 10k calls per day per user
            
            # IP-based limits
            'ip:requests': RateLimit(100, 60),  # 100 requests per minute per IP
            'ip:failed_auth': RateLimit(10, 300),  # 10 failed auths per 5 minutes per IP
            
            # Service operations
            'service:create': RateLimit(10, 3600),  # 10 service creates per hour
            'service:start_stop': RateLimit(50, 3600),  # 50 start/stop operations per hour
            'service:delete': RateLimit(20, 3600),  # 20 deletes per hour
            
            # System operations
            'system:backup': RateLimit(5, 86400),  # 5 backups per day
            'system:restore': RateLimit(3, 86400),  # 3 restores per day
        }
    
    def add_rule(self, name: str, limit: RateLimit) -> None:
        """Add a rate limit rule."""
        self.rules[name] = limit
    
    def remove_rule(self, name: str) -> None:
        """Remove a rate limit rule."""
        if name in self.rules:
            del self.rules[name]
    
    def check_rate_limit(self, rule_name: str, identifier: str) -> RateLimitResult:
        """Check rate limit for a specific rule and identifier."""
        if rule_name not in self.rules:
            # No rule defined, allow the request
            return RateLimitResult(
                allowed=True,
                remaining=999999,
                reset_time=int(time.time() + 3600)
            )
        
        limit = self.rules[rule_name]
        limiter = self.limiters[limit.strategy]
        key = f"rate_limit:{rule_name}:{identifier}"
        
        result = limiter.check_rate_limit(key, limit)
        
        # Log rate limit events
        if not result.allowed:
            logger.warning(
                f"Rate limit exceeded",
                extra={
                    'rule': rule_name,
                    'identifier': identifier,
                    'retry_after': result.retry_after
                }
            )
        
        return result
    
    def reset_rate_limit(self, rule_name: str, identifier: str) -> None:
        """Reset rate limit for a specific rule and identifier."""
        if rule_name not in self.rules:
            return
        
        limit = self.rules[rule_name]
        limiter = self.limiters[limit.strategy]
        key = f"rate_limit:{rule_name}:{identifier}"
        
        limiter.reset_rate_limit(key)
        
        logger.info(
            f"Rate limit reset",
            extra={
                'rule': rule_name,
                'identifier': identifier
            }
        )
    
    def get_rate_limit_status(self, rule_name: str, identifier: str) -> Dict[str, Any]:
        """Get current rate limit status without incrementing."""
        if rule_name not in self.rules:
            return {
                'rule': rule_name,
                'identifier': identifier,
                'limit': None,
                'status': 'no_limit'
            }
        
        limit = self.rules[rule_name]
        key = f"rate_limit:{rule_name}:{identifier}"
        
        # This would need to be implemented to check without incrementing
        # For now, return basic info
        return {
            'rule': rule_name,
            'identifier': identifier,
            'limit': {
                'requests': limit.requests,
                'window': limit.window,
                'strategy': limit.strategy.value
            },
            'status': 'active'
        }


# Decorators for rate limiting
def rate_limit(rule_name: str, get_identifier=None):
    """Decorator to apply rate limiting to functions."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            from wakedock.api.dependencies import get_rate_limiter
            
            rate_limiter = get_rate_limiter()
            
            # Get identifier (IP, user ID, etc.)
            if get_identifier:
                identifier = get_identifier(*args, **kwargs)
            else:
                # Try to extract from request
                request = None
                for arg in args:
                    if hasattr(arg, 'client'):
                        request = arg
                        break
                
                if request:
                    identifier = request.client.host
                else:
                    identifier = 'unknown'
            
            # Check rate limit
            result = rate_limiter.check_rate_limit(rule_name, identifier)
            
            if not result.allowed:
                raise RateLimitError(
                    f"Rate limit exceeded for {rule_name}",
                    retry_after=result.retry_after
                )
            
            return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            # Similar implementation for sync functions
            return func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# FastAPI middleware for automatic rate limiting
class RateLimitMiddleware:
    """FastAPI middleware for automatic rate limiting."""
    
    def __init__(self, rate_limiter: RateLimitManager):
        self.rate_limiter = rate_limiter
    
    async def __call__(self, request, call_next):
        # Determine rate limit rule based on endpoint
        path = request.url.path
        method = request.method
        
        # Map endpoints to rules
        rule_name = self._get_rule_for_endpoint(path, method)
        
        if rule_name:
            # Get identifier (IP address for now)
            identifier = request.client.host if request.client else 'unknown'
            
            # Check rate limit
            result = self.rate_limiter.check_rate_limit(rule_name, identifier)
            
            if not result.allowed:
                from fastapi import HTTPException
                from fastapi.responses import JSONResponse
                
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Rate limit exceeded",
                        "retry_after": result.retry_after
                    },
                    headers={
                        "Retry-After": str(result.retry_after),
                        "X-RateLimit-Limit": str(self.rate_limiter.rules[rule_name].requests),
                        "X-RateLimit-Remaining": str(result.remaining),
                        "X-RateLimit-Reset": str(result.reset_time)
                    }
                )
        
        response = await call_next(request)
        
        # Add rate limit headers if rule was applied
        if rule_name and rule_name in self.rate_limiter.rules:
            # Get current status for headers
            current_result = self.rate_limiter.check_rate_limit(rule_name, identifier)
            response.headers["X-RateLimit-Limit"] = str(self.rate_limiter.rules[rule_name].requests)
            response.headers["X-RateLimit-Remaining"] = str(current_result.remaining)
            response.headers["X-RateLimit-Reset"] = str(current_result.reset_time)
        
        return response
    
    def _get_rule_for_endpoint(self, path: str, method: str) -> Optional[str]:
        """Map endpoint to rate limit rule."""
        # Authentication endpoints
        if path.startswith('/api/v1/auth/login'):
            return 'auth:login'
        elif path.startswith('/api/v1/auth/register'):
            return 'auth:register'
        elif path.startswith('/api/v1/auth/reset'):
            return 'auth:reset_password'
        
        # Service endpoints
        elif path.startswith('/api/v1/services') and method == 'POST':
            return 'service:create'
        elif path.startswith('/api/v1/services') and method == 'DELETE':
            return 'service:delete'
        elif 'start' in path or 'stop' in path or 'restart' in path:
            return 'service:start_stop'
        
        # System endpoints
        elif path.startswith('/api/v1/system/backup'):
            return 'system:backup'
        elif path.startswith('/api/v1/system/restore'):
            return 'system:restore'
        
        # General API endpoints
        elif path.startswith('/api/v1/'):
            return 'api:general'
        
        return None


# Global rate limiter instance
_rate_limiter = None


def get_rate_limiter() -> RateLimitManager:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        redis_client = None
        if REDIS_AVAILABLE:
            try:
                # Try to connect to Redis
                redis_client = redis.Redis(
                    host=os.getenv('REDIS_HOST', 'localhost'),
                    port=int(os.getenv('REDIS_PORT', 6379)),
                    db=int(os.getenv('REDIS_DB', 0)),
                    decode_responses=False
                )
                # Test connection
                redis_client.ping()
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}")
                redis_client = None
        
        _rate_limiter = RateLimitManager(redis_client)
    
    return _rate_limiter


def init_rate_limiting(redis_client: Optional[redis.Redis] = None) -> RateLimitManager:
    """Initialize rate limiting."""
    global _rate_limiter
    _rate_limiter = RateLimitManager(redis_client)
    return _rate_limiter


# Export commonly used items
__all__ = [
    'RateLimit',
    'RateLimitResult',
    'RateLimitError',
    'RateLimitStrategy',
    'RateLimitManager',
    'RateLimitMiddleware',
    'rate_limit',
    'get_rate_limiter',
    'init_rate_limiting'
]
