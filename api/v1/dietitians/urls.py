from django.urls import path
from . import views

urlpatterns = [
    # Profil yönetimi
    path('profile/', views.DiyetisyenProfileView.as_view(), name='diyetisyen-profile'),
    
    # Müsaitlik yönetimi
    path('availability/', views.MusaitlikListCreateView.as_view(), name='diyetisyen-availability'),
    path('availability/bulk/', views.bulk_create_availability, name='diyetisyen-availability-bulk'),
    path('availability/<int:pk>/', views.MusaitlikDetailView.as_view(), name='diyetisyen-availability-detail'),
    
    # Danışan yönetimi
    path('clients/', views.AssignedClientsView.as_view(), name='diyetisyen-clients'),
    
    # Not yönetimi
    path('notes/', views.DiyetisyenNotListCreateView.as_view(), name='diyetisyen-notes'),
    path('notes/<int:pk>/', views.DiyetisyenNotDetailView.as_view(), name='diyetisyen-note-detail'),
    
    # İstatistikler ve raporlar
    path('statistics/', views.diyetisyen_statistics, name='diyetisyen-statistics'),
    path('earnings/', views.earnings_report, name='diyetisyen-earnings'),
]