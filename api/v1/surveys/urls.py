from django.urls import path
from . import views

urlpatterns = [
    # Public endpoints - kullanıcılar için
    path('question-sets/', views.SoruSetiListView.as_view(), name='survey-question-sets'),
    path('question-sets/<int:pk>/', views.SoruSetiDetailView.as_view(), name='question-set-detail'),
    path('submit/', views.anket_cevapla, name='submit-survey'),
    
    # Kullanıcı anket geçmişi
    path('my-surveys/', views.UserAnketListView.as_view(), name='user-surveys'),
    path('my-surveys/<int:pk>/', views.user_anket_detail, name='user-survey-detail'),
    
    # Admin endpoints
    path('admin/question-sets/', views.AdminSoruSetiListView.as_view(), name='admin-question-sets'),
    path('admin/responses/', views.AdminAnketOturumListView.as_view(), name='admin-survey-responses'),
    path('admin/question-sets/<int:soru_seti_id>/stats/', views.admin_anket_istatistikleri, name='admin-survey-stats'),
]