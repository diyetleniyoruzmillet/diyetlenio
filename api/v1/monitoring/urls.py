"""
URLs for monitoring API endpoints.
"""
from django.urls import path
from . import views

app_name = 'monitoring'

urlpatterns = [
    path('metrics/summary/', views.metrics_summary, name='metrics_summary'),
    path('metrics/endpoint/', views.endpoint_metrics, name='endpoint_metrics'),
    path('metrics/health/', views.health_metrics, name='health_metrics'),
    path('metrics/export/', views.export_metrics, name='export_metrics'),
    path('status/', views.api_status, name='api_status'),
    path('alerts/check/', views.trigger_alert_check, name='trigger_alert_check'),
]