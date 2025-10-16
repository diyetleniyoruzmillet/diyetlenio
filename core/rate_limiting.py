"""
Advanced rate limiting with user/role-based limits.
"""
import time
from typing import Dict, Optional, Tuple, Any
from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser
import logging
import hashlib

logger = logging.getLogger(__name__)


class RateLimitConfig:
    """Configuration for rate limiting rules."""
    
    # Default rate limits by user role
    ROLE_LIMITS = {
        'admin': {
            'default': '1000/hour',
            'login': '20/minute',
            'api_calls': '500/minute',
        },
        'diyetisyen': {
            'default': '500/hour',
            'login': '10/minute',
            'api_calls': '200/minute',
            'appointment_create': '50/hour',
        },
        'danisan': {
            'default': '200/hour',
            'login': '5/minute',
            'api_calls': '100/minute',
            'appointment_create': '20/hour',
        },
        'ANONYMOUS': {
            'default': '50/hour',
            'login': '3/minute',
            'register': '2/minute',
            'api_calls': '20/minute',
        }
    }
    
    # Endpoint-specific rate limits
    ENDPOINT_LIMITS = {
        '/api/v1/auth/login/': {
            'admin': '20/minute',
            'diyetisyen': '10/minute',
            'danisan': '5/minute',
            'ANONYMOUS': '3/minute',
        },
        '/api/v1/auth/register/': {
            'ANONYMOUS': '2/minute',
        },
        '/api/v1/appointments/': {
            'diyetisyen': '100/hour',
            'danisan': '50/hour',
        },
        '/api/v1/users/search/': {
            'admin': '200/minute',
            'diyetisyen': '50/minute',
            'danisan': '10/minute',
        }
    }
    
    # Premium user multipliers
    PREMIUM_MULTIPLIERS = {
        'PREMIUM': 2.0,
        'VIP': 5.0,
    }


class RateLimiter:
    """Advanced rate limiter with user/role support."""
    
    def __init__(self):
        self.cache_prefix = 'rate_limit'
        self.default_window = 3600  # 1 hour
    
    def _get_cache_key(self, identifier: str, endpoint: str, window: str) -> str:
        """Generate cache key for rate limiting."""
        key_parts = [self.cache_prefix, identifier, endpoint, window]
        key_string = ':'.join(key_parts)
        # Use hash to avoid key length issues
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _parse_rate_limit(self, rate_limit: str) -> Tuple[int, int]:
        """Parse rate limit string (e.g., '100/hour') into (limit, seconds)."""
        try:
            limit, period = rate_limit.split('/')
            limit = int(limit)
            
            period_seconds = {
                'second': 1,
                'minute': 60,
                'hour': 3600,
                'day': 86400
            }.get(period, 3600)
            
            return limit, period_seconds
            
        except (ValueError, KeyError):
            logger.error(f"Invalid rate limit format: {rate_limit}")
            return 100, 3600  # Default fallback
    
    def _get_user_identifier(self, request) -> str:
        """Get unique identifier for user (user ID or IP)."""
        if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
            return f"user:{request.user.id}"
        else:
            return f"ip:{self._get_client_ip(request)}"
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '')
        return ip
    
    def _get_user_role(self, request) -> str:
        """Get user role for rate limiting."""
        if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
            try:
                return request.user.rol.rol_adi
            except AttributeError:
                return 'danisan'  # Default role
        else:
            return 'ANONYMOUS'
    
    def _get_rate_limit_for_user(self, request, endpoint: str) -> str:
        """Get appropriate rate limit for user and endpoint."""
        user_role = self._get_user_role(request)
        
        # Check endpoint-specific limits first
        endpoint_limits = RateLimitConfig.ENDPOINT_LIMITS.get(endpoint, {})
        if user_role in endpoint_limits:
            return endpoint_limits[user_role]
        
        # Check role-based limits
        role_limits = RateLimitConfig.ROLE_LIMITS.get(user_role, {})
        
        # Try to find specific limit type based on endpoint
        if '/auth/login' in endpoint:
            return role_limits.get('login', role_limits.get('default', '50/hour'))
        elif '/auth/register' in endpoint:
            return role_limits.get('register', role_limits.get('default', '50/hour'))
        elif '/appointments' in endpoint and request.method == 'POST':
            return role_limits.get('appointment_create', role_limits.get('default', '50/hour'))
        elif endpoint.startswith('/api/'):
            return role_limits.get('api_calls', role_limits.get('default', '50/hour'))
        
        return role_limits.get('default', '50/hour')
    
    def _apply_premium_multiplier(self, limit: int, request) -> int:
        """Apply premium multiplier if user has premium status."""
        if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
            # Check if user has premium status (this would depend on your premium system)
            # For now, we'll check if user has a premium attribute
            premium_status = getattr(request.user, 'premium_status', None)
            
            if premium_status in RateLimitConfig.PREMIUM_MULTIPLIERS:
                multiplier = RateLimitConfig.PREMIUM_MULTIPLIERS[premium_status]
                return int(limit * multiplier)
        
        return limit
    
    def is_rate_limited(self, request, endpoint: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request should be rate limited.
        
        Returns:
            Tuple of (is_limited, info_dict)
        """
        try:
            identifier = self._get_user_identifier(request)
            rate_limit_str = self._get_rate_limit_for_user(request, endpoint)
            limit, window_seconds = self._parse_rate_limit(rate_limit_str)
            
            # Apply premium multiplier
            limit = self._apply_premium_multiplier(limit, request)
            
            # Generate cache key
            cache_key = self._get_cache_key(identifier, endpoint, f"{window_seconds}s")
            
            # Get current count
            current_count = cache.get(cache_key, 0)
            
            # Calculate reset time
            reset_time = int(time.time()) + window_seconds
            
            info = {
                'limit': limit,
                'remaining': max(0, limit - current_count - 1),
                'reset_time': reset_time,
                'retry_after': window_seconds if current_count >= limit else None
            }
            
            if current_count >= limit:
                # Rate limit exceeded
                logger.warning(
                    f"Rate limit exceeded for {identifier} on {endpoint}",
                    extra={
                        'identifier': identifier,
                        'endpoint': endpoint,
                        'current_count': current_count,
                        'limit': limit,
                        'window_seconds': window_seconds
                    }
                )
                return True, info
            
            # Increment counter
            try:
                # Use atomic increment if available
                if hasattr(cache, 'incr'):
                    try:
                        cache.incr(cache_key)
                    except ValueError:
                        # Key doesn't exist, set it
                        cache.set(cache_key, 1, window_seconds)
                else:
                    # Fallback to set
                    cache.set(cache_key, current_count + 1, window_seconds)
            except Exception as e:
                logger.error(f"Failed to update rate limit cache: {e}")
            
            return False, info
            
        except Exception as e:
            logger.error(f"Error in rate limiting check: {e}")
            # In case of error, don't rate limit
            return False, {}
    
    def get_rate_limit_status(self, request, endpoint: str) -> Dict[str, Any]:
        """Get current rate limit status for debugging."""
        identifier = self._get_user_identifier(request)
        rate_limit_str = self._get_rate_limit_for_user(request, endpoint)
        limit, window_seconds = self._parse_rate_limit(rate_limit_str)
        limit = self._apply_premium_multiplier(limit, request)
        
        cache_key = self._get_cache_key(identifier, endpoint, f"{window_seconds}s")
        current_count = cache.get(cache_key, 0)
        
        return {
            'identifier': identifier,
            'endpoint': endpoint,
            'rate_limit': rate_limit_str,
            'limit': limit,
            'current_count': current_count,
            'remaining': max(0, limit - current_count),
            'window_seconds': window_seconds,
            'cache_key': cache_key
        }


class AdvancedRateLimitMiddleware(MiddlewareMixin):
    """Advanced rate limiting middleware with user/role support."""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, 'RATE_LIMIT_ENABLED', True)
        self.rate_limiter = RateLimiter()
        super().__init__(get_response)
    
    def process_request(self, request):
        if not self.enabled:
            return None
        
        # Skip rate limiting for admin and static files
        if (request.path.startswith('/admin/') or 
            request.path.startswith('/static/') or 
            request.path.startswith('/media/')):
            return None
        
        # Skip rate limiting for health checks
        if request.path in ['/health/', '/status/']:
            return None
        
        # Check rate limit
        is_limited, info = self.rate_limiter.is_rate_limited(request, request.path)
        
        if is_limited:
            response_data = {
                'error': {
                    'message': 'Rate limit exceeded. Please try again later.',
                    'code': 'RATE_LIMIT_EXCEEDED',
                    'details': {
                        'limit': info.get('limit'),
                        'retry_after': info.get('retry_after')
                    }
                }
            }
            
            response = JsonResponse(response_data, status=429)
            
            # Add rate limit headers
            response['X-RateLimit-Limit'] = str(info.get('limit', ''))
            response['X-RateLimit-Remaining'] = str(info.get('remaining', ''))
            response['X-RateLimit-Reset'] = str(info.get('reset_time', ''))
            
            if info.get('retry_after'):
                response['Retry-After'] = str(info['retry_after'])
            
            return response
        
        # Store rate limit info in request for use in response
        request.rate_limit_info = info
        
        return None
    
    def process_response(self, request, response):
        # Add rate limit headers to successful responses
        if hasattr(request, 'rate_limit_info'):
            info = request.rate_limit_info
            response['X-RateLimit-Limit'] = str(info.get('limit', ''))
            response['X-RateLimit-Remaining'] = str(info.get('remaining', ''))
            response['X-RateLimit-Reset'] = str(info.get('reset_time', ''))
        
        return response


# Decorator for rate limiting specific views
def rate_limit(rate: str = None, per_user: bool = True, key_func=None):
    """
    Decorator for applying rate limits to specific views.
    
    Args:
        rate: Rate limit string (e.g., '10/minute')
        per_user: Whether to apply rate limit per user or globally
        key_func: Custom function to generate cache key
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            rate_limiter = RateLimiter()
            
            # Use custom rate if provided, otherwise use default logic
            if rate:
                limit, window_seconds = rate_limiter._parse_rate_limit(rate)
                identifier = rate_limiter._get_user_identifier(request) if per_user else 'global'
                
                # Use custom key function if provided
                if key_func:
                    identifier = key_func(request, *args, **kwargs)
                
                cache_key = rate_limiter._get_cache_key(identifier, request.path, f"{window_seconds}s")
                current_count = cache.get(cache_key, 0)
                
                if current_count >= limit:
                    return JsonResponse({
                        'error': {
                            'message': 'Rate limit exceeded for this action',
                            'code': 'RATE_LIMIT_EXCEEDED'
                        }
                    }, status=429)
                
                # Increment counter
                cache.set(cache_key, current_count + 1, window_seconds)
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


# Helper function to check rate limits programmatically
def check_rate_limit(request, action: str, custom_rate: str = None) -> Tuple[bool, Dict]:
    """
    Programmatically check rate limit for an action.
    
    Args:
        request: Django request object
        action: Action name for cache key
        custom_rate: Custom rate limit string
        
    Returns:
        Tuple of (is_limited, info_dict)
    """
    rate_limiter = RateLimiter()
    endpoint = f"/action/{action}"
    
    if custom_rate:
        # Override the rate limit temporarily
        identifier = rate_limiter._get_user_identifier(request)
        limit, window_seconds = rate_limiter._parse_rate_limit(custom_rate)
        cache_key = rate_limiter._get_cache_key(identifier, endpoint, f"{window_seconds}s")
        current_count = cache.get(cache_key, 0)
        
        info = {
            'limit': limit,
            'remaining': max(0, limit - current_count - 1),
            'reset_time': int(time.time()) + window_seconds
        }
        
        if current_count >= limit:
            return True, info
        
        cache.set(cache_key, current_count + 1, window_seconds)
        return False, info
    else:
        return rate_limiter.is_rate_limited(request, endpoint)