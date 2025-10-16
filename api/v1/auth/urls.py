from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views, views_extended

urlpatterns = [
    # Genel authentication
    path('login/', views.CustomTokenObtainPairView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('password-change/', views.PasswordChangeView.as_view(), name='password_change'),
    path('verify/', views.verify_token, name='verify_token'),
    
    # Eski genel kayıt (geriye uyumluluk için)
    path('register/', views.RegisterView.as_view(), name='register'),
    
    # Ayrı kayıt formları
    path('register/danisan/', views_extended.DanisanRegisterView.as_view(), name='danisan_register'),
    path('register/diyetisyen/', views_extended.DiyetisyenRegisterView.as_view(), name='diyetisyen_register'),
    
    # Admin için diyetisyen yönetimi
    path('diyetisyen/pending/', views_extended.DiyetisyenPendingListView.as_view(), name='diyetisyen_pending'),
]