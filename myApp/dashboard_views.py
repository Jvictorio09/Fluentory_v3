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
    TeacherRequest,
    Lead,
    LeadTimeline,
    LeadEnrollmentLink,
    LeadGiftLink,
    GiftPurchase,
    CourseAccess,
    ExamAttempt,
    Certification,
    LessonQuiz,
    LessonQuizAttempt,
    LessonQuizQuestion,
    Bundle,
    BundlePurchase,
    Cohort,
    CohortMember,
)
from django.contrib import messages
from django.db import models
from django.contrib.auth.models import User
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone


@staff_member_required
def dashboard_home(request):
    """Main dashboard overview with analytics"""
    from datetime import timedelta
    
    # Basic stats
    total_courses = Course.objects.count()
    total_lessons = Lesson.objects.count()
    approved_lessons = Lesson.objects.filter(ai_generation_status='approved').count()
    pending_lessons = Lesson.objects.filter(ai_generation_status='pending').count()
    recent_lessons = Lesson.objects.select_related('course').order_by('-created_at')[:10]
    courses = Course.objects.annotate(lesson_count=Count('lessons')).order_by('-created_at')
    
    # Student Analytics
    total_students = User.objects.filter(is_staff=False, is_superuser=False).count()
    active_students = User.objects.filter(
        is_staff=False, 
        is_superuser=False,
        last_login__gte=timezone.now() - timedelta(days=30)
    ).count()
    new_students_30d = User.objects.filter(
        is_staff=False,
        is_superuser=False,
        date_joined__gte=timezone.now() - timedelta(days=30)
    ).count()
    
    # Enrollment Analytics
    total_enrollments = CourseEnrollment.objects.count()
    active_enrollments = CourseEnrollment.objects.filter(
        enrolled_at__gte=timezone.now() - timedelta(days=30)
    ).count()
    
    # Course Access Analytics
    total_accesses = CourseAccess.objects.filter(status='unlocked').count()
    expired_accesses = CourseAccess.objects.filter(status='expired').count()
    
    # Progress Analytics
    total_progress = UserProgress.objects.count()
    completed_lessons = UserProgress.objects.filter(completed=True).count()
    completion_rate = (completed_lessons / total_progress * 100) if total_progress > 0 else 0
    
    # Certification Analytics
    total_certifications = Certification.objects.count()
    certifications_30d = Certification.objects.filter(
        issued_at__gte=timezone.now() - timedelta(days=30)
    ).count() if Certification.objects.filter(issued_at__isnull=False).exists() else 0
    
    # Course Performance Analytics
    course_performance = []
    for course in Course.objects.all()[:10]:
        enrollments = CourseEnrollment.objects.filter(course=course).count()
        accesses = CourseAccess.objects.filter(course=course, status='unlocked').count()
        total_students_course = enrollments + accesses
        
        total_lessons_course = course.lessons.count()
        completed = UserProgress.objects.filter(
            lesson__course=course,
            completed=True
        ).count()
        course_completion_rate = (completed / (total_lessons_course * total_students_course * 100)) if total_students_course > 0 and total_lessons_course > 0 else 0
        
        certifications_course = Certification.objects.filter(course=course, status='passed').count()
        
        course_performance.append({
            'course': course,
            'total_students': total_students_course,
            'completion_rate': min(course_completion_rate * 100, 100),
            'certifications': certifications_course,
            'lessons': total_lessons_course,
        })
    
    # Recent Activity (last 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    recent_progress = UserProgress.objects.filter(
        last_accessed__gte=seven_days_ago
    ).count()
    recent_certifications = Certification.objects.filter(
        issued_at__gte=seven_days_ago
    ).count() if Certification.objects.filter(issued_at__isnull=False).exists() else 0
    
    # Get student activity feed
    student_activities = get_student_activity_feed(limit=10)
    
    # Enrollment trend (last 30 days)
    enrollment_trend = []
    for i in range(30, 0, -1):
        date = timezone.now() - timedelta(days=i)
        count = CourseEnrollment.objects.filter(
            enrolled_at__date=date.date()
        ).count()
        enrollment_trend.append({
            'date': date.strftime('%m/%d'),
            'count': count
        })
    
    return render(request, 'dashboard/home.html', {
        'total_courses': total_courses,
        'total_lessons': total_lessons,
        'approved_lessons': approved_lessons,
        'pending_lessons': pending_lessons,
        'recent_lessons': recent_lessons,
        'courses': courses,
        'student_activities': student_activities,
        # Analytics data
        'total_students': total_students,
        'active_students': active_students,
        'new_students_30d': new_students_30d,
        'total_enrollments': total_enrollments,
        'active_enrollments': active_enrollments,
        'total_accesses': total_accesses,
        'expired_accesses': expired_accesses,
        'total_progress': total_progress,
        'completed_lessons': completed_lessons,
        'completion_rate': round(completion_rate, 1),
        'total_certifications': total_certifications,
        'certifications_30d': certifications_30d,
        'course_performance': course_performance,
        'recent_progress': recent_progress,
        'recent_certifications': recent_certifications,
        'enrollment_trend': enrollment_trend,
    })


@staff_member_required
def dashboard_students(request):
    """Smart student list with activity updates and filtering"""
    # Get filter parameters
    course_filter = request.GET.get('course', '')
    status_filter = request.GET.get('status', 'all')  # all, active, completed, certified
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort', 'recent')  # recent, progress, name, enrolled
    
    # Get all users including admin/staff
    # Show all users who have activity OR all users if none have activity
    students_query = User.objects.all()
    
    # Auto-enroll admin/staff users in all active courses if they don't have enrollments
    admin_users = students_query.filter(Q(is_staff=True) | Q(is_superuser=True))
    active_courses = Course.objects.filter(status='active')
    
    for admin_user in admin_users:
        for course in active_courses:
            CourseEnrollment.objects.get_or_create(
                user=admin_user,
                course=course,
                defaults={'payment_type': 'full'}
            )
    
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
        # Get enrollments (legacy system)
        enrollments = CourseEnrollment.objects.filter(user=student).select_related('course')
        
        # Get course access records (new access control system)
        course_accesses = CourseAccess.objects.filter(
            user=student,
            status='unlocked'
        ).select_related('course')
        
        # Combine both - get unique courses from enrollments and accesses
        enrollment_courses = set(enrollments.values_list('course_id', flat=True))
        access_courses = set(course_accesses.values_list('course_id', flat=True))
        all_course_ids = enrollment_courses | access_courses
        
        # Apply course filter
        if course_filter:
            if int(course_filter) not in all_course_ids:
                continue
            all_course_ids = {int(course_filter)}
        
        # Get all courses for this student (even if empty, we still show the student)
        student_courses = Course.objects.filter(id__in=all_course_ids) if all_course_ids else Course.objects.none()
        
        # Calculate overall stats
        total_courses = len(all_course_ids)
        total_lessons_all = 0
        completed_lessons_all = 0
        certifications_count = 0
        recent_activity = None
        
        for course in student_courses:
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
            'course_accesses': course_accesses,
            'courses': student_courses,
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
        preview_video_url = request.POST.get('preview_video_url', '').strip()
        course.preview_video_url = preview_video_url if preview_video_url else None
        
        # Delivery type and pricing
        course.delivery_type = request.POST.get('delivery_type', course.delivery_type)
        course.is_paid = request.POST.get('is_paid') == 'on'
        price = request.POST.get('price', '') or None
        course.price = float(price) if price else None
        course.currency = request.POST.get('currency', course.currency)
        
        course.save()
        
        # Update teacher assignment if live course
        if course.delivery_type == 'live':
            teacher_ids = request.POST.getlist('teachers')
            if teacher_ids:
                from django.contrib.auth.models import User
                teachers = User.objects.filter(id__in=teacher_ids)
                course.teachers.set(teachers)
            else:
                course.teachers.clear()
        else:
            course.teachers.clear()
        
        messages.success(request, 'Course updated successfully.')
        return redirect('dashboard_course_detail', course_slug=course.slug)
    
    # Get all users who could be teachers
    from django.contrib.auth.models import User
    from django.db.models import Q
    potential_teachers = User.objects.filter(
        Q(is_staff=False) | Q(taught_courses__isnull=False)
    ).distinct().order_by('username')
    
    return render(request, 'dashboard/course_detail.html', {
        'course': course,
        'potential_teachers': potential_teachers,
        'course_types': Course.COURSE_TYPES,
        'delivery_types': Course.DELIVERY_TYPE_CHOICES,
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
        elif action == 'edit_question':
            q_id = request.POST.get('question_id')
            if q_id:
                try:
                    question = LessonQuizQuestion.objects.get(id=q_id, quiz=quiz)
                    question.text = request.POST.get('q_text', '').strip()
                    question.option_a = request.POST.get('q_option_a', '').strip()
                    question.option_b = request.POST.get('q_option_b', '').strip()
                    question.option_c = request.POST.get('q_option_c', '').strip()
                    question.option_d = request.POST.get('q_option_d', '').strip()
                    question.correct_option = request.POST.get('q_correct_option', 'A') or 'A'
                    question.save()
                    messages.success(request, 'Question updated.')
                except LessonQuizQuestion.DoesNotExist:
                    messages.error(request, 'Question not found.')
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
        
        # Delivery type and pricing
        delivery_type = request.POST.get('delivery_type', 'pre_recorded')
        is_paid = request.POST.get('is_paid') == 'on'
        price = request.POST.get('price', '') or None
        currency = request.POST.get('currency', 'USD')
        
        preview_video_url = request.POST.get('preview_video_url', '').strip()
        
        course = Course.objects.create(
            name=name,
            slug=slug,
            short_description=short_description,
            description=description,
            course_type=course_type,
            status=status,
            coach_name=coach_name,
            delivery_type=delivery_type,
            is_paid=is_paid,
            price=float(price) if price else None,
            currency=currency,
            preview_video_url=preview_video_url if preview_video_url else None,
        )
        
        # Assign teacher if live course
        if delivery_type == 'live':
            teacher_ids = request.POST.getlist('teachers')
            if teacher_ids:
                from django.contrib.auth.models import User
                teachers = User.objects.filter(id__in=teacher_ids)
                course.teachers.set(teachers)
        
        messages.success(request, f'Course "{course.name}" has been created successfully.')
        return redirect('dashboard_courses')
    
    # Get all users who could be teachers (non-staff users or users with taught courses)
    from django.contrib.auth.models import User
    potential_teachers = User.objects.filter(
        Q(is_staff=False) | Q(taught_courses__isnull=False)
    ).distinct().order_by('username')
    
    return render(request, 'dashboard/add_course.html', {
        'potential_teachers': potential_teachers,
    })


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
    
    # Get all course access records for this student
    from .models import CourseAccess
    course_accesses = CourseAccess.objects.filter(user=user).select_related('course', 'bundle_purchase', 'cohort', 'granted_by', 'revoked_by').order_by('-granted_at')
    
    # Get bundles and cohorts for access management
    from .models import Bundle, Cohort
    bundles = Bundle.objects.filter(is_active=True)
    cohorts = Cohort.objects.filter(is_active=True)
    all_courses = Course.objects.filter(status='active')
    
    return render(request, 'dashboard/student_detail.html', {
        'student': user,
        'course_data': course_data,
        'course_accesses': course_accesses,
        'bundles': bundles,
        'cohorts': cohorts,
        'courses': all_courses,
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


# ========== ACCESS MANAGEMENT VIEWS ==========

@staff_member_required
@require_http_methods(["POST"])
def grant_course_access_view(request, user_id):
    """Grant course access to a student"""
    user = get_object_or_404(User, id=user_id)
    from .utils.access import grant_course_access
    from django.utils import timezone
    from datetime import timedelta
    
    course_id = request.POST.get('course_id')
    access_type = request.POST.get('access_type', 'manual')
    expires_in_days = request.POST.get('expires_in_days', '')
    notes = request.POST.get('notes', '')
    
    if not course_id:
        return JsonResponse({'success': False, 'error': 'Course ID required'}, status=400)
    
    course = get_object_or_404(Course, id=course_id)
    
    # Calculate expiration
    expires_at = None
    if expires_in_days:
        try:
            days = int(expires_in_days)
            expires_at = timezone.now() + timedelta(days=days)
        except ValueError:
            pass
    
    # Grant access
    access = grant_course_access(
        user=user,
        course=course,
        access_type=access_type,
        granted_by=request.user,
        expires_at=expires_at,
        notes=notes
    )
    
    return JsonResponse({
        'success': True,
        'message': f'Access granted to {course.name}',
        'access_id': access.id
    })


@staff_member_required
@require_http_methods(["POST"])
def revoke_course_access_view(request, user_id):
    """Revoke course access from a student"""
    user = get_object_or_404(User, id=user_id)
    from .utils.access import revoke_course_access
    
    course_id = request.POST.get('course_id')
    reason = request.POST.get('reason', '')
    notes = request.POST.get('notes', '')
    
    if not course_id:
        return JsonResponse({'success': False, 'error': 'Course ID required'}, status=400)
    
    course = get_object_or_404(Course, id=course_id)
    
    # Revoke access
    access = revoke_course_access(
        user=user,
        course=course,
        revoked_by=request.user,
        reason=reason,
        notes=notes
    )
    
    if access:
        return JsonResponse({
            'success': True,
            'message': f'Access revoked for {course.name}'
        })
    else:
        return JsonResponse({
            'success': False,
            'error': 'No active access found to revoke'
        }, status=400)


@staff_member_required
@require_http_methods(["POST"])
def grant_bundle_access_view(request, user_id):
    """Grant bundle access to a student"""
    user = get_object_or_404(User, id=user_id)
    from .utils.access import grant_bundle_access
    
    bundle_id = request.POST.get('bundle_id')
    purchase_id = request.POST.get('purchase_id', '')
    notes = request.POST.get('notes', '')
    
    if not bundle_id:
        return JsonResponse({'success': False, 'error': 'Bundle ID required'}, status=400)
    
    bundle = get_object_or_404(Bundle, id=bundle_id)
    
    # Create bundle purchase
    bundle_purchase = BundlePurchase.objects.create(
        user=user,
        bundle=bundle,
        purchase_id=purchase_id,
        notes=notes
    )
    
    # Grant access to all courses in bundle
    granted_accesses = grant_bundle_access(user, bundle_purchase)
    
    return JsonResponse({
        'success': True,
        'message': f'Bundle access granted - {len(granted_accesses)} courses unlocked',
        'bundle_purchase_id': bundle_purchase.id
    })


@staff_member_required
@require_http_methods(["POST"])
def add_to_cohort_view(request, user_id):
    """Add student to a cohort"""
    user = get_object_or_404(User, id=user_id)
    
    cohort_id = request.POST.get('cohort_id')
    if not cohort_id:
        return JsonResponse({'success': False, 'error': 'Cohort ID required'}, status=400)
    
    cohort = get_object_or_404(Cohort, id=cohort_id)
    
    # Add to cohort
    member, created = CohortMember.objects.get_or_create(
        user=user,
        cohort=cohort
    )
    
    if created:
        # Grant access to courses associated with cohort (if any)
        # Note: This requires adding a many-to-many relationship between Cohort and Course
        # For now, we'll just add them to the cohort
        message = f'Added to cohort: {cohort.name}'
    else:
        message = f'Already in cohort: {cohort.name}'
    
    return JsonResponse({
        'success': True,
        'message': message
    })


@staff_member_required
def bulk_access_management(request):
    """Bulk access management page"""
    # Get all active courses, bundles, and cohorts
    courses = Course.objects.filter(status='active')
    bundles = Bundle.objects.filter(is_active=True)
    cohorts = Cohort.objects.filter(is_active=True)
    
    # Get all users (for selection)
    users = User.objects.all().order_by('username')
    
    return render(request, 'dashboard/bulk_access.html', {
        'courses': courses,
        'bundles': bundles,
        'cohorts': cohorts,
        'users': users,
    })


@staff_member_required
@require_http_methods(["POST"])
def bulk_grant_access_view(request):
    """Bulk grant course access to multiple students"""
    from .utils.access import grant_course_access
    from django.utils import timezone
    from datetime import timedelta
    
    user_ids = request.POST.getlist('user_ids[]')
    course_ids = request.POST.getlist('course_ids[]')
    access_type = request.POST.get('access_type', 'manual')
    expires_in_days = request.POST.get('expires_in_days', '')
    notes = request.POST.get('notes', '')
    
    if not user_ids or not course_ids:
        return JsonResponse({'success': False, 'error': 'Users and courses required'}, status=400)
    
    # Calculate expiration
    expires_at = None
    if expires_in_days:
        try:
            days = int(expires_in_days)
            expires_at = timezone.now() + timedelta(days=days)
        except ValueError:
            pass
    
    granted_count = 0
    for user_id in user_ids:
        try:
            user = User.objects.get(id=user_id)
            for course_id in course_ids:
                try:
                    course = Course.objects.get(id=course_id)
                    # Check if access already exists
                    existing = CourseAccess.objects.filter(
                        user=user,
                        course=course,
                        status='unlocked'
                    ).first()
                    if not existing:
                        grant_course_access(
                            user=user,
                            course=course,
                            access_type=access_type,
                            granted_by=request.user,
                            expires_at=expires_at,
                            notes=notes
                        )
                        granted_count += 1
                except Course.DoesNotExist:
                    continue
        except User.DoesNotExist:
            continue
    
    return JsonResponse({
        'success': True,
        'message': f'Granted {granted_count} access records',
        'granted_count': granted_count
    })


@staff_member_required
def dashboard_analytics(request):
    """Comprehensive analytics dashboard"""
    from datetime import timedelta
    
    # Date ranges
    now = timezone.now()
    last_7_days = now - timedelta(days=7)
    last_30_days = now - timedelta(days=30)
    last_90_days = now - timedelta(days=90)
    
    # Student Analytics
    total_students = User.objects.filter(is_staff=False, is_superuser=False).count()
    active_students = User.objects.filter(
        is_staff=False, is_superuser=False,
        last_login__gte=last_30_days
    ).count()
    new_students_7d = User.objects.filter(
        is_staff=False, is_superuser=False,
        date_joined__gte=last_7_days
    ).count()
    new_students_30d = User.objects.filter(
        is_staff=False, is_superuser=False,
        date_joined__gte=last_30_days
    ).count()
    inactive_students = User.objects.filter(
        is_staff=False, is_superuser=False,
        last_login__lt=last_90_days
    ).count()
    
    # Enrollment Analytics
    total_enrollments = CourseEnrollment.objects.count()
    enrollments_7d = CourseEnrollment.objects.filter(enrolled_at__gte=last_7_days).count()
    enrollments_30d = CourseEnrollment.objects.filter(enrolled_at__gte=last_30_days).count()
    
    # Access Analytics
    total_accesses = CourseAccess.objects.filter(status='unlocked').count()
    expired_accesses = CourseAccess.objects.filter(status='expired').count()
    pending_accesses = CourseAccess.objects.filter(status='pending').count()
    
    # Progress Analytics
    total_progress = UserProgress.objects.count()
    completed_lessons = UserProgress.objects.filter(completed=True).count()
    progress_7d = UserProgress.objects.filter(last_accessed__gte=last_7_days).count()
    completion_rate = (completed_lessons / total_progress * 100) if total_progress > 0 else 0
    
    # Certification Analytics
    total_certifications = Certification.objects.count()
    certifications_7d = Certification.objects.filter(
        issued_at__gte=last_7_days
    ).count() if Certification.objects.filter(issued_at__isnull=False).exists() else 0
    certifications_30d = Certification.objects.filter(
        issued_at__gte=last_30_days
    ).count() if Certification.objects.filter(issued_at__isnull=False).exists() else 0
    
    # Course Performance Detailed
    course_performance_detailed = []
    for course in Course.objects.all():
        enrollments = CourseEnrollment.objects.filter(course=course).count()
        accesses = CourseAccess.objects.filter(course=course, status='unlocked').count()
        total_students_course = enrollments + accesses
        
        total_lessons_course = course.lessons.count()
        completed = UserProgress.objects.filter(
            lesson__course=course,
            completed=True
        ).count()
        total_possible = total_lessons_course * total_students_course
        course_completion_rate = (completed / total_possible * 100) if total_possible > 0 else 0
        
        certifications_course = Certification.objects.filter(course=course, status='passed').count()
        
        # Recent activity
        recent_enrollments = CourseEnrollment.objects.filter(
            course=course,
            enrolled_at__gte=last_7_days
        ).count()
        
        course_performance_detailed.append({
            'course': course,
            'total_students': total_students_course,
            'completion_rate': min(course_completion_rate, 100),
            'certifications': certifications_course,
            'lessons': total_lessons_course,
            'recent_enrollments': recent_enrollments,
            'completed_lessons': completed,
        })
    
    # Sort by total students
    course_performance_detailed.sort(key=lambda x: x['total_students'], reverse=True)
    
    # Enrollment trend (last 30 days)
    enrollment_trend = []
    for i in range(30, 0, -1):
        date = now - timedelta(days=i)
        count = CourseEnrollment.objects.filter(
            enrolled_at__date=date.date()
        ).count()
        enrollment_trend.append({
            'date': date.strftime('%m/%d'),
            'count': count
        })
    
    # Certification trend (last 30 days)
    certification_trend = []
    if Certification.objects.filter(issued_at__isnull=False).exists():
        for i in range(30, 0, -1):
            date = now - timedelta(days=i)
            count = Certification.objects.filter(
                issued_at__date=date.date()
            ).count()
            certification_trend.append({
                'date': date.strftime('%m/%d'),
                'count': count
            })
    
    # Top performing courses
    top_courses = sorted(course_performance_detailed, key=lambda x: x['total_students'], reverse=True)[:5]
    
    # Most active students
    active_students_list = User.objects.filter(
        is_staff=False, is_superuser=False
    ).annotate(
        progress_count=Count('progress', filter=Q(progress__last_accessed__gte=last_7_days))
    ).filter(progress_count__gt=0).order_by('-progress_count')[:10]
    
    # Additional Phase 1 Analytics
    
    # Students with zero progress
    students_with_progress = UserProgress.objects.values_list('user_id', flat=True).distinct()
    students_zero_progress = User.objects.filter(
        is_staff=False, is_superuser=False
    ).exclude(id__in=students_with_progress).count()
    
    # Students who completed at least one course
    students_with_completions = UserProgress.objects.filter(
        completed=True
    ).values_list('user_id', flat=True).distinct().count()
    
    # Average lessons completed per student
    total_lessons_completed = UserProgress.objects.filter(completed=True).count()
    avg_lessons_per_student = round(total_lessons_completed / total_students, 1) if total_students > 0 else 0
    
    # Course completion rates by course type
    course_type_stats = {}
    for course_type, _ in Course.COURSE_TYPES:
        courses_of_type = Course.objects.filter(course_type=course_type)
        total_enrollments_type = CourseEnrollment.objects.filter(course__in=courses_of_type).count()
        total_accesses_type = CourseAccess.objects.filter(course__in=courses_of_type, status='unlocked').count()
        total_students_type = total_enrollments_type + total_accesses_type
        
        total_lessons_type = sum(c.lessons.count() for c in courses_of_type)
        completed_lessons_type = UserProgress.objects.filter(
            lesson__course__in=courses_of_type,
            completed=True
        ).count()
        completion_rate_type = (completed_lessons_type / (total_lessons_type * total_students_type * 100)) if total_students_type > 0 and total_lessons_type > 0 else 0
        
        course_type_stats[course_type] = {
            'total_courses': courses_of_type.count(),
            'total_students': total_students_type,
            'completion_rate': min(completion_rate_type * 100, 100),
        }
    
    # Certification rate (certifications / eligible students)
    students_with_all_lessons = []
    for course in Course.objects.all():
        total_lessons = course.lessons.count()
        if total_lessons > 0:
            enrollments = CourseEnrollment.objects.filter(course=course)
            accesses = CourseAccess.objects.filter(course=course, status='unlocked')
            for enrollment in enrollments:
                completed = UserProgress.objects.filter(
                    user=enrollment.user,
                    lesson__course=course,
                    completed=True
                ).count()
                if completed >= total_lessons:
                    students_with_all_lessons.append((enrollment.user.id, course.id))
            for access in accesses:
                completed = UserProgress.objects.filter(
                    user=access.user,
                    lesson__course=course,
                    completed=True
                ).count()
                if completed >= total_lessons:
                    students_with_all_lessons.append((access.user.id, course.id))
    
    eligible_students_count = len(set(students_with_all_lessons))
    certification_rate = (total_certifications / eligible_students_count * 100) if eligible_students_count > 0 else 0
    
    # Trophy distribution
    trophy_distribution = {
        'bronze': 0,  # 1 certification
        'silver': 0,  # 3 certifications
        'gold': 0,    # 5 certifications
        'platinum': 0, # 8 certifications
        'diamond': 0,  # 12 certifications
        'ultimate': 0  # 20 certifications
    }
    for user in User.objects.filter(is_staff=False, is_superuser=False):
        cert_count = Certification.objects.filter(user=user, status='passed').count()
        if cert_count >= 20:
            trophy_distribution['ultimate'] += 1
        elif cert_count >= 12:
            trophy_distribution['diamond'] += 1
        elif cert_count >= 8:
            trophy_distribution['platinum'] += 1
        elif cert_count >= 5:
            trophy_distribution['gold'] += 1
        elif cert_count >= 3:
            trophy_distribution['silver'] += 1
        elif cert_count >= 1:
            trophy_distribution['bronze'] += 1
    
    # Exam & Quiz Analytics
    total_exam_attempts = ExamAttempt.objects.count()
    passed_exams = ExamAttempt.objects.filter(passed=True).count()
    exam_pass_rate = (passed_exams / total_exam_attempts * 100) if total_exam_attempts > 0 else 0
    avg_exam_score = ExamAttempt.objects.aggregate(Avg('score'))['score__avg'] or 0
    
    total_quiz_attempts = LessonQuizAttempt.objects.count()
    passed_quizzes = LessonQuizAttempt.objects.filter(passed=True).count()
    quiz_pass_rate = (passed_quizzes / total_quiz_attempts * 100) if total_quiz_attempts > 0 else 0
    avg_quiz_score = LessonQuizAttempt.objects.aggregate(Avg('score'))['score__avg'] or 0
    
    # Access Source Analytics
    access_by_method = {
        'enrollment': CourseEnrollment.objects.count(),
        'course_access': CourseAccess.objects.filter(status='unlocked').count(),
        'bundle': BundlePurchase.objects.count(),
        'cohort': CohortMember.objects.count(),
    }
    
    # Drop-off analysis (students who started but didn't complete)
    students_who_started = set()
    students_who_completed = set()
    for course in Course.objects.all():
        enrollments = CourseEnrollment.objects.filter(course=course)
        accesses = CourseAccess.objects.filter(course=course, status='unlocked')
        total_lessons = course.lessons.count()
        
        for enrollment in enrollments:
            students_who_started.add(enrollment.user.id)
            completed = UserProgress.objects.filter(
                user=enrollment.user,
                lesson__course=course,
                completed=True
            ).count()
            if completed >= total_lessons and total_lessons > 0:
                students_who_completed.add(enrollment.user.id)
        
        for access in accesses:
            students_who_started.add(access.user.id)
            completed = UserProgress.objects.filter(
                user=access.user,
                lesson__course=course,
                completed=True
            ).count()
            if completed >= total_lessons and total_lessons > 0:
                students_who_completed.add(access.user.id)
    
    drop_off_count = len(students_who_started) - len(students_who_completed)
    drop_off_rate = (drop_off_count / len(students_who_started) * 100) if len(students_who_started) > 0 else 0
    
    return render(request, 'dashboard/analytics.html', {
        # Student metrics
        'total_students': total_students,
        'active_students': active_students,
        'new_students_7d': new_students_7d,
        'new_students_30d': new_students_30d,
        'inactive_students': inactive_students,
        
        # Enrollment metrics
        'total_enrollments': total_enrollments,
        'enrollments_7d': enrollments_7d,
        'enrollments_30d': enrollments_30d,
        
        # Access metrics
        'total_accesses': total_accesses,
        'expired_accesses': expired_accesses,
        'pending_accesses': pending_accesses,
        
        # Progress metrics
        'total_progress': total_progress,
        'completed_lessons': completed_lessons,
        'progress_7d': progress_7d,
        'completion_rate': round(completion_rate, 1),
        
        # Certification metrics
        'total_certifications': total_certifications,
        'certifications_7d': certifications_7d,
        'certifications_30d': certifications_30d,
        
        # Detailed data
        'course_performance': course_performance_detailed,
        'enrollment_trend': enrollment_trend,
        'certification_trend': certification_trend,
        'top_courses': top_courses,
        'active_students_list': active_students_list,
        
        # Additional Phase 1 Analytics
        'students_zero_progress': students_zero_progress,
        'students_with_completions': students_with_completions,
        'avg_lessons_per_student': avg_lessons_per_student,
        'course_type_stats': course_type_stats,
        'certification_rate': round(certification_rate, 1),
        'trophy_distribution': trophy_distribution,
        'total_exam_attempts': total_exam_attempts,
        'passed_exams': passed_exams,
        'exam_pass_rate': round(exam_pass_rate, 1),
        'avg_exam_score': round(avg_exam_score, 1),
        'total_quiz_attempts': total_quiz_attempts,
        'passed_quizzes': passed_quizzes,
        'quiz_pass_rate': round(quiz_pass_rate, 1),
        'avg_quiz_score': round(avg_quiz_score, 1),
        'access_by_method': access_by_method,
        'drop_off_count': drop_off_count,
        'drop_off_rate': round(drop_off_rate, 1),
        'eligible_students_count': eligible_students_count,
    })


# Helper functions (imported from views.py or defined here)
def generate_slug(text):
    """Generate URL-friendly slug from text"""
    import unicodedata
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text.lower())
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


# ========== BUNDLE MANAGEMENT ==========

@staff_member_required
def dashboard_bundles(request):
    """List all bundles"""
    bundles = Bundle.objects.annotate(
        course_count=Count('courses'),
        purchase_count=Count('purchases')
    ).order_by('-created_at')
    
    return render(request, 'dashboard/bundles.html', {
        'bundles': bundles,
    })


@staff_member_required
def dashboard_add_bundle(request):
    """Create a new bundle"""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        bundle_type = request.POST.get('bundle_type', 'fixed')
        price = request.POST.get('price', '') or None
        is_active = request.POST.get('is_active') == 'on'
        max_course_selections = request.POST.get('max_course_selections', '') or None
        course_ids = request.POST.getlist('courses')
        
        if not name:
            messages.error(request, 'Bundle name is required')
            return redirect('dashboard_add_bundle')
        
        # Generate slug from name
        slug = generate_slug(name)
        # Ensure slug is unique
        base_slug = slug
        counter = 1
        while Bundle.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        bundle = Bundle.objects.create(
            name=name,
            slug=slug,
            description=description,
            bundle_type=bundle_type,
            price=float(price) if price else None,
            is_active=is_active,
            max_course_selections=int(max_course_selections) if max_course_selections else None
        )
        
        # Add courses
        if course_ids:
            courses = Course.objects.filter(id__in=course_ids)
            bundle.courses.set(courses)
        
        messages.success(request, f'Bundle "{bundle.name}" created successfully!')
        return redirect('dashboard_bundles')
    
    courses = Course.objects.filter(status='active').order_by('name')
    return render(request, 'dashboard/add_bundle.html', {
        'courses': courses,
    })


@staff_member_required
def dashboard_edit_bundle(request, bundle_id):
    """Edit an existing bundle"""
    bundle = get_object_or_404(Bundle, id=bundle_id)
    
    if request.method == 'POST':
        bundle.name = request.POST.get('name')
        bundle.description = request.POST.get('description', '')
        bundle.bundle_type = request.POST.get('bundle_type', 'fixed')
        price = request.POST.get('price', '') or None
        bundle.is_active = request.POST.get('is_active') == 'on'
        max_course_selections = request.POST.get('max_course_selections', '') or None
        course_ids = request.POST.getlist('courses')
        
        if not bundle.name:
            messages.error(request, 'Bundle name is required')
            return redirect('dashboard_edit_bundle', bundle_id=bundle_id)
        
        # Update slug if name changed
        new_slug = generate_slug(bundle.name)
        if new_slug != bundle.slug:
            base_slug = new_slug
            counter = 1
            while Bundle.objects.filter(slug=new_slug).exclude(id=bundle.id).exists():
                new_slug = f"{base_slug}-{counter}"
                counter += 1
            bundle.slug = new_slug
        
        bundle.price = float(price) if price else None
        bundle.max_course_selections = int(max_course_selections) if max_course_selections else None
        bundle.save()
        
        # Update courses
        if course_ids:
            courses = Course.objects.filter(id__in=course_ids)
            bundle.courses.set(courses)
        else:
            bundle.courses.clear()
        
        messages.success(request, f'Bundle "{bundle.name}" updated successfully!')
        return redirect('dashboard_bundles')
    
    courses = Course.objects.filter(status='active').order_by('name')
    selected_course_ids = bundle.courses.values_list('id', flat=True)
    
    return render(request, 'dashboard/edit_bundle.html', {
        'bundle': bundle,
        'courses': courses,
        'selected_course_ids': selected_course_ids,
    })


@staff_member_required
@require_http_methods(["POST"])
def dashboard_delete_bundle(request, bundle_id):
    """Delete a bundle"""
    bundle = get_object_or_404(Bundle, id=bundle_id)
    bundle_name = bundle.name
    
    # Check if bundle has purchases
    purchase_count = bundle.purchases.count()
    if purchase_count > 0:
        messages.error(request, f'Cannot delete bundle "{bundle_name}" because it has {purchase_count} purchase(s).')
        return redirect('dashboard_bundles')
    
    bundle.delete()
    messages.success(request, f'Bundle "{bundle_name}" deleted successfully!')
    return redirect('dashboard_bundles')


# ============================================================================
# CRM LEAD MANAGEMENT VIEWS
# ============================================================================

@staff_member_required
def dashboard_leads(request):
    """List all leads with filtering, pagination, and search"""
    from django.core.paginator import Paginator
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    source_filter = request.GET.get('source', '')
    owner_filter = request.GET.get('owner', '')
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort', '-updated_at')
    
    # Base queryset
    leads = Lead.objects.all()
    
    # Apply filters
    if status_filter:
        leads = leads.filter(status=status_filter)
    if source_filter:
        leads = leads.filter(source=source_filter)
    if owner_filter:
        leads = leads.filter(owner_id=owner_filter)
    if search_query:
        leads = leads.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    
    # Apply sorting
    valid_sorts = {
        'updated': '-updated_at',
        'created': '-created_at',
        'name': 'first_name',
        'last_contact': '-last_contact_date',
    }
    sort_key = valid_sorts.get(sort_by, '-updated_at')
    leads = leads.order_by(sort_key)
    
    # Pagination
    paginator = Paginator(leads, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    owners = User.objects.filter(is_staff=True).order_by('username')
    
    # AJAX request - return JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        leads_data = []
        for lead in page_obj:
            leads_data.append({
                'id': lead.id,
                'name': lead.get_full_name(),
                'email': lead.email,
                'phone': lead.phone,
                'status': lead.status,
                'status_display': lead.get_status_display(),
                'source': lead.source,
                'source_display': lead.get_source_display(),
                'owner': lead.owner.username if lead.owner else None,
                'last_contact': lead.last_contact_date.isoformat() if lead.last_contact_date else None,
                'created_at': lead.created_at.isoformat(),
                'updated_at': lead.updated_at.isoformat(),
            })
        return JsonResponse({
            'leads': leads_data,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'page_number': page_obj.number,
            'num_pages': paginator.num_pages,
        })
    
    # Regular request - render template
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'source_filter': source_filter,
        'owner_filter': owner_filter,
        'search_query': search_query,
        'sort_by': sort_by,
        'owners': owners,
        'status_choices': Lead.STATUS_CHOICES,
        'source_choices': Lead.SOURCE_CHOICES,
    }
    return render(request, 'dashboard/crm/leads.html', context)


@staff_member_required
def dashboard_lead_detail(request, lead_id):
    """View full lead profile with timeline and linked items"""
    lead = get_object_or_404(Lead, id=lead_id)
    
    # Get timeline events
    timeline_events = lead.timeline_events.all()[:50]
    
    # Get linked enrollments
    enrollment_links = lead.enrollment_links.select_related('enrollment__course', 'enrollment__user').all()
    
    # Get linked gifts
    gift_links = lead.gift_links.select_related('gift__course', 'gift__purchaser').all()
    
    context = {
        'lead': lead,
        'timeline_events': timeline_events,
        'enrollment_links': enrollment_links,
        'gift_links': gift_links,
        'owners': User.objects.filter(is_staff=True).order_by('username'),
    }
    return render(request, 'dashboard/crm/lead_detail.html', context)


@staff_member_required
def dashboard_lead_create(request):
    """Create new lead"""
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        status = request.POST.get('status', 'new')
        source = request.POST.get('source', 'website')
        owner_id = request.POST.get('owner', '')
        notes = request.POST.get('notes', '').strip()
        
        # Validation
        if not first_name or not last_name:
            messages.error(request, 'First name and last name are required.')
            return redirect('dashboard_leads')
        
        if not email:
            messages.error(request, 'Email is required.')
            return redirect('dashboard_leads')
        
        # Check if lead with email already exists
        if Lead.objects.filter(email=email).exists():
            messages.error(request, f'A lead with email {email} already exists.')
            return redirect('dashboard_leads')
        
        # Create lead
        lead = Lead.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            status=status,
            source=source,
            owner_id=owner_id if owner_id else None,
            notes=notes,
        )
        
        # Create timeline event
        LeadTimeline.objects.create(
            lead=lead,
            event_type='LEAD_CREATED',
            actor=request.user,
            description=f"Lead created by {request.user.username}",
        )
        
        messages.success(request, f'Lead "{lead.get_full_name()}" created successfully!')
        return redirect('dashboard_lead_detail', lead_id=lead.id)
    
    context = {
        'status_choices': Lead.STATUS_CHOICES,
        'source_choices': Lead.SOURCE_CHOICES,
        'owners': User.objects.filter(is_staff=True).order_by('username'),
    }
    return render(request, 'dashboard/crm/lead_create.html', context)


@staff_member_required
def dashboard_lead_edit(request, lead_id):
    """Edit lead fields"""
    lead = get_object_or_404(Lead, id=lead_id)
    
    if request.method == 'POST':
        old_status = lead.status
        old_owner = lead.owner
        
        # Update fields
        lead.first_name = request.POST.get('first_name', '').strip()
        lead.last_name = request.POST.get('last_name', '').strip()
        lead.email = request.POST.get('email', '').strip()
        lead.phone = request.POST.get('phone', '').strip()
        lead.status = request.POST.get('status', lead.status)
        lead.source = request.POST.get('source', lead.source)
        lead.notes = request.POST.get('notes', '').strip()
        
        owner_id = request.POST.get('owner', '')
        lead.owner_id = owner_id if owner_id else None
        
        # Update last contact date
        lead.last_contact_date = timezone.now()
        lead.updated_at = timezone.now()
        lead.save()
        
        # Create timeline events for changes
        if old_status != lead.status:
            LeadTimeline.objects.create(
                lead=lead,
                event_type='LEAD_STATUS_CHANGED',
                actor=request.user,
                description=f"Status changed from {old_status} to {lead.status}",
                metadata={'old_status': old_status, 'new_status': lead.status}
            )
        
        if old_owner != lead.owner:
            LeadTimeline.objects.create(
                lead=lead,
                event_type='LEAD_OWNER_CHANGED',
                actor=request.user,
                description=f"Owner changed from {old_owner.username if old_owner else 'None'} to {lead.owner.username if lead.owner else 'None'}",
                metadata={'old_owner_id': old_owner.id if old_owner else None, 'new_owner_id': lead.owner.id if lead.owner else None}
            )
        
        LeadTimeline.objects.create(
            lead=lead,
            event_type='LEAD_UPDATED',
            actor=request.user,
            description=f"Lead updated by {request.user.username}",
        )
        
        messages.success(request, f'Lead "{lead.get_full_name()}" updated successfully!')
        return redirect('dashboard_lead_detail', lead_id=lead.id)
    
    context = {
        'lead': lead,
        'status_choices': Lead.STATUS_CHOICES,
        'source_choices': Lead.SOURCE_CHOICES,
        'owners': User.objects.filter(is_staff=True).order_by('username'),
    }
    return render(request, 'dashboard/crm/lead_edit.html', context)


@staff_member_required
@require_http_methods(["POST"])
def dashboard_lead_add_note(request, lead_id):
    """Add timestamped note to lead"""
    lead = get_object_or_404(Lead, id=lead_id)
    note_text = request.POST.get('note', '').strip()
    
    if not note_text:
        messages.error(request, 'Note cannot be empty.')
        return redirect('dashboard_lead_detail', lead_id=lead.id)
    
    # Append to existing notes
    timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    new_note = f"\n\n[{timestamp}] {request.user.username}: {note_text}"
    lead.notes = (lead.notes + new_note).strip()
    lead.last_contact_date = timezone.now()
    lead.updated_at = timezone.now()
    lead.save()
    
    # Create timeline event
    LeadTimeline.objects.create(
        lead=lead,
        event_type='LEAD_NOTE_ADDED',
        actor=request.user,
        description=f"Note added: {note_text[:100]}",
        metadata={'note': note_text}
    )
    
    messages.success(request, 'Note added successfully!')
    return redirect('dashboard_lead_detail', lead_id=lead.id)


@staff_member_required
@require_http_methods(["POST"])
def dashboard_lead_link_user(request, lead_id):
    """Link or unlink user account to lead"""
    lead = get_object_or_404(Lead, id=lead_id)
    action = request.POST.get('action', 'link')
    user_id = request.POST.get('user_id', '')
    
    if action == 'link':
        if not user_id:
            messages.error(request, 'User ID is required.')
            return redirect('dashboard_lead_detail', lead_id=lead.id)
        
        user = get_object_or_404(User, id=user_id)
        
        # Check if user is already linked to another lead
        if Lead.objects.filter(linked_user=user).exclude(id=lead.id).exists():
            messages.error(request, f'User {user.username} is already linked to another lead.')
            return redirect('dashboard_lead_detail', lead_id=lead.id)
        
        lead.linked_user = user
        lead.save()
        
        # Create timeline event
        LeadTimeline.objects.create(
            lead=lead,
            event_type='USER_LINKED_TO_LEAD',
            actor=request.user,
            description=f"User {user.username} linked to lead",
            metadata={'user_id': user.id, 'user_email': user.email}
        )
        
        messages.success(request, f'User {user.username} linked successfully!')
    
    elif action == 'unlink':
        if lead.linked_user:
            unlinked_user = lead.linked_user
            lead.linked_user = None
            lead.save()
            
            # Create timeline event
            LeadTimeline.objects.create(
                lead=lead,
                event_type='USER_UNLINKED_FROM_LEAD',
                actor=request.user,
                description=f"User {unlinked_user.username} unlinked from lead",
                metadata={'user_id': unlinked_user.id}
            )
            
            messages.success(request, f'User {unlinked_user.username} unlinked successfully!')
    
    return redirect('dashboard_lead_detail', lead_id=lead.id)


@staff_member_required
@require_http_methods(["POST"])
def dashboard_lead_link_gift(request, lead_id):
    """Link or unlink gift enrollment to lead"""
    lead = get_object_or_404(Lead, id=lead_id)
    action = request.POST.get('action', 'link')
    gift_id = request.POST.get('gift_id', '')
    
    if action == 'link':
        if not gift_id:
            messages.error(request, 'Gift ID is required.')
            return redirect('dashboard_lead_detail', lead_id=lead.id)
        
        gift = get_object_or_404(GiftPurchase, id=gift_id)
        
        # Check if already linked
        if LeadGiftLink.objects.filter(lead=lead, gift=gift).exists():
            messages.error(request, 'Gift is already linked to this lead.')
            return redirect('dashboard_lead_detail', lead_id=lead.id)
        
        # Create link
        LeadGiftLink.objects.create(
            lead=lead,
            gift=gift,
            created_by=request.user
        )
        
        # Create timeline event
        LeadTimeline.objects.create(
            lead=lead,
            event_type='GIFT_LINKED_TO_LEAD',
            actor=request.user,
            description=f"Gift for {gift.course.name} linked to lead",
            metadata={'gift_id': gift.id, 'course_id': gift.course.id}
        )
        
        messages.success(request, 'Gift linked successfully!')
    
    elif action == 'unlink':
        if not gift_id:
            messages.error(request, 'Gift ID is required.')
            return redirect('dashboard_lead_detail', lead_id=lead.id)
        
        gift_link = get_object_or_404(LeadGiftLink, lead=lead, gift_id=gift_id)
        gift = gift_link.gift
        gift_link.delete()
        
        # Create timeline event
        LeadTimeline.objects.create(
            lead=lead,
            event_type='GIFT_UNLINKED_FROM_LEAD',
            actor=request.user,
            description=f"Gift for {gift.course.name} unlinked from lead",
            metadata={'gift_id': gift.id}
        )
        
        messages.success(request, 'Gift unlinked successfully!')
    
    return redirect('dashboard_lead_detail', lead_id=lead.id)


@staff_member_required
@require_http_methods(["POST"])
def dashboard_lead_link_enrollment(request, lead_id):
    """Link or unlink enrollment to lead"""
    lead = get_object_or_404(Lead, id=lead_id)
    action = request.POST.get('action', 'link')
    enrollment_id = request.POST.get('enrollment_id', '')
    
    if action == 'link':
        if not enrollment_id:
            messages.error(request, 'Enrollment ID is required.')
            return redirect('dashboard_lead_detail', lead_id=lead.id)
        
        enrollment = get_object_or_404(CourseEnrollment, id=enrollment_id)
        
        # Check if already linked
        if LeadEnrollmentLink.objects.filter(lead=lead, enrollment=enrollment).exists():
            messages.error(request, 'Enrollment is already linked to this lead.')
            return redirect('dashboard_lead_detail', lead_id=lead.id)
        
        # Create link
        LeadEnrollmentLink.objects.create(
            lead=lead,
            enrollment=enrollment,
            created_by=request.user
        )
        
        # Create timeline event
        LeadTimeline.objects.create(
            lead=lead,
            event_type='ENROLLMENT_LINKED_TO_LEAD',
            actor=request.user,
            description=f"Enrollment in {enrollment.course.name} linked to lead",
            metadata={'enrollment_id': enrollment.id, 'course_id': enrollment.course.id}
        )
        
        messages.success(request, 'Enrollment linked successfully!')
    
    elif action == 'unlink':
        if not enrollment_id:
            messages.error(request, 'Enrollment ID is required.')
            return redirect('dashboard_lead_detail', lead_id=lead.id)
        
        enrollment_link = get_object_or_404(LeadEnrollmentLink, lead=lead, enrollment_id=enrollment_id)
        enrollment = enrollment_link.enrollment
        enrollment_link.delete()
        
        # Create timeline event
        LeadTimeline.objects.create(
            lead=lead,
            event_type='ENROLLMENT_UNLINKED_FROM_LEAD',
            actor=request.user,
            description=f"Enrollment in {enrollment.course.name} unlinked from lead",
            metadata={'enrollment_id': enrollment.id}
        )
        
        messages.success(request, 'Enrollment unlinked successfully!')
    
    return redirect('dashboard_lead_detail', lead_id=lead.id)


@staff_member_required
def dashboard_crm_analytics(request):
    """CRM Analytics dashboard"""
    from django.db.models import Count, Q
    from datetime import datetime, timedelta
    
    # Date range filter
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    owner_filter = request.GET.get('owner', '')
    source_filter = request.GET.get('source', '')
    
    # Base queryset
    leads = Lead.objects.all()
    
    # Apply date filters
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            leads = leads.filter(created_at__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            leads = leads.filter(created_at__lt=date_to_obj)
        except ValueError:
            pass
    
    # Apply other filters
    if owner_filter:
        leads = leads.filter(owner_id=owner_filter)
    if source_filter:
        leads = leads.filter(source=source_filter)
    
    # Calculate metrics
    total_leads = leads.count()
    leads_by_status = leads.values('status').annotate(count=Count('id')).order_by('-count')
    enrolled_leads = leads.filter(status='enrolled').count()
    conversion_rate = (enrolled_leads / total_leads * 100) if total_leads > 0 else 0
    
    # Source performance
    source_performance = leads.values('source').annotate(
        total=Count('id'),
        enrolled=Count('id', filter=Q(status='enrolled'))
    ).order_by('-total')
    
    for item in source_performance:
        item['conversion_rate'] = (item['enrolled'] / item['total'] * 100) if item['total'] > 0 else 0
    
    context = {
        'total_leads': total_leads,
        'leads_by_status': leads_by_status,
        'enrolled_leads': enrolled_leads,
        'conversion_rate': round(conversion_rate, 2),
        'source_performance': source_performance,
        'date_from': date_from,
        'date_to': date_to,
        'owner_filter': owner_filter,
        'source_filter': source_filter,
        'owners': User.objects.filter(is_staff=True).order_by('username'),
        'source_choices': Lead.SOURCE_CHOICES,
    }
    return render(request, 'dashboard/crm/analytics.html', context)


# ========== TEACHER REQUEST MANAGEMENT ==========

@staff_member_required
def dashboard_teacher_requests(request):
    """List all teacher registration requests and approved teachers"""
    status_filter = request.GET.get('status', 'pending')
    search_query = request.GET.get('search', '')
    
    requests = TeacherRequest.objects.all()
    
    if status_filter and status_filter != 'all':
        requests = requests.filter(status=status_filter)
    
    if search_query:
        requests = requests.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(user__username__icontains=search_query)
        )
    
    requests = requests.order_by('-created_at')
    
    # Count by status
    pending_count = TeacherRequest.objects.filter(status='pending').count()
    approved_count = TeacherRequest.objects.filter(status='approved').count()
    rejected_count = TeacherRequest.objects.filter(status='rejected').count()
    
    # Get list of approved teachers (users with approved TeacherRequest or who teach courses)
    from django.contrib.auth.models import User
    from django.db.models import Count
    
    # Get users with approved teacher requests
    approved_request_users = TeacherRequest.objects.filter(
        status='approved'
    ).values_list('user_id', flat=True)
    
    # Get all teachers (users who teach courses or have approved requests)
    teachers = User.objects.filter(
        Q(id__in=approved_request_users) | Q(taught_courses__isnull=False)
    ).distinct().annotate(
        course_count=Count('taught_courses')
    ).order_by('-date_joined')
    
    # Apply search to teachers if provided
    if search_query:
        teachers = teachers.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    context = {
        'requests': requests,
        'status_filter': status_filter,
        'search_query': search_query,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'teachers': teachers,
    }
    return render(request, 'dashboard/teacher_requests.html', context)


@staff_member_required
def dashboard_teacher_request_detail(request, request_id):
    """View detailed teacher request"""
    teacher_request = get_object_or_404(TeacherRequest, id=request_id)
    
    context = {
        'request': teacher_request,
    }
    return render(request, 'dashboard/teacher_request_detail.html', context)


@staff_member_required
@require_http_methods(["POST"])
def dashboard_teacher_request_approve(request, request_id):
    """Approve a teacher request"""
    from django.utils import timezone
    from .utils.email import send_teacher_approval_email
    
    teacher_request = get_object_or_404(TeacherRequest, id=request_id)
    
    if teacher_request.status != 'pending':
        messages.error(request, 'This request has already been processed.')
        return redirect('dashboard_teacher_request_detail', request_id=request_id)
    
    # Update status
    teacher_request.status = 'approved'
    teacher_request.reviewed_by = request.user
    teacher_request.reviewed_at = timezone.now()
    teacher_request.save()
    
    # Set user as staff (teacher) if user exists
    if teacher_request.user:
        teacher_request.user.is_staff = True
        teacher_request.user.save()
    
    # Send approval email
    email_result = send_teacher_approval_email(teacher_request)
    
    messages.success(request, f'Teacher request approved! Email sent to {teacher_request.email}.')
    return redirect('dashboard_teacher_request_detail', request_id=request_id)


@staff_member_required
@require_http_methods(["POST"])
def dashboard_teacher_request_reject(request, request_id):
    """Reject a teacher request"""
    from django.utils import timezone
    from .utils.email import send_teacher_rejection_email
    
    teacher_request = get_object_or_404(TeacherRequest, id=request_id)
    
    if teacher_request.status != 'pending':
        messages.error(request, 'This request has already been processed.')
        return redirect('dashboard_teacher_request_detail', request_id=request_id)
    
    rejection_reason = request.POST.get('rejection_reason', '').strip()
    
    # Update status
    teacher_request.status = 'rejected'
    teacher_request.reviewed_by = request.user
    teacher_request.reviewed_at = timezone.now()
    if rejection_reason:
        teacher_request.admin_notes = f"Rejection reason: {rejection_reason}"
    teacher_request.save()
    
    # Send rejection email
    email_result = send_teacher_rejection_email(teacher_request, rejection_reason)
    
    messages.success(request, f'Teacher request rejected. Email sent to {teacher_request.email}.')
    return redirect('dashboard_teacher_request_detail', request_id=request_id)

