from django.urls import path
from . import views, views_webrtc

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('api/stats/', views.api_stats, name='api_stats'),
    
    # Authentication
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('register/client/', views.register_view, name='register_client'),
    path('register/dietitian/', views.register_dietitian_view, name='register_dietitian'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/change-password/', views.change_password, name='change_password'),
    
    # Password Reset
    path('password-reset/', views.password_reset_view, name='password_reset'),
    path('password-reset/confirm/<uidb64>/<token>/', views.password_reset_confirm_view, name='password_reset_confirm'),
    
    # Approval system
    path('approval/pending/', views.approval_pending, name='approval_pending'),
    path('approval/rejected/', views.approval_rejected, name='approval_rejected'),
    
    # Notifications
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/api/', views.notifications_api, name='notifications_api'),
    path('notifications/mark-read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/redirect/<int:notification_id>/', views.notification_redirect, name='notification_redirect'),
    
    # Appointments
    path('appointments/', views.appointments_list, name='appointments_list'),
    path('appointment/create/<int:diyetisyen_id>/', views.appointment_create, name='appointment_create'),
    path('appointment/<int:appointment_id>/', views.appointment_detail, name='appointment_detail'),
    path('appointment/<int:appointment_id>/cancel/', views.appointment_cancel, name='appointment_cancel'),
    path('appointment/<int:appointment_id>/approve/', views.appointment_approve, name='appointment_approve'),
    
    # Dietitians
    path('dietitians/', views.dietitians_list, name='dietitians_list'),
    path('dietitian/<int:dietitian_id>/', views.dietitian_detail, name='dietitian_detail'),
    
    # Articles
    path('articles/', views.articles_list, name='articles_list'),
    path('articles/<slug:slug>/', views.article_detail, name='article_detail'),
    path('articles/category/<int:category_id>/', views.articles_by_category, name='articles_by_category'),
    
    # Dashboard Article Management
    path('dashboard/articles/', views.dashboard_articles_list, name='dashboard_articles_list'),
    path('dashboard/articles/create/', views.dashboard_article_create, name='dashboard_article_create'),
    path('dashboard/articles/<int:article_id>/edit/', views.dashboard_article_edit, name='dashboard_article_edit'),
    path('dashboard/articles/<int:article_id>/delete/', views.dashboard_article_delete, name='dashboard_article_delete'),
    path('dashboard/articles/api/', views.dashboard_articles_api, name='dashboard_articles_api'),
    
    # Static Pages
    path('about/', views.about_view, name='about'),
    path('contact/', views.contact_view, name='contact'),
    path('privacy/', views.privacy_view, name='privacy'),
    path('terms/', views.terms_view, name='terms'),
    
    # Emergency Chat
    path('emergency-chat/', views.emergency_chat_view, name='emergency_chat'),
    path('api/start-emergency-chat/', views.start_emergency_chat, name='start_emergency_chat'),
    
    # WebRTC Video Calls
    path('video-call/<str:call_id>/', views_webrtc.video_call_view, name='video_call'),
    path('emergency-call/', views_webrtc.emergency_call_view, name='emergency_call'),
    path('appointment/<int:randevu_id>/video-call/', views_webrtc.appointment_video_call, name='appointment_video_call'),
    
    # Schedule API
    path('api/schedule/', views.schedule_api, name='schedule_api'),
    
    # Diet Plans API
    path('api/diet-plans/', views.diet_plans_api, name='diet_plans_api'),
    path('api/diet-plans/<int:plan_id>/', views.diet_plan_detail_api, name='diet_plan_detail_api'),
    
    # Admin API
    path('api/analytics/', views.analytics_api, name='analytics_api'),
    path('api/users/', views.user_management_api, name='user_management_api'),
    path('api/users/<int:user_id>/', views.user_delete_api, name='user_delete_api'),
    path('api/dietitians/', views.dietitian_management_api, name='dietitian_management_api'),
    path('api/dietitians/<int:dietitian_id>/', views.dietitian_detail_api, name='dietitian_detail_api'),
    path('api/admin/dietitians/<int:dietitian_id>/approve/', views.dietitian_approve_api, name='dietitian_approve_api'),
    path('api/admin/dietitians/<int:dietitian_id>/reject/', views.dietitian_reject_api, name='dietitian_reject_api'),
    path('api/appointments/', views.appointment_management_api, name='appointment_management_api'),
    path('api/logs/', views.system_logs_api, name='system_logs_api'),
    path('api/bulk-email/', views.bulk_email_api, name='bulk_email_api'),
    
    # Admin Matching API
    path('api/admin/patients/', views.admin_patients_api, name='admin_patients_api'),
    path('api/admin/patients/unmatched/', views.admin_patients_unmatched_api, name='admin_patients_unmatched_api'),
    path('api/admin/dietitians/', views.admin_dietitians_api, name='admin_dietitians_api'),
    path('api/admin/matchings/create/', views.admin_matchings_create_api, name='admin_matchings_create_api'),
    path('api/admin/matchings/<int:matching_id>/', views.admin_matchings_detail_api, name='admin_matchings_detail_api'),
    path('api/admin/matchings/<int:matching_id>/update/', views.admin_matchings_update_api, name='admin_matchings_update_api'),
    path('api/admin/matchings/<int:matching_id>/change-dietitian/', views.admin_matchings_change_dietitian_api, name='admin_matchings_change_dietitian_api'),
    path('api/admin/matchings/<int:matching_id>/delete/', views.admin_matchings_delete_api, name='admin_matchings_delete_api'),
    
    # User management for admin dashboard
    path('dashboard/user/<int:user_id>/', views.user_detail_api, name='user_detail_api'),
    path('dashboard/user/<int:user_id>/update/', views.user_update_api, name='user_update_api'),
    
    # Admin Appointment Management API
    path('api/admin/appointments/<int:appointment_id>/', views.appointment_detail_api, name='appointment_detail_api'),
    path('api/admin/appointments/<int:appointment_id>/update/', views.appointment_update_api, name='appointment_update_api'),
    path('api/admin/appointments/<int:appointment_id>/suggestions/', views.auto_assign_suggestions_api, name='auto_assign_suggestions_api'),
    
    # Test Data Creation API
    path('api/admin/create-test-data/', views.create_test_data_api, name='create_test_data_api'),
    
    # Survey Management API
    path('api/admin/questions/', views.admin_questions_api, name='admin_questions_api'),
    path('api/admin/questions/<int:question_id>/', views.admin_question_detail_api, name='admin_question_detail_api'),
    path('api/admin/survey-preview/', views.admin_survey_preview_api, name='admin_survey_preview_api'),
    path('api/admin/activate-survey/', views.admin_activate_survey_api, name='admin_activate_survey_api'),
    path('api/admin/survey-responses/', views.admin_survey_responses_api, name='admin_survey_responses_api'),
    path('api/admin/survey-responses/<int:session_id>/', views.admin_survey_responses_api, name='admin_survey_response_detail_api'),
    path('api/admin/survey-analytics/', views.admin_survey_analytics_api, name='admin_survey_analytics_api'),
    
    # Survey Response API (for clients)
    path('survey/', views.survey_view, name='survey'),
    path('api/survey/start/', views.survey_start_api, name='survey_start_api'),
    path('api/survey/questions/', views.survey_questions_api, name='survey_questions_api'),
    path('api/survey/answers/<int:session_id>/', views.survey_answers_api, name='survey_answers_api'),
    path('api/survey/submit/', views.survey_submit_api, name='survey_submit_api'),
    path('api/survey/results/<int:session_id>/', views.survey_results_api, name='survey_results_api'),
    path('api/survey/status/', views.survey_status_api, name='survey_status_api'),
    
    # Dietitian Profile Pages (must be last to avoid conflicts)
    path('<path:slug>/', views.dietitian_profile, name='dietitian_profile'),
]