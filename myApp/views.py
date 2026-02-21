from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.conf import settings
from django.utils.text import slugify
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
    CoursePurchase,
    TeacherRequest,
    GiftPurchase,
)
from django.db.models import Avg, Count, Q
from django.db import models
from django.utils import timezone
from .utils.transcription import transcribe_video
from .utils.access import has_course_access


def landing(request):
    """Premium landing page view"""
    # Get featured courses for the landing page (exclude Tawjehi courses)
    courses = Course.objects.filter(status='active', visibility='public').exclude(course_type='tawjehi')[:6]
    return render(request, 'landing.html', {
        'courses': courses,
    })

def tawjehi_page(request):
    """Tawjehi exam preparation courses page"""
    # Get only Tawjehi courses
    tawjehi_courses = Course.objects.filter(
        status='active',
        course_type='tawjehi'
    ).order_by('name')
    
    # Group courses by subject
    subjects = {
        'physics': {'name': 'Physics', 'icon': 'fa-atom', 'courses': []},
        'mathematics': {'name': 'Mathematics', 'icon': 'fa-calculator', 'courses': []},
        'english': {'name': 'English', 'icon': 'fa-language', 'courses': []},
        'arabic': {'name': 'Arabic', 'icon': 'fa-book', 'courses': []},
        'chemistry': {'name': 'Chemistry', 'icon': 'fa-flask', 'courses': []},
        'biology': {'name': 'Biology', 'icon': 'fa-dna', 'courses': []},
        'other': {'name': 'Other Subjects', 'icon': 'fa-graduation-cap', 'courses': []},
    }
    
    # Categorize courses by subject (checking name for subject keywords)
    for course in tawjehi_courses:
        course_name_lower = course.name.lower()
        categorized = False
        
        for subject_key, subject_info in subjects.items():
            if subject_key == 'other':
                continue
            if subject_key in course_name_lower:
                subjects[subject_key]['courses'].append(course)
                categorized = True
                break
        
        if not categorized:
            subjects['other']['courses'].append(course)
    
    # Remove empty subject categories
    subjects = {k: v for k, v in subjects.items() if v['courses']}
    
    return render(request, 'tawjehi/tawjehi_page.html', {
        'subjects': subjects,
        'all_courses': tawjehi_courses,
    })

def home(request):
    """Home page view - shows courses hub (premium landing)"""
    # Get all active courses for the homepage (exclude Tawjehi courses)
    courses = Course.objects.filter(status='active', visibility='public').exclude(course_type='tawjehi')
    
    # Define category mappings
    CATEGORY_MAPPING = {
        'natural_health': {
            'name': 'Natural Health',
            'icon': 'fa-seedling',
            'description': 'Holistic wellness & natural therapies',
            'subtitle': 'Learn plant-based healing, herbs, and holistic wellness tools.',
            'course_types': ['aroma_therapy', 'nutrition', 'naturopathy', 'ayurveda'],
            'color': 'emerald',
            'bg_color': 'emerald-200/60',
            'badge_color': 'emerald-100/70',
            'text_color': 'emerald-700',
            'icon_bg': 'from-emerald-100 to-teal-soft/60',
            'icon_text': 'emerald-800',
            'hover_border': 'teal-soft/50',
            'hover_shadow': 'teal-soft/10',
            'link_color': 'teal-soft',
        },
        'personal_development': {
            'name': 'Personal Development',
            'icon': 'fa-brain',
            'description': 'Mindset, psychology, and performance',
            'subtitle': 'Coach others (and yourself) through proven growth frameworks.',
            'course_types': ['positive_psychology', 'nlp', 'art_therapy', 'hypnotherapy'],
            'color': 'sky',
            'bg_color': 'sky-200/70',
            'badge_color': 'sky-100/80',
            'text_color': 'sky-800',
            'icon_bg': 'from-sky-100 to-blue-soft/70',
            'icon_text': 'sky-900',
            'hover_border': 'blue-soft/50',
            'hover_shadow': 'blue-soft/10',
            'link_color': 'blue-soft',
        },
        'energy_therapies': {
            'name': 'Energy Therapies',
            'icon': 'fa-bolt',
            'description': 'Subtle energy & transformational work',
            'subtitle': 'Learn modalities that support emotional, mental, and spiritual wellness.',
            'course_types': [],  # Will include any courses not in other categories
            'color': 'purple',
            'bg_color': 'purple-200/80',
            'badge_color': 'purple-100/80',
            'text_color': 'purple-800',
            'icon_bg': 'from-purple-100 to-purple-400/80',
            'icon_text': 'purple-900',
            'hover_border': 'purple-400/60',
            'hover_shadow': 'purple-300/20',
            'link_color': 'purple-700',
        },
    }
    
    # Group courses by category
    categories_data = {}
    all_categorized_types = set()
    
    for cat_key, cat_info in CATEGORY_MAPPING.items():
        categories_data[cat_key] = {
            **cat_info,
            'courses': [],
        }
        all_categorized_types.update(cat_info['course_types'])
    
    # Get progress and favorite status for each course if user is authenticated
    courses_data = []
    user = request.user if request.user.is_authenticated else None
    
    for course in courses:
        course_info = {
            'course': course,
            'has_any_progress': False,
            'progress_percentage': 0,
            'is_favorited': False,
        }
        
        if user:
            # Check if course has any progress
            has_any_progress = UserProgress.objects.filter(
                user=user,
                lesson__course=course
            ).filter(
                Q(completed=True) | Q(video_watch_percentage__gt=0) | Q(status__in=['in_progress', 'completed'])
            ).exists()
            
            # Calculate progress percentage
            total_lessons = course.lessons.count()
            completed_lessons = UserProgress.objects.filter(
                user=user,
                lesson__course=course,
                completed=True
            ).count()
            progress_percentage = int((completed_lessons / total_lessons * 100)) if total_lessons > 0 else 0
            
            # Check if favorited
            from .models import FavoriteCourse
            is_favorited = FavoriteCourse.objects.filter(user=user, course=course).exists()
            
            course_info.update({
                'has_any_progress': has_any_progress,
                'progress_percentage': progress_percentage,
                'is_favorited': is_favorited,
            })
        
        courses_data.append(course_info)
        
        # Categorize course
        course_type = course.course_type
        categorized = False
        
        for cat_key, cat_info in CATEGORY_MAPPING.items():
            if course_type in cat_info['course_types']:
                categories_data[cat_key]['courses'].append(course)
                categorized = True
                break
        
        # If not categorized, add to energy_therapies or create a catch-all
        if not categorized:
            categories_data['energy_therapies']['courses'].append(course)
    
    # Filter out categories with no courses
    categories_list = [
        cat_data for cat_key, cat_data in categories_data.items()
        if len(cat_data['courses']) > 0
    ]
    
    # Select featured courses (top 3)
    # Priority: courses with special_tag first, then by lesson count
    from django.db.models import Count, Case, When, IntegerField
    featured_courses = list(
        courses.annotate(
            lesson_count=Count('lessons'),
            has_special_tag=Case(
                When(special_tag='', then=0),
                default=1,
                output_field=IntegerField()
            )
        )
        .order_by('-has_special_tag', '-lesson_count', 'id')[:3]
    )
    
    # Map course types to styling
    COURSE_STYLE_MAP = {
        'aroma_therapy': {
            'color': 'teal',
            'bg_gradient': 'from-emerald-100 via-emerald-50 to-teal-soft/30',
            'icon': 'fa-leaf',
            'icon_color': 'emerald-700',
            'border_color': 'emerald-200/80',
            'hover_border': 'teal-soft/60',
            'hover_shadow': 'teal-soft/10',
            'badge_color': 'teal-soft',
            'badge_bg': 'teal-soft/5',
            'link_color': 'teal-soft',
        },
        'hypnotherapy': {
            'color': 'blue',
            'bg_gradient': 'from-slate-900 via-slate-800 to-blue-soft/60',
            'icon': 'fa-brain',
            'icon_color': 'blue-soft',
            'border_color': 'slate-600/60',
            'hover_border': 'blue-soft/60',
            'hover_shadow': 'blue-soft/10',
            'badge_color': 'blue-soft',
            'badge_bg': 'blue-soft/5',
            'link_color': 'blue-soft',
        },
        'nutrition': {
            'color': 'coral',
            'bg_gradient': 'from-amber-100 via-orange-50 to-coral-cta/50',
            'icon': 'fa-carrot',
            'icon_color': 'amber-700',
            'border_color': 'amber-300',
            'hover_border': 'coral-cta/60',
            'hover_shadow': 'coral-cta/10',
            'badge_color': 'coral-cta',
            'badge_bg': 'coral-cta/5',
            'link_color': 'coral-cta',
        },
        'art_therapy': {
            'color': 'purple',
            'bg_gradient': 'from-purple-100 via-purple-50 to-purple-400/50',
            'icon': 'fa-palette',
            'icon_color': 'purple-700',
            'border_color': 'purple-200/80',
            'hover_border': 'purple-400/60',
            'hover_shadow': 'purple-300/10',
            'badge_color': 'purple-600',
            'badge_bg': 'purple-100/5',
            'link_color': 'purple-600',
        },
        'positive_psychology': {
            'color': 'sky',
            'bg_gradient': 'from-sky-100 via-sky-50 to-blue-soft/50',
            'icon': 'fa-heart',
            'icon_color': 'sky-700',
            'border_color': 'sky-200/80',
            'hover_border': 'sky-400/60',
            'hover_shadow': 'sky-300/10',
            'badge_color': 'sky-600',
            'badge_bg': 'sky-100/5',
            'link_color': 'sky-600',
        },
        'nlp': {
            'color': 'indigo',
            'bg_gradient': 'from-indigo-100 via-indigo-50 to-indigo-400/50',
            'icon': 'fa-lightbulb',
            'icon_color': 'indigo-700',
            'border_color': 'indigo-200/80',
            'hover_border': 'indigo-400/60',
            'hover_shadow': 'indigo-300/10',
            'badge_color': 'indigo-600',
            'badge_bg': 'indigo-100/5',
            'link_color': 'indigo-600',
        },
    }
    
    # Get default style for courses without specific mapping
    default_style = {
        'color': 'teal',
        'bg_gradient': 'from-emerald-100 via-emerald-50 to-teal-soft/30',
        'icon': 'fa-book-open',
        'icon_color': 'emerald-700',
        'border_color': 'emerald-200/80',
        'hover_border': 'teal-soft/60',
        'hover_shadow': 'teal-soft/10',
        'badge_color': 'teal-soft',
        'badge_bg': 'teal-soft/5',
        'link_color': 'teal-soft',
    }
    
    # Render the new premium landing page instead of the old partialsv2 hub
    return render(request, 'landing.html', {
        'courses': courses,
        'courses_data': courses_data,
        'categories': categories_list,
        'featured_courses': featured_courses[:6],
        'course_style_map': COURSE_STYLE_MAP,
        'default_style': default_style,
    })


def _is_teacher_user(user):
    """Helper function to check if a user is a teacher (not admin)
    
    A user is a teacher if:
    - They have an approved TeacherRequest, OR
    - They teach at least one course (have taught_courses)
    
    Note: Superusers are always admins, not teachers.
    """
    if not user or not user.is_authenticated:
        return False
    
    # Superusers are admins, not teachers
    if user.is_superuser:
        return False
    
    # Refresh user from database to ensure we have latest data
    try:
        user.refresh_from_db()
    except:
        pass
    
    # Check if user has approved TeacherRequest (this is the primary indicator)
    from .models import TeacherRequest
    try:
        # Use user.id to avoid any potential caching issues
        if TeacherRequest.objects.filter(user_id=user.id, status='approved').exists():
            return True
    except Exception as e:
        # Log error but continue
        pass
    
    # Check if user teaches any courses (secondary check)
    try:
        # Use user.id to avoid any potential caching issues
        from .models import Course
        if Course.objects.filter(teachers__id=user.id).exists():
            return True
    except Exception as e:
        # Log error but continue
        pass
    
    return False


def login_view(request):
    """Premium login page"""
    # Allow access to login page even when logged in if ?force=true (for testing)
    force = request.GET.get('force', '').lower() == 'true'
    if request.user.is_authenticated and not force:
        # Redirect based on user role: admin → admin dashboard, teacher → teacher dashboard, student → student dashboard
        if request.user.is_superuser:
            return redirect('dashboard_home')
        elif _is_teacher_user(request.user):
            return redirect('teacher_dashboard')
        elif request.user.is_staff:
            return redirect('dashboard_home')  # Staff but not teacher → admin dashboard
        else:
            return redirect('student_dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Determine redirect based on user role
            if user.is_superuser:
                next_url = request.GET.get('next', 'dashboard_home')
            elif _is_teacher_user(user):
                next_url = request.GET.get('next', 'teacher_dashboard')
            elif user.is_staff:
                next_url = request.GET.get('next', 'dashboard_home')
            else:
                next_url = request.GET.get('next', 'student_dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'login.html')


def register_view(request):
    """Premium registration page"""
    # Redirect if already logged in
    if request.user.is_authenticated:
        return redirect('student_dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        
        # Validation
        errors = []
        
        if not username:
            errors.append('Username is required.')
        elif len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        elif User.objects.filter(username=username).exists():
            errors.append('Username already exists.')
        
        if not email:
            errors.append('Email is required.')
        elif User.objects.filter(email=email).exists():
            errors.append('Email already registered.')
        
        if not password:
            errors.append('Password is required.')
        elif len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        
        if password != password_confirm:
            errors.append('Passwords do not match.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            # Create user
            try:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
                # Automatically log in the user
                login(request, user)
                messages.success(request, 'Account created successfully! Welcome to Fluentory.')
                
                # If registering with a gift, redirect to redeem
                gift_token = request.GET.get('gift')
                if gift_token:
                    return redirect('redeem_gift', gift_token=gift_token)
                
                return redirect('student_dashboard')
            except Exception as e:
                messages.error(request, f'Error creating account: {str(e)}')
    
    return render(request, 'register.html')


def register_teacher_view(request):
    """Teacher registration view"""
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        bio = request.POST.get('bio', '').strip()
        qualifications = request.POST.get('qualifications', '').strip()
        languages_spoken = request.POST.get('languages_spoken', '').strip()
        teaching_experience = request.POST.get('teaching_experience', '').strip()
        motivation = request.POST.get('motivation', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        password_confirm = request.POST.get('password_confirm', '').strip()
        
        # Validation
        if not all([first_name, last_name, email, bio, qualifications, languages_spoken, teaching_experience, motivation, username, password]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'register_teacher.html')
        
        if password != password_confirm:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'register_teacher.html')
        
        if len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'register_teacher.html')
        
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists. Please choose a different one.')
            return render(request, 'register_teacher.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered. Please use a different email or log in.')
            return render(request, 'register_teacher.html')
        
        # Check if there's already a pending request for this email
        if TeacherRequest.objects.filter(email=email, status='pending').exists():
            messages.info(request, 'You already have a pending teacher registration request. We will review it shortly.')
            return render(request, 'register_teacher.html')
        
        # Create user account
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            # Create teacher request
            teacher_request = TeacherRequest.objects.create(
                user=user,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                bio=bio,
                qualifications=qualifications,
                languages_spoken=languages_spoken,
                teaching_experience=teaching_experience,
                motivation=motivation,
                status='pending'
            )
            
            # Send confirmation email
            from .utils.email import send_teacher_request_email
            email_result = send_teacher_request_email(teacher_request)
            
            # Notify admins
            from .utils.email import notify_admin_teacher_request
            notify_admin_teacher_request(teacher_request)
            
            messages.success(request, 'Your teacher registration request has been submitted! We will review your application and send you an email shortly.')
            return redirect('login')
        except Exception as e:
            messages.error(request, f'Error creating account: {str(e)}')
    
    return render(request, 'register_teacher.html')


def logout_view(request):
    """Logout view"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


def courses(request):
    """Courses listing page"""
    course_type = request.GET.get('type', 'all')
    search_query = request.GET.get('search', '')
    
    # Exclude Tawjehi courses from main course listing
    courses = Course.objects.all().exclude(course_type='tawjehi')
    
    if course_type != 'all':
        courses = courses.filter(course_type=course_type)
    
    if search_query:
        courses = courses.filter(name__icontains=search_query)
    
    # Get progress and favorite status for each course if user is authenticated
    courses_data = []
    in_progress_courses = []
    not_started_courses = []
    user = request.user if request.user.is_authenticated else None
    
    for course in courses:
        course_info = {
            'course': course,
            'has_any_progress': False,
            'progress_percentage': 0,
            'is_favorited': False,
        }
        
        if user:
            # Check if course has any progress
            has_any_progress = UserProgress.objects.filter(
                user=user,
                lesson__course=course
            ).filter(
                Q(completed=True) | Q(video_watch_percentage__gt=0) | Q(status__in=['in_progress', 'completed'])
            ).exists()
            
            # Calculate progress percentage
            total_lessons = course.lessons.count()
            completed_lessons = UserProgress.objects.filter(
                user=user,
                lesson__course=course,
                completed=True
            ).count()
            progress_percentage = int((completed_lessons / total_lessons * 100)) if total_lessons > 0 else 0
            
            # Check if favorited
            from .models import FavoriteCourse
            is_favorited = FavoriteCourse.objects.filter(user=user, course=course).exists()
            
            course_info.update({
                'has_any_progress': has_any_progress,
                'progress_percentage': progress_percentage,
                'is_favorited': is_favorited,
            })
            
            # Separate into in-progress and not-started
            if has_any_progress:
                in_progress_courses.append(course_info)
            else:
                not_started_courses.append(course_info)
        else:
            # For non-authenticated users, put all in not_started
            not_started_courses.append(course_info)
        
        courses_data.append(course_info)
    
    return render(request, 'courses.html', {
        'courses_data': courses_data,  # Keep for backward compatibility
        'in_progress_courses': in_progress_courses,
        'not_started_courses': not_started_courses,
        'courses': courses,  # Keep for backward compatibility
        'selected_type': course_type,
        'search_query': search_query,
    })


def course_detail(request, course_slug):
    """Course detail page - premium sales page"""
    course = get_object_or_404(Course, slug=course_slug)
    
    # For authenticated users with access, redirect to first lesson
    if request.user.is_authenticated:
        from .utils.access import has_course_access
        has_access, access_record, _ = has_course_access(request.user, course)
        if has_access:
            first_lesson = course.lessons.first()
            if first_lesson:
                return lesson_detail(request, course_slug, first_lesson.slug)
    
    # Process preview video URL for embedding
    preview_video_embed_url = None
    video_type = None
    if course.preview_video_url:
        import re
        url = course.preview_video_url.strip()
        
        # YouTube URL processing - handle multiple formats (order matters!)
        youtube_video_id = None
        
        # Try to extract video ID from various YouTube URL formats
        # Pattern 1: youtu.be/VIDEO_ID (short URL - check first as it's most reliable)
        short_match = re.search(r'youtu\.be/([a-zA-Z0-9_-]{11})', url, re.IGNORECASE)
        if short_match:
            youtube_video_id = short_match.group(1)
        
        # Pattern 2: youtube.com/embed/VIDEO_ID
        if not youtube_video_id:
            embed_match = re.search(r'youtube\.com/embed/([a-zA-Z0-9_-]{11})', url, re.IGNORECASE)
            if embed_match:
                youtube_video_id = embed_match.group(1)
        
        # Pattern 3: youtube.com/watch?v=VIDEO_ID (with or without additional params)
        if not youtube_video_id:
            watch_match = re.search(r'youtube\.com/watch\?[^&]*v=([a-zA-Z0-9_-]{11})', url, re.IGNORECASE)
            if watch_match:
                youtube_video_id = watch_match.group(1)
        
        # Pattern 4: youtube.com/v/VIDEO_ID (old format)
        if not youtube_video_id:
            v_match = re.search(r'youtube\.com/v/([a-zA-Z0-9_-]{11})', url, re.IGNORECASE)
            if v_match:
                youtube_video_id = v_match.group(1)
        
        # Validate video ID is exactly 11 characters
        if youtube_video_id and len(youtube_video_id) == 11:
            # Clean YouTube embed URL - simple format
            preview_video_embed_url = f"https://www.youtube.com/embed/{youtube_video_id}"
            video_type = 'youtube'
        elif youtube_video_id:
            # Invalid video ID length - don't treat as YouTube
            youtube_video_id = None
        # Vimeo URL processing
        elif re.search(r'vimeo\.com', url, re.IGNORECASE):
            vimeo_match = re.search(r'vimeo\.com/(?:video/)?(\d+)', url)
            if vimeo_match:
                preview_video_embed_url = f"https://player.vimeo.com/video/{vimeo_match.group(1)}"
                video_type = 'vimeo'
        # Google Drive URL processing
        elif re.search(r'drive\.google\.com', url, re.IGNORECASE):
            drive_match = re.search(r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)', url)
            if drive_match:
                preview_video_embed_url = f"https://drive.google.com/file/d/{drive_match.group(1)}/preview"
                video_type = 'google_drive'
        # Cloudinary URL processing (direct video URLs)
        elif re.search(r'cloudinary\.com', url, re.IGNORECASE):
            # Cloudinary URLs can be used directly, but we can add .mp4 extension if needed
            preview_video_embed_url = url
            video_type = 'cloudinary'
        # If no match, use original URL (for direct video files or other platforms)
        if not preview_video_embed_url:
            preview_video_embed_url = url
            video_type = 'direct'
    
    # Show premium sales page for non-authenticated or users without access
    # Include purchase information if course is paid
    return render(request, 'course_detail.html', {
        'course': course,
        'show_purchase': course.is_paid and course.price is not None,
        'preview_video_embed_url': preview_video_embed_url,
        'video_type': video_type,
        'is_youtube': video_type == 'youtube',
        'is_vimeo': video_type == 'vimeo',
        'is_google_drive': video_type == 'google_drive',
        'is_cloudinary': video_type == 'cloudinary',
        'is_direct': video_type == 'direct',
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

    # Get quiz and quiz attempts for this user
    lesson_quiz = getattr(lesson, 'quiz', None)
    quiz_attempts = None
    latest_quiz_attempt = None
    quiz_passed = False
    if lesson_quiz:
        quiz_attempts = LessonQuizAttempt.objects.filter(
            user=request.user,
            quiz=lesson_quiz
        ).order_by('-completed_at')
        latest_quiz_attempt = quiz_attempts.first() if quiz_attempts.exists() else None
        quiz_passed = LessonQuizAttempt.objects.filter(
            user=request.user,
            quiz=lesson_quiz,
            passed=True
        ).exists()

    # Extract YouTube video ID if video_url is a YouTube URL
    youtube_video_id = None
    if lesson.video_url:
        import re
        # Match various YouTube URL formats - improved patterns
        youtube_patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})',  # Standard formats: watch?v=ID or youtu.be/ID
            r'youtube\.com\/embed\/([a-zA-Z0-9_-]{11})',  # Embed format: embed/ID
            r'youtube\.com\/v\/([a-zA-Z0-9_-]{11})',  # Old format: v/ID
            r'youtube\.com\/watch\?.*[&?]v=([a-zA-Z0-9_-]{11})',  # With other params: watch?param=value&v=ID
            r'youtu\.be\/([a-zA-Z0-9_-]{11})',  # Short URL: youtu.be/ID
        ]
        for pattern in youtube_patterns:
            match = re.search(pattern, lesson.video_url, re.IGNORECASE)
            if match:
                youtube_video_id = match.group(1)
                # Validate it's exactly 11 characters (YouTube video IDs are always 11 chars)
                if len(youtube_video_id) == 11:
                    break
                else:
                    youtube_video_id = None

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
        'lesson_quiz': lesson_quiz,
        'quiz_attempts': quiz_attempts,
        'latest_quiz_attempt': latest_quiz_attempt,
        'quiz_passed': quiz_passed,
        'youtube_video_id': youtube_video_id,
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
    
    # Get next lesson for redirect after passing
    all_lessons = course.lessons.order_by('order', 'id')
    next_lesson = None
    if all_lessons.exists():
        lessons_list = list(all_lessons)
        for idx, l in enumerate(lessons_list):
            if l.id == lesson.id and idx + 1 < len(lessons_list):
                next_lesson = lessons_list[idx + 1]
                break

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
        'next_lesson': next_lesson,
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
        
        # Handle content blocks if provided
        content_blocks_data = None
        content_blocks_json = request.POST.get('content_blocks', '')
        if content_blocks_json:
            try:
                import json
                content_blocks_data = json.loads(content_blocks_json)
            except json.JSONDecodeError:
                pass
        
        # Create lesson draft
        lesson = Lesson.objects.create(
            course=course,
            working_title=working_title,
            rough_notes=rough_notes,
            title=working_title,  # Temporary
            slug=generate_slug(working_title),
            description='',  # Will be AI-generated
        )
        
        # Handle content blocks if provided
        if content_blocks_data:
            # Convert to Editor.js format
            editorjs_blocks = []
            for block in content_blocks_data:
                if block.get('type') == 'paragraph':
                    editorjs_blocks.append({
                        'type': 'paragraph',
                        'data': {
                            'text': block.get('data', {}).get('text', '')
                        }
                    })
                elif block.get('type') == 'header':
                    editorjs_blocks.append({
                        'type': 'header',
                        'data': {
                            'text': block.get('data', {}).get('text', ''),
                            'level': int(block.get('data', {}).get('level', 2))
                        }
                    })
                elif block.get('type') == 'image':
                    editorjs_blocks.append({
                        'type': 'image',
                        'data': {
                            'file': {
                                'url': block.get('data', {}).get('url', '')
                            },
                            'caption': block.get('data', {}).get('caption', ''),
                            'withBorder': False,
                            'withBackground': False,
                            'stretched': False
                        }
                    })
                elif block.get('type') == 'list':
                    items = block.get('data', {}).get('items', [])
                    if isinstance(items, str):
                        items = [item.strip() for item in items.split('\n') if item.strip()]
                    editorjs_blocks.append({
                        'type': 'list',
                        'data': {
                            'style': block.get('data', {}).get('style', 'unordered'),
                            'items': items
                        }
                    })
            
            lesson.content = {
                'blocks': editorjs_blocks
            }
        
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
        
        # If content blocks were added, they're already saved in the lesson.content field
        # Redirect to AI generation page (which will show the content blocks)
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
            
            # Handle video URL updates (also save on approve)
            vimeo_url = request.POST.get('vimeo_url', '').strip()
            google_drive_url = request.POST.get('google_drive_url', '').strip()
            video_url = request.POST.get('video_url', '').strip()
            
            if vimeo_url:
                lesson.vimeo_url = vimeo_url
                # Extract Vimeo ID from URL if possible
                if 'vimeo.com/' in vimeo_url:
                    vimeo_id = vimeo_url.split('vimeo.com/')[-1].split('?')[0].split('/')[-1]
                    if vimeo_id.isdigit():
                        lesson.vimeo_id = vimeo_id
            else:
                # Only clear if explicitly empty (don't clear if field wasn't in form)
                if 'vimeo_url' in request.POST:
                    lesson.vimeo_url = ''
                    lesson.vimeo_id = ''
            
            if google_drive_url:
                lesson.google_drive_url = google_drive_url
                # Extract Google Drive ID from URL if possible
                if '/d/' in google_drive_url:
                    drive_id = google_drive_url.split('/d/')[1].split('/')[0]
                    lesson.google_drive_id = drive_id
            else:
                # Only clear if explicitly empty (don't clear if field wasn't in form)
                if 'google_drive_url' in request.POST:
                    lesson.google_drive_url = ''
                    lesson.google_drive_id = ''
            
            # Always update video_url if it's in the POST data
            if 'video_url' in request.POST:
                lesson.video_url = video_url
                if video_url:
                    messages.info(request, f'Video URL saved: {video_url[:50]}...')
                else:
                    lesson.video_url = ''
            
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
            
            # Handle content blocks update
            import json
            content_blocks_json = request.POST.get('content_blocks', '')
            if content_blocks_json:
                try:
                    content_data = json.loads(content_blocks_json)
                    lesson.content = content_data
                except json.JSONDecodeError:
                    messages.error(request, 'Invalid content blocks format.')
            
            # Handle video URL updates
            vimeo_url = request.POST.get('vimeo_url', '').strip()
            google_drive_url = request.POST.get('google_drive_url', '').strip()
            video_url = request.POST.get('video_url', '').strip()
            
            # Debug: Log what we received
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Video URL POST data - vimeo_url: '{vimeo_url}', google_drive_url: '{google_drive_url}', video_url: '{video_url}'")
            
            if vimeo_url:
                lesson.vimeo_url = vimeo_url
                # Extract Vimeo ID from URL if possible
                if 'vimeo.com/' in vimeo_url:
                    vimeo_id = vimeo_url.split('vimeo.com/')[-1].split('?')[0].split('/')[-1]
                    if vimeo_id.isdigit():
                        lesson.vimeo_id = vimeo_id
            else:
                # Only clear if explicitly empty (don't clear if field wasn't in form)
                if 'vimeo_url' in request.POST:
                    lesson.vimeo_url = ''
                    lesson.vimeo_id = ''
            
            if google_drive_url:
                lesson.google_drive_url = google_drive_url
                # Extract Google Drive ID from URL if possible
                if '/d/' in google_drive_url:
                    drive_id = google_drive_url.split('/d/')[1].split('/')[0]
                    lesson.google_drive_id = drive_id
            else:
                # Only clear if explicitly empty (don't clear if field wasn't in form)
                if 'google_drive_url' in request.POST:
                    lesson.google_drive_url = ''
                    lesson.google_drive_id = ''
            
            # Always update video_url if it's in the POST data
            if 'video_url' in request.POST:
                lesson.video_url = video_url
                if video_url:
                    messages.info(request, f'Video URL saved: {video_url[:50]}...')
                else:
                    lesson.video_url = ''
            
            lesson.save()
            messages.success(request, 'Lesson content updated successfully.')
    
    return render(request, 'creator/generate_lesson_ai.html', {
        'course': course,
        'lesson': lesson,
    })


@staff_member_required
def upload_pdf_lessons(request, course_slug):
    """Upload PDF files and generate lesson content"""
    course = get_object_or_404(Course, slug=course_slug)
    
    if request.method == 'POST':
        module_name = request.POST.get('module_name', '').strip()
        pdf_files = request.FILES.getlist('pdf_files')
        use_ai = request.POST.get('use_ai_generation') == 'on'
        split_by_pages = request.POST.get('split_by_pages')
        split_by_pages = int(split_by_pages) if split_by_pages and split_by_pages.isdigit() else None
        
        if not module_name:
            messages.error(request, 'Module name is required.')
            return render(request, 'creator/upload_pdf_lessons.html', {
                'course': course,
            })
        
        if not pdf_files:
            messages.error(request, 'Please select at least one PDF file.')
            return render(request, 'creator/upload_pdf_lessons.html', {
                'course': course,
            })
        
        # Import utilities
        try:
            from myApp.utils.pdf_extractor import PDFExtractor
            from myApp.utils.ai_content_generator import AIContentGenerator
            from myApp.utils.pdf_image_extractor import PDFImageExtractor
            from django.db.models import Max
        except ImportError as e:
            messages.error(request, f'Required packages not installed: {str(e)}')
            return render(request, 'creator/upload_pdf_lessons.html', {
                'course': course,
            })
        
        # Initialize extractor and AI generator
        pdf_extractor = PDFExtractor()
        image_extractor = None
        try:
            image_extractor = PDFImageExtractor()
        except Exception as e:
            messages.warning(request, f'Image extraction not available: {str(e)}. PDFs will be processed without images.')
        
        ai_generator = None
        if use_ai:
            try:
                ai_generator = AIContentGenerator()
            except Exception as e:
                messages.warning(request, f'AI generation not available: {str(e)}. Using basic text extraction.')
                use_ai = False
        
        # Get or create module
        module, module_created = Module.objects.get_or_create(
            course=course,
            name=module_name,
            defaults={
                'order': (Module.objects.filter(course=course).aggregate(max_order=Max('order'))['max_order'] or 0) + 1,
                'description': f'Module content for {module_name}'
            }
        )
        
        if module_created:
            messages.success(request, f'Created module: {module_name}')
        
        # Process each PDF
        lessons_created = 0
        lessons_updated = 0
        errors = []
        
        for pdf_file in pdf_files:
            try:
                # Save uploaded file temporarily
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                    for chunk in pdf_file.chunks():
                        temp_file.write(chunk)
                    temp_path = temp_file.name
                
                try:
                    # Extract images from PDF (if image extractor is available)
                    pdf_images = []
                    if image_extractor:
                        try:
                            # Generate a prefix for image public_ids based on PDF filename
                            pdf_name_slug = slugify(os.path.splitext(pdf_file.name)[0])
                            pdf_images = image_extractor.extract_and_upload_images(
                                temp_path,
                                folder='pdf-lessons',
                                public_id_prefix=pdf_name_slug,
                                min_size=500,  # Minimum 500px width or height
                                quality=85
                            )
                            if pdf_images:
                                messages.info(request, f'Extracted and uploaded {len(pdf_images)} image(s) from {pdf_file.name}')
                        except Exception as e:
                            messages.warning(request, f'Could not extract images from {pdf_file.name}: {str(e)}')
                    
                    if split_by_pages and split_by_pages > 0:
                        # Split PDF into multiple lessons
                        chunks = pdf_extractor.extract_by_pages(temp_path, split_by_pages)
                        
                        for i, chunk in enumerate(chunks, 1):
                            suggested_title = f"{os.path.splitext(pdf_file.name)[0]} - Part {i}"
                            # Filter images for this chunk's page range
                            chunk_images = [
                                img for img in pdf_images 
                                if chunk['start_page'] <= img['page_num'] <= chunk['end_page']
                            ]
                            created, updated = _process_pdf_chunk(
                                course, module, chunk['text'], suggested_title,
                                ai_generator, not use_ai, course.name, module_name,
                                images=chunk_images
                            )
                            lessons_created += created
                            lessons_updated += updated
                    else:
                        # Process entire PDF as single lesson
                        pdf_text = pdf_extractor.extract_text(temp_path)
                        suggested_title = os.path.splitext(pdf_file.name)[0]
                        
                        created, updated = _process_pdf_chunk(
                            course, module, pdf_text, suggested_title,
                            ai_generator, not use_ai, course.name, module_name,
                            images=pdf_images
                        )
                        lessons_created += created
                        lessons_updated += updated
                        
                finally:
                    # Clean up temporary file
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except:
                            pass
                            
            except Exception as e:
                errors.append(f"Error processing {pdf_file.name}: {str(e)}")
                continue
        
        # Show results
        if lessons_created > 0:
            messages.success(request, f'Successfully created {lessons_created} lesson(s)!')
        if lessons_updated > 0:
            messages.info(request, f'Updated {lessons_updated} existing lesson(s).')
        if errors:
            for error in errors:
                messages.error(request, error)
        
        # Redirect back to appropriate page based on referrer
        referrer = request.META.get('HTTP_REFERER', '')
        if 'dashboard' in referrer:
            return redirect('dashboard_course_lessons', course_slug=course_slug)
        return redirect('course_lessons', course_slug=course_slug)
    
    return render(request, 'creator/upload_pdf_lessons.html', {
        'course': course,
    })


@staff_member_required
def clear_course_lessons(request, course_slug):
    """Clear all lessons from a course (for testing/re-uploading)"""
    course = get_object_or_404(Course, slug=course_slug)
    module_name = request.GET.get('module_name', '').strip() or request.POST.get('module_name', '').strip()
    
    if request.method == 'POST':
        try:
            if module_name:
                # Clear lessons from specific module
                module = Module.objects.filter(course=course, name=module_name).first()
                if module:
                    lessons_count = module.lessons.count()
                    module.lessons.all().delete()
                    messages.success(request, f'Cleared {lessons_count} lesson(s) from module "{module_name}"')
                else:
                    messages.warning(request, f'Module "{module_name}" not found. No lessons to clear.')
            else:
                # Clear all lessons from course
                lessons_count = course.lessons.count()
                course.lessons.all().delete()
                messages.success(request, f'Cleared {lessons_count} lesson(s) from course "{course.name}"')
        except Exception as e:
            messages.error(request, f'Error clearing lessons: {str(e)}')
    
    # Redirect back to appropriate page based on referrer
    referrer = request.META.get('HTTP_REFERER', '')
    if 'dashboard' in referrer:
        return redirect('dashboard_upload_pdf_lessons', course_slug=course_slug)
    return redirect('upload_pdf_lessons', course_slug=course_slug)


def _insert_images_contextually(content_blocks, images, pdf_text):
    """
    Insert images into content blocks at logical positions based on page numbers.
    Images are inserted after headers or distributed evenly throughout content.
    """
    if not images or not content_blocks:
        return content_blocks
    
    # Extract page numbers from PDF text to estimate content distribution
    page_markers = re.findall(r'--- Page (\d+) ---', pdf_text)
    total_pages = int(page_markers[-1]) if page_markers else 1
    
    # Calculate approximate position for each image based on page number
    # Position is a ratio (0.0 to 1.0) indicating where in the content the image should appear
    image_positions = []
    for img in images:
        page_num = img.get('page_num', 1)
        position_ratio = (page_num - 1) / max(total_pages, 1)
        image_positions.append({
            'image': img,
            'position_ratio': position_ratio,
            'page_num': page_num
        })
    
    # Sort by position ratio
    image_positions.sort(key=lambda x: x['position_ratio'])
    
    # Special handling: If we only have one paragraph block, split it and insert images
    if len(content_blocks) == 1 and content_blocks[0].get('type') == 'paragraph':
        # Split long paragraphs at logical points and insert images
        text = content_blocks[0]['data'].get('text', '')
        if len(text) > 500 and len(images) > 0:
            # Split text into chunks and insert images between chunks
            chunks = _split_text_with_images(text, images, total_pages)
            result_blocks = []
            for chunk in chunks:
                if isinstance(chunk, dict) and chunk.get('type') == 'image':
                    result_blocks.append(chunk)
                else:
                    result_blocks.append({
                        'type': 'paragraph',
                        'data': {'text': chunk}
                    })
            return result_blocks
    
    # Find header positions in content blocks for better image placement
    header_positions = []
    for i, block in enumerate(content_blocks):
        if block.get('type') == 'header':
            header_positions.append(i)
    
    # Insert images at appropriate positions
    result_blocks = []
    images_inserted = 0
    
    for i, block in enumerate(content_blocks):
        result_blocks.append(block)
        
        # Check if we should insert an image after this block
        while images_inserted < len(image_positions):
            current_image = image_positions[images_inserted]
            current_position_ratio = (i + 1) / max(len(content_blocks), 1)
            
            # Insert image if we've reached or passed the target position
            if current_position_ratio >= current_image['position_ratio']:
                # Prefer inserting after headers, but insert anywhere if we've passed the position
                is_header = block.get('type') == 'header'
                is_good_position = is_header or current_position_ratio >= current_image['position_ratio'] + 0.1
                
                if is_good_position or i == len(content_blocks) - 1:
                    # Create image block
                    image_block = {
                        'type': 'image',
                        'data': {
                            'file': {
                                'url': current_image['image']['url']
                            },
                            'caption': f"Image from page {current_image['page_num']}",
                            'withBorder': False,
                            'withBackground': False,
                            'stretched': False
                        }
                    }
                    result_blocks.append(image_block)
                    images_inserted += 1
                else:
                    # Wait for a better position (like after next header)
                    break
            else:
                # Haven't reached this image's position yet
                break
    
    # Add any remaining images at the end (shouldn't happen, but safety check)
    while images_inserted < len(image_positions):
        current_image = image_positions[images_inserted]
        image_block = {
            'type': 'image',
            'data': {
                'file': {
                    'url': current_image['image']['url']
                },
                'caption': f"Image from page {current_image['page_num']}",
                'withBorder': False,
                'withBackground': False,
                'stretched': False
            }
        }
        result_blocks.append(image_block)
        images_inserted += 1
    
    return result_blocks


def _split_text_with_images(text, images, total_pages):
    """
    Split text into chunks and return list of text chunks and image blocks
    positioned based on page numbers.
    """
    if not images:
        return [text]
    
    # Find page markers in text
    page_markers = list(re.finditer(r'--- Page (\d+) ---', text))
    
    result = []
    current_pos = 0
    
    for img_idx, img in enumerate(sorted(images, key=lambda x: x.get('page_num', 0))):
        page_num = img.get('page_num', 1)
        
        # Find the position in text corresponding to this page
        target_pos = len(text)
        for marker in page_markers:
            marker_page = int(marker.group(1))
            if marker_page >= page_num:
                target_pos = marker.start()
                break
        
        # If we haven't reached the target position yet, add text up to it
        if current_pos < target_pos:
            chunk = text[current_pos:target_pos].strip()
            if chunk:
                result.append(chunk)
            current_pos = target_pos
        
        # Add the image
        result.append({
            'type': 'image',
            'data': {
                'file': {'url': img['url']},
                'caption': f"Image from page {page_num}",
                'withBorder': False,
                'withBackground': False,
                'stretched': False
            }
        })
    
    # Add remaining text
    if current_pos < len(text):
        chunk = text[current_pos:].strip()
        if chunk:
            result.append(chunk)
    
    return result if result else [text]


def _process_pdf_chunk(course, module, pdf_text, suggested_title, ai_generator, skip_ai, course_name, module_name, images=None):
    """Helper method to process PDF chunk and create/update lesson"""
    from django.db.models import Max
    
    if images is None:
        images = []
    
    created = 0
    updated = 0
    
    # Generate lesson slug
    lesson_slug = slugify(suggested_title)
    
    # Get next order number
    max_order = Lesson.objects.filter(course=course, module=module).aggregate(
        max_order=Max('order')
    )['max_order'] or 0
    
    if skip_ai or not ai_generator:
        # Create basic lesson without AI generation
        # Create basic content blocks with images if available
        import uuid
        import time
        
        basic_blocks = [
            {
                'type': 'paragraph',
                'data': {
                    'text': pdf_text[:1000] + '...' if len(pdf_text) > 1000 else pdf_text
                }
            }
        ]
        
        # Add images if available - insert contextually
        if images:
            sorted_images = sorted(images, key=lambda x: x.get('page_num', 0))
            basic_blocks = _insert_images_contextually(basic_blocks, sorted_images, pdf_text)
        
        # Convert to Editor.js format
        editorjs_blocks = []
        for block in basic_blocks:
            editorjs_blocks.append({
                'id': str(uuid.uuid4()),
                'type': block['type'],
                'data': block['data']
            })
        
        basic_content = {
            'time': int(time.time() * 1000),
            'blocks': editorjs_blocks,
            'version': '2.28.2'
        }
        
        lesson, was_created = Lesson.objects.get_or_create(
            course=course,
            module=module,
            slug=lesson_slug,
            defaults={
                'title': suggested_title,
                'description': pdf_text[:500] + '...' if len(pdf_text) > 500 else pdf_text,
                'order': max_order + 1,
                'lesson_type': 'video',
                'ai_generation_status': 'pending',
                'content': basic_content,
            }
        )
        
        if was_created:
            created = 1
        else:
            updated = 1
    else:
        # Generate AI content
        try:
            ai_content = ai_generator.generate_lesson_content(
                pdf_text=pdf_text,
                course_name=course_name,
                module_name=module_name,
                suggested_title=suggested_title
            )
            
            # Add image blocks to content blocks
            content_blocks_with_images = list(ai_content['content_blocks'])
            
            # Insert images into content blocks based on page numbers and content structure
            if images:
                sorted_images = sorted(images, key=lambda x: x.get('page_num', 0))
                content_blocks_with_images = _insert_images_contextually(
                    content_blocks_with_images, 
                    sorted_images,
                    pdf_text
                )
            
            # Convert content blocks to Editor.js format
            editorjs_content = ai_generator.convert_to_editorjs_format(
                content_blocks_with_images
            )
            
            # Create or update lesson
            lesson, was_created = Lesson.objects.get_or_create(
                course=course,
                module=module,
                slug=lesson_slug,
                defaults={
                    'title': ai_content['clean_title'],
                    'description': ai_content['full_description'],
                    'order': max_order + 1,
                    'lesson_type': 'video',
                    'content': editorjs_content,
                    'ai_generation_status': 'generated',
                    'ai_clean_title': ai_content['clean_title'],
                    'ai_short_summary': ai_content['short_summary'],
                    'ai_full_description': ai_content['full_description'],
                    'ai_outcomes': ai_content['outcomes'],
                    'ai_coach_actions': ai_content['coach_actions'],
                }
            )
            
            if was_created:
                created = 1
            else:
                # Update existing lesson
                lesson.title = ai_content['clean_title']
                lesson.description = ai_content['full_description']
                lesson.content = editorjs_content
                lesson.ai_generation_status = 'generated'
                lesson.ai_clean_title = ai_content['clean_title']
                lesson.ai_short_summary = ai_content['short_summary']
                lesson.ai_full_description = ai_content['full_description']
                lesson.ai_outcomes = ai_content['outcomes']
                lesson.ai_coach_actions = ai_content['coach_actions']
                lesson.save()
                updated = 1
                
        except Exception as e:
            # Fall back to basic lesson creation
            lesson, was_created = Lesson.objects.get_or_create(
                course=course,
                module=module,
                slug=lesson_slug,
                defaults={
                    'title': suggested_title,
                    'description': pdf_text[:500] + '...' if len(pdf_text) > 500 else pdf_text,
                    'order': max_order + 1,
                    'lesson_type': 'video',
                    'ai_generation_status': 'pending',
                }
            )
            if was_created:
                created = 1
            else:
                updated = 1
    
    return created, updated


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
    
    If the lesson has a quiz, it must be passed before the lesson can be completed.
    """
    lesson = get_object_or_404(Lesson, id=lesson_id)
    
    # Check if lesson has a required quiz
    try:
        quiz = lesson.quiz
        if quiz.is_required:
            # Check if user has passed the quiz
            passed_attempt = LessonQuizAttempt.objects.filter(
                user=request.user,
                quiz=quiz,
                passed=True
            ).exists()
            
            if not passed_attempt:
                return JsonResponse({
                    'success': False,
                    'error': 'You must pass the lesson quiz before completing this lesson.',
                    'quiz_required': True,
                    'quiz_url': f'/courses/{lesson.course.slug}/{lesson.slug}/quiz/'
                }, status=400)
    except LessonQuiz.DoesNotExist:
        # No quiz, proceed with completion
        pass
    
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
    
    # Check if this is the last lesson in the course
    course = lesson.course
    all_lessons = course.lessons.order_by('order', 'id')
    is_last_lesson = False
    certificate_url = None
    
    if all_lessons.exists():
        last_lesson = all_lessons.last()
        if last_lesson.id == lesson.id:
            # This is the last lesson, check if all lessons are now completed
            completed_lessons_count = UserProgress.objects.filter(
                user=request.user,
                lesson__course=course,
                completed=True
            ).count()
            
            if completed_lessons_count == all_lessons.count():
                is_last_lesson = True
                
                # Check if there's a final exam for this course
                has_exam = Exam.objects.filter(course=course).exists()
                
                # Get or create certification
                certification, created = Certification.objects.get_or_create(
                    user=request.user,
                    course=course,
                    defaults={'status': 'not_eligible'}
                )
                
                # If there's no exam, automatically issue the certificate
                if not has_exam:
                    certification.status = 'passed'
                    if not certification.issued_at:
                        certification.issued_at = timezone.now()
                    
                    # Generate certificate PDF and upload to Cloudinary
                    try:
                        from .utils.certificate_generator import generate_certificate
                        cert_result = generate_certificate(
                            user=request.user,
                            course=course,
                            issued_date=certification.issued_at,
                            upload_to_cloudinary=True
                        )
                        
                        if cert_result and cert_result.get('certificate_url'):
                            # Store the generated certificate URL
                            certification.accredible_certificate_url = cert_result['certificate_url']
                            if cert_result.get('certificate_id'):
                                certification.accredible_certificate_id = cert_result['certificate_id']
                    except Exception as e:
                        # Log error but don't fail certificate issuance
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error generating certificate: {str(e)}")
                    
                    certification.save()
                
                # Determine certificate URL
                if certification.accredible_certificate_url:
                    certificate_url = certification.accredible_certificate_url
                else:
                    # Redirect to course progress page to view certificate status
                    certificate_url = reverse('student_course_progress', args=[course.slug])
    
    return JsonResponse({
        'success': True,
        'message': 'Lesson marked as complete',
        'lesson_id': lesson_id,
        'is_last_lesson': is_last_lesson,
        'certificate_url': certificate_url
    })


@login_required
def view_certificate(request, course_slug):
    """View or download certificate for a course"""
    course = get_object_or_404(Course, slug=course_slug)
    
    # Get certification
    try:
        certification = Certification.objects.get(user=request.user, course=course)
    except Certification.DoesNotExist:
        messages.error(request, 'Certificate not found.')
        return redirect('student_certifications')
    
    # Check if certificate is passed
    if certification.status != 'passed':
        messages.warning(request, 'Certificate not yet issued.')
        return redirect('student_course_progress', course_slug=course_slug)
    
    # If certificate URL exists, redirect to it
    if certification.accredible_certificate_url:
        return redirect(certification.accredible_certificate_url)
    
    # Otherwise, generate on-the-fly
    try:
        from .utils.certificate_generator import generate_certificate
        cert_result = generate_certificate(
            user=request.user,
            course=course,
            issued_date=certification.issued_at or timezone.now(),
            upload_to_cloudinary=False  # Generate for direct download
        )
        
        if cert_result and cert_result.get('pdf_buffer'):
            from django.http import HttpResponse
            response = HttpResponse(
                cert_result['pdf_buffer'].getvalue(),
                content_type='application/pdf'
            )
            response['Content-Disposition'] = f'inline; filename="certificate_{course.slug}_{request.user.id}.pdf"'
            return response
        else:
            messages.error(request, 'Error generating certificate.')
            return redirect('student_certifications')
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating certificate: {str(e)}")
        messages.error(request, 'Error generating certificate.')
        return redirect('student_certifications')


def verify_certificate(request, certificate_id):
    """
    Verify a certificate by certificate ID.
    Public endpoint - no login required.
    """
    from .models import Certification
    from django.conf import settings
    
    # Parse certificate ID format: CERT-{COURSE_SLUG}-{USER_ID}-{DATE}
    try:
        parts = certificate_id.split('-')
        if len(parts) < 4 or parts[0] != 'CERT':
            raise ValueError("Invalid certificate ID format")
        
        course_slug = parts[1].lower()
        user_id = int(parts[2])
        # Date is in format YYYYMMDD (no hyphens), so parts[3] is the full date
        date_str = parts[3] if len(parts) > 3 else ''
        
        # Find the certification
        try:
            certification = Certification.objects.select_related('user', 'course').get(
                user_id=user_id,
                course__slug=course_slug,
                status='passed'
            )
            
            # Verify the certificate ID matches
            expected_cert_id = f"CERT-{course_slug.upper()}-{user_id}-{certification.issued_at.strftime('%Y%m%d') if certification.issued_at else ''}"
            if certificate_id.upper() != expected_cert_id.upper():
                # Certificate ID doesn't match - might be invalid
                return render(request, 'certificate_verification.html', {
                    'valid': False,
                    'error': 'Certificate ID does not match our records.',
                    'certificate_id': certificate_id
                })
            
            # Certificate is valid
            return render(request, 'certificate_verification.html', {
                'valid': True,
                'certification': certification,
                'certificate_id': certificate_id,
                'student_name': certification.user.get_full_name() or certification.user.username,
                'course_name': certification.course.name,
                'issued_date': certification.issued_at,
            })
            
        except Certification.DoesNotExist:
            return render(request, 'certificate_verification.html', {
                'valid': False,
                'error': 'Certificate not found in our records.',
                'certificate_id': certificate_id
            })
        except Exception as e:
            return render(request, 'certificate_verification.html', {
                'valid': False,
                'error': 'Error verifying certificate. Please check the certificate ID.',
                'certificate_id': certificate_id
            })
            
    except (ValueError, IndexError) as e:
        return render(request, 'certificate_verification.html', {
            'valid': False,
            'error': 'Invalid certificate ID format.',
            'certificate_id': certificate_id
        })


@require_http_methods(["POST"])
@login_required
def toggle_favorite_course(request, course_id):
    """Toggle favorite status for a course"""
    from .models import FavoriteCourse, Course
    course = get_object_or_404(Course, id=course_id)
    user = request.user
    
    favorite, created = FavoriteCourse.objects.get_or_create(
        user=user,
        course=course
    )
    
    if not created:
        # Already favorited, remove it
        favorite.delete()
        is_favorited = False
    else:
        # Just favorited
        is_favorited = True
    
    return JsonResponse({
        'success': True,
        'is_favorited': is_favorited,
        'message': 'Course favorited' if is_favorited else 'Course unfavorited'
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
        if isinstance(upstream_payload, list) and len(upstream_payload) > 0:
            # Handle list format like [{'output': '...'}]
            first_item = upstream_payload[0]
            if isinstance(first_item, dict):
                message_text = (
                    first_item.get('output')
                    or first_item.get('Output')
                    or first_item.get('message')
                    or first_item.get('Message')
                    or first_item.get('response')
                    or first_item.get('Response')
                    or first_item.get('text')
                    or first_item.get('Text')
                    or first_item.get('answer')
                    or first_item.get('Answer')
                )
            elif isinstance(first_item, str):
                message_text = first_item
        elif isinstance(upstream_payload, dict):
            # Many of your test webhooks wrap like: {"Response": {"output": "..."}}.
            inner = upstream_payload.get('Response', upstream_payload)
            if isinstance(inner, dict):
                message_text = (
                    inner.get('output')
                    or inner.get('Output')
                    or inner.get('message')
                    or inner.get('Message')
                    or inner.get('response')
                    or inner.get('Response')
                    or inner.get('text')
                    or inner.get('Text')
                    or inner.get('answer')
                    or inner.get('Answer')
                )
            else:
                # Try direct keys on upstream_payload
                message_text = (
                    upstream_payload.get('output')
                    or upstream_payload.get('Output')
                    or upstream_payload.get('message')
                    or upstream_payload.get('Message')
                    or upstream_payload.get('response')
                    or upstream_payload.get('Response')
                    or upstream_payload.get('text')
                    or upstream_payload.get('Text')
                    or upstream_payload.get('answer')
                    or upstream_payload.get('Answer')
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
    """Student dashboard - overview with access control: My Courses, Available to Unlock, Not Available"""
    user = request.user
    
    # Redirect teachers to teacher dashboard
    if _is_teacher_user(user):
        return redirect('teacher_dashboard')
    
    # Use access control system to organize courses
    from .utils.access import get_courses_by_visibility, has_course_access, check_course_prerequisites
    
    courses_by_visibility = get_courses_by_visibility(user)
    my_courses = courses_by_visibility['my_courses']
    available_to_unlock = courses_by_visibility['available_to_unlock']
    not_available = courses_by_visibility['not_available']
    
    # Also check legacy enrollments for backward compatibility
    enrollments = CourseEnrollment.objects.filter(user=user).select_related('course')
    if not enrollments.exists() and user.is_staff:
        # Auto-enroll admin/staff in all active courses
        for course in Course.objects.filter(status='active'):
            CourseEnrollment.objects.get_or_create(user=user, course=course)
        enrollments = CourseEnrollment.objects.filter(user=user).select_related('course')
    
    # Process My Courses (courses with access)
    my_courses_data = []
    for course in my_courses:
        # Check access record
        has_access, access_record, _ = has_course_access(user, course)
        if not has_access:
            continue
            
        # Get enrollment (legacy) or create access-based data
        enrollment = CourseEnrollment.objects.filter(user=user, course=course).first()
        
        # Calculate progress
        total_lessons = course.lessons.count()
        completed_lessons = UserProgress.objects.filter(
            user=user,
            lesson__course=course,
            completed=True
        ).count()
        
        progress_percentage = int((completed_lessons / total_lessons * 100)) if total_lessons > 0 else 0
        
        # Check if course has any progress at all (watched videos, even if not completed)
        has_any_progress = UserProgress.objects.filter(
            user=user,
            lesson__course=course
        ).filter(
            Q(completed=True) | Q(video_watch_percentage__gt=0) | Q(status__in=['in_progress', 'completed'])
        ).exists()
        
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
        
        # Check if course is favorited
        from .models import FavoriteCourse
        is_favorited = FavoriteCourse.objects.filter(user=user, course=course).exists()
        
        my_courses_data.append({
            'course': course,
            'enrollment': enrollment,
            'access_record': access_record,
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
            'progress_percentage': progress_percentage,
            'has_any_progress': has_any_progress,
            'avg_watch_percentage': round(avg_watch, 1),
            'exam_info': exam_info,
            'certification': certification,
            'cert_status': cert_status,
            'cert_display': cert_display,
            'is_favorited': is_favorited,
        })
    
    # Also include legacy enrollments that might not have access records yet
    for enrollment in enrollments:
        course = enrollment.course
        # Skip if already in my_courses_data
        if any(cd['course'].id == course.id for cd in my_courses_data):
            continue
            
        # Check if course has access
        has_access, access_record, _ = has_course_access(user, course)
        if not has_access:
            # Try to create access from enrollment (migration path)
            from .utils.access import grant_course_access
            access_record = grant_course_access(
                user=user,
                course=course,
                access_type='purchase',
                notes="Migrated from legacy enrollment"
            )
        
        # Calculate progress
        total_lessons = course.lessons.count()
        completed_lessons = UserProgress.objects.filter(
            user=user,
            lesson__course=course,
            completed=True
        ).count()
        progress_percentage = int((completed_lessons / total_lessons * 100)) if total_lessons > 0 else 0
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
        
        # Get certification
        try:
            certification = Certification.objects.get(user=user, course=course)
            cert_status = certification.status
            cert_display = certification.get_status_display()
        except Certification.DoesNotExist:
            cert_status = 'not_eligible' if progress_percentage < 100 else 'eligible'
            cert_display = 'Not Eligible' if progress_percentage < 100 else 'Eligible'
            certification = None
        
        my_courses_data.append({
            'course': course,
            'enrollment': enrollment,
            'access_record': access_record,
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
            'progress_percentage': progress_percentage,
            'avg_watch_percentage': round(avg_watch, 1),
            'exam_info': exam_info,
            'certification': certification,
            'cert_status': cert_status,
            'cert_display': cert_display,
        })
    
    # Process Available to Unlock courses
    available_courses_data = []
    for course in available_to_unlock:
        # Check prerequisites
        prereqs_met, missing_prereqs = check_course_prerequisites(user, course)
        
        # Check if course is in a bundle
        from .models import Bundle
        bundles_with_course = Bundle.objects.filter(courses=course, is_active=True)
        
        # Check if user has any pending purchases for this course
        from .models import CoursePurchase
        has_pending_purchase = CoursePurchase.objects.filter(
            user=user,
            course=course,
            status='pending'
        ).exists()
        
        available_courses_data.append({
            'course': course,
            'prereqs_met': prereqs_met,
            'missing_prereqs': missing_prereqs,
            'bundles': bundles_with_course,
            'has_pending_purchase': has_pending_purchase,
        })
    
    # Process Not Available courses
    not_available_data = []
    for course in not_available:
        not_available_data.append({
            'course': course,
            'reason': course.get_visibility_display(),
        })
    
    # Get filter/sort parameters
    filter_favorites = request.GET.get('favorites', '')
    sort_by = request.GET.get('sort', 'progress')  # progress, favorites, name
    
    # Filter by favorites if requested
    if filter_favorites == 'true':
        my_courses_data = [c for c in my_courses_data if c.get('is_favorited', False)]
    
    # Sort courses
    if sort_by == 'favorites':
        # Favorites first, then by progress
        my_courses_data.sort(key=lambda x: (not x.get('is_favorited', False), -x['progress_percentage']))
    elif sort_by == 'name':
        my_courses_data.sort(key=lambda x: x['course'].name.lower())
    else:  # default: progress
        my_courses_data.sort(key=lambda x: x['progress_percentage'], reverse=True)
    
    # Overall stats
    total_courses = len(my_courses_data)
    completed_courses = sum(1 for c in my_courses_data if c['progress_percentage'] == 100)
    total_lessons_all = sum(c['total_lessons'] for c in my_courses_data)
    completed_lessons_all = sum(c['completed_lessons'] for c in my_courses_data)
    overall_progress = int((completed_lessons_all / total_lessons_all * 100)) if total_lessons_all > 0 else 0
    
    return render(request, 'student/dashboard.html', {
        'course_data': my_courses_data,  # Renamed for backward compatibility
        'my_courses': my_courses_data,
        'available_to_unlock': available_courses_data,
        'not_available': not_available_data,
        'total_courses': total_courses,
        'completed_courses': completed_courses,
        'total_lessons_all': total_lessons_all,
        'completed_lessons_all': completed_lessons_all,
        'overall_progress': overall_progress,
        'filter_favorites': filter_favorites,
        'sort_by': sort_by,
    })


@login_required
def student_course_progress(request, course_slug):
    """Detailed progress view for a specific course"""
    course = get_object_or_404(Course, slug=course_slug)
    user = request.user
    
    # Check access using the access control system
    from .utils.access import has_course_access
    has_access, access_record, _ = has_course_access(user, course)
    
    if not has_access:
        messages.error(request, 'You do not have access to this course.')
        return redirect('student_dashboard')
    
    # Get or create enrollment (for backward compatibility)
    enrollment = CourseEnrollment.objects.filter(user=user, course=course).first()
    if not enrollment:
        # Create enrollment for backward compatibility with existing code
        enrollment = CourseEnrollment.objects.create(
            user=user,
            course=course,
            payment_type='full'
        )
    
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


@staff_member_required
@require_http_methods(["POST"])
def train_lesson_chatbot(request, lesson_id):
    """Send transcript to training webhook and update lesson status"""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    
    try:
        data = json.loads(request.body)
        transcript = data.get('transcript', '').strip()
        
        if not transcript:
            return JsonResponse({'success': False, 'error': 'Transcript is required'}, status=400)
        
        # Update lesson status
        lesson.transcription = transcript
        lesson.ai_chatbot_training_status = 'training'
        lesson.save()
        
        # Prepare payload for training webhook
        training_webhook_url = 'https://katalyst-crm2.fly.dev/webhook/425e8e67-2aa6-4c50-b67f-0162e2496b51'
        
        payload = {
            'transcript': transcript,
            'lesson_id': lesson.id,
            'lesson_title': lesson.title,
            'course_name': lesson.course.name,
            'lesson_slug': lesson.slug,
        }
        
        # Send to training webhook
        try:
            response = requests.post(
                training_webhook_url,
                json=payload,
                timeout=30,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                response_data = response.json()
                
                # Store chatbot webhook ID if returned
                chatbot_webhook_id = response_data.get('chatbot_webhook_id') or response_data.get('webhook_id') or response_data.get('id')
                
                if chatbot_webhook_id:
                    lesson.ai_chatbot_webhook_id = str(chatbot_webhook_id)
                
                lesson.ai_chatbot_training_status = 'trained'
                lesson.ai_chatbot_trained_at = timezone.now()
                lesson.ai_chatbot_enabled = True
                lesson.save()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Chatbot trained successfully',
                    'chatbot_webhook_id': chatbot_webhook_id
                })
            else:
                lesson.ai_chatbot_training_status = 'failed'
                lesson.ai_chatbot_training_error = f"Webhook returned status {response.status_code}: {response.text[:500]}"
                lesson.save()
                
                return JsonResponse({
                    'success': False,
                    'error': f'Training webhook returned error: {response.status_code}'
                }, status=500)
                
        except requests.exceptions.RequestException as e:
            lesson.ai_chatbot_training_status = 'failed'
            lesson.ai_chatbot_training_error = str(e)
            lesson.save()
            
            return JsonResponse({
                'success': False,
                'error': f'Failed to connect to training webhook: {str(e)}'
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        lesson.ai_chatbot_training_status = 'failed'
        lesson.ai_chatbot_training_error = str(e)
        lesson.save()
        
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def lesson_chatbot(request, lesson_id):
    """Handle chatbot interactions for a lesson"""
    lesson = get_object_or_404(Lesson, id=lesson_id)
    
    # Check if chatbot is enabled and trained
    if not lesson.ai_chatbot_enabled or lesson.ai_chatbot_training_status != 'trained':
        return JsonResponse({
            'success': False,
            'error': 'Chatbot is not available for this lesson'
        }, status=400)
    
    # Check if user has access to this lesson
    if not has_course_access(request.user, lesson.course):
        return JsonResponse({
            'success': False,
            'error': 'You do not have access to this lesson'
        }, status=403)
    
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return JsonResponse({'success': False, 'error': 'Message is required'}, status=400)
        
        # Use the chatbot webhook
        chatbot_webhook_url = 'https://katalyst-crm2.fly.dev/webhook/swi-chatbot'
        
        payload = {
            'message': user_message,
            'lesson_id': lesson.id,
            'lesson_title': lesson.title,
            'course_name': lesson.course.name,
            'user_id': request.user.id,
            'user_email': request.user.email,
            'chatbot_webhook_id': lesson.ai_chatbot_webhook_id,  # If webhook needs specific ID
        }
        
        # Send to chatbot webhook
        try:
            response = requests.post(
                chatbot_webhook_url,
                json=payload,
                timeout=30,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                # Try to parse as JSON first
                response_text = response.text
                
                # Log raw response for debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"Raw webhook response for lesson {lesson.id} (first 500 chars): {response_text[:500]}")
                logger.info(f"Response headers: {dict(response.headers)}")
                
                # Check if it's HTML error page
                if response_text.strip().startswith('<!DOCTYPE') or response_text.strip().startswith('<html'):
                    return JsonResponse({
                        'success': False,
                        'error': 'Webhook returned HTML instead of JSON. Please check the webhook configuration.'
                    }, status=500)
                
                # Try to parse as JSON
                response_data = None
                try:
                    response_data = response.json()
                    logger.info(f"Parsed JSON response: {response_data}")
                except (ValueError, json.JSONDecodeError) as e:
                    logger.warning(
                        f"Failed to parse as JSON: {e}. Raw response (first 1000 chars): {response_text[:1000]}"
                    )
                    # Not JSON, treat as plain text / salvage malformed JSON (common when quotes are not escaped)
                    if response_text and response_text.strip():
                        cleaned_text = response_text.strip()
                        import re

                        # 1) Strong salvage: capture everything between the opening quote after Response/message/text/etc
                        # and the final quote before the closing brace. This works even if the content contains
                        # unescaped quotes (which breaks JSON).
                        key_names = ["Response", "response", "message", "Message", "text", "Text", "answer", "Answer"]
                        extracted_text = None
                        for key in key_names:
                            # Example broken JSON we see:
                            # { "Response": "Here ... \"Time Management...\" ...\nMore text" }
                            # But if quotes aren't escaped, json.loads fails; we still want the full value.
                            pattern = rf'"{re.escape(key)}"\s*:\s*"([\s\S]*)"\s*\}}'
                            m = re.search(pattern, cleaned_text)
                            if m and m.group(1) and len(m.group(1).strip()) > 0:
                                extracted_text = m.group(1)
                                break

                        # 2) Fallback: try a more conventional (escaped) match
                        if not extracted_text:
                            for key in key_names:
                                pattern = rf'"{re.escape(key)}"\s*:\s*"((?:[^"\\]|\\.)*)"'
                                m = re.search(pattern, cleaned_text, flags=re.DOTALL)
                                if m and m.group(1) and len(m.group(1).strip()) > 0:
                                    extracted_text = m.group(1)
                                    break

                        final_response = extracted_text if extracted_text else cleaned_text

                        # Unescape common sequences so the chat looks right
                        final_response = (
                            final_response.replace("\\n", "\n")
                            .replace("\\t", "\t")
                            .replace("\\r", "\r")
                            .replace('\\"', '"')
                            .replace("\\'", "'")
                        ).strip()

                        return JsonResponse({'success': True, 'response': final_response})

                    logger.error("Webhook returned empty response text")
                    return JsonResponse({'success': False, 'error': 'Webhook returned empty response'}, status=500)
                
                # Only process JSON response if we have response_data
                if response_data is None:
                    return JsonResponse({
                        'success': False,
                        'error': 'Webhook returned invalid response format'
                    }, status=500)
                
                # Extract AI response (adjust based on actual webhook response format)
                # Try multiple possible field names
                ai_response = None
                if isinstance(response_data, list) and len(response_data) > 0:
                    # Handle list format like [{'output': '...'}]
                    first_item = response_data[0]
                    if isinstance(first_item, dict):
                        ai_response = (
                            first_item.get('output') or
                            first_item.get('Output') or
                            first_item.get('response') or 
                            first_item.get('Response') or 
                            first_item.get('message') or 
                            first_item.get('Message') or 
                            first_item.get('text') or 
                            first_item.get('Text') or 
                            first_item.get('answer') or 
                            first_item.get('Answer') or 
                            first_item.get('content') or
                            first_item.get('Content') or
                            None
                        )
                    elif isinstance(first_item, str):
                        ai_response = first_item
                elif isinstance(response_data, dict):
                    ai_response = (
                        response_data.get('response') or 
                        response_data.get('Response') or 
                        response_data.get('message') or 
                        response_data.get('Message') or 
                        response_data.get('text') or 
                        response_data.get('Text') or 
                        response_data.get('answer') or 
                        response_data.get('Answer') or 
                        response_data.get('content') or
                        response_data.get('Content') or
                        response_data.get('output') or
                        response_data.get('Output') or
                        None
                    )
                    
                    # If still None, try to get the first string value from the dict
                    if ai_response is None:
                        for key, value in response_data.items():
                            if isinstance(value, str) and value.strip():
                                ai_response = value
                                break
                else:
                    # If it's not a dict or list, convert to string
                    ai_response = str(response_data)
                
                # If still None, convert entire dict to string
                if ai_response is None:
                    ai_response = str(response_data)
                
                logger.info(f"Extracted ai_response (type: {type(ai_response)}, value: {str(ai_response)[:200]})")
                
                # Clean the response - handle JSON strings and dict-like strings
                if isinstance(ai_response, str):
                    # Try to parse if it looks like JSON
                    if ai_response.strip().startswith('{') or ai_response.strip().startswith('['):
                        try:
                            parsed = json.loads(ai_response)
                            # Extract Response, response, message, text, or answer field
                            ai_response = parsed.get('Response') or parsed.get('response') or parsed.get('message') or parsed.get('text') or parsed.get('answer') or ai_response
                        except (json.JSONDecodeError, TypeError):
                            # If parsing fails, try to extract quoted text
                            import re
                            # Try to extract Response field from dict-like string
                            response_match = re.search(r"['\"]Response['\"]\s*:\s*['\"]([^'\"]+)['\"]", ai_response, re.IGNORECASE)
                            if response_match:
                                ai_response = response_match.group(1)
                            else:
                                # Try to extract any quoted text that's longer than 10 chars
                                quoted_match = re.search(r"['\"]([^'\"]{10,})['\"]", ai_response)
                                if quoted_match:
                                    ai_response = quoted_match.group(1)
                
                # If response is still empty, try one more time with the full response_text
                if not ai_response or (isinstance(ai_response, str) and not ai_response.strip()):
                    logger.warning(f"Empty response extracted. Trying response_text directly.")
                    # If response_text itself is not empty, use it
                    if response_text and response_text.strip() and not response_text.strip().startswith('<!DOCTYPE') and not response_text.strip().startswith('<html'):
                        # Try to parse it as JSON one more time
                        try:
                            text_parsed = json.loads(response_text)
                            if isinstance(text_parsed, dict):
                                ai_response = text_parsed.get('response') or text_parsed.get('Response') or text_parsed.get('message') or text_parsed.get('Message') or text_parsed.get('text') or text_parsed.get('Text') or text_parsed.get('answer') or text_parsed.get('Answer') or str(text_parsed)
                            else:
                                ai_response = str(text_parsed)
                        except:
                            # If it's not JSON, use it as plain text
                            ai_response = response_text[:500]
                
                # Ensure we have a clean string response
                if not ai_response or (isinstance(ai_response, str) and (not ai_response.strip() or ai_response.strip().startswith('{'))):
                    logger.error(f"Still empty after all attempts.")
                    return JsonResponse({
                        'success': False,
                        'error': 'The AI chatbot did not return a valid response. Please try again.'
                    }, status=500)
                
                logger.info(f"Final ai_response: {str(ai_response)[:200]}")
                
                return JsonResponse({
                    'success': True,
                    'response': str(ai_response)
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Chatbot webhook returned error: {response.status_code}'
                }, status=500)
                
        except requests.exceptions.RequestException as e:
            return JsonResponse({
                'success': False,
                'error': f'Failed to connect to chatbot webhook: {str(e)}'
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
@staff_member_required
def generate_course_content_webhook(request):
    """
    Webhook endpoint to generate course content, modules, and lessons.
    
    Expected payload:
    {
        "course": "positive_psychology" | "nlp" | "nutrition" | etc.,
        "module": "Module1" | "Module2" | etc.,
        "webhook_url": "https://..." (optional, uses default if not provided)
    }
    
    The webhook response should have content under "Response" field.
    """
    # Default webhook URL - can be overridden in request
    DEFAULT_WEBHOOK_URL = "https://katalyst-crm2.fly.dev/webhook/d90c3bb9-89f7-4658-86ba-f5406662b2b3"
    
    try:
        data = json.loads(request.body)
        
        # Extract course and module from request
        course_type = data.get('course')
        module_name = data.get('module')
        webhook_url = data.get('webhook_url', DEFAULT_WEBHOOK_URL)
        
        # Validate required fields
        if not course_type:
            return JsonResponse({
                'success': False,
                'error': 'Course parameter is required'
            }, status=400)
        
        if not module_name:
            return JsonResponse({
                'success': False,
                'error': 'Module parameter is required'
            }, status=400)
        
        # Validate course type
        valid_course_types = [
            'positive_psychology', 'nlp', 'nutrition', 'naturopathy',
            'hypnotherapy', 'ayurveda', 'art_therapy', 'aroma_therapy'
        ]
        
        if course_type not in valid_course_types:
            return JsonResponse({
                'success': False,
                'error': f'Invalid course type. Must be one of: {", ".join(valid_course_types)}'
            }, status=400)
        
        # Prepare payload for webhook with metadata filtering
        webhook_payload = {
            'course': course_type,
            'module': module_name,
            'metadata': {
                'course': course_type,
                'module': module_name,
            }
        }
        
        # Call the webhook
        try:
            response = requests.post(
                webhook_url,
                json=webhook_payload,
                headers={'Content-Type': 'application/json'},
                timeout=60  # Longer timeout for content generation
            )
            
            if response.status_code != 200:
                return JsonResponse({
                    'success': False,
                    'error': f'Webhook returned status {response.status_code}: {response.text[:500]}'
                }, status=500)
            
            # Parse webhook response
            try:
                webhook_response = response.json()
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'error': 'Webhook did not return valid JSON'
                }, status=500)
            
            # Extract content from Response field
            response_content = webhook_response.get('Response') or webhook_response.get('response')
            
            if not response_content:
                return JsonResponse({
                    'success': False,
                    'error': 'Webhook response does not contain Response field',
                    'webhook_response': webhook_response
                }, status=500)
            
            # Parse the response content (should be JSON with course/module/lesson structure)
            if isinstance(response_content, str):
                try:
                    response_content = json.loads(response_content)
                except json.JSONDecodeError:
                    # If it's not JSON, treat it as plain text description
                    response_content = {'description': response_content}
            
            # Process the response content and create/update course, module, and lessons
            result = process_course_content_response(
                course_type=course_type,
                module_name=module_name,
                content_data=response_content
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Content generated successfully',
                'result': result
            })
            
        except requests.exceptions.RequestException as e:
            return JsonResponse({
                'success': False,
                'error': f'Failed to connect to webhook: {str(e)}'
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
            }, status=500)


# ========== GIFT PURCHASE SYSTEM ==========

@login_required
def gift_course(request, course_slug):
    """Gift purchase page - form to purchase course as gift"""
    course = get_object_or_404(Course, slug=course_slug)
    
    # Check if course is paid
    if not course.is_paid or not course.price:
        messages.error(request, 'This course is not available for gifting.')
        return redirect('course_detail', course_slug=course.slug)
    
    if request.method == 'POST':
        recipient_email = request.POST.get('recipient_email', '').strip()
        recipient_name = request.POST.get('recipient_name', '').strip()
        gift_message = request.POST.get('gift_message', '').strip()
        
        if not recipient_email:
            messages.error(request, 'Recipient email is required.')
            return render(request, 'gift_course.html', {'course': course})
        
        # Create purchase (same as regular purchase)
        purchase = CoursePurchase.objects.create(
            user=request.user,
            course=course,
            amount=course.price,
            currency=course.currency,
            status='pending',
            provider='',
            provider_id='',
            notes=f"Gift purchase for {recipient_email}"
        )
        
        # Simulate payment (same as regular purchase)
        from django.conf import settings
        simulate_payment = getattr(settings, 'SIMULATE_PAYMENT', True)
        
        if simulate_payment:
            purchase.status = 'paid'
            purchase.paid_at = timezone.now()
            purchase.provider = 'simulated'
            purchase.provider_id = f'sim_gift_{purchase.id}_{int(timezone.now().timestamp())}'
            purchase.save()
        
        # Create gift purchase record (token will be auto-generated)
        gift = GiftPurchase.objects.create(
            purchaser=request.user,
            course=course,
            course_purchase=purchase,
            recipient_email=recipient_email,
            recipient_name=recipient_name,
            gift_message=gift_message,
            status='pending' if not simulate_payment else 'sent',
        )
        
        # If payment is simulated, send gift email immediately
        if simulate_payment:
            from .utils.email import send_gift_email
            email_result = send_gift_email(gift)
            
            if email_result['success']:
                gift.status = 'sent'
                gift.sent_at = timezone.now()
                gift.save()
                messages.success(request, f'Gift purchased and sent to {recipient_email}!')
            else:
                messages.warning(request, f'Gift purchased but email failed to send. Gift token: {gift.gift_token}')
        else:
            messages.info(request, 'Gift purchase initiated. Email will be sent after payment confirmation.')
        
        return redirect('gift_success', gift_token=gift.gift_token)
    
    return render(request, 'gift_course.html', {'course': course})


@login_required
def gift_success(request, gift_token):
    """Gift purchase success page"""
    gift = get_object_or_404(GiftPurchase, gift_token=gift_token)
    
    # Verify purchaser
    if gift.purchaser != request.user:
        messages.error(request, 'You do not have permission to view this gift.')
        return redirect('student_dashboard')
    
    return render(request, 'gift_success.html', {'gift': gift})


def redeem_gift(request, gift_token):
    """Gift redemption page - allows recipient to claim their gift"""
    gift = get_object_or_404(GiftPurchase, gift_token=gift_token)
    
    # Check if already redeemed
    if gift.recipient_user:
        messages.info(request, 'This gift has already been redeemed.')
        if request.user.is_authenticated and request.user == gift.recipient_user:
            return redirect('student_dashboard')
        return redirect('login')
    
    # Check if expired
    if gift.is_expired():
        gift.status = 'expired'
        gift.save()
        messages.error(request, 'This gift has expired.')
        return render(request, 'gift_expired.html', {'gift': gift})
    
    # Check if gift is in valid status
    if gift.status != 'sent':
        messages.error(request, 'This gift is not available for redemption.')
        return render(request, 'gift_error.html', {'gift': gift})
    
    # Auto-redeem if user is logged in and email matches
    if request.user.is_authenticated:
        if request.user.email.lower() == gift.recipient_email.lower():
            # Auto-redeem the gift
            from .utils.access import grant_purchase_access
            access = grant_purchase_access(request.user, gift.course, gift.course_purchase)
            
            # Update gift
            gift.recipient_user = request.user
            gift.status = 'redeemed'
            gift.redeemed_at = timezone.now()
            gift.save()
            
            messages.success(request, f'Congratulations! You now have access to {gift.course.name}.')
            return redirect('student_dashboard')
        else:
            # Email doesn't match - show warning
            messages.warning(request, f'This gift was sent to {gift.recipient_email}. Please log in with that email address.')
            return render(request, 'gift_redeem.html', {'gift': gift, 'email_mismatch': True})
    
    if request.method == 'POST':
        # User wants to redeem but not logged in
        messages.info(request, 'Please create an account or log in to claim your gift.')
        return redirect(f'/register/?gift={gift_token}')
    
    # Show redemption page (user not logged in)
    return render(request, 'gift_redeem.html', {'gift': gift})


def process_course_content_response(course_type, module_name, content_data):
    """
    Process webhook response and create/update course, module, and lessons.
    
    Expected content_data structure:
    {
        "course": {
            "name": "Positive Psychology",
            "description": "...",
            "short_description": "...",
            ...
        },
        "module": {
            "name": "Module1",
            "description": "...",
            "order": 1
        },
        "lessons": [
            {
                "title": "Lesson 1",
                "description": "...",
                "order": 1,
                ...
            },
            ...
        ]
    }
    """
    result = {
        'course_created': False,
        'course_updated': False,
        'module_created': False,
        'module_updated': False,
        'lessons_created': 0,
        'lessons_updated': 0,
        'errors': []
    }
    
    try:
        # Get or create course
        course_name = content_data.get('course', {}).get('name') or course_type.replace('_', ' ').title()
        course_slug = slugify(course_name)
        
        course, created = Course.objects.get_or_create(
            slug=course_slug,
            defaults={
                'name': course_name,
                'course_type': course_type,
                'description': content_data.get('course', {}).get('description', ''),
                'short_description': content_data.get('course', {}).get('short_description', '')[:300],
                'status': 'active',
            }
        )
        
        if created:
            result['course_created'] = True
        else:
            # Update existing course
            course.description = content_data.get('course', {}).get('description', course.description)
            course.short_description = content_data.get('course', {}).get('short_description', course.short_description)[:300]
            course.course_type = course_type
            course.save()
            result['course_updated'] = True
        
        # Get or create module
        module_data = content_data.get('module', {})
        module_display_name = module_data.get('name') or module_name
        module_order = module_data.get('order', 0)
        
        module, module_created = Module.objects.get_or_create(
            course=course,
            name=module_display_name,
            defaults={
                'description': module_data.get('description', ''),
                'order': module_order,
            }
        )
        
        if module_created:
            result['module_created'] = True
        else:
            # Update existing module
            module.description = module_data.get('description', module.description)
            module.order = module_order
            module.save()
            result['module_updated'] = True
        
        # Process lessons
        lessons_data = content_data.get('lessons', [])
        
        if not isinstance(lessons_data, list):
            result['errors'].append('Lessons data is not a list')
            return result
        
        for lesson_data in lessons_data:
            try:
                lesson_title = lesson_data.get('title', '')
                if not lesson_title:
                    result['errors'].append('Lesson missing title')
                    continue
                
                lesson_slug = slugify(lesson_title)
                lesson_order = lesson_data.get('order', 0)
                
                lesson, lesson_created = Lesson.objects.get_or_create(
                    course=course,
                    module=module,
                    slug=lesson_slug,
                    defaults={
                        'title': lesson_title,
                        'description': lesson_data.get('description', ''),
                        'order': lesson_order,
                        'lesson_type': lesson_data.get('lesson_type', 'video'),
                    }
                )
                
                if lesson_created:
                    result['lessons_created'] += 1
                else:
                    # Update existing lesson
                    lesson.title = lesson_title
                    lesson.description = lesson_data.get('description', lesson.description)
                    lesson.order = lesson_order
                    lesson.save()
                    result['lessons_updated'] += 1
                    
            except Exception as e:
                result['errors'].append(f'Error processing lesson: {str(e)}')
                continue
        
    except Exception as e:
        result['errors'].append(f'Error processing content: {str(e)}')
    
    return result


# ========== PURCHASE SYSTEM ==========

@login_required
@require_http_methods(["POST"])
def initiate_purchase(request, course_slug):
    """
    Initiate a course purchase.
    Creates a pending CoursePurchase record and returns purchase info for payment processing.
    """
    course = get_object_or_404(Course, slug=course_slug)
    user = request.user
    
    # Check if course is paid
    if not course.is_paid or not course.price:
        return JsonResponse({
            'success': False,
            'error': 'This course is not available for purchase'
        }, status=400)
    
    # Check if user already has access
    from .utils.access import has_course_access
    has_access, _, _ = has_course_access(user, course)
    if has_access:
        return JsonResponse({
            'success': False,
            'error': 'You already have access to this course'
        }, status=400)
    
    # Check if there's already a pending or paid purchase
    existing_purchase = CoursePurchase.objects.filter(
        user=user,
        course=course,
        status__in=['pending', 'paid']
    ).first()
    
    if existing_purchase:
        if existing_purchase.status == 'paid':
            return JsonResponse({
                'success': False,
                'error': 'You already have a paid purchase for this course'
            }, status=400)
        else:
            # Return existing pending purchase
            return JsonResponse({
                'success': True,
                'purchase_id': existing_purchase.id,
                'amount': str(existing_purchase.amount),
                'currency': existing_purchase.currency,
                'status': existing_purchase.status,
            })
    
    # Create new pending purchase
    purchase = CoursePurchase.objects.create(
        user=user,
        course=course,
        amount=course.price,
        currency=course.currency,
        status='pending',
        provider='',  # Will be set by webhook
        provider_id='',  # Will be set by webhook
    )
    
    # SIMULATE PAYMENT: If no payment provider is configured, auto-approve the purchase
    # This is for development/testing. In production, remove this and use actual payment provider.
    from django.conf import settings
    simulate_payment = getattr(settings, 'SIMULATE_PAYMENT', True)  # Default to True for development
    
    if simulate_payment:
        # Auto-approve the purchase
        purchase.status = 'paid'
        purchase.paid_at = timezone.now()
        purchase.provider = 'simulated'
        purchase.provider_id = f'sim_{purchase.id}_{int(timezone.now().timestamp())}'
        purchase.save()
        
        # Grant course access immediately
        from .utils.access import grant_purchase_access
        grant_purchase_access(user, course, purchase)
        
        return JsonResponse({
            'success': True,
            'purchase_id': purchase.id,
            'amount': str(purchase.amount),
            'currency': purchase.currency,
            'status': 'paid',
            'message': 'Purchase completed successfully! Access granted.',
            'redirect': f'/courses/{course.slug}/{course.lessons.first().slug}/' if course.lessons.exists() else f'/courses/{course.slug}/'
        })
    
    return JsonResponse({
        'success': True,
        'purchase_id': purchase.id,
        'amount': str(purchase.amount),
        'currency': purchase.currency,
        'status': purchase.status,
        'message': 'Purchase initiated. Redirecting to payment provider...'
    })


@require_http_methods(["POST"])
def purchase_webhook(request):
    """
    Webhook endpoint to confirm payment.
    Payment provider calls this after successful payment.
    
    Expected payload (JSON):
    {
        "purchase_id": 123,  # Our internal purchase ID
        "provider": "stripe",  # Payment provider name
        "provider_id": "ch_1234567890",  # Provider transaction ID
        "status": "paid",  # or "failed", "refunded"
        "amount": "99.00",
        "currency": "USD"
    }
    """
    try:
        data = json.loads(request.body)
        
        purchase_id = data.get('purchase_id')
        provider = data.get('provider', 'manual')
        provider_id = data.get('provider_id', '')
        status = data.get('status', 'paid')
        amount = data.get('amount')
        currency = data.get('currency', 'USD')
        
        if not purchase_id:
            return JsonResponse({
                'success': False,
                'error': 'purchase_id is required'
            }, status=400)
        
        # Get purchase
        try:
            purchase = CoursePurchase.objects.get(id=purchase_id)
        except CoursePurchase.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': f'Purchase {purchase_id} not found'
            }, status=404)
        
        # Update purchase
        purchase.provider = provider
        purchase.provider_id = provider_id
        purchase.status = status
        
        if status == 'paid':
            from django.utils import timezone
            purchase.paid_at = timezone.now()
            purchase.save()
            
            # Check if this is a gift purchase
            try:
                gift = GiftPurchase.objects.get(course_purchase=purchase)
                # Send gift email
                from .utils.email import send_gift_email
                email_result = send_gift_email(gift)
                
                if email_result['success']:
                    gift.status = 'sent'
                    gift.sent_at = timezone.now()
                    gift.save()
                    return JsonResponse({
                        'success': True,
                        'message': 'Payment confirmed and gift email sent',
                        'purchase_id': purchase.id,
                    })
                else:
                    return JsonResponse({
                        'success': True,
                        'message': 'Payment confirmed but gift email failed to send',
                        'warning': email_result.get('message', 'Email error'),
                        'purchase_id': purchase.id,
                    })
            except GiftPurchase.DoesNotExist:
                # Regular purchase - grant access to purchaser
                from .utils.access import grant_purchase_access
                access = grant_purchase_access(
                    user=purchase.user,
                    course=purchase.course,
                    purchase=purchase
                )
                
                return JsonResponse({
                    'success': True,
                    'message': 'Purchase confirmed and access granted',
                    'purchase_id': purchase.id,
                    'access_id': access.id,
                })
        else:
            purchase.save()
            return JsonResponse({
                'success': True,
                'message': f'Purchase status updated to {status}',
                'purchase_id': purchase.id,
            })
    
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON payload'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


