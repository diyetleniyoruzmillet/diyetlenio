"""
URLs for admin API endpoints.
"""
from django.urls import path
from . import views

app_name = 'admin'

urlpatterns = [
    path('stats/', views.admin_stats, name='admin_stats'),
    path('recent-activity/', views.recent_activity, name='recent_activity'),
    path('system-alerts/', views.system_alerts, name='system_alerts'),
    path('dietitians/<int:pk>/approve/', views.approve_diyetisyen, name='approve_dietitian'),
    path('dietitians/<int:pk>/reject/', views.reject_diyetisyen, name='reject_dietitian'),
    path('appointments/<int:pk>/', views.appointment_detail, name='appointment_detail'),
    path('appointments/<int:pk>/update/', views.update_appointment, name='update_appointment'),
    path('appointments/<int:pk>/approve/', views.approve_appointment, name='approve_appointment'),
    path('appointments/<int:pk>/cancel/', views.cancel_appointment, name='cancel_appointment'),
]