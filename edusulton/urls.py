# edusulton/urls.py faylini to'liq quyidagicha yangilang:

from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from courses import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),

    # Authentication
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),

    # Main pages
    path('', views.home, name='home'),
    path('course/<int:course_id>/', views.course_detail, name='course_detail'),
    path('module/<int:module_id>/', views.module_detail, name='module_detail'),
    path('lesson/<int:lesson_id>/', views.lesson_detail, name='lesson_detail'),
    path('listening/<int:listening_id>/', views.listening_detail, name='listening_detail'),
    path('speaking/<int:speaking_id>/', views.speaking_detail, name='speaking_detail'),

    # Test API endpoints
    path('api/submit-test/<int:lesson_id>/', views.submit_test, name='submit_test'),
    path('api/submit-question/', views.submit_question, name='submit_question'),
    path('api/save-listening-progress/', views.save_listening_progress, name='save_listening_progress'),
    path('listening/<int:listening_id>/check/', views.check_listening_answers, name='check_listening_answers'),
    path('api/submit-listening-test/<int:listening_id>/', views.submit_listening_test, name='submit_listening_test'),
    path('api/process-speaking/', views.process_speaking, name='process_speaking'),
    path('api/speaking-attempt/<int:attempt_id>/', views.get_speaking_attempt, name='get_speaking_attempt'),
path('reading/<int:reading_id>/', views.reading_detail, name='reading_detail'),
    path('api/submit-reading-test/<int:reading_id>/', views.submit_reading_test, name='submit_reading_test'),
    # Writing endpoints
    path('writing/<int:writing_id>/', views.writing_detail, name='writing_detail'),
    path('api/submit-writing/<int:writing_id>/', views.submit_writing, name='submit_writing'),
    path('api/writing-attempt/<int:attempt_id>/', views.get_writing_attempt, name='get_writing_attempt'),

]

# DEBUG rejimida media va static fayllarni ko'rsatish
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)