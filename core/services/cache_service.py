"""
Cache service for managing application cache operations.
"""
import json
from typing import Any, Optional, List, Dict
from django.core.cache import cache
from django.conf import settings
from django.db.models import QuerySet
from django.core.serializers import serialize
import logging

from .base_service import BaseService, ServiceResult

logger = logging.getLogger(__name__)


class CacheService(BaseService):
    """Service for cache-related operations."""
    
    def __init__(self):
        super().__init__()
        self.default_timeout = getattr(settings, 'CACHE_DEFAULT_TIMEOUT', 600)  # 10 minutes
        self.prefix = 'diyetlenio'
    
    def _make_key(self, key: str) -> str:
        """Create prefixed cache key."""
        return f"{self.prefix}:{key}"
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        try:
            cache_key = self._make_key(key)
            value = cache.get(cache_key, default)
            
            if value is not None:
                self.log_operation("Cache hit", key=key)
            else:
                self.log_operation("Cache miss", key=key)
            
            return value
            
        except Exception as e:
            self.log_error("Cache get", e, key=key)
            return default
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None) -> bool:
        """Set value in cache."""
        try:
            cache_key = self._make_key(key)
            cache_timeout = timeout or self.default_timeout
            
            success = cache.set(cache_key, value, cache_timeout)
            
            if success:
                self.log_operation("Cache set", key=key, timeout=cache_timeout)
            else:
                self.log_error("Cache set failed", Exception("Set operation failed"), key=key)
            
            return success
            
        except Exception as e:
            self.log_error("Cache set", e, key=key)
            return False
    
    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            cache_key = self._make_key(key)
            success = cache.delete(cache_key)
            
            self.log_operation("Cache delete", key=key, success=success)
            return success
            
        except Exception as e:
            self.log_error("Cache delete", e, key=key)
            return False
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values from cache."""
        try:
            cache_keys = {self._make_key(key): key for key in keys}
            cached_values = cache.get_many(list(cache_keys.keys()))
            
            # Convert back to original keys
            result = {}
            for cache_key, value in cached_values.items():
                original_key = cache_keys[cache_key]
                result[original_key] = value
            
            hits = len(result)
            misses = len(keys) - hits
            self.log_operation("Cache get_many", keys_requested=len(keys), hits=hits, misses=misses)
            
            return result
            
        except Exception as e:
            self.log_error("Cache get_many", e, keys=keys)
            return {}
    
    def set_many(self, data: Dict[str, Any], timeout: Optional[int] = None) -> bool:
        """Set multiple values in cache."""
        try:
            cache_data = {self._make_key(key): value for key, value in data.items()}
            cache_timeout = timeout or self.default_timeout
            
            cache.set_many(cache_data, cache_timeout)
            
            self.log_operation("Cache set_many", keys_count=len(data), timeout=cache_timeout)
            return True
            
        except Exception as e:
            self.log_error("Cache set_many", e, keys_count=len(data))
            return False
    
    def get_or_set(self, key: str, callable_func, timeout: Optional[int] = None) -> Any:
        """Get value from cache or set it using callable."""
        try:
            cache_key = self._make_key(key)
            cache_timeout = timeout or self.default_timeout
            
            value = cache.get(cache_key)
            
            if value is None:
                value = callable_func()
                cache.set(cache_key, value, cache_timeout)
                self.log_operation("Cache get_or_set (set)", key=key)
            else:
                self.log_operation("Cache get_or_set (hit)", key=key)
            
            return value
            
        except Exception as e:
            self.log_error("Cache get_or_set", e, key=key)
            # If cache fails, still try to get the value
            try:
                return callable_func()
            except Exception as inner_e:
                self.log_error("Cache get_or_set fallback", inner_e, key=key)
                raise inner_e
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate cache keys matching a pattern."""
        try:
            # Note: This requires Redis backend for pattern matching
            # For other backends, this might need to be implemented differently
            from django.core.cache.backends.redis import RedisCache
            
            if isinstance(cache, RedisCache):
                cache_pattern = self._make_key(pattern)
                keys = cache._cache.get_client().keys(cache_pattern)
                if keys:
                    deleted = cache._cache.get_client().delete(*keys)
                    self.log_operation("Cache invalidate_pattern", pattern=pattern, deleted=deleted)
                    return deleted
            
            self.log_operation("Cache invalidate_pattern (unsupported backend)", pattern=pattern)
            return 0
            
        except Exception as e:
            self.log_error("Cache invalidate_pattern", e, pattern=pattern)
            return 0
    
    # Specific cache methods for common use cases
    
    def cache_user_data(self, user_id: int, data: Dict, timeout: Optional[int] = None) -> bool:
        """Cache user-specific data."""
        key = f"user:{user_id}:data"
        return self.set(key, data, timeout)
    
    def get_user_data(self, user_id: int) -> Optional[Dict]:
        """Get cached user data."""
        key = f"user:{user_id}:data"
        return self.get(key)
    
    def cache_dietitian_availability(self, dietitian_id: int, availability_data: Dict, timeout: Optional[int] = None) -> bool:
        """Cache dietitian availability data."""
        key = f"dietitian:{dietitian_id}:availability"
        return self.set(key, availability_data, timeout or 3600)  # 1 hour default
    
    def get_dietitian_availability(self, dietitian_id: int) -> Optional[Dict]:
        """Get cached dietitian availability."""
        key = f"dietitian:{dietitian_id}:availability"
        return self.get(key)
    
    def cache_appointment_stats(self, user_id: int, stats: Dict, timeout: Optional[int] = None) -> bool:
        """Cache appointment statistics."""
        key = f"user:{user_id}:appointment_stats"
        return self.set(key, stats, timeout or 1800)  # 30 minutes default
    
    def get_appointment_stats(self, user_id: int) -> Optional[Dict]:
        """Get cached appointment statistics."""
        key = f"user:{user_id}:appointment_stats"
        return self.get(key)
    
    def cache_queryset(self, key: str, queryset: QuerySet, timeout: Optional[int] = None) -> bool:
        """Cache Django queryset results."""
        try:
            # Serialize queryset to JSON
            serialized_data = serialize('json', queryset)
            return self.set(key, serialized_data, timeout)
        except Exception as e:
            self.log_error("Cache queryset", e, key=key)
            return False
    
    def invalidate_user_cache(self, user_id: int) -> None:
        """Invalidate all cache entries for a user."""
        patterns = [
            f"user:{user_id}:*",
            f"dietitian:{user_id}:*"
        ]
        
        for pattern in patterns:
            self.invalidate_pattern(pattern)
    
    def warm_up_cache(self) -> ServiceResult:
        """Warm up commonly accessed cache entries."""
        try:
            # This method should be called periodically to pre-populate cache
            # with frequently accessed data
            
            # Example: Pre-cache active dietitians
            from core.models import Diyetisyen
            active_dietitians = Diyetisyen.objects.filter(
                kullanici__aktif_mi=True
            ).select_related('kullanici').prefetch_related('uzmanlik_alanlari')
            
            self.cache_queryset('active_dietitians', active_dietitians, 1800)
            
            self.log_operation("Cache warm up completed")
            return ServiceResult.success_result()
            
        except Exception as e:
            self.log_error("Cache warm up", e)
            return ServiceResult.error_result("Cache warm up failed")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics and health info."""
        try:
            # This is implementation-specific and might not work with all cache backends
            stats = {
                'backend': cache.__class__.__name__,
                'default_timeout': self.default_timeout,
                'prefix': self.prefix,
            }
            
            # Try to get Redis-specific stats if available
            try:
                if hasattr(cache, '_cache') and hasattr(cache._cache, 'get_client'):
                    redis_client = cache._cache.get_client()
                    info = redis_client.info()
                    stats.update({
                        'used_memory': info.get('used_memory_human'),
                        'connected_clients': info.get('connected_clients'),
                        'total_commands_processed': info.get('total_commands_processed'),
                    })
            except:
                pass
            
            return stats
            
        except Exception as e:
            self.log_error("Get cache stats", e)
            return {'error': 'Could not retrieve cache stats'}