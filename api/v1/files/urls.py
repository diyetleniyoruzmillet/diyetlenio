from django.urls import path
from . import views

urlpatterns = [
    # Dosya CRUD
    path('', views.DosyaListCreateView.as_view(), name='file-list-create'),
    path('<int:pk>/', views.DosyaDetailView.as_view(), name='file-detail'),
    
    # Dosya işlemleri
    path('<int:pk>/download/', views.download_file, name='file-download'),
    path('my-files/', views.my_files, name='my-files'),
    path('search/', views.search_files, name='file-search'),
]