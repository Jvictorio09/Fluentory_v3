from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Q
from django.core.files.uploadedfile import InMemoryUploadedFile
import json
import re
import requests
import csv
import io
import os
try:
    import fitz  # PyMuPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
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
)
from django.contrib import messages
from django.db import models
from django.contrib.auth.models import User
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone


@staff_member_required
def dashboard_home(request):
    """Main dashboard overview"""
    total_courses = Course.objects.count()
    total_lessons = Lesson.objects.count()
    approved_lessons = Lesson.objects.filter(ai_generation_status='approved').count()
    pending_lessons = Lesson.objects.filter(ai_generation_status='pending').count()
    recent_lessons = Lesson.objects.select_related('course').order_by('-created_at')[:10]
    courses = Course.objects.annotate(lesson_count=Count('lessons')).order_by('-created_at')
    
    # Get student activity feed
    student_activities = get_student_activity_feed(limit=10)
    
    return render(request, 'dashboard/home.html', {
        'total_courses': total_courses,
        'total_lessons': total_lessons,
        'approved_lessons': approved_lessons,
        'pending_lessons': pending_lessons,
        'recent_lessons': recent_lessons,
        'courses': courses,
        'student_activities': student_activities,
    })


@staff_member_required
def dashboard_students(request):
    """Smart student list with activity updates and filtering"""
    # Get filter parameters
    course_filter = request.GET.get('course', '')
    status_filter = request.GET.get('status', 'all')  # all, active, completed, certified
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort', 'recent')  # recent, progress, name, enrolled
    
    # Get all unique students (users with enrollments)
    students_query = User.objects.filter(enrollments__isnull=False).distinct()
    
    # Apply search filter
    if search_query:
        students_query = students_query.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    # Get student data with activity
    students_data = []
    for student in students_query:
        enrollments = CourseEnrollment.objects.filter(user=student).select_related('course')
        
        # Apply course filter
        if course_filter:
            enrollments = enrollments.filter(course_id=course_filter)
        
        if not enrollments.exists():
            continue
        
        # Calculate overall stats
        total_courses = enrollments.count()
        total_lessons_all = 0
        completed_lessons_all = 0
        certifications_count = 0
        recent_activity = None
        
        for enrollment in enrollments:
            course = enrollment.course
            total_lessons = course.lessons.count()
            completed_lessons = UserProgress.objects.filter(
                user=student,
                lesson__course=course,
                completed=True
            ).count()
            total_lessons_all += total_lessons
            completed_lessons_all += completed_lessons
            
            # Check for certification
            if Certification.objects.filter(user=student, course=course, status='passed').exists():
                certifications_count += 1
        
        overall_progress = int((completed_lessons_all / total_lessons_all * 100)) if total_lessons_all > 0 else 0
        
        # Get most recent activity
        recent_progress = UserProgress.objects.filter(user=student).order_by('-last_accessed').first()
        recent_exam = ExamAttempt.objects.filter(user=student).order_by('-started_at').first()
        recent_cert = Certification.objects.filter(user=student).order_by('-issued_at', '-created_at').first()
        
        # Determine most recent activity
        activities = []
        if recent_progress:
            activities.append(('progress', recent_progress.last_accessed, recent_progress))
        if recent_exam:
            activities.append(('exam', recent_exam.started_at, recent_exam))
        if recent_cert and recent_cert.issued_at:
            activities.append(('cert', recent_cert.issued_at, recent_cert))
        
        if activities:
            activities.sort(key=lambda x: x[1], reverse=True)
            recent_activity = activities[0]
        
        # Determine status
        if certifications_count > 0:
            student_status = 'certified'
        elif overall_progress == 100:
            student_status = 'completed'
        elif overall_progress > 0:
            student_status = 'active'
        else:
            student_status = 'inactive'
        
        # Apply status filter
        if status_filter != 'all':
            if status_filter == 'active' and student_status != 'active':
                continue
            elif status_filter == 'completed' and student_status != 'completed':
                continue
            elif status_filter == 'certified' and student_status != 'certified':
                continue
        
        students_data.append({
            'student': student,
            'total_courses': total_courses,
            'total_lessons': total_lessons_all,
            'completed_lessons': completed_lessons_all,
            'overall_progress': overall_progress,
            'certifications_count': certifications_count,
            'recent_activity': recent_activity,
            'status': student_status,
            'enrollments': enrollments,
        })
    
    # Sort students
    if sort_by == 'recent':
        students_data.sort(key=lambda x: x['recent_activity'][1] if x['recent_activity'] else (timezone.now() - timezone.timedelta(days=365)), reverse=True)
    elif sort_by == 'progress':
        students_data.sort(key=lambda x: x['overall_progress'], reverse=True)
    elif sort_by == 'name':
        students_data.sort(key=lambda x: x['student'].username.lower())
    elif sort_by == 'enrolled':
        students_data.sort(key=lambda x: x['student'].date_joined, reverse=True)
    
    # Get activity feed
    activity_feed = get_student_activity_feed(limit=50)
    
    courses = Course.objects.all()
    
    return render(request, 'dashboard/students.html', {
        'students_data': students_data,
        'activity_feed': activity_feed,
        'courses': courses,
        'course_filter': course_filter,
        'status_filter': status_filter,
        'search_query': search_query,
        'sort_by': sort_by,
    })


def get_student_activity_feed(limit=20):
    """Get a comprehensive activity feed of all student activities"""
    activities = []
    
    # Recent lesson completions
    recent_completions = UserProgress.objects.filter(
        completed=True,
        completed_at__isnull=False
    ).select_related('user', 'lesson', 'lesson__course').order_by('-completed_at')[:limit]
    
    for progress in recent_completions:
        activities.append({
            'type': 'lesson_completed',
            'timestamp': progress.completed_at,
            'user': progress.user,
            'course': progress.lesson.course,
            'lesson': progress.lesson,
            'data': {
                'watch_percentage': progress.video_watch_percentage,
            }
        })
    
    # Recent exam attempts
    recent_exams = ExamAttempt.objects.select_related('user', 'exam', 'exam__course').order_by('-started_at')[:limit]
    
    for attempt in recent_exams:
        activities.append({
            'type': 'exam_attempt',
            'timestamp': attempt.started_at,
            'user': attempt.user,
            'course': attempt.exam.course,
            'data': {
                'score': attempt.score,
                'passed': attempt.passed,
                'attempt_number': attempt.attempt_number(),
            }
        })
    
    # Recent certifications
    recent_certs = Certification.objects.filter(
        issued_at__isnull=False
    ).select_related('user', 'course').order_by('-issued_at')[:limit]
    
    for cert in recent_certs:
        activities.append({
            'type': 'certification_issued',
            'timestamp': cert.issued_at,
            'user': cert.user,
            'course': cert.course,
            'data': {
                'certificate_id': cert.accredible_certificate_id,
            }
        })
    
    # Recent progress updates (video watch)
    recent_progress = UserProgress.objects.filter(
        video_watch_percentage__gt=0,
        last_accessed__isnull=False
    ).select_related('user', 'lesson', 'lesson__course').order_by('-last_accessed')[:limit]
    
    for progress in recent_progress:
        # Only add if significant progress (avoid spam)
        if progress.video_watch_percentage >= 50 or progress.completed:
            activities.append({
                'type': 'progress_update',
                'timestamp': progress.last_accessed,
                'user': progress.user,
                'course': progress.lesson.course,
                'lesson': progress.lesson,
                'data': {
                    'watch_percentage': progress.video_watch_percentage,
                    'status': progress.status,
                }
            })
    
    # Sort by timestamp (most recent first)
    activities.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return activities[:limit]


@staff_member_required
def dashboard_courses(request):
    """List all courses"""
    courses = Course.objects.annotate(lesson_count=Count('lessons')).order_by('-created_at')
    return render(request, 'dashboard/courses.html', {
        'courses': courses,
    })


@staff_member_required
def dashboard_course_detail(request, course_slug):
    """Edit course details"""
    course = get_object_or_404(Course, slug=course_slug)
    
    if request.method == 'POST':
        course.name = request.POST.get('name', course.name)
        course.short_description = request.POST.get('short_description', course.short_description)
        course.description = request.POST.get('description', course.description)
        course.status = request.POST.get('status', course.status)
        course.course_type = request.POST.get('course_type', course.course_type)
        course.coach_name = request.POST.get('coach_name', course.coach_name)
        course.save()
        return redirect('dashboard_course_detail', course_slug=course.slug)
    
    return render(request, 'dashboard/course_detail.html', {
        'course': course,
    })


@staff_member_required
@require_http_methods(["POST"])
def dashboard_delete_course(request, course_slug):
    """Delete a course"""
    course = get_object_or_404(Course, slug=course_slug)
    course_name = course.name
    
    try:
        course.delete()
        messages.success(request, f'Course "{course_name}" has been deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting course: {str(e)}')
    
    return redirect('dashboard_courses')


@staff_member_required
def dashboard_lesson_quiz(request, lesson_id):
    """Create and manage a simple quiz for a lesson."""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    quiz, created = LessonQuiz.objects.get_or_create(
        lesson=lesson,
        defaults={
            'title': f'{lesson.title} Quiz',
            'passing_score': 80,
        },
    )

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save_quiz':
            quiz.title = request.POST.get('title') or quiz.title
            quiz.description = request.POST.get('description', '')
            try:
                quiz.passing_score = float(
                    request.POST.get('passing_score') or quiz.passing_score
                )
            except ValueError:
                pass
            quiz.is_required = bool(request.POST.get('is_required'))
            quiz.save()
            messages.success(request, 'Quiz settings updated.')
        elif action == 'add_question':
            text = request.POST.get('q_text', '').strip()
            if text:
                order = (
                    quiz.questions.aggregate(models.Max('order'))['order__max'] or 0
                ) + 1
                LessonQuizQuestion.objects.create(
                    quiz=quiz,
                    text=text,
                    option_a=request.POST.get('q_option_a', '').strip(),
                    option_b=request.POST.get('q_option_b', '').strip(),
                    option_c=request.POST.get('q_option_c', '').strip(),
                    option_d=request.POST.get('q_option_d', '').strip(),
                    correct_option=request.POST.get('q_correct_option', 'A') or 'A',
                    order=order,
                )
                messages.success(request, 'Question added.')
            else:
                messages.error(request, 'Question text is required.')
        elif action == 'delete_question':
            q_id = request.POST.get('question_id')
            if q_id:
                LessonQuizQuestion.objects.filter(id=q_id, quiz=quiz).delete()
                messages.success(request, 'Question deleted.')

        return redirect('dashboard_lesson_quiz', lesson_id=lesson.id)

    questions = LessonQuizQuestion.objects.filter(quiz=quiz).order_by('order', 'id')
    return render(request, 'dashboard/lesson_quiz.html', {
        'lesson': lesson,
        'quiz': quiz,
        'questions': questions,
    })


@staff_member_required
@require_http_methods(["POST"])
def dashboard_delete_quiz(request, lesson_id):
    """Delete a quiz for a lesson"""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    
    try:
        if hasattr(lesson, 'quiz'):
            quiz_title = lesson.quiz.title
            lesson.quiz.delete()
            messages.success(request, f'Quiz "{quiz_title}" has been deleted successfully.')
        else:
            messages.warning(request, 'No quiz found for this lesson.')
    except Exception as e:
        messages.error(request, f'Error deleting quiz: {str(e)}')
    
    return redirect('dashboard_lesson_quiz', lesson_id=lesson.id)


@staff_member_required
def dashboard_quizzes(request):
    """List all quizzes across all lessons"""
    # Get filter parameters
    course_filter = request.GET.get('course', '')
    search_query = request.GET.get('search', '')
    
    # Get all quizzes with related lesson and course info
    quizzes = LessonQuiz.objects.select_related('lesson', 'lesson__course').prefetch_related('questions').all()
    
    # Apply course filter
    if course_filter:
        quizzes = quizzes.filter(lesson__course_id=course_filter)
    
    # Apply search filter
    if search_query:
        quizzes = quizzes.filter(
            Q(title__icontains=search_query) |
            Q(lesson__title__icontains=search_query) |
            Q(lesson__course__name__icontains=search_query)
        )
    
    # Order by course and lesson
    quizzes = quizzes.order_by('lesson__course__name', 'lesson__order', 'lesson__id')
    
    # Get quiz data with question counts
    quiz_data = []
    for quiz in quizzes:
        quiz_data.append({
            'quiz': quiz,
            'lesson': quiz.lesson,
            'course': quiz.lesson.course,
            'question_count': quiz.questions.count(),
        })
    
    courses = Course.objects.all()
    
    return render(request, 'dashboard/quizzes.html', {
        'quiz_data': quiz_data,
        'courses': courses,
        'course_filter': course_filter,
        'search_query': search_query,
    })


@staff_member_required
def dashboard_course_lessons(request, course_slug):
    """View all lessons for a course"""
    course = get_object_or_404(Course, slug=course_slug)
    lessons = course.lessons.all()
    modules = course.modules.all()
    
    return render(request, 'dashboard/course_lessons.html', {
        'course': course,
        'lessons': lessons,
        'modules': modules,
    })


@staff_member_required
def dashboard_add_course(request):
    """Add new course"""
    if request.method == 'POST':
        name = request.POST.get('name')
        slug = generate_slug(name)
        short_description = request.POST.get('short_description', '')
        description = request.POST.get('description', '')
        course_type = request.POST.get('course_type', 'sprint')
        status = request.POST.get('status', 'active')
        coach_name = request.POST.get('coach_name', 'Sprint Coach')
        
        course = Course.objects.create(
            name=name,
            slug=slug,
            short_description=short_description,
            description=description,
            course_type=course_type,
            status=status,
            coach_name=coach_name,
        )
        messages.success(request, f'Course "{course.name}" has been created successfully.')
        return redirect('dashboard_courses')
    
    return render(request, 'dashboard/add_course.html')


@staff_member_required
def dashboard_lessons(request):
    """List all lessons across all courses"""
    lessons = Lesson.objects.select_related('course', 'module').order_by('-created_at')
    
    # Filtering
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        lessons = lessons.filter(ai_generation_status=status_filter)
    
    course_filter = request.GET.get('course', '')
    if course_filter:
        lessons = lessons.filter(course_id=course_filter)
    
    courses = Course.objects.all()
    
    return render(request, 'dashboard/lessons.html', {
        'lessons': lessons,
        'courses': courses,
        'status_filter': status_filter,
        'course_filter': course_filter,
    })


@staff_member_required
@require_http_methods(["POST"])
def dashboard_delete_lesson(request, lesson_id):
    """Delete a lesson"""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    lesson_title = lesson.title
    course_slug = lesson.course.slug if lesson.course else None
    
    try:
        lesson.delete()
        messages.success(request, f'Lesson "{lesson_title}" has been deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting lesson: {str(e)}')
    
    # Redirect back to lessons list or course lessons if we have course info
    if course_slug:
        return redirect('dashboard_course_lessons', course_slug=course_slug)
    return redirect('dashboard_lessons')


@staff_member_required
def dashboard_upload_quiz(request):
    """Upload quiz from CSV/PDF file or generate with AI"""
    courses = Course.objects.all()
    lessons = Lesson.objects.select_related('course').order_by('-created_at')
    
    if request.method == 'POST':
        lesson_id = request.POST.get('lesson_id')
        generation_method = request.POST.get('generation_method', 'upload')  # 'upload' or 'ai'
        
        if not lesson_id:
            messages.error(request, 'Please select a lesson.')
            return render(request, 'dashboard/upload_quiz.html', {
                'courses': courses,
                'lessons': lessons,
                'openai_available': OPENAI_AVAILABLE,
            })
        
        lesson = get_object_or_404(Lesson, id=lesson_id)
        
        try:
            # Get or create quiz
            quiz, created = LessonQuiz.objects.get_or_create(
                lesson=lesson,
                defaults={
                    'title': f'{lesson.title} Quiz',
                    'passing_score': 70,
                },
            )
            
            questions_created = 0
            
            if generation_method == 'ai':
                # Generate quiz using AI
                num_questions = int(request.POST.get('num_questions', 5))
                questions_created = generate_ai_quiz(lesson, quiz, num_questions)
            else:
                # Upload from file
                uploaded_file = request.FILES.get('quiz_file')
                if not uploaded_file:
                    messages.error(request, 'Please select a file to upload.')
                    return render(request, 'dashboard/upload_quiz.html', {
                        'courses': courses,
                        'lessons': lessons,
                        'openai_available': OPENAI_AVAILABLE,
                    })
                
                file_extension = uploaded_file.name.split('.')[-1].lower()
                
                if file_extension == 'csv':
                    questions_created = parse_csv_quiz(uploaded_file, quiz)
                elif file_extension == 'pdf':
                    if not PDF_AVAILABLE:
                        messages.error(request, 'PDF parsing is not available. Please install PyMuPDF.')
                        return render(request, 'dashboard/upload_quiz.html', {
                            'courses': courses,
                            'lessons': lessons,
                            'openai_available': OPENAI_AVAILABLE,
                        })
                    questions_created = parse_pdf_quiz(uploaded_file, quiz)
                else:
                    messages.error(request, f'Unsupported file format: {file_extension}. Please upload a CSV or PDF file.')
                    return render(request, 'dashboard/upload_quiz.html', {
                        'courses': courses,
                        'lessons': lessons,
                        'openai_available': OPENAI_AVAILABLE,
                    })
            
            if questions_created > 0:
                messages.success(request, f'Successfully created {questions_created} quiz question(s) for "{lesson.title}".')
                return redirect('dashboard_lesson_quiz', lesson_id=lesson.id)
            else:
                messages.warning(request, 'No questions were created. Please check your file format or lesson content.')
        
        except Exception as e:
            messages.error(request, f'Error processing: {str(e)}')
    
    return render(request, 'dashboard/upload_quiz.html', {
        'courses': courses,
        'lessons': lessons,
        'openai_available': OPENAI_AVAILABLE,
    })


def parse_csv_quiz(uploaded_file, quiz):
    """Parse CSV file and create quiz questions"""
    # Read the file
    file_content = uploaded_file.read().decode('utf-8')
    csv_reader = csv.DictReader(io.StringIO(file_content))
    
    questions_created = 0
    max_order = quiz.questions.aggregate(models.Max('order'))['order__max'] or 0
    
    for row_num, row in enumerate(csv_reader, start=1):
        try:
            # Expected CSV format: question, option_a, option_b, option_c, option_d, correct_answer
            question_text = row.get('question', '').strip()
            if not question_text:
                continue
            
            option_a = row.get('option_a', '').strip()
            option_b = row.get('option_b', '').strip()
            option_c = row.get('option_c', '').strip()
            option_d = row.get('option_d', '').strip()
            correct_answer = row.get('correct_answer', 'A').strip().upper()
            
            if not option_a or not option_b:
                continue
            
            # Validate correct_answer
            if correct_answer not in ['A', 'B', 'C', 'D']:
                correct_answer = 'A'
            
            # Create question
            LessonQuizQuestion.objects.create(
                quiz=quiz,
                text=question_text,
                option_a=option_a,
                option_b=option_b,
                option_c=option_c if option_c else '',
                option_d=option_d if option_d else '',
                correct_option=correct_answer,
                order=max_order + row_num,
            )
            questions_created += 1
        except Exception as e:
            # Skip rows with errors but continue processing
            continue
    
    return questions_created


def generate_ai_quiz(lesson, quiz, num_questions=5):
    """Generate quiz questions using AI based on lesson content"""
    if not OPENAI_AVAILABLE:
        raise Exception('OpenAI is not available. Please install the openai package.')
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise Exception('OPENAI_API_KEY not found in environment variables.')
    
    try:
        client = OpenAI(api_key=api_key)
        
        # Gather lesson content for AI context
        lesson_content = []
        if lesson.title:
            lesson_content.append(f"Lesson Title: {lesson.title}")
        if lesson.description:
            lesson_content.append(f"Description: {lesson.description}")
        if lesson.transcription:
            lesson_content.append(f"Transcription: {lesson.transcription[:2000]}")  # Limit transcription length
        if lesson.ai_full_description:
            lesson_content.append(f"Full Description: {lesson.ai_full_description}")
        
        if not lesson_content:
            raise Exception('Lesson does not have enough content for AI generation. Please add a description or transcription.')
        
        content_text = "\n\n".join(lesson_content)
        
        # Create prompt for AI
        prompt = f"""Based on the following lesson content, generate {num_questions} multiple-choice quiz questions.

Lesson Content:
{content_text}

Generate {num_questions} quiz questions with the following format:
- Each question should test understanding of key concepts from the lesson
- Each question should have 4 options (A, B, C, D)
- One option should be clearly correct
- The other options should be plausible but incorrect
- Questions should vary in difficulty

Return the questions in JSON format:
{{
  "questions": [
    {{
      "question": "Question text here",
      "option_a": "Option A text",
      "option_b": "Option B text",
      "option_c": "Option C text",
      "option_d": "Option D text",
      "correct_answer": "A"
    }}
  ]
}}

Only return valid JSON, no additional text."""
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that creates educational quiz questions. Always return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        # Parse response
        response_text = response.choices[0].message.content.strip()
        
        # Clean up response (remove markdown code blocks if present)
        if response_text.startswith('```'):
            response_text = response_text.split('```')[1]
            if response_text.startswith('json'):
                response_text = response_text[4:]
            response_text = response_text.strip()
        if response_text.endswith('```'):
            response_text = response_text.rsplit('```', 1)[0].strip()
        
        # Parse JSON
        try:
            quiz_data = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                quiz_data = json.loads(json_match.group())
            else:
                raise Exception('Failed to parse AI response as JSON.')
        
        # Create quiz questions
        questions_created = 0
        max_order = quiz.questions.aggregate(models.Max('order'))['order__max'] or 0
        
        for idx, q_data in enumerate(quiz_data.get('questions', []), start=1):
            try:
                question_text = q_data.get('question', '').strip()
                option_a = q_data.get('option_a', '').strip()
                option_b = q_data.get('option_b', '').strip()
                option_c = q_data.get('option_c', '').strip()
                option_d = q_data.get('option_d', '').strip()
                correct_answer = q_data.get('correct_answer', 'A').strip().upper()
                
                if not question_text or not option_a or not option_b:
                    continue
                
                if correct_answer not in ['A', 'B', 'C', 'D']:
                    correct_answer = 'A'
                
                LessonQuizQuestion.objects.create(
                    quiz=quiz,
                    text=question_text,
                    option_a=option_a,
                    option_b=option_b,
                    option_c=option_c if option_c else '',
                    option_d=option_d if option_d else '',
                    correct_option=correct_answer,
                    order=max_order + idx,
                )
                questions_created += 1
            except Exception as e:
                continue
        
        return questions_created
    
    except Exception as e:
        raise Exception(f'AI generation failed: {str(e)}')


def parse_pdf_quiz(uploaded_file, quiz):
    """Parse PDF file and create quiz questions"""
    # Read PDF content
    pdf_bytes = uploaded_file.read()
    pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    text_content = ""
    for page in pdf_doc:
        text_content += page.get_text()
    
    pdf_doc.close()
    
    # Try to parse questions from PDF text
    # Expected format: Questions should be numbered (1., 2., etc.) with options A, B, C, D
    questions_created = 0
    max_order = quiz.questions.aggregate(models.Max('order'))['order__max'] or 0
    
    # Split by question numbers (1., 2., etc.)
    question_pattern = r'(\d+\.\s+.*?)(?=\d+\.|$)'
    questions_text = re.findall(question_pattern, text_content, re.DOTALL | re.IGNORECASE)
    
    for idx, question_block in enumerate(questions_text, start=1):
        try:
            lines = [line.strip() for line in question_block.split('\n') if line.strip()]
            if len(lines) < 3:  # Need at least question + 2 options
                continue
            
            question_text = lines[0].lstrip('0123456789. ').strip()
            if not question_text:
                continue
            
            # Extract options (looking for A., B., C., D. patterns)
            options = {}
            current_option = None
            option_text = []
            
            for line in lines[1:]:
                # Check if line starts with option letter
                option_match = re.match(r'^([A-D])[\.\)]\s*(.*)$', line, re.IGNORECASE)
                if option_match:
                    # Save previous option if exists
                    if current_option:
                        options[current_option] = ' '.join(option_text).strip()
                    current_option = option_match.group(1).upper()
                    option_text = [option_match.group(2)]
                elif current_option:
                    option_text.append(line)
            
            # Save last option
            if current_option:
                options[current_option] = ' '.join(option_text).strip()
            
            # Need at least A and B options
            if 'A' not in options or 'B' not in options:
                continue
            
            # Determine correct answer (look for "Answer:" or "Correct:" patterns)
            correct_answer = 'A'  # Default
            for line in lines:
                answer_match = re.search(r'(?:answer|correct)[:\s]+([A-D])', line, re.IGNORECASE)
                if answer_match:
                    correct_answer = answer_match.group(1).upper()
                    break
            
            # Create question
            LessonQuizQuestion.objects.create(
                quiz=quiz,
                text=question_text,
                option_a=options.get('A', ''),
                option_b=options.get('B', ''),
                option_c=options.get('C', ''),
                option_d=options.get('D', ''),
                correct_option=correct_answer if correct_answer in ['A', 'B', 'C', 'D'] else 'A',
                order=max_order + idx,
            )
            questions_created += 1
        except Exception as e:
            # Skip questions with errors
            continue
    
    return questions_created


@staff_member_required
def dashboard_add_lesson(request):
    """Add new lesson - redirects to creator flow"""
    course_id = request.GET.get('course')
    if course_id:
        course = get_object_or_404(Course, id=course_id)
        return redirect('add_lesson', course_slug=course.slug)
    
    courses = Course.objects.all()
    return render(request, 'dashboard/select_course.html', {
        'courses': courses,
    })


@staff_member_required
def dashboard_edit_lesson(request, lesson_id):
    """Edit lesson - redirects to AI generation page"""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    return redirect('generate_lesson_ai', course_slug=lesson.course.slug, lesson_id=lesson.id)


@staff_member_required
def dashboard_student_progress(request):
    """Student progress overview - all students"""
    # Get filter parameters
    course_filter = request.GET.get('course', '')
    search_query = request.GET.get('search', '')
    
    # Get all enrollments
    enrollments = CourseEnrollment.objects.select_related('user', 'course').all()
    
    # Apply filters
    if course_filter:
        enrollments = enrollments.filter(course_id=course_filter)
    
    if search_query:
        enrollments = enrollments.filter(
            Q(user__username__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(course__name__icontains=search_query)
        )
    
    # Calculate progress for each enrollment
    enrollment_data = []
    for enrollment in enrollments:
        total_lessons = enrollment.course.lessons.count()
        completed_lessons = UserProgress.objects.filter(
            user=enrollment.user,
            lesson__course=enrollment.course,
            completed=True
        ).count()
        
        progress_percentage = int((completed_lessons / total_lessons * 100)) if total_lessons > 0 else 0
        
        # Get certification status
        try:
            cert = Certification.objects.get(user=enrollment.user, course=enrollment.course)
            cert_status = cert.get_status_display()
        except Certification.DoesNotExist:
            cert_status = 'Not Eligible' if progress_percentage < 100 else 'Eligible'
        
        enrollment_data.append({
            'enrollment': enrollment,
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
            'progress_percentage': progress_percentage,
            'cert_status': cert_status,
        })
    
    courses = Course.objects.all()
    
    return render(request, 'dashboard/student_progress.html', {
        'enrollment_data': enrollment_data,
        'courses': courses,
        'course_filter': course_filter,
        'search_query': search_query,
    })


@staff_member_required
def dashboard_student_detail(request, user_id, course_slug=None):
    """Detailed student progress view"""
    user = get_object_or_404(User, id=user_id)
    
    if course_slug:
        course = get_object_or_404(Course, slug=course_slug)
        courses = [course]
    else:
        # Get all courses the user is enrolled in
        courses = Course.objects.filter(enrollments__user=user).distinct()
    
    course_data = []
    for course in courses:
        enrollment = CourseEnrollment.objects.filter(user=user, course=course).first()
        
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
            })
        
        # Get exam attempts
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
        
        course_data.append({
            'course': course,
            'enrollment': enrollment,
            'lesson_progress': lesson_progress,
            'exam_attempts': exam_attempts,
            'certification': certification,
        })
    
    return render(request, 'dashboard/student_detail.html', {
        'student': user,
        'course_data': course_data,
    })


@staff_member_required
def dashboard_course_progress(request, course_slug):
    """View all student progress for a specific course"""
    course = get_object_or_404(Course, slug=course_slug)
    
    # Get all enrollments for this course
    enrollments = CourseEnrollment.objects.filter(course=course).select_related('user')
    
    # Calculate progress for each student
    student_progress = []
    for enrollment in enrollments:
        total_lessons = course.lessons.count()
        completed_lessons = UserProgress.objects.filter(
            user=enrollment.user,
            lesson__course=course,
            completed=True
        ).count()
        
        # Get average video watch percentage
        avg_watch = UserProgress.objects.filter(
            user=enrollment.user,
            lesson__course=course
        ).aggregate(avg=Avg('video_watch_percentage'))['avg'] or 0
        
        # Get exam attempts
        exam_attempts_count = 0
        passed_exam = False
        try:
            exam = Exam.objects.get(course=course)
            exam_attempts = ExamAttempt.objects.filter(user=enrollment.user, exam=exam)
            exam_attempts_count = exam_attempts.count()
            passed_exam = exam_attempts.filter(passed=True).exists()
        except Exam.DoesNotExist:
            pass
        
        # Get certification status
        try:
            cert = Certification.objects.get(user=enrollment.user, course=course)
            cert_status = cert.get_status_display()
        except Certification.DoesNotExist:
            cert_status = 'Not Eligible' if completed_lessons < total_lessons else 'Eligible'
        
        student_progress.append({
            'user': enrollment.user,
            'enrollment': enrollment,
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
            'progress_percentage': int((completed_lessons / total_lessons * 100)) if total_lessons > 0 else 0,
            'avg_watch_percentage': round(avg_watch, 1),
            'exam_attempts': exam_attempts_count,
            'passed_exam': passed_exam,
            'cert_status': cert_status,
        })
    
    # Sort by progress percentage (descending)
    student_progress.sort(key=lambda x: x['progress_percentage'], reverse=True)
    
    return render(request, 'dashboard/course_progress.html', {
        'course': course,
        'student_progress': student_progress,
    })


# Helper functions (imported from views.py or defined here)
def generate_slug(text):
    """Generate URL-friendly slug from text"""
    import unicodedata
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')

