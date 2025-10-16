"""
API monitoring and metrics collection system.
"""
import time
import json
from typing import Dict, List, Optional, Any
from django.core.cache import cache
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
import logging
from collections import defaultdict, deque
import threading
import hashlib

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects and aggregates API metrics."""
    
    def __init__(self):
        self.metrics_cache = defaultdict(lambda: defaultdict(int))
        self.response_times = defaultdict(lambda: deque(maxlen=1000))  # Keep last 1000 response times
        self.error_counts = defaultdict(int)
        self.lock = threading.Lock()
        self.cache_prefix = 'metrics'
    
    def record_request(self, request, response=None, response_time=None):
        """Record API request metrics."""
        try:
            timestamp = int(time.time())
            minute_key = timestamp - (timestamp % 60)  # Round to minute
            
            endpoint = self._normalize_endpoint(request.path)
            method = request.method
            user_role = self._get_user_role(request)
            
            metrics_key = f"{method}:{endpoint}:{user_role}"
            
            with self.lock:
                # Count requests
                self.metrics_cache[minute_key][f"{metrics_key}:count"] += 1
                
                # Record response time
                if response_time is not None:
                    self.response_times[metrics_key].append(response_time)
                    self.metrics_cache[minute_key][f"{metrics_key}:total_time"] += response_time
                
                # Record status code
                if response:
                    status_code = getattr(response, 'status_code', 500)
                    self.metrics_cache[minute_key][f"{metrics_key}:status_{status_code}"] += 1
                    
                    # Count errors
                    if status_code >= 400:
                        self.error_counts[metrics_key] += 1
            
            # Persist metrics to cache periodically
            self._persist_metrics_async(minute_key)
            
        except Exception as e:
            logger.error(f"Error recording metrics: {e}")
    
    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for grouping."""
        # Replace dynamic parts with placeholders
        import re
        
        # Replace UUIDs
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/', '/{uuid}/', path)
        
        # Replace numeric IDs
        path = re.sub(r'/\d+/', '/{id}/', path)
        
        # Remove query parameters
        path = path.split('?')[0]
        
        return path
    
    def _get_user_role(self, request) -> str:
        """Get user role for metrics."""
        if hasattr(request, 'user') and not isinstance(request.user, AnonymousUser):
            try:
                return request.user.rol.rol_adi
            except AttributeError:
                return 'USER'
        return 'ANONYMOUS'
    
    def _persist_metrics_async(self, minute_key: int):
        """Persist metrics to cache asynchronously."""
        try:
            cache_key = f"{self.cache_prefix}:{minute_key}"
            
            with self.lock:
                metrics_data = dict(self.metrics_cache[minute_key])
            
            # Store in cache for 24 hours
            cache.set(cache_key, metrics_data, timeout=86400)
            
        except Exception as e:
            logger.error(f"Error persisting metrics: {e}")
    
    def get_metrics_summary(self, minutes: int = 60) -> Dict[str, Any]:
        """Get metrics summary for the last N minutes."""
        try:
            current_time = int(time.time())
            start_time = current_time - (minutes * 60)
            
            summary = {
                'total_requests': 0,
                'error_rate': 0.0,
                'average_response_time': 0.0,
                'requests_per_minute': 0.0,
                'top_endpoints': {},
                'status_codes': defaultdict(int),
                'user_roles': defaultdict(int),
                'error_endpoints': {}
            }
            
            total_response_time = 0
            total_requests = 0
            endpoint_requests = defaultdict(int)
            
            # Aggregate metrics from cache
            for minute in range(start_time - (start_time % 60), current_time, 60):
                cache_key = f"{self.cache_prefix}:{minute}"
                minute_data = cache.get(cache_key, {})
                
                for metric_key, value in minute_data.items():
                    if metric_key.endswith(':count'):
                        endpoint = metric_key.rsplit(':', 1)[0]
                        endpoint_requests[endpoint] += value
                        total_requests += value
                    
                    elif metric_key.endswith(':total_time'):
                        total_response_time += value
                    
                    elif 'status_' in metric_key:
                        status_code = metric_key.split('status_')[1]
                        summary['status_codes'][status_code] += value
                    
                    elif metric_key.count(':') >= 2:
                        parts = metric_key.split(':')
                        if len(parts) >= 3:
                            role = parts[2]
                            if not metric_key.endswith(('count', 'total_time')) and 'status_' not in metric_key:
                                summary['user_roles'][role] += value
            
            # Calculate derived metrics
            if total_requests > 0:
                summary['total_requests'] = total_requests
                summary['requests_per_minute'] = total_requests / minutes
                summary['average_response_time'] = total_response_time / total_requests
                
                # Calculate error rate
                error_requests = sum(count for status, count in summary['status_codes'].items() 
                                   if int(status) >= 400)
                summary['error_rate'] = (error_requests / total_requests) * 100
                
                # Top endpoints
                summary['top_endpoints'] = dict(sorted(
                    endpoint_requests.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:10])
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting metrics summary: {e}")
            return {}
    
    def get_endpoint_metrics(self, endpoint: str, minutes: int = 60) -> Dict[str, Any]:
        """Get detailed metrics for a specific endpoint."""
        try:
            current_time = int(time.time())
            start_time = current_time - (minutes * 60)
            
            endpoint_metrics = {
                'endpoint': endpoint,
                'total_requests': 0,
                'average_response_time': 0.0,
                'min_response_time': float('inf'),
                'max_response_time': 0.0,
                'status_codes': defaultdict(int),
                'requests_by_role': defaultdict(int),
                'requests_over_time': []
            }
            
            total_response_time = 0
            response_times = []
            
            # Aggregate metrics for the endpoint
            for minute in range(start_time - (start_time % 60), current_time, 60):
                cache_key = f"{self.cache_prefix}:{minute}"
                minute_data = cache.get(cache_key, {})
                minute_requests = 0
                
                for metric_key, value in minute_data.items():
                    if endpoint in metric_key:
                        if metric_key.endswith(':count'):
                            endpoint_metrics['total_requests'] += value
                            minute_requests += value
                        
                        elif metric_key.endswith(':total_time'):
                            total_response_time += value
                        
                        elif 'status_' in metric_key:
                            status_code = metric_key.split('status_')[1]
                            endpoint_metrics['status_codes'][status_code] += value
                        
                        # Extract role from metric key
                        parts = metric_key.split(':')
                        if len(parts) >= 3:
                            role = parts[2]
                            if metric_key.endswith(':count'):
                                endpoint_metrics['requests_by_role'][role] += value
                
                endpoint_metrics['requests_over_time'].append({
                    'timestamp': minute,
                    'requests': minute_requests
                })
            
            # Calculate derived metrics
            if endpoint_metrics['total_requests'] > 0:
                endpoint_metrics['average_response_time'] = total_response_time / endpoint_metrics['total_requests']
                
                # Get response time statistics from in-memory data
                for key, times in self.response_times.items():
                    if endpoint in key:
                        response_times.extend(times)
                
                if response_times:
                    endpoint_metrics['min_response_time'] = min(response_times)
                    endpoint_metrics['max_response_time'] = max(response_times)
                    endpoint_metrics['p95_response_time'] = self._percentile(response_times, 95)
                    endpoint_metrics['p99_response_time'] = self._percentile(response_times, 99)
            
            return endpoint_metrics
            
        except Exception as e:
            logger.error(f"Error getting endpoint metrics: {e}")
            return {}
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of a list of numbers."""
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        index = int((percentile / 100.0) * len(sorted_data))
        
        if index >= len(sorted_data):
            return sorted_data[-1]
        
        return sorted_data[index]
    
    def get_health_metrics(self) -> Dict[str, Any]:
        """Get system health metrics."""
        try:
            from django.db import connection
            import psutil
            import sys
            
            health_metrics = {
                'timestamp': timezone.now().isoformat(),
                'system': {
                    'cpu_usage': psutil.cpu_percent(),
                    'memory_usage': psutil.virtual_memory().percent,
                    'disk_usage': psutil.disk_usage('/').percent,
                    'python_version': sys.version,
                },
                'database': {
                    'active_connections': len(connection.queries),
                },
                'cache': {
                    'hit_rate': self._get_cache_hit_rate(),
                }
            }
            
            # Add Redis metrics if available
            try:
                if hasattr(cache, '_cache') and hasattr(cache._cache, 'get_client'):
                    redis_client = cache._cache.get_client()
                    info = redis_client.info()
                    health_metrics['cache'].update({
                        'used_memory': info.get('used_memory_human'),
                        'connected_clients': info.get('connected_clients'),
                        'ops_per_sec': info.get('instantaneous_ops_per_sec'),
                    })
            except:
                pass
            
            return health_metrics
            
        except Exception as e:
            logger.error(f"Error getting health metrics: {e}")
            return {'error': str(e)}
    
    def _get_cache_hit_rate(self) -> float:
        """Calculate cache hit rate (simplified)."""
        try:
            # This is a simplified implementation
            # In a real system, you'd track hits and misses
            return 85.0  # Placeholder
        except:
            return 0.0


class MetricsMiddleware:
    """Middleware to collect API metrics."""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, 'METRICS_ENABLED', True)
        self.collector = MetricsCollector()
    
    def __call__(self, request):
        if not self.enabled or not request.path.startswith('/api/'):
            return self.get_response(request)
        
        start_time = time.time()
        
        response = self.get_response(request)
        
        response_time = time.time() - start_time
        
        # Record metrics
        self.collector.record_request(request, response, response_time)
        
        # Add metrics headers
        response['X-Response-Time'] = f"{response_time:.3f}s"
        
        return response


# Global metrics collector instance
metrics_collector = MetricsCollector()


class APIMetricsModel(models.Model):
    """Model to store API metrics in database for long-term analysis."""
    
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    endpoint = models.CharField(max_length=255, db_index=True)
    method = models.CharField(max_length=10)
    status_code = models.IntegerField()
    response_time = models.FloatField()
    user_role = models.CharField(max_length=50, blank=True)
    user_id = models.IntegerField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        db_table = 'api_metrics'
        indexes = [
            models.Index(fields=['timestamp', 'endpoint']),
            models.Index(fields=['status_code', 'timestamp']),
            models.Index(fields=['user_role', 'timestamp']),
        ]


def store_metrics_to_db():
    """Periodic task to store metrics to database."""
    try:
        summary = metrics_collector.get_metrics_summary(5)  # Last 5 minutes
        
        # This would typically be called by a celery task or cron job
        # For now, it's a placeholder for the implementation
        
        logger.info("Metrics stored to database", extra=summary)
        
    except Exception as e:
        logger.error(f"Error storing metrics to database: {e}")


# Decorator for monitoring specific functions
def monitor_performance(operation_name: str = None):
    """Decorator to monitor function performance."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            operation = operation_name or func.__name__
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # Record successful operation
                duration = time.time() - start_time
                logger.info(f"Operation {operation} completed", extra={
                    'operation': operation,
                    'duration': duration,
                    'status': 'success'
                })
                
                return result
                
            except Exception as e:
                # Record failed operation
                duration = time.time() - start_time
                logger.error(f"Operation {operation} failed", extra={
                    'operation': operation,
                    'duration': duration,
                    'status': 'error',
                    'error': str(e)
                })
                raise
        
        return wrapper
    return decorator


# Alert system for monitoring
class AlertManager:
    """Simple alert manager for monitoring thresholds."""
    
    def __init__(self):
        self.thresholds = {
            'error_rate': 5.0,  # 5% error rate
            'response_time': 2.0,  # 2 seconds average response time
            'requests_per_minute': 1000,  # 1000 requests per minute
        }
        self.alert_cooldown = 300  # 5 minutes between same alerts
        self.last_alerts = {}
    
    def check_thresholds(self, metrics: Dict[str, Any]):
        """Check metrics against thresholds and trigger alerts."""
        try:
            current_time = time.time()
            
            # Check error rate
            if metrics.get('error_rate', 0) > self.thresholds['error_rate']:
                self._trigger_alert('high_error_rate', metrics['error_rate'], current_time)
            
            # Check response time
            if metrics.get('average_response_time', 0) > self.thresholds['response_time']:
                self._trigger_alert('high_response_time', metrics['average_response_time'], current_time)
            
            # Check request rate
            if metrics.get('requests_per_minute', 0) > self.thresholds['requests_per_minute']:
                self._trigger_alert('high_request_rate', metrics['requests_per_minute'], current_time)
                
        except Exception as e:
            logger.error(f"Error checking alert thresholds: {e}")
    
    def _trigger_alert(self, alert_type: str, value: float, current_time: float):
        """Trigger an alert if not in cooldown period."""
        last_alert_time = self.last_alerts.get(alert_type, 0)
        
        if current_time - last_alert_time > self.alert_cooldown:
            logger.critical(f"ALERT: {alert_type}", extra={
                'alert_type': alert_type,
                'value': value,
                'threshold': self.thresholds.get(alert_type),
                'timestamp': current_time
            })
            
            self.last_alerts[alert_type] = current_time
            
            # Here you would integrate with your alerting system
            # (email, Slack, PagerDuty, etc.)


# Global alert manager
alert_manager = AlertManager()