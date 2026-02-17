# Functions Documentation

This document provides a comprehensive overview of all functions in the system, organized by user role (Admin and Student).

---

## Table of Contents

1. [Admin Functions](#admin-functions)
2. [Student Functions](#student-functions)
3. [Helper Functions](#helper-functions)

---

## Admin Functions

All admin functions are located in `myApp/dashboard_views.py` and require `@staff_member_required` decorator.

### Dashboard Overview

#### `dashboard_home(request)`
- **URL**: `/dashboard/`
- **Method**: GET
- **Purpose**: Main dashboard overview with analytics
- **Returns**: Dashboard home page with:
  - Total courses and lessons count
  - Approved and pending lessons
  - Student analytics (total, active, new in 30 days)
  - Enrollment analytics
  - Course access analytics
  - Progress analytics (completion rates)
  - Certification analytics
  - Course performance overview
  - Recent activity feed
  - Enrollment trends (30-day chart)

#### `dashboard_analytics(request)`
- **URL**: `/dashboard/analytics/`
- **Method**: GET
- **Purpose**: Comprehensive analytics dashboard
- **Returns**: Detailed analytics including:
  - Student metrics (total, active, new, inactive)
  - Enrollment metrics (total, 7-day, 30-day)
  - Access metrics (total, expired, pending)
  - Progress metrics (total, completed, 7-day activity, completion rate)
  - Certification metrics (total, 7-day, 30-day)
  - Course performance by course
  - Enrollment and certification trends (30-day charts)
  - Top 5 courses by enrollment
  - Most active students
  - Exam & Quiz analytics
  - Access source analytics
  - Drop-off analysis
  - Trophy distribution

### Course Management

#### `dashboard_courses(request)`
- **URL**: `/dashboard/courses/`
- **Method**: GET
- **Purpose**: List all courses
- **Returns**: List of all courses with lesson counts

#### `dashboard_add_course(request)`
- **URL**: `/dashboard/courses/add/`
- **Method**: GET, POST
- **Purpose**: Create new course
- **POST Parameters**:
  - `name`: Course name (required)
  - `short_description`: Short description
  - `description`: Full description
  - `course_type`: Course type (default: 'sprint')
  - `status`: Status (default: 'active')
  - `coach_name`: Coach name (default: 'Sprint Coach')
- **Returns**: Redirects to courses list on success

#### `dashboard_course_detail(request, course_slug)`
- **URL**: `/dashboard/courses/<slug>/`
- **Method**: GET, POST
- **Purpose**: Edit course details
- **POST Parameters**:
  - `name`: Course name
  - `short_description`: Short description
  - `description`: Full description
  - `status`: Course status
  - `course_type`: Course type
  - `coach_name`: Coach name
- **Returns**: Course detail page with edit form

#### `dashboard_delete_course(request, course_slug)`
- **URL**: `/dashboard/courses/<slug>/delete/`
- **Method**: POST
- **Purpose**: Delete a course
- **Returns**: Redirects to courses list with success/error message

#### `dashboard_course_lessons(request, course_slug)`
- **URL**: `/dashboard/courses/<slug>/lessons/`
- **Method**: GET
- **Purpose**: View all lessons for a course
- **Returns**: List of lessons and modules for the course

### Lesson Management

#### `dashboard_lessons(request)`
- **URL**: `/dashboard/lessons/`
- **Method**: GET
- **Purpose**: List all lessons across courses
- **Query Parameters**:
  - `status`: Filter by AI generation status (all, pending, approved, etc.)
  - `course`: Filter by course ID
- **Returns**: List of all lessons with filtering options

#### `dashboard_add_lesson(request)`
- **URL**: `/dashboard/lessons/add/`
- **Method**: GET
- **Purpose**: Add new lesson - redirects to creator flow
- **Query Parameters**:
  - `course`: Course ID (optional)
- **Returns**: Redirects to lesson creation page or course selection page

#### `dashboard_edit_lesson(request, lesson_id)`
- **URL**: `/dashboard/lessons/<id>/edit/`
- **Method**: GET
- **Purpose**: Edit lesson - redirects to AI generation page
- **Returns**: Redirects to lesson AI generation page

#### `dashboard_delete_lesson(request, lesson_id)`
- **URL**: `/dashboard/lessons/<id>/delete/`
- **Method**: POST
- **Purpose**: Delete a lesson
- **Returns**: Redirects to lessons list or course lessons page

### Quiz Management

#### `dashboard_lesson_quiz(request, lesson_id)`
- **URL**: `/dashboard/lessons/<id>/quiz/`
- **Method**: GET, POST
- **Purpose**: Create and manage a quiz for a lesson
- **POST Actions**:
  - `save_quiz`: Update quiz settings (title, description, passing_score, is_required)
  - `add_question`: Add new question (q_text, q_option_a, q_option_b, q_option_c, q_option_d, q_correct_option)
  - `edit_question`: Edit existing question (question_id, q_text, options, q_correct_option)
  - `delete_question`: Delete question (question_id)
- **Returns**: Quiz management page with questions list

#### `dashboard_delete_quiz(request, lesson_id)`
- **URL**: `/dashboard/lessons/<id>/quiz/delete/`
- **Method**: POST
- **Purpose**: Delete a quiz for a lesson
- **Returns**: Redirects to quiz page with success/error message

#### `dashboard_quizzes(request)`
- **URL**: `/dashboard/quizzes/`
- **Method**: GET
- **Purpose**: List all quizzes across all lessons
- **Query Parameters**:
  - `course`: Filter by course ID
  - `search`: Search by quiz title, lesson title, or course name
- **Returns**: List of all quizzes with question counts

#### `dashboard_upload_quiz(request)`
- **URL**: `/dashboard/lessons/upload-quiz/`
- **Method**: GET, POST
- **Purpose**: Upload quiz from CSV/PDF file or generate with AI
- **POST Parameters**:
  - `lesson_id`: Lesson ID (required)
  - `generation_method`: 'upload' or 'ai'
  - `quiz_file`: File upload (for CSV/PDF)
  - `num_questions`: Number of questions (for AI generation)
- **Returns**: Redirects to quiz page on success

### Student Management

#### `dashboard_students(request)`
- **URL**: `/dashboard/students/`
- **Method**: GET
- **Purpose**: Smart student list with activity updates and filtering
- **Query Parameters**:
  - `course`: Filter by course ID
  - `status`: Filter by status (all, active, completed, certified)
  - `search`: Search by username, email, first name, last name
  - `sort`: Sort by (recent, progress, name, enrolled)
- **Returns**: List of students with:
  - Total courses enrolled
  - Total lessons and completed lessons
  - Overall progress percentage
  - Certifications count
  - Recent activity
  - Status (active, completed, certified, inactive)
  - Activity feed

#### `dashboard_student_progress(request)`
- **URL**: `/dashboard/students/progress/`
- **Method**: GET
- **Purpose**: Student progress overview - all students
- **Query Parameters**:
  - `course`: Filter by course ID
  - `search`: Search by username, email, or course name
- **Returns**: List of enrollments with:
  - Total lessons and completed lessons
  - Progress percentage
  - Certification status

#### `dashboard_student_detail(request, user_id, course_slug=None)`
- **URL**: `/dashboard/students/<user_id>/` or `/dashboard/students/<user_id>/<course_slug>/`
- **Method**: GET
- **Purpose**: Detailed student progress view
- **Returns**: Student detail page with:
  - All courses the student is enrolled in
  - Lesson progress for each course
  - Exam attempts
  - Certification status
  - Course access records
  - Access management options (grant/revoke access, add to cohort, grant bundle)

#### `dashboard_course_progress(request, course_slug)`
- **URL**: `/dashboard/courses/<slug>/progress/`
- **Method**: GET
- **Purpose**: View all student progress for a specific course
- **Returns**: List of students with:
  - Progress percentage
  - Average video watch percentage
  - Exam attempts count
  - Passed exam status
  - Certification status

### Access Management

#### `grant_course_access_view(request, user_id)`
- **URL**: `/dashboard/students/<user_id>/grant-access/`
- **Method**: POST
- **Purpose**: Grant course access to a student
- **POST Parameters**:
  - `course_id`: Course ID (required)
  - `access_type`: Access type (default: 'manual')
  - `expires_in_days`: Number of days until expiration (optional)
  - `notes`: Notes (optional)
- **Returns**: JSON response with success status

#### `revoke_course_access_view(request, user_id)`
- **URL**: `/dashboard/students/<user_id>/revoke-access/`
- **Method**: POST
- **Purpose**: Revoke course access from a student
- **POST Parameters**:
  - `course_id`: Course ID (required)
  - `reason`: Reason for revocation (optional)
  - `notes`: Notes (optional)
- **Returns**: JSON response with success status

#### `grant_bundle_access_view(request, user_id)`
- **URL**: `/dashboard/students/<user_id>/grant-bundle/`
- **Method**: POST
- **Purpose**: Grant bundle access to a student
- **POST Parameters**:
  - `bundle_id`: Bundle ID (required)
  - `purchase_id`: Purchase ID (optional)
  - `notes`: Notes (optional)
- **Returns**: JSON response with success status and number of courses unlocked

#### `add_to_cohort_view(request, user_id)`
- **URL**: `/dashboard/students/<user_id>/add-cohort/`
- **Method**: POST
- **Purpose**: Add student to a cohort
- **POST Parameters**:
  - `cohort_id`: Cohort ID (required)
- **Returns**: JSON response with success status

#### `bulk_access_management(request)`
- **URL**: `/dashboard/access/bulk/`
- **Method**: GET
- **Purpose**: Bulk access management page
- **Returns**: Page with options to grant access to multiple students and courses

#### `bulk_grant_access_view(request)`
- **URL**: `/dashboard/access/bulk/grant/`
- **Method**: POST
- **Purpose**: Bulk grant course access to multiple students
- **POST Parameters**:
  - `user_ids[]`: Array of user IDs (required)
  - `course_ids[]`: Array of course IDs (required)
  - `access_type`: Access type (default: 'manual')
  - `expires_in_days`: Number of days until expiration (optional)
  - `notes`: Notes (optional)
- **Returns**: JSON response with success status and count of granted accesses

### Bundle Management

#### `dashboard_bundles(request)`
- **URL**: `/dashboard/bundles/`
- **Method**: GET
- **Purpose**: List all bundles
- **Returns**: List of bundles with course count and purchase count

#### `dashboard_add_bundle(request)`
- **URL**: `/dashboard/bundles/add/`
- **Method**: GET, POST
- **Purpose**: Create a new bundle
- **POST Parameters**:
  - `name`: Bundle name (required)
  - `description`: Bundle description
  - `bundle_type`: Bundle type ('fixed' or 'custom')
  - `price`: Price (optional)
  - `is_active`: Active status (checkbox)
  - `max_course_selections`: Maximum course selections (optional)
  - `courses[]`: Array of course IDs
- **Returns**: Redirects to bundles list on success

#### `dashboard_edit_bundle(request, bundle_id)`
- **URL**: `/dashboard/bundles/<id>/edit/`
- **Method**: GET, POST
- **Purpose**: Edit an existing bundle
- **POST Parameters**: Same as `dashboard_add_bundle`
- **Returns**: Redirects to bundles list on success

#### `dashboard_delete_bundle(request, bundle_id)`
- **URL**: `/dashboard/bundles/<id>/delete/`
- **Method**: POST
- **Purpose**: Delete a bundle
- **Returns**: Redirects to bundles list with success/error message (prevents deletion if bundle has purchases)

### Helper Functions (Admin)

#### `get_student_activity_feed(limit=20)`
- **Purpose**: Get a comprehensive activity feed of all student activities
- **Parameters**:
  - `limit`: Maximum number of activities to return (default: 20)
- **Returns**: List of activities including:
  - Lesson completions
  - Exam attempts
  - Certifications issued
  - Progress updates
- **Activity Types**: 'lesson_completed', 'exam_attempt', 'certification_issued', 'progress_update'

#### `parse_csv_quiz(uploaded_file, quiz)`
- **Purpose**: Parse CSV file and create quiz questions
- **Parameters**:
  - `uploaded_file`: CSV file object
  - `quiz`: LessonQuiz object
- **CSV Format**: question, option_a, option_b, option_c, option_d, correct_answer
- **Returns**: Number of questions created

#### `generate_ai_quiz(lesson, quiz, num_questions=5)`
- **Purpose**: Generate quiz questions using AI based on lesson content
- **Parameters**:
  - `lesson`: Lesson object
  - `quiz`: LessonQuiz object
  - `num_questions`: Number of questions to generate (default: 5)
- **Returns**: Number of questions created
- **Requirements**: OpenAI API key must be set in environment

#### `parse_pdf_quiz(uploaded_file, quiz)`
- **Purpose**: Parse PDF file and create quiz questions
- **Parameters**:
  - `uploaded_file`: PDF file object
  - `quiz`: LessonQuiz object
- **Returns**: Number of questions created
- **Requirements**: PyMuPDF (fitz) must be installed

#### `generate_slug(text)`
- **Purpose**: Generate URL-friendly slug from text
- **Parameters**:
  - `text`: Text to convert to slug
- **Returns**: URL-friendly slug string

---

## Student Functions

All student functions are located in `myApp/views.py` and require `@login_required` decorator (except public views).

### Public Views

#### `home(request)`
- **URL**: `/`
- **Method**: GET
- **Purpose**: Home page - shows courses hub (premium landing)
- **Returns**: Landing page with:
  - All active public courses
  - Courses grouped by categories (Natural Health, Personal Development, Energy Therapies)
  - Featured courses
  - Course progress and favorite status (if authenticated)

#### `login_view(request)`
- **URL**: `/login/`
- **Method**: GET, POST
- **Purpose**: User authentication
- **POST Parameters**:
  - `username`: Username
  - `password`: Password
- **Returns**: Redirects to student dashboard on success, or login page with error

#### `logout_view(request)`
- **URL**: `/logout/`
- **Method**: GET
- **Purpose**: User logout
- **Returns**: Redirects to login page with success message

#### `courses(request)`
- **URL**: `/courses/`
- **Method**: GET
- **Purpose**: Course catalog page
- **Query Parameters**:
  - `type`: Filter by course type (default: 'all')
  - `search`: Search by course name
- **Returns**: Course listing page with:
  - Courses separated into "Continue Learning" and "Learn More" sections
  - Progress percentage for each course
  - Favorite status
  - Filtering and sorting options

#### `course_detail(request, course_slug)`
- **URL**: `/courses/<slug>/`
- **Method**: GET
- **Purpose**: Course detail page - premium sales page
- **Returns**: 
  - If user is authenticated and has access: Redirects to first lesson
  - Otherwise: Premium sales page for the course

### Lesson Views

#### `lesson_detail(request, course_slug, lesson_slug)`
- **URL**: `/courses/<slug>/<lesson_slug>/`
- **Method**: GET
- **Purpose**: Lesson detail page with three-column layout
- **Returns**: Lesson page with:
  - Video player (Vimeo/Google Drive/Cloudinary)
  - Lesson content and description
  - Progress tracking
  - Lesson completion status
  - Next/Previous lesson navigation
  - Quiz link (if available)
  - AI chatbot integration
  - Lesson locking (requires previous lessons to be completed)

#### `lesson_quiz_view(request, course_slug, lesson_slug)`
- **URL**: `/courses/<slug>/<lesson_slug>/quiz/`
- **Method**: GET, POST
- **Purpose**: Display and submit lesson quiz
- **POST Parameters**:
  - `q_<question_id>`: Selected answer for each question
- **Returns**: Quiz page with:
  - Multiple-choice questions
  - Score calculation
  - Pass/fail determination
  - Results display
  - Next lesson link (if passed)

### Student Dashboard

#### `student_dashboard(request)`
- **URL**: `/my-dashboard/`
- **Method**: GET
- **Purpose**: Student's personal dashboard
- **Query Parameters**:
  - `favorites`: Filter by favorites ('true')
  - `sort`: Sort by (progress, favorites, name)
- **Returns**: Dashboard with:
  - Overall stats (courses enrolled, completed, lessons completed, overall progress)
  - "My Courses" section with:
    - Progress percentage per course
    - Average video watch percentage
    - Exam info (attempts, passed status, availability)
    - Certification status
    - Favorite toggle
    - "Continue Learning" vs "Start Course" buttons
  - "Available to Unlock" section (courses that can be unlocked)
  - "Not Available" section (courses not accessible)
  - Filter by favorites
  - Sort options

#### `student_course_progress(request, course_slug)`
- **URL**: `/my-dashboard/course/<slug>/`
- **Method**: GET
- **Purpose**: Detailed progress view for a specific course
- **Returns**: Course progress page with:
  - All lessons with individual progress
  - Watch percentage per lesson
  - Lesson status (not_started, in_progress, completed)
  - Last accessed timestamp
  - Overall course progress percentage
  - Exam info and attempts
  - Certification status
  - Exam availability

#### `student_certifications(request)`
- **URL**: `/my-certifications/`
- **Method**: GET
- **Purpose**: View all certifications
- **Returns**: Certifications page with:
  - All certifications earned by the student
  - Eligible courses (completed but no certification yet)

#### `view_certificate(request, course_slug)`
- **URL**: `/certificate/<slug>/`
- **Method**: GET
- **Purpose**: View certificate for a course
- **Returns**: Certificate display page

### API Endpoints (Student)

#### `update_video_progress(request, lesson_id)`
- **URL**: `/api/lessons/<id>/progress/`
- **Method**: POST
- **Purpose**: Update video watch progress
- **POST Parameters** (JSON):
  - `watch_percentage`: Video watch percentage (0-100)
  - `last_watched_timestamp`: Last watched timestamp in seconds
  - `status`: Progress status ('not_started', 'in_progress', 'completed')
- **Returns**: JSON response with success status

#### `complete_lesson(request, lesson_id)`
- **URL**: `/api/lessons/<id>/complete/`
- **Method**: POST
- **Purpose**: Mark lesson as completed
- **POST Parameters** (JSON):
  - `watch_percentage`: Final video watch percentage
- **Returns**: JSON response with:
  - Success status
  - Next lesson info (if available)
  - Course completion status

#### `toggle_favorite_course(request, course_id)`
- **URL**: `/api/courses/<id>/favorite/`
- **Method**: POST
- **Purpose**: Toggle favorite status for a course
- **Returns**: JSON response with:
  - Success status
  - New favorite status (true/false)

#### `chatbot_webhook(request)`
- **URL**: `/api/chatbot/`
- **Method**: POST
- **Purpose**: AI chatbot integration webhook
- **POST Parameters** (JSON):
  - `action`: Action type (e.g., 'free_form', 'summarize', 'key_points', etc.)
  - `action_text`: Action description
  - `user_message`: User's message
  - `lesson_id`: Lesson ID
  - `lesson_title`: Lesson title
  - `course_name`: Course name
- **Returns**: JSON response with AI-generated content

#### `lesson_chatbot(request, lesson_id)`
- **URL**: `/api/lessons/<id>/chatbot/`
- **Method**: POST
- **Purpose**: Chat with lesson-specific AI chatbot
- **POST Parameters** (JSON):
  - `message`: User's message
- **Returns**: JSON response with chatbot reply

---

## Helper Functions

### Utility Functions

#### `extract_vimeo_id(url)`
- **Purpose**: Extract Vimeo video ID from URL
- **Parameters**:
  - `url`: Vimeo URL
- **Returns**: Vimeo video ID or None

#### `fetch_vimeo_metadata(vimeo_id)`
- **Purpose**: Fetch metadata from Vimeo API
- **Parameters**:
  - `vimeo_id`: Vimeo video ID
- **Returns**: Dictionary with video metadata (title, description, duration, thumbnail)

#### `generate_ai_lesson_content(lesson)`
- **Purpose**: Generate AI content for a lesson
- **Parameters**:
  - `lesson`: Lesson object
- **Returns**: Dictionary with generated content

#### `format_duration(seconds)`
- **Purpose**: Format duration in seconds to human-readable format
- **Parameters**:
  - `seconds`: Duration in seconds
- **Returns**: Formatted duration string (e.g., "1h 23m")

---

## Notes

- All admin functions require staff member authentication (`@staff_member_required`)
- All student functions (except public views) require user authentication (`@login_required`)
- API endpoints return JSON responses
- Most POST endpoints include CSRF protection
- Error handling is implemented throughout with appropriate error messages
- Progress tracking is automatic when students watch videos
- Course access is managed through the access control system (CourseAccess model)
- Legacy enrollment system (CourseEnrollment) is still supported for backward compatibility

---

## Function Categories Summary

### Admin Functions (Total: 30+)
- Dashboard Overview: 2 functions
- Course Management: 5 functions
- Lesson Management: 4 functions
- Quiz Management: 4 functions
- Student Management: 4 functions
- Access Management: 6 functions
- Bundle Management: 4 functions
- Helper Functions: 5+ functions

### Student Functions (Total: 15+)
- Public Views: 5 functions
- Lesson Views: 2 functions
- Student Dashboard: 4 functions
- API Endpoints: 5+ functions

---

*Last Updated: Based on current codebase structure*

