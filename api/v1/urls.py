from django.urls import path, include

urlpatterns = [
    path('auth/', include('api.v1.auth.urls')),
    path('appointments/', include('api.v1.appointments.urls')),
    path('admin/', include('api.v1.admin.urls')),
    path('dietitians/', include('api.v1.dietitians.urls')),
    path('users/', include('api.v1.users.urls')),
    path('files/', include('api.v1.files.urls')),
    # path('analytics/', include('api.v1.analytics.urls')),  # Temporarily disabled
    path('diet-plans/', include('api.v1.diet_plans.urls')),
    path('articles/', include('api.v1.articles.urls')),
    path('reviews/', include('api.v1.reviews.urls')),
    path('surveys/', include('api.v1.surveys.urls')),
    path('support/', include('api.v1.support.urls')),
    path('webrtc/', include('api.v1.webrtc.urls')),
]