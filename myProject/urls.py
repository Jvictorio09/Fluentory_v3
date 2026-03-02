from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from myApp import views
from myApp import dashboard_views
from myApp import teacher_views

urlpatterns = [
    # Public-facing URLs
    path('v1/', views.landing, name='landing'),
    path('', views.v3_landing, name='v3_landing'),
    path('home/', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('register/teacher/', views.register_teacher_view, name='register_teacher'),
    path('logout/', views.logout_view, name='logout'),
    path('courses/', views.courses, name='courses'),
    path('tawjehi/', views.tawjehi_page, name='tawjehi_page'),
    # Purchase and gift endpoints must come before course_detail and lesson_detail to avoid URL matching conflicts
    path('courses/<slug:course_slug>/purchase/', views.initiate_purchase, name='initiate_purchase'),
    path('courses/<slug:course_slug>/gift/', views.gift_course, name='gift_course'),
    path('courses/<slug:course_slug>/', views.course_detail, name='course_detail'),
    path('courses/<slug:course_slug>/<slug:lesson_slug>/', views.lesson_detail, name='lesson_detail'),
    path('courses/<slug:course_slug>/<slug:lesson_slug>/quiz/', views.lesson_quiz_view, name='lesson_quiz'),
    
    # Student Dashboard (Client-facing)
    path('my-dashboard/', views.student_dashboard, name='student_dashboard'),
    path('my-dashboard/course/<slug:course_slug>/', views.student_course_progress, name='student_course_progress'),
    path('my-certifications/', views.student_certifications, name='student_certifications'),
    path('certificate/<slug:course_slug>/', views.view_certificate, name='view_certificate'),
    path('verify-certificate/<str:certificate_id>/', views.verify_certificate, name='verify_certificate'),
    
    # Dashboard URLs (Admin-facing, for developers)
    path('dashboard/', dashboard_views.dashboard_home, name='dashboard_home'),
    path('dashboard/analytics/', dashboard_views.dashboard_analytics, name='dashboard_analytics'),
    path('dashboard/courses/', dashboard_views.dashboard_courses, name='dashboard_courses'),
    path('dashboard/courses/add/', dashboard_views.dashboard_add_course, name='dashboard_add_course'),
    path('dashboard/courses/<slug:course_slug>/', dashboard_views.dashboard_course_detail, name='dashboard_course_detail'),
    path('dashboard/courses/<slug:course_slug>/delete/', dashboard_views.dashboard_delete_course, name='dashboard_delete_course'),
    path('dashboard/courses/<slug:course_slug>/lessons/', dashboard_views.dashboard_course_lessons, name='dashboard_course_lessons'),
    path('dashboard/courses/<slug:course_slug>/sample-certificate/', dashboard_views.dashboard_sample_certificate, name='dashboard_sample_certificate'),
    path('dashboard/courses/<slug:course_slug>/edit-certificate-template/', dashboard_views.dashboard_edit_certificate_template, name='dashboard_edit_certificate_template'),
    path('dashboard/courses/<slug:course_slug>/upload-pdf/', views.upload_pdf_lessons, name='dashboard_upload_pdf_lessons'),
    path('dashboard/courses/<slug:course_slug>/clear-lessons/', views.clear_course_lessons, name='dashboard_clear_course_lessons'),
    path('dashboard/lessons/', dashboard_views.dashboard_lessons, name='dashboard_lessons'),
    path('dashboard/lessons/add/', dashboard_views.dashboard_add_lesson, name='dashboard_add_lesson'),
    path('dashboard/lessons/upload-quiz/', dashboard_views.dashboard_upload_quiz, name='dashboard_upload_quiz'),
    path('dashboard/lessons/<int:lesson_id>/edit/', dashboard_views.dashboard_edit_lesson, name='dashboard_edit_lesson'),
    path('dashboard/lessons/<int:lesson_id>/delete/', dashboard_views.dashboard_delete_lesson, name='dashboard_delete_lesson'),
    path('dashboard/lessons/<int:lesson_id>/quiz/', dashboard_views.dashboard_lesson_quiz, name='dashboard_lesson_quiz'),
    path('dashboard/lessons/<int:lesson_id>/quiz/delete/', dashboard_views.dashboard_delete_quiz, name='dashboard_delete_quiz'),
    path('dashboard/quizzes/', dashboard_views.dashboard_quizzes, name='dashboard_quizzes'),
    
    # Student Progress Monitoring
    path('dashboard/students/', dashboard_views.dashboard_students, name='dashboard_students'),
    path('dashboard/students/progress/', dashboard_views.dashboard_student_progress, name='dashboard_student_progress'),
    path('dashboard/students/<int:user_id>/', dashboard_views.dashboard_student_detail, name='dashboard_student_detail'),
    path('dashboard/students/<int:user_id>/<slug:course_slug>/', dashboard_views.dashboard_student_detail, name='dashboard_student_detail_course'),
    path('dashboard/courses/<slug:course_slug>/progress/', dashboard_views.dashboard_course_progress, name='dashboard_course_progress'),
    
    # Bundle Management
    path('dashboard/bundles/', dashboard_views.dashboard_bundles, name='dashboard_bundles'),
    path('dashboard/bundles/add/', dashboard_views.dashboard_add_bundle, name='dashboard_add_bundle'),
    path('dashboard/bundles/<int:bundle_id>/edit/', dashboard_views.dashboard_edit_bundle, name='dashboard_edit_bundle'),
    path('dashboard/bundles/<int:bundle_id>/delete/', dashboard_views.dashboard_delete_bundle, name='dashboard_delete_bundle'),
    
    # Access Management
    path('dashboard/access/bulk/', dashboard_views.bulk_access_management, name='dashboard_bulk_access'),
    path('dashboard/access/bulk/grant/', dashboard_views.bulk_grant_access_view, name='dashboard_bulk_grant_access'),
    path('dashboard/students/<int:user_id>/grant-access/', dashboard_views.grant_course_access_view, name='dashboard_grant_access'),
    path('dashboard/students/<int:user_id>/revoke-access/', dashboard_views.revoke_course_access_view, name='dashboard_revoke_access'),
    path('dashboard/students/<int:user_id>/grant-bundle/', dashboard_views.grant_bundle_access_view, name='dashboard_grant_bundle'),
    path('dashboard/students/<int:user_id>/add-cohort/', dashboard_views.add_to_cohort_view, name='dashboard_add_cohort'),
    
    # Creator/Lesson Upload Flow (kept for lesson creation)
    path('creator/', views.creator_dashboard, name='creator_dashboard'),
    path('creator/courses/<slug:course_slug>/lessons/', views.course_lessons, name='course_lessons'),
    path('creator/courses/<slug:course_slug>/add-lesson/', views.add_lesson, name='add_lesson'),
    path('creator/courses/<slug:course_slug>/upload-pdf/', views.upload_pdf_lessons, name='upload_pdf_lessons'),
    path('creator/courses/<slug:course_slug>/clear-lessons/', views.clear_course_lessons, name='clear_course_lessons'),
    path('creator/courses/<slug:course_slug>/lessons/<int:lesson_id>/generate/', views.generate_lesson_ai, name='generate_lesson_ai'),
    path('creator/verify-vimeo/', views.verify_vimeo_url, name='verify_vimeo_url'),
    path('creator/upload-video-transcribe/', views.upload_video_transcribe, name='upload_video_transcribe'),
    path('creator/lessons/<int:lesson_id>/transcription-status/', views.check_transcription_status, name='check_transcription_status'),
    
    # Chatbot webhook endpoint
    path('api/chatbot/', views.chatbot_webhook, name='chatbot_webhook'),
    
    # AI Chatbot endpoints
    path('api/lessons/<int:lesson_id>/train-chatbot/', views.train_lesson_chatbot, name='train_lesson_chatbot'),
    path('api/lessons/<int:lesson_id>/chatbot/', views.lesson_chatbot, name='lesson_chatbot'),
    
    # Lesson progress tracking endpoints
    path('api/lessons/<int:lesson_id>/progress/', views.update_video_progress, name='update_video_progress'),
    path('api/lessons/<int:lesson_id>/complete/', views.complete_lesson, name='complete_lesson'),
    
    # Favorite course endpoint
    path('api/courses/<int:course_id>/favorite/', views.toggle_favorite_course, name='toggle_favorite_course'),
    
    # Course content generation webhook endpoint
    path('api/generate-course-content/', views.generate_course_content_webhook, name='generate_course_content_webhook'),
    
    # Purchase system endpoints (purchase URL moved above to avoid conflicts)
    path('api/purchase/webhook/', views.purchase_webhook, name='purchase_webhook'),
    
    # Gift purchase endpoints (gift URL moved above to avoid conflicts)
    path('gift/success/<str:gift_token>/', views.gift_success, name='gift_success'),
    path('gift/redeem/<str:gift_token>/', views.redeem_gift, name='redeem_gift'),
    
    # Teacher URLs
    path('teacher/', teacher_views.teacher_dashboard, name='teacher_dashboard'),
    path('teacher/courses/', teacher_views.teacher_courses, name='teacher_courses'),
    path('teacher/courses/add/', teacher_views.teacher_add_course, name='teacher_add_course'),
    path('teacher/courses/<slug:course_slug>/', teacher_views.teacher_course_detail, name='teacher_course_detail'),
    path('teacher/courses/<slug:course_slug>/delete/', teacher_views.teacher_delete_course, name='teacher_delete_course'),
    path('teacher/courses/<slug:course_slug>/lessons/', teacher_views.teacher_course_lessons, name='teacher_course_lessons'),
    path('teacher/sessions/', teacher_views.teacher_live_sessions, name='teacher_live_sessions'),
    path('teacher/courses/<slug:course_slug>/sessions/create/', teacher_views.teacher_live_session_create, name='teacher_live_session_create'),
    path('teacher/sessions/<int:session_id>/', teacher_views.teacher_live_session_detail, name='teacher_live_session_detail'),
    path('teacher/sessions/<int:session_id>/edit/', teacher_views.teacher_live_session_edit, name='teacher_live_session_edit'),
    path('teacher/sessions/<int:session_id>/cancel/', teacher_views.teacher_live_session_cancel, name='teacher_live_session_cancel'),
    path('teacher/sessions/<int:session_id>/bookings/', teacher_views.teacher_session_bookings, name='teacher_session_bookings'),
    path('teacher/bookings/<int:booking_id>/attendance/', teacher_views.teacher_mark_attendance, name='teacher_mark_attendance'),
    
    # CRM Lead Management
    path('dashboard/crm/leads/', dashboard_views.dashboard_leads, name='dashboard_leads'),
    path('dashboard/crm/leads/create/', dashboard_views.dashboard_lead_create, name='dashboard_lead_create'),
    path('dashboard/crm/leads/<int:lead_id>/', dashboard_views.dashboard_lead_detail, name='dashboard_lead_detail'),
    path('dashboard/crm/leads/<int:lead_id>/edit/', dashboard_views.dashboard_lead_edit, name='dashboard_lead_edit'),
    path('dashboard/crm/leads/<int:lead_id>/add-note/', dashboard_views.dashboard_lead_add_note, name='dashboard_lead_add_note'),
    path('dashboard/crm/leads/<int:lead_id>/link-user/', dashboard_views.dashboard_lead_link_user, name='dashboard_lead_link_user'),
    path('dashboard/crm/leads/<int:lead_id>/link-gift/', dashboard_views.dashboard_lead_link_gift, name='dashboard_lead_link_gift'),
    path('dashboard/crm/leads/<int:lead_id>/link-enrollment/', dashboard_views.dashboard_lead_link_enrollment, name='dashboard_lead_link_enrollment'),
    path('dashboard/crm/analytics/', dashboard_views.dashboard_crm_analytics, name='dashboard_crm_analytics'),
    
    # Teacher Request Management
    path('dashboard/teacher-requests/', dashboard_views.dashboard_teacher_requests, name='dashboard_teacher_requests'),
    path('dashboard/teacher-requests/<int:request_id>/', dashboard_views.dashboard_teacher_request_detail, name='dashboard_teacher_request_detail'),
    path('dashboard/teacher-requests/<int:request_id>/approve/', dashboard_views.dashboard_teacher_request_approve, name='dashboard_teacher_request_approve'),
    path('dashboard/teacher-requests/<int:request_id>/reject/', dashboard_views.dashboard_teacher_request_reject, name='dashboard_teacher_request_reject'),
    
    # Admin (optional - can be removed if not needed)
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
