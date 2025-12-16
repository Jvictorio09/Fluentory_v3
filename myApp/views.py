from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.conf import settings
from datetime import datetime
import json
import re
import requests
import os
import threading
from .models import (
    Course,
    Lesson,
    Module,
    UserProgress,
    CourseEnrollment,
    Exam,
    ExamAttempt,
    Certification,
    LessonQuiz,
    LessonQuizQuestion,
    LessonQuizAttempt,
)
from django.db.models import Avg, Count, Q
from django.db import models
from .utils.transcription import transcribe_video


def home(request):
    """Home page view - shows landing page for non-authenticated, redirects authenticated users"""
    if request.user.is_authenticated:
        return redirect('courses')
    return render(request, 'landing.html')


def login_view(request):
    """Premium login page"""
    # Allow access to login page even when logged in if ?force=true (for testing)
    force = request.GET.get('force', '').lower() == 'true'
    if request.user.is_authenticated and not force:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next', 'home')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'login.html')


def logout_view(request):
    """Logout view"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


def courses(request):
    """Courses listing page"""
    course_type = request.GET.get('type', 'all')
    search_query = request.GET.get('search', '')
    
    courses = Course.objects.all()
    
    if course_type != 'all':
        courses = courses.filter(course_type=course_type)
    
    if search_query:
        courses = courses.filter(name__icontains=search_query)
    
    return render(request, 'courses.html', {
        'courses': courses,
        'selected_type': course_type,
        'search_query': search_query,
    })


@login_required
def course_detail(request, course_slug):
    """Course detail page - redirects to first lesson or course overview"""
    course = get_object_or_404(Course, slug=course_slug)
    first_lesson = course.lessons.first()
    
    if first_lesson:
        return lesson_detail(request, course_slug, first_lesson.slug)
    
    return render(request, 'course_detail.html', {
        'course': course,
    })


@login_required
def lesson_detail(request, course_slug, lesson_slug):
    """Lesson detail page with three-column layout"""
    course = get_object_or_404(Course, slug=course_slug)
    lesson = get_object_or_404(Lesson, course=course, slug=lesson_slug)
    
    # Get user progress
    enrollment = CourseEnrollment.objects.filter(
        user=request.user, 
        course=course
    ).first()
    
    progress_percentage = course.get_user_progress(request.user)
    completed_lessons = list(
        UserProgress.objects.filter(
            user=request.user,
            lesson__course=course,
            completed=True
        ).values_list('lesson_id', flat=True)
    )
    
    # Get current lesson progress
    current_lesson_progress = UserProgress.objects.filter(
        user=request.user,
        lesson=lesson
    ).first()
    
    video_watch_percentage = current_lesson_progress.video_watch_percentage if current_lesson_progress else 0.0
    last_watched_timestamp = current_lesson_progress.last_watched_timestamp if current_lesson_progress else 0.0
    lesson_status = current_lesson_progress.status if current_lesson_progress else 'not_started'
    
    # Get all lessons ordered by order field
    all_lessons = course.lessons.order_by('order', 'id')
    
    # Determine which lessons are accessible
    accessible_lessons = []
    # First lesson is always accessible
    if all_lessons.exists():
        first_lesson = all_lessons.first()
        accessible_lessons.append(first_lesson.id)
        
        # For each subsequent lesson, check if all previous lessons are completed
        for current_lesson in all_lessons[1:]:
            # Get all previous lessons (with lower order or same order but lower id)
            previous_lessons = all_lessons.filter(
                models.Q(order__lt=current_lesson.order) |
                models.Q(order=current_lesson.order, id__lt=current_lesson.id)
            )
            
            # Check if all previous lessons are completed
            all_previous_completed = True
            for prev_lesson in previous_lessons:
                if prev_lesson.id not in completed_lessons:
                    all_previous_completed = False
                    break
            
            if all_previous_completed:
                accessible_lessons.append(current_lesson.id)
        
        # Check if current lesson is locked
        lesson_locked = lesson.id not in accessible_lessons
        
        # If lesson is locked, redirect to first incomplete lesson or show message
        if lesson_locked:
            # Find first incomplete lesson
            first_incomplete = None
            for l in all_lessons:
                if l.id not in completed_lessons:
                    first_incomplete = l
                    break
            
            if first_incomplete:
                messages.warning(request, 'Please complete previous lessons before accessing this one.')
                return redirect('lesson_detail', course_slug=course_slug, lesson_slug=first_incomplete.slug)
            else:
                messages.info(request, 'All lessons completed!')
    
    # Work out next lesson (for auto-advance after completion)
    next_lesson = None
    if all_lessons.exists():
        lessons_list = list(all_lessons)
        for idx, l in enumerate(lessons_list):
            if l.id == lesson.id and idx + 1 < len(lessons_list):
                next_lesson = lessons_list[idx + 1]
                break

    return render(request, 'lesson.html', {
        'course': course,
        'lesson': lesson,
        'progress_percentage': progress_percentage,
        'completed_lessons': completed_lessons,
        'accessible_lessons': accessible_lessons,
        'enrollment': enrollment,
        'current_lesson_progress': current_lesson_progress,
        'video_watch_percentage': video_watch_percentage,
        'last_watched_timestamp': last_watched_timestamp,
        'lesson_status': lesson_status,
        'next_lesson': next_lesson,
        'lesson_quiz': getattr(lesson, 'quiz', None),
    })


@login_required
def lesson_quiz_view(request, course_slug, lesson_slug):
    """Simple multiple‑choice quiz attached to a lesson (optional)."""
    course = get_object_or_404(Course, slug=course_slug)
    lesson = get_object_or_404(Lesson, course=course, slug=lesson_slug)

    # Require that a quiz exists for this lesson
    try:
        quiz = lesson.quiz
    except LessonQuiz.DoesNotExist:
        messages.info(request, 'No quiz is configured for this lesson yet.')
        return redirect('lesson_detail', course_slug=course_slug, lesson_slug=lesson_slug)

    questions = quiz.questions.all()
    result = None

    if request.method == 'POST':
        total = questions.count()
        correct = 0
        for q in questions:
            answer = request.POST.get(f'q_{q.id}')
            if answer and answer == q.correct_option:
                correct += 1

        score = (correct / total * 100) if total > 0 else 0
        passed = score >= quiz.passing_score

        LessonQuizAttempt.objects.create(
            user=request.user,
            quiz=quiz,
            score=score,
            passed=passed,
        )

        result = {
            'score': round(score, 1),
            'passed': passed,
            'correct': correct,
            'total': total,
        }

    return render(request, 'lesson_quiz.html', {
        'course': course,
        'lesson': lesson,
        'quiz': quiz,
        'questions': questions,
        'result': result,
    })


# ========== CREATOR DASHBOARD VIEWS ==========

@staff_member_required
def creator_dashboard(request):
    """Main creator dashboard"""
    courses = Course.objects.all()
    return render(request, 'creator/dashboard.html', {
        'courses': courses,
    })


@staff_member_required
def course_lessons(request, course_slug):
    """View all lessons for a course"""
    course = get_object_or_404(Course, slug=course_slug)
    lessons = course.lessons.all()
    modules = course.modules.all()
    
    return render(request, 'creator/course_lessons.html', {
        'course': course,
        'lessons': lessons,
        'modules': modules,
    })


@staff_member_required
def add_lesson(request, course_slug):
    """Add new lesson - 3-step flow with video upload and transcription"""
    course = get_object_or_404(Course, slug=course_slug)
    
    if request.method == 'POST':
        # Handle form submission
        vimeo_url = request.POST.get('vimeo_url', '')
        working_title = request.POST.get('working_title', '')
        rough_notes = request.POST.get('rough_notes', '')
        transcription = request.POST.get('transcription', '')
        
        # Extract Vimeo ID
        vimeo_id = extract_vimeo_id(vimeo_url) if vimeo_url else None
        
        # Create lesson draft
        lesson = Lesson.objects.create(
            course=course,
            working_title=working_title,
            rough_notes=rough_notes,
            title=working_title,  # Temporary
            slug=generate_slug(working_title),
            description='',  # Will be AI-generated
        )
        
        # Handle Vimeo URL if provided
        if vimeo_id:
            vimeo_data = fetch_vimeo_metadata(vimeo_id)
            lesson.vimeo_url = vimeo_url
            lesson.vimeo_id = vimeo_id
            lesson.vimeo_thumbnail = vimeo_data.get('thumbnail', '')
            lesson.vimeo_duration_seconds = vimeo_data.get('duration', 0)
            lesson.video_duration = vimeo_data.get('duration', 0) // 60
        
        # Handle video file upload and transcription (temporary - not saved)
        if 'video_file' in request.FILES:
            video_file = request.FILES['video_file']
            # Don't save video_file to lesson - only use for transcription
            lesson.transcription_status = 'processing'
            lesson.save()
            
            # Start transcription in background (video will be deleted after)
            def process_transcription():
                import tempfile
                temp_path = None
                try:
                    # Save to temporary file (not in media folder)
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
                        for chunk in video_file.chunks():
                            temp_file.write(chunk)
                        temp_path = temp_file.name
                    
                    # Transcribe from temporary file
                    result = transcribe_video(temp_path)
                    
                    # Update lesson with transcription
                    lesson.transcription_status = 'completed' if result['success'] else 'failed'
                    lesson.transcription = result.get('transcription', '')
                    lesson.transcription_error = result.get('error', '')
                    lesson.save()
                except Exception as e:
                    lesson.transcription_status = 'failed'
                    lesson.transcription_error = str(e)
                    lesson.save()
                finally:
                    # Always delete temporary video file
                    if temp_path and os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except:
                            pass
            
            # Run transcription in background thread
            thread = threading.Thread(target=process_transcription)
            thread.daemon = True
            thread.start()
        elif transcription:
            # If transcription was manually edited, save it
            lesson.transcription = transcription
            lesson.transcription_status = 'completed'
        
        lesson.save()
        return redirect('generate_lesson_ai', course_slug=course_slug, lesson_id=lesson.id)
    
    return render(request, 'creator/add_lesson.html', {
        'course': course,
    })


@staff_member_required
def generate_lesson_ai(request, course_slug, lesson_id):
    """Generate AI content for lesson"""
    course = get_object_or_404(Course, slug=course_slug)
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'generate':
            # Generate AI content
            ai_content = generate_ai_lesson_content(lesson)
            
            lesson.ai_clean_title = ai_content.get('clean_title', lesson.working_title)
            lesson.ai_short_summary = ai_content.get('short_summary', '')
            lesson.ai_full_description = ai_content.get('full_description', '')
            lesson.ai_outcomes = ai_content.get('outcomes', [])
            lesson.ai_coach_actions = ai_content.get('coach_actions', [])
            lesson.ai_generation_status = 'generated'
            lesson.save()
            
        elif action == 'approve':
            # Approve and finalize lesson
            lesson.title = lesson.ai_clean_title or lesson.working_title
            lesson.description = lesson.ai_full_description
            lesson.slug = generate_slug(lesson.title)
            lesson.ai_generation_status = 'approved'
            lesson.save()
            
            return redirect('course_lessons', course_slug=course_slug)
        
        elif action == 'edit':
            # Update with manual edits
            lesson.ai_clean_title = request.POST.get('clean_title', lesson.ai_clean_title)
            lesson.ai_short_summary = request.POST.get('short_summary', lesson.ai_short_summary)
            lesson.ai_full_description = request.POST.get('full_description', lesson.ai_full_description)
            
            # Parse outcomes
            outcomes_text = request.POST.get('outcomes', '')
            if outcomes_text:
                lesson.ai_outcomes = [o.strip() for o in outcomes_text.split('\n') if o.strip()]
            
            lesson.save()
    
    return render(request, 'creator/generate_lesson_ai.html', {
        'course': course,
        'lesson': lesson,
    })


@require_http_methods(["POST"])
@staff_member_required
def verify_vimeo_url(request):
    """AJAX endpoint to verify Vimeo URL and fetch metadata"""
    vimeo_url = request.POST.get('vimeo_url', '')
    vimeo_id = extract_vimeo_id(vimeo_url)
    
    if not vimeo_id:
        return JsonResponse({
            'success': False,
            'error': 'Invalid Vimeo URL format'
        })
    
    vimeo_data = fetch_vimeo_metadata(vimeo_id)
    
    if vimeo_data:
        return JsonResponse({
            'success': True,
            'vimeo_id': vimeo_id,
            'thumbnail': vimeo_data.get('thumbnail', ''),
            'duration': vimeo_data.get('duration', 0),
            'duration_formatted': format_duration(vimeo_data.get('duration', 0)),
            'title': vimeo_data.get('title', ''),
        })
    
    return JsonResponse({
        'success': False,
        'error': 'Could not fetch video metadata'
    })


@require_http_methods(["POST"])
@staff_member_required
def upload_video_transcribe(request):
    """AJAX endpoint to upload video and start transcription - video is NOT saved, only used temporarily"""
    if 'video_file' not in request.FILES:
        return JsonResponse({
            'success': False,
            'error': 'No video file provided'
        })
    
    video_file = request.FILES['video_file']
    
    # Validate file type
    if not video_file.name.lower().endswith('.mp4'):
        return JsonResponse({
            'success': False,
            'error': 'Please upload an MP4 video file'
        })
    
    # Validate file size (500MB limit)
    if video_file.size > 500 * 1024 * 1024:
        return JsonResponse({
            'success': False,
            'error': 'File size exceeds 500MB limit'
        })
    
    # Use system temp directory (not media folder) - will be deleted after transcription
    import tempfile
    temp_path = None
    
    try:
        # Save to system temporary file (outside media folder)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
            for chunk in video_file.chunks():
                temp_file.write(chunk)
            temp_path = temp_file.name
        
        # Transcribe from temporary file
        result = transcribe_video(temp_path)
        
        # Always delete temporary video file (we don't save videos)
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        
        if result['success']:
            return JsonResponse({
                'success': True,
                'transcription': result['transcription'],
                'status': 'completed'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Transcription failed')
            })
    except Exception as e:
        # Clean up temp file on error
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@require_http_methods(["POST"])
@staff_member_required
def check_transcription_status(request, lesson_id):
    """AJAX endpoint to check transcription status"""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    
    return JsonResponse({
        'status': lesson.transcription_status,
        'transcription': lesson.transcription,
        'error': lesson.transcription_error
    })


# ========== HELPER FUNCTIONS ==========

def extract_vimeo_id(url):
    """Extract Vimeo video ID from URL"""
    if not url:
        return None
    
    # Pattern: https://vimeo.com/123456789 or https://vimeo.com/123456789?param=value
    pattern = r'vimeo\.com/(\d+)'
    match = re.search(pattern, url)
    
    if match:
        return match.group(1)
    return None


def fetch_vimeo_metadata(vimeo_id):
    """Fetch metadata from Vimeo API (using oEmbed endpoint)"""
    try:
        oembed_url = f"https://vimeo.com/api/oembed.json?url=https://vimeo.com/{vimeo_id}"
        response = requests.get(oembed_url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'title': data.get('title', ''),
                'thumbnail': data.get('thumbnail_url', ''),
                'duration': data.get('duration', 0),
            }
    except Exception as e:
        print(f"Error fetching Vimeo metadata: {e}")
    
    return {}


def generate_ai_lesson_content(lesson):
    """Generate AI content for lesson (placeholder - connect to OpenAI later)"""
    # This is a placeholder - in production, connect to OpenAI API
    # For now, generate basic content based on working title and notes
    
    working_title = lesson.working_title or "Lesson"
    rough_notes = lesson.rough_notes or ""
    
    # Generate clean title
    clean_title = working_title.title()
    if "session" in clean_title.lower():
        clean_title = clean_title.replace("Session", "Session").replace("session", "Session")
    
    # Generate short summary
    short_summary = f"A strategic session covering key concepts from {working_title}. "
    if rough_notes:
        short_summary += "Focuses on practical implementation and actionable insights."
    else:
        short_summary += "Designed to accelerate your progress and build real assets."
    
    # Generate full description
    full_description = f"In this session, you'll dive deep into {working_title}. "
    if rough_notes:
        full_description += f"{rough_notes[:200]}... "
    full_description += "You'll learn practical strategies, implement key frameworks, and walk away with tangible outputs that move your business forward."
    
    # Generate outcomes (placeholder - should be AI-generated based on content)
    outcomes = [
        "Clear action plan for immediate implementation",
        "Key frameworks and strategies from the session",
        "Personalized insights tailored to your offer",
        "Next steps checklist for continued progress"
    ]
    
    # Generate coach actions
    coach_actions = [
        "Summarize in 5 bullets",
        "Turn this into a 3-step action plan",
        "Generate 3 email hooks from this content",
        "Give me a comprehension quiz"
    ]
    
    return {
        'clean_title': clean_title,
        'short_summary': short_summary,
        'full_description': full_description,
        'outcomes': outcomes,
        'coach_actions': coach_actions,
    }


def generate_slug(text):
    """Generate URL-friendly slug from text"""
    import unicodedata
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


def format_duration(seconds):
    """Format seconds as MM:SS"""
    if not seconds:
        return "0:00"
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


# ========== CHATBOT WEBHOOK ==========

@require_http_methods(["POST"])
@login_required
def update_video_progress(request, lesson_id):
    """Update video watch progress for a lesson"""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    
    try:
        data = json.loads(request.body)
        watch_percentage = float(data.get('watch_percentage', 0))
        timestamp = float(data.get('timestamp', 0))
        
        # Get or create UserProgress
        user_progress, created = UserProgress.objects.get_or_create(
            user=request.user,
            lesson=lesson,
            defaults={
                'video_watch_percentage': watch_percentage,
                'last_watched_timestamp': timestamp,
                'progress_percentage': int(watch_percentage)
            }
        )
        
        # Update progress
        if not created:
            user_progress.video_watch_percentage = watch_percentage
            user_progress.last_watched_timestamp = timestamp
            user_progress.progress_percentage = int(watch_percentage)
        
        # Auto-update status based on watch progress
        user_progress.update_status()
        
        return JsonResponse({
            'success': True,
            'watch_percentage': user_progress.video_watch_percentage,
            'status': user_progress.status,
            'completed': user_progress.completed
        })
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        return JsonResponse({'error': f'Invalid data: {str(e)}'}, status=400)


@require_http_methods(["POST"])
@login_required
def complete_lesson(request, lesson_id):
    """Mark a lesson as complete for the current user.

    NOTE: Video watch-percentage checks have been intentionally disabled so that
    the user can complete a lesson at any time by clicking the Finish button.
    """
    lesson = get_object_or_404(Lesson, id=lesson_id)
    
    # Get or create UserProgress
    user_progress, created = UserProgress.objects.get_or_create(
        user=request.user,
        lesson=lesson
    )

    # Mark as completed
    user_progress.completed = True
    user_progress.status = 'completed'
    user_progress.completed_at = datetime.now()
    user_progress.progress_percentage = 100
    user_progress.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Lesson marked as complete',
        'lesson_id': lesson_id
    })


@require_http_methods(["POST"])
@login_required
def chatbot_webhook(request):
    """Forward chatbot messages to the appropriate webhook based on lesson"""
    # Default webhook URL
    DEFAULT_WEBHOOK_URL = "https://kane-course-website.fly.dev/webhook/12e91cca-0e58-4769-9f11-68399ec2f970"
    
    # Lesson-specific webhook URLs
    LESSON_WEBHOOKS = {
        2: "https://kane-course-website.fly.dev/webhook/7d81ca5f-0033-4a9c-8b75-ae44005f8451",
        3: "https://kane-course-website.fly.dev/webhook/258fb5ce-b70f-48a7-b8b6-f6b0449ddbeb",
        4: "https://kane-course-website.fly.dev/webhook/19fd5879-7fc0-437d-9953-65bb70526c0b",
        5: "https://kane-course-website.fly.dev/webhook/bab1f0ef-b5bc-415f-8f73-88cc31c5c75a",
        6: "https://kane-course-website.fly.dev/webhook/6ed2483b-9c8d-4c20-85e4-432fbf033ad8",
        7: "https://kane-course-website.fly.dev/webhook/400f7a4d-3731-4ed0-90f1-35157579c7b0",
        8: "https://kane-course-website.fly.dev/webhook/0b6fee4a-bb9a-46da-831c-7d20ec7dd627",
        9: "https://kane-course-website.fly.dev/webhook/4c79ba33-2660-4816-9526-8e3513aad427",
        10: "https://kane-course-website.fly.dev/webhook/0373896c-d889-4f72-ba42-83ad6857a5e1",
        11: "https://kane-course-website.fly.dev/webhook/a571ba83-d96d-46c0-a88c-71416eda82a3",
        12: "https://kane-course-website.fly.dev/webhook/97427f57-0e89-4da3-846a-1e4453f8a58c",
    }
    
    try:
        # Get the request data
        data = json.loads(request.body)
        
        # Ensure we have a Django session and attach its ID
        if not request.session.session_key:
            request.session.save()
        data['session_id'] = request.session.session_key
        
        # Enrich payload with course/lesson code for downstream processing,
        # e.g. "virtualrockstar_session1"
        lesson_id = data.get('lesson_id')
        if lesson_id:
            try:
                lesson_obj = Lesson.objects.select_related('course').get(id=lesson_id)
                course_slug = (lesson_obj.course.slug or '').replace('-', '').replace(' ', '').lower()
                lesson_slug = (lesson_obj.slug or '').replace('-', '').replace(' ', '').lower()
                if course_slug and lesson_slug:
                    data['course_lesson_code'] = f"{course_slug}_{lesson_slug}"
            except Lesson.DoesNotExist:
                pass
        
        # Determine which webhook URL to use based on lesson_id
        webhook_url = LESSON_WEBHOOKS.get(lesson_id, DEFAULT_WEBHOOK_URL)
        
        # Forward to the webhook
        response = requests.post(
            webhook_url,
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        # Return the response from the webhook
        # Frontend treats any "error" key as a hard error, so we avoid using that
        # here and always surface the upstream payload as a normal response.
        try:
            upstream_payload = response.json()
        except ValueError:
            upstream_payload = response.text

        # Extract a clean text message for the frontend chat UI.
        message_text = None
        if isinstance(upstream_payload, dict):
            # Many of your test webhooks wrap like: {"Response": {"output": "..."}}.
            inner = upstream_payload.get('Response', upstream_payload)
            if isinstance(inner, dict):
                message_text = (
                    inner.get('output')
                    or inner.get('message')
                    or inner.get('response')
                )
        if not message_text:
            message_text = str(upstream_payload)

        # Frontend expects `data.response` to be the text to display.
        return JsonResponse({'response': message_text}, status=200)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except requests.RequestException as e:
        return JsonResponse({'error': str(e)}, status=500)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ========== STUDENT DASHBOARD (CLIENT VIEW) ==========

@login_required
def student_dashboard(request):
    """Student dashboard - overview of all enrolled courses and progress"""
    user = request.user
    
    # Get all enrollments; if none exist, auto-enroll the user into all active courses
    enrollments = CourseEnrollment.objects.filter(user=user).select_related('course')
    if not enrollments.exists():
        for course in Course.objects.filter(status='active'):
            CourseEnrollment.objects.get_or_create(user=user, course=course)
        enrollments = CourseEnrollment.objects.filter(user=user).select_related('course')
    
    course_data = []
    for enrollment in enrollments:
        course = enrollment.course
        
        # Calculate progress
        total_lessons = course.lessons.count()
        completed_lessons = UserProgress.objects.filter(
            user=user,
            lesson__course=course,
            completed=True
        ).count()
        
        progress_percentage = int((completed_lessons / total_lessons * 100)) if total_lessons > 0 else 0
        
        # Get average video watch percentage
        avg_watch = UserProgress.objects.filter(
            user=user,
            lesson__course=course
        ).aggregate(avg=Avg('video_watch_percentage'))['avg'] or 0
        
        # Get exam info
        exam_info = None
        try:
            exam = Exam.objects.get(course=course)
            exam_attempts = ExamAttempt.objects.filter(user=user, exam=exam).order_by('-started_at')
            latest_attempt = exam_attempts.first()
            exam_info = {
                'exists': True,
                'attempts_count': exam_attempts.count(),
                'max_attempts': exam.max_attempts,
                'latest_attempt': latest_attempt,
                'passed': exam_attempts.filter(passed=True).exists(),
                'is_available': enrollment.is_exam_available(),
            }
        except Exam.DoesNotExist:
            exam_info = {'exists': False}
        
        # Get certification status
        try:
            certification = Certification.objects.get(user=user, course=course)
            cert_status = certification.status
            cert_display = certification.get_status_display()
        except Certification.DoesNotExist:
            cert_status = 'not_eligible' if progress_percentage < 100 else 'eligible'
            cert_display = 'Not Eligible' if progress_percentage < 100 else 'Eligible'
            certification = None
        
        course_data.append({
            'course': course,
            'enrollment': enrollment,
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
            'progress_percentage': progress_percentage,
            'avg_watch_percentage': round(avg_watch, 1),
            'exam_info': exam_info,
            'certification': certification,
            'cert_status': cert_status,
            'cert_display': cert_display,
        })
    
    # Sort by progress (descending)
    course_data.sort(key=lambda x: x['progress_percentage'], reverse=True)
    
    # Overall stats
    total_courses = len(course_data)
    completed_courses = sum(1 for c in course_data if c['progress_percentage'] == 100)
    total_lessons_all = sum(c['total_lessons'] for c in course_data)
    completed_lessons_all = sum(c['completed_lessons'] for c in course_data)
    overall_progress = int((completed_lessons_all / total_lessons_all * 100)) if total_lessons_all > 0 else 0
    
    return render(request, 'student/dashboard.html', {
        'course_data': course_data,
        'total_courses': total_courses,
        'completed_courses': completed_courses,
        'total_lessons_all': total_lessons_all,
        'completed_lessons_all': completed_lessons_all,
        'overall_progress': overall_progress,
    })


@login_required
def student_course_progress(request, course_slug):
    """Detailed progress view for a specific course"""
    course = get_object_or_404(Course, slug=course_slug)
    user = request.user
    
    # Check enrollment
    enrollment = CourseEnrollment.objects.filter(user=user, course=course).first()
    if not enrollment:
        messages.error(request, 'You are not enrolled in this course.')
        return redirect('student_dashboard')
    
    # Get all lessons with progress
    lessons = course.lessons.order_by('order', 'id')
    lesson_progress = []
    
    for lesson in lessons:
        progress = UserProgress.objects.filter(user=user, lesson=lesson).first()
        lesson_progress.append({
            'lesson': lesson,
            'progress': progress,
            'watch_percentage': progress.video_watch_percentage if progress else 0,
            'status': progress.status if progress else 'not_started',
            'completed': progress.completed if progress else False,
            'last_accessed': progress.last_accessed if progress else None,
        })
    
    # Calculate overall progress
    total_lessons = len(lessons)
    completed_lessons = sum(1 for lp in lesson_progress if lp['completed'])
    progress_percentage = int((completed_lessons / total_lessons * 100)) if total_lessons > 0 else 0
    
    # Get exam info
    exam = None
    exam_attempts = []
    try:
        exam = Exam.objects.get(course=course)
        exam_attempts = ExamAttempt.objects.filter(user=user, exam=exam).order_by('-started_at')
    except Exam.DoesNotExist:
        pass
    
    # Get certification
    try:
        certification = Certification.objects.get(user=user, course=course)
    except Certification.DoesNotExist:
        certification = None
    
    return render(request, 'student/course_progress.html', {
        'course': course,
        'enrollment': enrollment,
        'lesson_progress': lesson_progress,
        'total_lessons': total_lessons,
        'completed_lessons': completed_lessons,
        'progress_percentage': progress_percentage,
        'exam': exam,
        'exam_attempts': exam_attempts,
        'certification': certification,
        'is_exam_available': enrollment.is_exam_available(),
    })


@login_required
def student_certifications(request):
    """View all certifications"""
    user = request.user
    
    certifications = Certification.objects.filter(user=user).select_related('course').order_by('-issued_at', '-created_at')
    
    # Get eligible courses (completed but no certification yet)
    enrollments = CourseEnrollment.objects.filter(user=user).select_related('course')
    eligible_courses = []
    
    for enrollment in enrollments:
        total_lessons = enrollment.course.lessons.count()
        completed_lessons = UserProgress.objects.filter(
            user=user,
            lesson__course=enrollment.course,
            completed=True
        ).count()
        
        if completed_lessons >= total_lessons and total_lessons > 0:
            # Check if certification exists
            if not Certification.objects.filter(user=user, course=enrollment.course).exists():
                eligible_courses.append(enrollment.course)
    
    return render(request, 'student/certifications.html', {
        'certifications': certifications,
        'eligible_courses': eligible_courses,
    })
