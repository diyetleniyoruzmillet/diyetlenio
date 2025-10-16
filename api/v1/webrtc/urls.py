"""
WebRTC API URLs
"""
from django.urls import path
from . import views

app_name = 'webrtc'

urlpatterns = [
    # Call management
    path('call/initiate/', views.initiate_call, name='initiate_call'),
    path('call/<str:call_id>/join/', views.join_call, name='join_call'),
    path('call/<str:call_id>/end/', views.end_call, name='end_call'),
    path('call/<str:call_id>/status/', views.get_call_status, name='get_call_status'),
    
    # WebRTC signaling
    path('call/<str:call_id>/offer/', views.send_offer, name='send_offer'),
    path('call/<str:call_id>/answer/', views.send_answer, name='send_answer'),
    path('call/<str:call_id>/ice-candidate/', views.send_ice_candidate, name='send_ice_candidate'),
    path('call/<str:call_id>/signal/', views.webrtc_signaling, name='webrtc_signaling'),
    
    # Special call types
    path('emergency/', views.emergency_call, name='emergency_call'),
    
    # Configuration
    path('config/', views.get_webrtc_config, name='get_webrtc_config'),
]