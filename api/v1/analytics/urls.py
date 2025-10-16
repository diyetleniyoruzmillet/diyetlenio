from django.urls import path
from . import views

urlpatterns = [
    # Platform genel istatistikleri
    path('platform/', views.platform_statistics, name='analytics-platform'),
    
    # Randevu analitiği
    path('appointments/trend/', views.randevu_trend, name='analytics-appointment-trend'),
    
    # Diyetisyen analitiği
    path('dietitians/performance/', views.diyetisyen_performance, name='analytics-dietitian-performance'),
    path('dietitians/cancellations/', views.cancellation_analysis, name='analytics-cancellation-analysis'),
    
    # Uzmanlık alanı analitiği
    path('specialties/', views.specialty_statistics, name='analytics-specialties'),
    
    # Müdahale raporu
    path('interventions/', views.intervention_report, name='analytics-interventions'),
]