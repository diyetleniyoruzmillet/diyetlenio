from django.urls import path
from . import views

urlpatterns = [
    # Kullanıcı arama (Admin)
    path('search/', views.search_users, name='user-search'),
    
    # Profil yönetimi
    path('profile/update/', views.UserProfileUpdateView.as_view(), name='user-profile-update'),
    
    # Sağlık verileri (Danışan)
    path('health-data/', views.HealthDataListCreateView.as_view(), name='user-health-data'),
    path('health-data/<int:pk>/', views.HealthDataDetailView.as_view(), name='user-health-data-detail'),
    
    # Bildirimler
    path('notifications/', views.NotificationListView.as_view(), name='user-notifications'),
    path('notifications/<int:pk>/read/', views.mark_notification_read, name='user-notification-read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='user-notifications-mark-all-read'),
    
    # Public diyetisyen listesi
    path('dietitians/', views.PublicDiyetisyenListView.as_view(), name='user-dietitians'),
    path('specialties/', views.UzmanlikAlaniListView.as_view(), name='user-specialties'),
    
    # İstatistikler
    path('statistics/', views.user_statistics, name='user-statistics'),
]