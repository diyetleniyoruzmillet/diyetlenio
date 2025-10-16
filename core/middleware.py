"""
Custom middleware for Diyetlenio project.
"""
import time
import json
from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)


class RateLimitMiddleware(MiddlewareMixin):
    """
    Rate limiting middleware to prevent API abuse.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, 'RATE_LIMIT_ENABLED', True)
        super().__init__(get_response)
    
    def process_request(self, request):
        if not self.enabled:
            return None
        
        # Skip rate limiting for admin and static files
        if request.path.startswith('/admin/') or request.path.startswith('/static/'):
            return None
        
        # Get client IP
        client_ip = self.get_client_ip(request)
        
        # Define rate limits for different endpoints
        rate_limits = {
            '/api/v1/auth/login/': getattr(settings, 'LOGIN_RATE_LIMIT', '5/minute'),
            '/api/v1/auth/register/': '3/minute',
            '/notifications/api/': '120/hour',  # More generous for notifications
            'default': getattr(settings, 'DEFAULT_RATE_LIMIT', '200/hour')
        }
        
        # Get appropriate rate limit
        rate_limit = rate_limits.get(request.path, rate_limits['default'])
        
        # Check rate limit
        if self.is_rate_limited(client_ip, request.path, rate_limit):
            logger.warning(f"Rate limit exceeded for IP {client_ip} on {request.path}")
            return JsonResponse({
                'error': 'Rate limit exceeded. Please try again later.',
                'code': 'rate_limit_exceeded'
            }, status=429)
        
        return None
    
    def get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def is_rate_limited(self, client_ip, path, rate_limit):
        """Check if client has exceeded rate limit."""
        # Parse rate limit (e.g., "5/minute", "100/hour")
        limit, period = rate_limit.split('/')
        limit = int(limit)
        
        period_seconds = {
            'second': 1,
            'minute': 60,
            'hour': 3600,
            'day': 86400
        }.get(period, 3600)
        
        # Create cache key
        cache_key = f"rate_limit:{client_ip}:{path}:{period}"
        
        # Get current count
        current_count = cache.get(cache_key, 0)
        
        if current_count >= limit:
            return True
        
        # Increment counter
        try:
            cache.set(cache_key, current_count + 1, period_seconds)
        except Exception as e:
            logger.error(f"Failed to set rate limit cache: {e}")
        
        return False


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Add security headers to all responses.
    """
    
    def process_response(self, request, response):
        # Security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # Content Security Policy
        if not settings.DEBUG:
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https:; "
                "font-src 'self' https://cdn.jsdelivr.net; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            )
        
        return response


class APILoggingMiddleware(MiddlewareMixin):
    """
    Log all API requests and responses.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        super().__init__(get_response)
    
    def process_request(self, request):
        # Log API requests
        if request.path.startswith('/api/'):
            start_time = time.time()
            request._logging_start_time = start_time
            
            # Log request details
            logger.info(f"API Request: {request.method} {request.path} from {self.get_client_ip(request)}")
            
            # Log request body for POST/PUT/PATCH (excluding sensitive data)
            if request.method in ['POST', 'PUT', 'PATCH'] and request.content_type == 'application/json':
                try:
                    body = json.loads(request.body.decode('utf-8'))
                    # Remove sensitive fields
                    sensitive_fields = ['password', 'token', 'secret', 'key']
                    for field in sensitive_fields:
                        if field in body:
                            body[field] = '***HIDDEN***'
                    logger.debug(f"Request body: {body}")
                except (ValueError, UnicodeDecodeError):
                    pass
        
        return None
    
    def process_response(self, request, response):
        # Log API responses
        if request.path.startswith('/api/') and hasattr(request, '_logging_start_time'):
            duration = time.time() - request._logging_start_time
            logger.info(f"API Response: {response.status_code} for {request.method} {request.path} in {duration:.3f}s")
            
            # Log error responses
            if response.status_code >= 400:
                logger.warning(f"API Error {response.status_code}: {request.method} {request.path}")
        
        return response
    
    def get_client_ip(self, request):
        """Get client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class HealthCheckMiddleware(MiddlewareMixin):
    """
    Simple health check endpoint.
    """
    
    def process_request(self, request):
        if request.path == '/health/':
            from django.db import connections
            from django.core.cache import cache
            
            # Check database connectivity
            try:
                connections['default'].cursor().execute("SELECT 1")
                db_status = 'ok'
            except Exception as e:
                db_status = f'error: {str(e)}'
            
            # Check cache connectivity
            try:
                cache.set('health_check', 'ok', 60)
                cache_status = 'ok' if cache.get('health_check') == 'ok' else 'error'
            except Exception as e:
                cache_status = f'error: {str(e)}'
            
            health_data = {
                'status': 'ok' if db_status == 'ok' and cache_status == 'ok' else 'error',
                'database': db_status,
                'cache': cache_status,
                'timestamp': time.time()
            }
            
            status_code = 200 if health_data['status'] == 'ok' else 503
            return JsonResponse(health_data, status=status_code)
        
        return None