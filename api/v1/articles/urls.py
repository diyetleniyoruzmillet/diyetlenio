from django.urls import path
from . import views

urlpatterns = [
    # Kategori endpoints
    path('categories/', views.MakaleKategoriListView.as_view(), name='article-categories'),
    path('admin/categories/', views.AdminMakaleKategoriListCreateView.as_view(), name='admin-categories'),
    path('admin/categories/<int:pk>/', views.AdminMakaleKategoriDetailView.as_view(), name='admin-category-detail'),
    
    # Public endpoints - onaylanmış makaleler
    path('public/', views.PublicMakaleListView.as_view(), name='public-articles'),
    path('public/<int:pk>/', views.PublicMakaleDetailView.as_view(), name='public-article-detail'),
    
    # Makale yorumları
    path('public/<int:makale_id>/comments/', views.MakaleYorumListView.as_view(), name='article-comments'),
    path('public/<int:makale_id>/comments/add/', views.makale_yorum_ekle, name='add-article-comment'),
    
    # Author endpoints - yazarlar için
    path('my-articles/', views.AuthorMakaleListCreateView.as_view(), name='author-articles'),
    path('my-articles/<int:pk>/', views.AuthorMakaleDetailView.as_view(), name='author-article-detail'),
    
    # Admin endpoints - makale onay/red
    path('admin/pending/', views.AdminPendingMakaleListView.as_view(), name='admin-pending-articles'),
    path('admin/<int:pk>/approve/', views.admin_makale_onay, name='admin-approve-article'),
]