# Functions Reference

Current module-level Python functions in `myApp` (excluding class methods).

## myApp/views.py
- `_lessons_list_redirect(request, course_slug)`
- `_lessons_back_url(request, course_slug)`
- `landing(request)`
- `v3_landing(request)`
- `teacher_public_profile(request, username)`
- `tawjehi_page(request)`
- `home(request)`
- `_is_teacher_user(user)`
- `login_view(request)`
- `register_view(request)`
- `register_teacher_view(request)`
- `become_teacher_page(request)`
- `logout_view(request)`
- `courses(request)`
- `course_detail(request, course_slug)`
- `enroll_free_course(request, course_slug)`
- `lesson_detail(request, course_slug, lesson_slug)`
- `lesson_quiz_view(request, course_slug, lesson_slug)`
- `creator_dashboard(request)`
- `course_lessons(request, course_slug)`
- `add_lesson(request, course_slug)`
- `generate_lesson_ai(request, course_slug, lesson_id)`
- `upload_pdf_lessons(request, course_slug)`
- `clear_course_lessons(request, course_slug)`
- `_insert_images_contextually(content_blocks, images, pdf_text)`
- `_split_text_with_images(text, images, total_pages)`
- `_process_pdf_chunk(course, module, pdf_text, suggested_title, ai_generator, skip_ai, course_name, module_name, images=None)`
- `verify_vimeo_url(request)`
- `upload_video_transcribe(request)`
- `check_transcription_status(request, lesson_id)`
- `extract_vimeo_id(url)`
- `fetch_vimeo_metadata(vimeo_id)`
- `generate_ai_lesson_content(lesson)`
- `generate_slug(text)`
- `format_duration(seconds)`
- `update_video_progress(request, lesson_id)`
- `_complete_lesson_and_maybe_certificate(user, lesson)`
- `complete_lesson(request, lesson_id)`
- `view_certificate(request, course_slug)`
- `verify_certificate(request, certificate_id)`
- `toggle_favorite_course(request, course_id)`
- `chatbot_webhook(request)`
- `student_dashboard(request)`
- `student_course_progress(request, course_slug)`
- `student_certifications(request)`
- `train_lesson_chatbot(request, lesson_id)`
- `lesson_chatbot(request, lesson_id)`
- `generate_course_content_webhook(request)`
- `gift_course(request, course_slug)`
- `gift_success(request, gift_token)`
- `redeem_gift(request, gift_token)`
- `process_course_content_response(course_type, module_name, content_data)`
- `_build_purchase_redirect(course)`
- `_create_stripe_checkout_session(request, purchase)`
- `_transaction_status_for_purchase_status(status)`
- `_log_payment_transaction(purchase, provider='', provider_id='', status='pending', metadata=None)`
- `_finalize_purchase(purchase, provider='manual', provider_id='', status='paid')`
- `initiate_purchase(request, course_slug)`
- `stripe_webhook(request)`
- `purchase_webhook(request)`

## myApp/dashboard_views.py
- `dashboard_home(request)`
- `dashboard_students(request)`
- `get_student_activity_feed(limit=20)`
- `dashboard_courses(request)`
- `dashboard_course_detail(request, course_slug)`
- `dashboard_delete_course(request, course_slug)`
- `dashboard_lesson_quiz(request, lesson_id)`
- `dashboard_delete_quiz(request, lesson_id)`
- `dashboard_quizzes(request)`
- `dashboard_course_lessons(request, course_slug)`
- `dashboard_add_course(request)`
- `api_ai_generation_status(request, course_id)`
- `_update_ai_gen_progress(course_id, status, progress, current, error='')`
- `_fallback_course_structure(course_name, description)`
- `generate_ai_course_structure(course_name, description, course_type='sprint', coach_name='Sprint Coach')`
- `_build_editorjs_content(lesson_title, lesson_description)`
- `_extract_json_payload(raw_text)`
- `generate_ai_lesson_metadata(course_name, module_title, lesson_title, lesson_description, course_type='sprint', coach_name='Sprint Coach')`
- `generate_ai_lesson_content(course_name, module_title, metadata)`
- `_extract_text_from_editorjs(content)`
- `_train_lesson_chatbot_from_text(lesson, transcript)`
- `generate_ai_final_exam_questions(course_name, lesson_summaries, num_questions=20)`
- `_generate_course_ai_content(course_id, course_name, description, course_type, coach_name)`
- `dashboard_lessons(request)`
- `dashboard_delete_lesson(request, lesson_id)`
- `dashboard_upload_quiz(request)`
- `parse_csv_quiz(uploaded_file, quiz)`
- `generate_ai_quiz(lesson, quiz, num_questions=5)`
- `parse_pdf_quiz(uploaded_file, quiz)`
- `dashboard_add_lesson(request)`
- `dashboard_edit_lesson(request, lesson_id)`
- `dashboard_student_progress(request)`
- `dashboard_student_detail(request, user_id, course_slug=None)`
- `dashboard_course_progress(request, course_slug)`
- `grant_course_access_view(request, user_id)`
- `revoke_course_access_view(request, user_id)`
- `grant_bundle_access_view(request, user_id)`
- `add_to_cohort_view(request, user_id)`
- `bulk_access_management(request)`
- `bulk_grant_access_view(request)`
- `dashboard_analytics(request)`
- `generate_slug(text)`
- `dashboard_bundles(request)`
- `dashboard_add_bundle(request)`
- `dashboard_edit_bundle(request, bundle_id)`
- `dashboard_delete_bundle(request, bundle_id)`
- `dashboard_leads(request)`
- `dashboard_lead_detail(request, lead_id)`
- `dashboard_lead_create(request)`
- `dashboard_lead_edit(request, lead_id)`
- `dashboard_lead_add_note(request, lead_id)`
- `dashboard_lead_link_user(request, lead_id)`
- `dashboard_lead_link_gift(request, lead_id)`
- `dashboard_lead_link_enrollment(request, lead_id)`
- `dashboard_crm_analytics(request)`
- `dashboard_teacher_requests(request)`
- `dashboard_teacher_request_detail(request, request_id)`
- `dashboard_teacher_request_approve(request, request_id)`
- `dashboard_teacher_request_reject(request, request_id)`
- `dashboard_edit_certificate_template(request, course_slug)`
- `dashboard_sample_certificate(request, course_slug=None)`
- `dashboard_site_settings(request)`
- `dashboard_assign_partner(request, user_id)`

## myApp/teacher_views.py
- `_configure_cloudinary()`
- `_upload_teacher_photo_to_cloudinary(uploaded_file, username)`
- `_delete_cloudinary_image(public_id)`
- `teacher_required(view_func)`
- `teacher_dashboard(request)`
- `teacher_profile(request)`
- `teacher_courses(request)`
- `teacher_add_course(request)`
- `teacher_course_detail(request, course_slug)`
- `teacher_delete_course(request, course_slug)`
- `teacher_course_lessons(request, course_slug)`
- `teacher_live_sessions(request)`
- `teacher_live_session_create(request, course_slug)`
- `teacher_live_session_detail(request, session_id)`
- `teacher_live_session_edit(request, session_id)`
- `teacher_live_session_cancel(request, session_id)`
- `teacher_session_bookings(request, session_id)`
- `teacher_mark_attendance(request, booking_id)`

## myApp/feature_views.py
- `create_refund_request(request, purchase_id)`
- `process_refund_request(request, refund_id)`
- `apply_voucher(request, course_slug)`
- `submit_course_review(request, course_id)`
- `submit_teacher_review(request, teacher_id)`
- `moderate_review(request, review_type, review_id)`
- `placement_test_view(request)`
- `faq_page(request)`
- `social_links(request)`
- `cms_page_editor(request, slug)`
- `cms_public_page(request, slug)`
- `analytics_snapshot(request)`
- `teacher_note_create(request, student_id, course_id)`
- `checkout_offers(request, course_id)`
- `issue_video_token(request, lesson_id)`
- `available_teacher_slots(request, teacher_id)`
- `booking_change_request(request, booking_id)`
- `trigger_notification_event(request)`
- `regenerate_invoice(request, purchase_id)`

## myApp/partner_views.py
- `partner_dashboard(request)`
- `partner_dashboard_api(request)`

## myApp/context_processors.py
- `platform_context(_request)`

## myApp/signals.py
- `auto_link_enrollment_to_lead(sender, instance, created, **kwargs)`
- `auto_link_gift_to_lead(sender, instance, created, **kwargs)`
- `create_bookings_when_live_session_created(sender, instance, created, **kwargs)`
- `purchase_event_signal(sender, instance, created, **kwargs)`

## myApp/services/automation.py
- `queue_sequence(trigger_key, user=None, payload=None)`
- `process_due_sequences()`

## myApp/services/notifications.py
- `queue_notification(event_key, user=None, payload=None)`
- `render_template(template, payload)`
- `process_notification_event(event)`

## myApp/services/payments.py
- `get_gateway(provider)`
- `create_checkout_for_purchase(purchase, provider='stripe', request=None, idempotency_key='')`
- `request_refund(purchase, amount, actor=None, reason='')`
- `process_refund(refund, actor=None)`

## myApp/services/invoicing.py
- `issue_invoice_for_purchase(purchase)`

## myApp/services/audit.py
- `write_audit_log(action, actor=None, entity_type='', entity_id='', metadata=None)`

## myApp/services/feature_flags.py
- `is_feature_enabled(key, user=None)`
- `get_setting(key, default=None)`
- `get_enabled_flags()`

## myApp/utils/access.py
- `ensure_live_session_bookings_for_user_course(user, course)`
- `ensure_live_session_bookings_for_session(session)`
- `has_course_access(user, course)`
- `grant_course_access(user, course, access_type, granted_by=None, bundle_purchase=None, cohort=None, purchase=None, expires_at=None, notes='')`
- `revoke_course_access(user, course, revoked_by, reason='', notes='')`
- `get_user_accessible_courses(user)`
- `get_courses_by_visibility(user)`
- `check_course_prerequisites(user, course)`
- `grant_bundle_access(user, bundle_purchase)`
- `grant_cohort_access(user, cohort)`
- `grant_purchase_access(user, course, purchase)`

## myApp/utils/teacher.py
- `get_eligible_course_teacher_users()`
- `is_teacher(user)`
- `is_course_teacher(user, course)`
- `require_course_teacher(user, course)`
- `get_teacher_courses(user)`
- `get_teacher_course_scope(user)`
- `split_teacher_owned_vs_company_courses(user, queryset=None)`
- `is_session_teacher(user, session)`
- `require_session_teacher(user, session)`
- `is_booking_teacher(user, booking)`
- `require_booking_teacher(user, booking)`
- `get_course_instructors(course)`

## myApp/utils/transcription.py
- `transcribe_video(video_file_path)`
- `extract_audio_from_video(video_path, audio_path)`

## myApp/utils/certificate_generator.py
- `generate_certificate_from_template(template_path, user_name, course_name, issued_date, certificate_id=None, field_positions=None, verification_url=None)`
- `generate_certificate_pdf(user_name, course_name, issued_date, certificate_id=None, modules=None, template_path=None, field_positions=None, verification_url=None)`
- `upload_certificate_to_cloudinary(pdf_buffer, user_id, course_slug)`
- `generate_certificate(user, course, issued_date=None, upload_to_cloudinary=True)`

## myApp/utils/email.py
- `_resend_emails_endpoint()`
- `_send_resend_email(to_emails, subject, html_content)`
- `_get_public_domain()`
- `send_gift_email(gift_purchase)`
- `send_gift_purchaser_confirmation_email(gift_purchase)`
- `send_teacher_request_email(teacher_request)`
- `notify_admin_teacher_request(teacher_request)`
- `send_teacher_approval_email(teacher_request)`
- `send_teacher_rejection_email(teacher_request, rejection_reason='')`

---

If you want, I can generate a second version that includes **class methods** too (models/services), and link each function to its file path for quick navigation.
