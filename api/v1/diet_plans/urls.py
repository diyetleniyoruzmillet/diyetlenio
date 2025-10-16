from django.urls import path
from . import views

urlpatterns = [
    # Diyetisyen diet plan endpoints
    path('', views.DiyetListesiListCreateView.as_view(), name='diet-plans-list-create'),
    path('<int:pk>/', views.DiyetListesiDetailView.as_view(), name='diet-plan-detail'),
    
    # Danışan diet plan endpoints  
    path('my-plans/', views.DanisanDiyetPlanlariView.as_view(), name='danisan-diet-plans'),
    path('my-plans/<int:pk>/', views.danisan_diyet_plan_detay, name='danisan-diet-plan-detail'),
]