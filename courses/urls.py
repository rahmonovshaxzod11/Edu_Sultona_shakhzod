# from django.urls import path
# from . import views
#
# urlpatterns = [
#     path('', views.home, name='home'),
#     path('course/<int:course_id>/', views.course_detail, name='course_detail'),
#     path('module/<int:module_id>/', views.module_detail, name='module_detail'),
#     path('lesson/<int:lesson_id>/', views.lesson_detail, name='lesson_detail'),
#     path('listening/<int:listening_id>/', views.listening_detail, name='listening_detail'),
#     path('api/submit-test/<int:lesson_id>/', views.submit_test, name='submit_test'),
#     path('api/submit-question/', views.submit_question, name='submit_question'),
#     path('api/save-listening-progress/', views.save_listening_progress, name='save_listening_progress'),
#     path('listening/<int:listening_id>/check/', views.check_listening_answers, name='check_listening_answers'),
#     path('api/submit-listening-test/<int:listening_id>/', views.submit_listening_test, name='submit_listening_test'),
#     path('speaking/<int:speaking_id>/', views.speaking_detail, name='speaking_detail'),
#     path('api/process-speaking/', views.process_speaking, name='process_speaking'),
#     path('api/speaking-attempt/<int:attempt_id>/', views.get_speaking_attempt, name='get_speaking_attempt'),
#
# ]