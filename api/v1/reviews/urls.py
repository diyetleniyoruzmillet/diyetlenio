from django.urls import path
from . import views

urlpatterns = [
    # Public endpoints - onaylanmış yorumlar
    path('dietitian/<int:diyetisyen_id>/', views.diyetisyen_yorumlari, name='dietitian-reviews'),
    path('dietitian/<int:diyetisyen_id>/stats/', views.diyetisyen_yorum_stats, name='dietitian-review-stats'),
    
    # Danışan endpoints
    path('my-reviews/', views.DanisanYorumListCreateView.as_view(), name='danisan-reviews'),
    path('my-reviews/<int:pk>/', views.DanisanYorumDetailView.as_view(), name='danisan-review-detail'),
    
    # Diyetisyen endpoints - aldıkları yorumlar
    path('received/', views.diyetisyen_aldigi_yorumlar, name='dietitian-received-reviews'),
    
    # Admin endpoints - yorum onay/red
    path('admin/pending/', views.AdminPendingYorumListView.as_view(), name='admin-pending-reviews'),
    path('admin/<int:pk>/approve/', views.admin_yorum_onay, name='admin-approve-review'),
]