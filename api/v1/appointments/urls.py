from django.urls import path
from . import views

urlpatterns = [
    # Randevu endpoints
    path('', views.RandevuListCreateView.as_view(), name='randevu-list-create'),
    path('<int:pk>/', views.RandevuDetailView.as_view(), name='randevu-detail'),
    path('<int:pk>/cancel/', views.cancel_randevu, name='randevu-cancel'),
    path('<int:pk>/complete/', views.complete_randevu, name='randevu-complete'),
    
    # Müsaitlik endpoints
    path('availability/', views.availability_view, name='availability'),
    path('old-availability/', views.MusaitlikListView.as_view(), name='musaitlik-list'),  # Backward compatibility
    
    # Diyetisyen müsaitlik şablonu endpoints
    path('schedule-templates/', views.DiyetisyenMusaitlikSablonListCreateView.as_view(), name='schedule-templates-list-create'),
    path('schedule-templates/<int:pk>/', views.DiyetisyenMusaitlikSablonDetailView.as_view(), name='schedule-templates-detail'),
    
    # Diyetisyen izin endpoints
    path('leaves/', views.DiyetisyenIzinListCreateView.as_view(), name='leaves-list-create'),
    path('leaves/<int:pk>/', views.DiyetisyenIzinDetailView.as_view(), name='leaves-detail'),
    
    # Haftalık program endpoint
    path('weekly-schedule/', views.weekly_schedule_view, name='weekly-schedule'),
    
    # Online meeting endpoint
    path('<int:pk>/meeting-room/', views.create_meeting_room, name='create-meeting-room'),
]