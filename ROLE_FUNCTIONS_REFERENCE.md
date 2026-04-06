# Fluentory — Functions by role (complete reference)

This document lists **all view functions and major helpers** grouped by **Admin dashboard** (`/dashboard/`, staff), **Django admin** (`/admin/`), **Student** (client UI + student APIs), **Teacher** (`/teacher/`), and **Partner-style operations** (no separate `/partner/` app — see § Partner).

Sources: `myProject/urls.py`, `myApp/views.py`, `myApp/dashboard_views.py`, `myApp/teacher_views.py`, `myApp/admin.py`.

---

## Partner (B2B / org workflows)

There is **no dedicated “partner” portal or `partner_views` module** in this codebase. Partner-style work is done through **staff**:

- **Bulk access & cohorts**: `bulk_access_management`, `bulk_grant_access_view`, per-student grant/revoke, bundle grant, add to cohort (`dashboard_views`).
- **CRM**: leads list/detail, notes, linking users/gifts/enrollments, CRM analytics (`dashboard_views`).
- **Teacher onboarding**: teacher request queue (approve/reject) (`dashboard_views`).
- Optional **Django admin** for raw data: `CourseAccess`, `Cohort`, `Bundle`, `CoursePurchase`, etc. (`myApp/admin.py`).

---

## Admin dashboard (staff — `myApp/dashboard_views.py`)

All listed routes use **`@staff_member_required`** unless noted.

### Pages & actions (URL name → function)

| URL name | Function | Purpose |
|----------|----------|---------|
| `dashboard_home` | `dashboard_home` | Main overview: course/lesson/student/enrollment/access/progress/cert metrics, activity feed, enrollment trend. |
| `dashboard_analytics` | `dashboard_analytics` | Deeper analytics dashboard. |
| `dashboard_courses` | `dashboard_courses` | List all courses. |
| `dashboard_add_course` | `dashboard_add_course` | Create course (incl. AI course generation pipeline). |
| `dashboard_course_detail` | `dashboard_course_detail` | Course detail/edit in dashboard. |
| `dashboard_delete_course` | `dashboard_delete_course` | Delete course. |
| `dashboard_course_lessons` | `dashboard_course_lessons` | Lessons list for a course. |
| `dashboard_sample_certificate` | `dashboard_sample_certificate` | Preview/sample certificate for a course. |
| `dashboard_edit_certificate_template` | `dashboard_edit_certificate_template` | Edit certificate template for a course. |
| `api_ai_generation_status` | `api_ai_generation_status` | JSON API: AI generation job status for a course. |
| `dashboard_lessons` | `dashboard_lessons` | Global lessons list. |
| `dashboard_add_lesson` | `dashboard_add_lesson` | Add lesson (dashboard flow). |
| `dashboard_edit_lesson` | `dashboard_edit_lesson` | Edit lesson. |
| `dashboard_delete_lesson` | `dashboard_delete_lesson` | Delete lesson. |
| `dashboard_upload_quiz` | `dashboard_upload_quiz` | Upload quiz (CSV/PDF + AI parsing). |
| `dashboard_lesson_quiz` | `dashboard_lesson_quiz` | Manage quiz for a lesson. |
| `dashboard_delete_quiz` | `dashboard_delete_quiz` | Delete lesson quiz. |
| `dashboard_quizzes` | `dashboard_quizzes` | All quizzes overview. |
| `dashboard_students` | `dashboard_students` | Student list with filters/search/sort. |
| `dashboard_student_progress` | `dashboard_student_progress` | Cross-student progress view. |
| `dashboard_student_detail` | `dashboard_student_detail` | Student detail (optional per-course variant via URL). |
| `dashboard_course_progress` | `dashboard_course_progress` | Progress for one course across learners. |
| `dashboard_bundles` | `dashboard_bundles` | Bundle list. |
| `dashboard_add_bundle` | `dashboard_add_bundle` | Create bundle. |
| `dashboard_edit_bundle` | `dashboard_edit_bundle` | Edit bundle. |
| `dashboard_delete_bundle` | `dashboard_delete_bundle` | Delete bundle. |
| `dashboard_bulk_access` | `bulk_access_management` | Bulk access management UI. |
| `dashboard_bulk_grant_access` | `bulk_grant_access_view` | Grant access in bulk (POST). |
| `dashboard_grant_access` | `grant_course_access_view` | Grant course access to one user. |
| `dashboard_revoke_access` | `revoke_course_access_view` | Revoke course access. |
| `dashboard_grant_bundle` | `grant_bundle_access_view` | Grant bundle access to a user. |
| `dashboard_add_cohort` | `add_to_cohort_view` | Add user to cohort. |
| `dashboard_leads` | `dashboard_leads` | CRM leads list. |
| `dashboard_lead_create` | `dashboard_lead_create` | Create lead. |
| `dashboard_lead_detail` | `dashboard_lead_detail` | Lead detail. |
| `dashboard_lead_edit` | `dashboard_lead_edit` | Edit lead. |
| `dashboard_lead_add_note` | `dashboard_lead_add_note` | Add timeline note. |
| `dashboard_lead_link_user` | `dashboard_lead_link_user` | Link lead to user account. |
| `dashboard_lead_link_gift` | `dashboard_lead_link_gift` | Link lead to gift purchase. |
| `dashboard_lead_link_enrollment` | `dashboard_lead_link_enrollment` | Link lead to enrollment. |
| `dashboard_crm_analytics` | `dashboard_crm_analytics` | CRM analytics. |
| `dashboard_teacher_requests` | `dashboard_teacher_requests` | Teacher application queue. |
| `dashboard_teacher_request_detail` | `dashboard_teacher_request_detail` | Single teacher request. |
| `dashboard_teacher_request_approve` | `dashboard_teacher_request_approve` | Approve request. |
| `dashboard_teacher_request_reject` | `dashboard_teacher_request_reject` | Reject request. |

### Dashboard-only helpers (same file)

| Function | Purpose |
|----------|---------|
| `get_student_activity_feed` | Builds recent student activity entries for dashboard home. |
| `_update_ai_gen_progress` | Updates cached AI generation progress for a course. |
| `_fallback_course_structure` | Fallback course outline when AI structure fails. |
| `generate_ai_course_structure` | AI-generated course/module outline. |
| `_build_editorjs_content` | Builds Editor.js JSON for lesson body. |
| `_extract_json_payload` | Parses JSON from raw AI text. |
| `generate_ai_lesson_metadata` | AI lesson metadata (titles, summaries, etc.). |
| `generate_ai_lesson_content` | AI lesson body content. |
| `_extract_text_from_editorjs` | Flatten Editor.js to plain text. |
| `_train_lesson_chatbot_from_text` | Trains chatbot from transcript text (internal). |
| `generate_ai_final_exam_questions` | AI-generated final exam questions. |
| `_generate_course_ai_content` | Orchestrates full AI course content generation (threaded). |
| `parse_csv_quiz` | Parse uploaded CSV into quiz questions. |
| `generate_ai_quiz` | AI-generated quiz from lesson context. |
| `parse_pdf_quiz` | Parse quiz from PDF upload. |
| `generate_slug` | URL slug helper (dashboard). |

---

## Admin / staff creator tools (`myApp/views.py` — staff-only routes)

These are **not** under `/dashboard/` but are **staff-only** (`@staff_member_required`) unless noted.

| Function | URL / purpose |
|----------|----------------|
| `creator_dashboard` | `/creator/` — list all courses for creators. |
| `course_lessons` | `/creator/courses/<slug>/lessons/` — lessons for a course (staff). |
| `upload_pdf_lessons` | `/creator/.../upload-pdf/` and `/dashboard/courses/.../upload-pdf/` — PDF → lessons pipeline. |
| `clear_course_lessons` | `/creator/.../clear-lessons/` and `/dashboard/.../clear-lessons/` — delete all lessons for a course. |
| `verify_vimeo_url` | `/creator/verify-vimeo/` — validate Vimeo URL. |
| `upload_video_transcribe` | `/creator/upload-video-transcribe/` — upload + transcription. |
| `check_transcription_status` | `/creator/lessons/<id>/transcription-status/` — poll transcription job. |
| `generate_course_content_webhook` | `/api/generate-course-content/` — **POST** webhook for external AI course generation. |
| `train_lesson_chatbot` | `/api/lessons/<id>/train-chatbot/` — **POST**, staff: send transcript to training webhook. |

`add_lesson` and `generate_lesson_ai` are **`@login_required`** and use `require_course_teacher` — staff **or** assigned teacher can use them via `/creator/` routes.

---

## Django admin (`/admin/` — `myApp/admin.py`)

Registered model admins (each exposes list/detail/edit through Django’s UI):

| Model | Admin class |
|-------|-------------|
| `Course` | `CourseAdmin` |
| `Module` | `ModuleAdmin` |
| `Lesson` | `LessonAdmin` |
| `UserProgress` | `UserProgressAdmin` |
| `CourseEnrollment` | `CourseEnrollmentAdmin` |
| `Exam` | `ExamAdmin` |
| `ExamAttempt` | `ExamAttemptAdmin` |
| `Certification` | `CertificationAdmin` |
| `Cohort` | `CohortAdmin` |
| `CohortMember` | `CohortMemberAdmin` |
| `Bundle` | `BundleAdmin` |
| `BundlePurchase` | `BundlePurchaseAdmin` |
| `CoursePurchase` | `CoursePurchaseAdmin` |
| `CourseAccess` | `CourseAccessAdmin` |
| `LearningPath` | `LearningPathAdmin` |
| `LearningPathCourse` | `LearningPathCourseAdmin` |
| `LiveSession` | `LiveSessionAdmin` |
| `Booking` | `BookingAdmin` |
| `GiftPurchase` | `GiftPurchaseAdmin` |
| `TeacherRequest` | `TeacherRequestAdmin` |
| `TeacherProfile` | `TeacherProfileAdmin` |

**Not** registered in `admin.py`: e.g. CRM `Lead` / timeline models — those are managed via **dashboard CRM** only.

---

## Student (`myApp/views.py` + APIs)

### Student UI pages (`@login_required`)

| Function | URL name | Purpose |
|----------|----------|---------|
| `student_dashboard` | `student_dashboard` | `/my-dashboard/` — my courses, unlockable, locked; redirects teachers to teacher dashboard. |
| `student_course_progress` | `student_course_progress` | `/my-dashboard/course/<slug>/` — per-course progress, live sessions & bookings, exam, cert. |
| `student_certifications` | `student_certifications` | `/my-certifications/` — list certs + eligible courses. |
| `view_certificate` | `view_certificate` | `/certificate/<slug>/` — view/download PDF or Accredible redirect. |

### Public (no login)

| Function | URL name | Purpose |
|----------|----------|---------|
| `verify_certificate` | `verify_certificate` | `/verify-certificate/<id>/` — public certificate verification page. |

### Learning & catalog (student-facing; many are public GET)

| Function | URL name | Purpose |
|----------|----------|---------|
| `landing` | `landing` | Premium landing. |
| `v3_landing` | `v3_landing` | V3 landing. |
| `home` | `home` | Home / courses hub. |
| `courses` | `courses` | Course catalog. |
| `course_detail` | `course_detail` | Course detail page. |
| `tawjehi_page` | `tawjehi_page` | Tawjehi courses by subject. |
| `teacher_public_profile` | `teacher_public_profile` | Public teacher profile. |
| `enroll_free_course` | `enroll_free_course` | **POST** — enroll in free course. |
| `lesson_detail` | `lesson_detail` | Lesson player / content (`@login_required`). |
| `lesson_quiz_view` | `lesson_quiz` | Lesson quiz take/review (`@login_required`). |

### Auth

| Function | Purpose |
|----------|---------|
| `login_view` | Login. |
| `register_view` | Student registration. |
| `register_teacher_view` | Teacher application registration. |
| `logout_view` | Logout. |

### Student APIs (`@login_required` unless noted)

| Function | Route | Purpose |
|----------|-------|---------|
| `update_video_progress` | `POST /api/lessons/<id>/progress/` | Video watch progress; also handles **Stripe-signed** webhook branch when `Stripe-Signature` + `STRIPE_WEBHOOK_SECRET` set. |
| `complete_lesson` | `POST /api/lessons/<id>/complete/` | Mark lesson complete; certificate path. |
| `toggle_favorite_course` | `POST /api/courses/<id>/favorite/` | Favorite/unfavorite course. |
| `lesson_chatbot` | `POST /api/lessons/<id>/chatbot/` | Lesson AI chat (requires access + trained chatbot). |
| `chatbot_webhook` | `POST /api/chatbot/` | Proxies chat to external webhooks (legacy paths). |
| `initiate_purchase` | `POST /courses/<slug>/purchase/` | Start purchase (simulate / Stripe checkout). |
| `gift_course` | `POST /courses/<slug>/gift/` | Gift a course purchase. |
| `gift_success` | `GET /gift/success/<token>/` | Post-gift payment page (purchaser only). |
| `redeem_gift` | `GET/POST /gift/redeem/<token>/` | Redeem gift link (**no login required** until claim; supports auto-redeem when logged-in email matches). |

### Webhooks / integrations (not student UI; used by payments & automation)

| Function | Route | Purpose |
|----------|-------|---------|
| `purchase_webhook` | `POST /api/purchase/webhook/` | **csrf_exempt** — JSON payment confirmation (`purchase_id`, `provider`, `status`, etc.). |
| `generate_course_content_webhook` | `POST /api/generate-course-content/` | External AI fills course structure (staff). |

---

## Student-related internal helpers (`myApp/views.py`)

| Function | Purpose |
|----------|---------|
| `_lessons_list_redirect` | After lesson save: staff → creator list; teacher → teacher lessons. |
| `_lessons_back_url` | Back link URL for lesson editor. |
| `_is_teacher_user` | Detect teacher (approved request or teaches courses). |
| `_complete_lesson_and_maybe_certificate` | Complete lesson + issue certificate when appropriate. |
| `_build_purchase_redirect` | Redirect URL after purchase. |
| `_create_stripe_checkout_session` | Stripe Checkout session for a `CoursePurchase`. |
| `_finalize_purchase` | Finalize purchase (access, gift email, etc.). |
| `_insert_images_contextually` | PDF pipeline: place images in content. |
| `_split_text_with_images` | PDF chunking with images. |
| `_process_pdf_chunk` | PDF chunk → lesson/module creation. |
| `extract_vimeo_id` | Parse Vimeo ID from URL. |
| `fetch_vimeo_metadata` | Vimeo metadata fetch. |
| `generate_ai_lesson_content` | Generate lesson content from lesson record. |
| `generate_slug` | Slug from text. |
| `format_duration` | Format seconds as `M:SS`. |
| `process_course_content_response` | Parse AI webhook response into course/module/lesson rows. |

---

## Teacher (`myApp/teacher_views.py`)

All dashboard views use `@login_required` + `@teacher_required` (approved `TeacherRequest` **or** assigned to a course; superusers are **not** treated as teachers here).

### Helpers / decorator

| Name | Purpose |
|------|---------|
| `teacher_required` | Decorator: must be teacher (not superuser). |
| `_configure_cloudinary` | Lazy Cloudinary config. |
| `_upload_teacher_photo_to_cloudinary` | Profile photo upload. |
| `_delete_cloudinary_image` | Remove old Cloudinary asset. |

### Views

| Function | URL name | Purpose |
|----------|----------|---------|
| `teacher_dashboard` | `teacher_dashboard` | Overview: courses (mine vs company), sessions, bookings, stats. |
| `teacher_profile` | `teacher_profile` | Edit public profile (bio, links, photo). |
| `teacher_courses` | `teacher_courses` | List courses teacher owns or teaches. |
| `teacher_add_course` | `teacher_add_course` | Create course. |
| `teacher_course_detail` | `teacher_course_detail` | Edit course metadata. |
| `teacher_delete_course` | `teacher_delete_course` | **POST** — delete course. |
| `teacher_course_lessons` | `teacher_course_lessons` | Read-only lesson list for course. |
| `teacher_live_sessions` | `teacher_live_sessions` | All live sessions for teacher’s courses. |
| `teacher_live_session_create` | `teacher_live_session_create` | Create session. |
| `teacher_live_session_detail` | `teacher_live_session_detail` | Session + bookings. |
| `teacher_live_session_edit` | `teacher_live_session_edit` | Edit session. |
| `teacher_live_session_cancel` | `teacher_live_session_cancel` | **POST** — cancel session. |
| `teacher_session_bookings` | `teacher_session_bookings` | Bookings for session. |
| `teacher_mark_attendance` | `teacher_mark_attendance` | **POST** — attended / no-show. |

---

## Cross-role: creator lesson flow (`views.py`)

Used from **staff** (`/creator/`) or **teachers** with `require_course_teacher`:

| Function | Purpose |
|----------|---------|
| `add_lesson` | Multi-step lesson create (Vimeo, transcription, AI). |
| `generate_lesson_ai` | Trigger AI generation for a lesson. |

---

## Index: URL patterns (quick)

- **Student client**: `/my-dashboard/`, `/my-certifications/`, `/certificate/`, `/verify-certificate/`, `/courses/`, `/courses/<slug>/`, `/courses/<slug>/<lesson>/`, quiz, purchase, gift, redeem.
- **Admin app**: `/dashboard/...` (all `dashboard_views` above).
- **Staff creator**: `/creator/...`.
- **Teacher**: `/teacher/...`.
- **APIs**: `/api/lessons/...`, `/api/courses/.../favorite/`, `/api/chatbot/`, `/api/generate-course-content/`, `/api/purchase/webhook/`.
- **Django admin**: `/admin/`.

---

*Generated from the Fluentory_v3-1 codebase. If you add routes or views, update this file or regenerate from `urls.py` and `grep ^def` in the three view modules.*
