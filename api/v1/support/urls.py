from django.urls import path
from . import views

urlpatterns = [
    # Şikayet endpoints
    path('complaints/', views.SikayetListCreateView.as_view(), name='complaints'),
    path('complaints/<int:pk>/', views.SikayetDetailView.as_view(), name='complaint-detail'),
    
    # Promosyon kodu kontrolü
    path('promo-codes/validate/', views.promosyon_kodu_kontrol, name='validate-promo-code'),
    
    # Admin şikayet endpoints
    path('admin/complaints/', views.AdminSikayetListView.as_view(), name='admin-complaints'),
    path('admin/complaints/<int:pk>/resolve/', views.admin_sikayet_cozum, name='admin-resolve-complaint'),
    
    # Admin promosyon kodu endpoints
    path('admin/promo-codes/', views.AdminPromosyonKoduListCreateView.as_view(), name='admin-promo-codes'),
    path('admin/promo-codes/<int:pk>/', views.AdminPromosyonKoduDetailView.as_view(), name='admin-promo-code-detail'),
    path('admin/promo-codes/stats/', views.admin_promosyon_istatistikleri, name='admin-promo-stats'),
]