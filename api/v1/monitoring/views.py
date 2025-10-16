"""
API endpoints for monitoring and metrics.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from drf_spectacular.utils import extend_schema

from core.services.auth_service import AuthService
from core.monitoring import metrics_collector, alert_manager
from core.rate_limiting import check_rate_limit


@extend_schema(
    summary="API Metrics Summary",
    description="Get API metrics summary for the last specified minutes (Admin only)",
    parameters=[
        {
            'name': 'minutes',
            'in': 'query',
            'description': 'Number of minutes to include in summary (default: 60)',
            'required': False,
            'schema': {'type': 'integer', 'minimum': 1, 'maximum': 1440}
        }
    ]
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@method_decorator(cache_page(60))  # Cache for 1 minute
def metrics_summary(request):
    """Get API metrics summary."""
    if not AuthService.is_admin(request.user):
        return Response({
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Check rate limit
    is_limited, _ = check_rate_limit(request, 'metrics_summary', '10/minute')
    if is_limited:
        return Response({
            'error': 'Rate limit exceeded'
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
    
    try:
        minutes = int(request.query_params.get('minutes', 60))
        minutes = max(1, min(1440, minutes))  # Clamp between 1 and 1440 (24 hours)
        
        summary = metrics_collector.get_metrics_summary(minutes)
        
        return Response({
            'success': True,
            'data': {
                'period_minutes': minutes,
                'metrics': summary
            }
        })
        
    except Exception as e:
        return Response({
            'error': f'Error getting metrics: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    summary="Endpoint Metrics",
    description="Get detailed metrics for a specific endpoint (Admin only)",
    parameters=[
        {
            'name': 'endpoint',
            'in': 'query',
            'description': 'Endpoint path to get metrics for',
            'required': True,
            'schema': {'type': 'string'}
        },
        {
            'name': 'minutes',
            'in': 'query',
            'description': 'Number of minutes to include (default: 60)',
            'required': False,
            'schema': {'type': 'integer', 'minimum': 1, 'maximum': 1440}
        }
    ]
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def endpoint_metrics(request):
    """Get metrics for a specific endpoint."""
    if not AuthService.is_admin(request.user):
        return Response({
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    endpoint = request.query_params.get('endpoint')
    if not endpoint:
        return Response({
            'error': 'Endpoint parameter is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        minutes = int(request.query_params.get('minutes', 60))
        minutes = max(1, min(1440, minutes))
        
        endpoint_data = metrics_collector.get_endpoint_metrics(endpoint, minutes)
        
        return Response({
            'success': True,
            'data': {
                'period_minutes': minutes,
                'endpoint_metrics': endpoint_data
            }
        })
        
    except Exception as e:
        return Response({
            'error': f'Error getting endpoint metrics: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    summary="System Health Metrics",
    description="Get system health and performance metrics (Admin only)"
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
@method_decorator(cache_page(30))  # Cache for 30 seconds
def health_metrics(request):
    """Get system health metrics."""
    if not AuthService.is_admin(request.user):
        return Response({
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        health_data = metrics_collector.get_health_metrics()
        
        return Response({
            'success': True,
            'data': health_data
        })
        
    except Exception as e:
        return Response({
            'error': f'Error getting health metrics: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    summary="API Status Check",
    description="Simple API status check endpoint (public)"
)
@api_view(['GET'])
def api_status(request):
    """Simple API status check."""
    try:
        from django.db import connection
        from django.core.cache import cache
        
        # Check database
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_status = "ok"
        
        # Check cache
        test_key = "health_check_test"
        cache.set(test_key, "ok", 60)
        cache_status = "ok" if cache.get(test_key) == "ok" else "error"
        
        # Get basic metrics
        summary = metrics_collector.get_metrics_summary(5)  # Last 5 minutes
        
        response_data = {
            'status': 'ok',
            'timestamp': request.META.get('HTTP_X_REQUEST_TIMESTAMP'),
            'services': {
                'database': db_status,
                'cache': cache_status,
                'api': 'ok'
            },
            'metrics': {
                'requests_last_5min': summary.get('total_requests', 0),
                'error_rate_last_5min': summary.get('error_rate', 0.0),
                'avg_response_time': summary.get('average_response_time', 0.0)
            }
        }
        
        return Response(response_data)
        
    except Exception as e:
        return Response({
            'status': 'error',
            'error': str(e),
            'services': {
                'database': 'error',
                'cache': 'error',
                'api': 'error'
            }
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)


@extend_schema(
    summary="Trigger Alert Check",
    description="Manually trigger alert threshold checks (Admin only)"
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_alert_check(request):
    """Manually trigger alert threshold checks."""
    if not AuthService.is_admin(request.user):
        return Response({
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # Get current metrics
        metrics = metrics_collector.get_metrics_summary(5)  # Last 5 minutes
        
        # Check thresholds
        alert_manager.check_thresholds(metrics)
        
        return Response({
            'success': True,
            'message': 'Alert check triggered',
            'data': {
                'checked_metrics': metrics,
                'thresholds': alert_manager.thresholds
            }
        })
        
    except Exception as e:
        return Response({
            'error': f'Error triggering alert check: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@extend_schema(
    summary="Metrics Export",
    description="Export metrics data in various formats (Admin only)",
    parameters=[
        {
            'name': 'format',
            'in': 'query',
            'description': 'Export format (json, csv)',
            'required': False,
            'schema': {'type': 'string', 'enum': ['json', 'csv']}
        },
        {
            'name': 'period',
            'in': 'query',
            'description': 'Time period in minutes',
            'required': False,
            'schema': {'type': 'integer', 'minimum': 1, 'maximum': 10080}
        }
    ]
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_metrics(request):
    """Export metrics data."""
    if not AuthService.is_admin(request.user):
        return Response({
            'error': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    export_format = request.query_params.get('format', 'json').lower()
    period = int(request.query_params.get('period', 60))
    
    if export_format not in ['json', 'csv']:
        return Response({
            'error': 'Invalid format. Supported formats: json, csv'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        metrics = metrics_collector.get_metrics_summary(period)
        
        if export_format == 'json':
            return Response({
                'success': True,
                'format': 'json',
                'period_minutes': period,
                'data': metrics
            })
        
        elif export_format == 'csv':
            # Convert metrics to CSV format
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write headers
            writer.writerow(['Metric', 'Value'])
            
            # Write basic metrics
            writer.writerow(['Total Requests', metrics.get('total_requests', 0)])
            writer.writerow(['Error Rate (%)', metrics.get('error_rate', 0.0)])
            writer.writerow(['Avg Response Time (s)', metrics.get('average_response_time', 0.0)])
            writer.writerow(['Requests Per Minute', metrics.get('requests_per_minute', 0.0)])
            
            # Write status codes
            for status_code, count in metrics.get('status_codes', {}).items():
                writer.writerow([f'Status {status_code}', count])
            
            # Write top endpoints
            for endpoint, count in metrics.get('top_endpoints', {}).items():
                writer.writerow([f'Endpoint: {endpoint}', count])
            
            csv_content = output.getvalue()
            output.close()
            
            from django.http import HttpResponse
            response = HttpResponse(csv_content, content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="metrics_{period}min.csv"'
            return response
        
    except Exception as e:
        return Response({
            'error': f'Error exporting metrics: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)