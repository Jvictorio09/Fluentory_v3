"""
Teacher Views
Teachers can create and manage their own courses and create live class sessions for those courses.
They can view sessions assigned to them, review student bookings, and mark attendance.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from .models import (
    Course, Lesson, Module, LiveSession, Booking, UserProgress, CourseEnrollment, TeacherRequest
)
from .utils.teacher import (
    is_teacher, is_course_teacher, require_course_teacher, get_teacher_courses,
    require_session_teacher, require_booking_teacher
)


def teacher_required(view_func):
    """Decorator to require user to be a teacher
    Uses the same logic as _is_teacher_user() in views.py to avoid redirect loops
    """
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        # Use the same logic as _is_teacher_user in views.py
        # Check if user has approved TeacherRequest or teaches courses
        # TeacherRequest and Course are already imported at the top
        
        # Superusers are admins, not teachers
        if user.is_superuser:
            messages.error(request, 'You must be a teacher to access this page.')
            return redirect('dashboard_home')
        
        # Refresh user from database to ensure we have latest data
        try:
            user.refresh_from_db()
        except:
            pass
        
        # Check if user has approved TeacherRequest (primary indicator)
        has_approved_request = TeacherRequest.objects.filter(user_id=user.id, status='approved').exists()
        
        # Check if user teaches any courses (secondary check)
        has_courses = Course.objects.filter(teachers__id=user.id).exists()
        
        if not (has_approved_request or has_courses):
            messages.error(request, 'You must be a teacher to access this page.')
            return redirect('student_dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper


# ========== TEACHER DASHBOARD ==========

@login_required
@teacher_required
def teacher_dashboard(request):
    """Teacher dashboard - overview with courses, sessions, bookings, stats"""
    user = request.user
    
    # Get teacher's courses
    courses = get_teacher_courses(user)
    
    # Get upcoming live sessions (next 30 days)
    now = timezone.now()
    upcoming_sessions = LiveSession.objects.filter(
        course__in=courses,
        scheduled_at__gte=now,
        status='scheduled'
    ).order_by('scheduled_at')[:10]
    
    # Get recent bookings (last 7 days)
    recent_bookings = Booking.objects.filter(
        session__course__in=courses,
        booked_at__gte=now - timedelta(days=7)
    ).select_related('user', 'session', 'session__course').order_by('-booked_at')[:10]
    
    # Quick stats
    total_courses = courses.count()
    total_sessions = LiveSession.objects.filter(course__in=courses).count()
    upcoming_sessions_count = LiveSession.objects.filter(
        course__in=courses,
        scheduled_at__gte=now,
        status='scheduled'
    ).count()
    total_bookings = Booking.objects.filter(session__course__in=courses).count()
    pending_bookings = Booking.objects.filter(
        session__course__in=courses,
        status='pending'
    ).count()
    
    return render(request, 'teacher/dashboard.html', {
        'courses': courses,
        'upcoming_sessions': upcoming_sessions,
        'recent_bookings': recent_bookings,
        'total_courses': total_courses,
        'total_sessions': total_sessions,
        'upcoming_sessions_count': upcoming_sessions_count,
        'total_bookings': total_bookings,
        'pending_bookings': pending_bookings,
    })


# ========== COURSE MANAGEMENT ==========

@login_required
@teacher_required
def teacher_courses(request):
    """List courses the teacher owns/teaches"""
    courses = get_teacher_courses(request.user).annotate(
        lesson_count=Count('lessons'),
        session_count=Count('live_sessions'),
    ).order_by('-created_at')
    
    return render(request, 'teacher/courses.html', {
        'courses': courses,
    })


@login_required
@teacher_required
def teacher_add_course(request):
    """Create new course (same fields as admin create)"""
    if request.method == 'POST':
        from django.utils.text import slugify
        
        name = request.POST.get('name')
        if not name:
            messages.error(request, 'Course name is required.')
            return render(request, 'teacher/add_course.html', {
                'course_types': Course.COURSE_TYPES,
            })
        
        # Generate slug
        slug = slugify(name)
        base_slug = slug
        counter = 1
        while Course.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        # Delivery type and pricing
        delivery_type = request.POST.get('delivery_type', 'pre_recorded')
        is_paid = request.POST.get('is_paid') == 'on'
        price = request.POST.get('price', '') or None
        currency = request.POST.get('currency', 'USD')
        
        course = Course.objects.create(
            name=name,
            slug=slug,
            short_description=request.POST.get('short_description', ''),
            description=request.POST.get('description', ''),
            course_type=request.POST.get('course_type', 'sprint'),
            status=request.POST.get('status', 'active'),
            coach_name=request.POST.get('coach_name', ''),
            delivery_type=delivery_type,
            is_paid=is_paid,
            price=float(price) if price else None,
            currency=currency,
        )
        
        # Assign teacher to course (always assign creator, and additional teachers if live)
        course.teachers.add(request.user)
        if delivery_type == 'live':
            teacher_ids = request.POST.getlist('teachers')
            if teacher_ids:
                from django.contrib.auth.models import User
                teachers = User.objects.filter(id__in=teacher_ids)
                course.teachers.add(*teachers)
        
        messages.success(request, f'Course "{course.name}" has been created successfully.')
        return redirect('teacher_course_detail', course_slug=course.slug)
    
    # Get all users who could be teachers
    from django.contrib.auth.models import User
    from django.db.models import Q
    potential_teachers = User.objects.filter(
        Q(is_staff=False) | Q(taught_courses__isnull=False)
    ).distinct().order_by('username')
    
    return render(request, 'teacher/add_course.html', {
        'course_types': Course.COURSE_TYPES,
        'potential_teachers': potential_teachers,
    })


@login_required
@teacher_required
def teacher_course_detail(request, course_slug):
    """Edit course details (same as admin edit)"""
    course = get_object_or_404(Course, slug=course_slug)
    require_course_teacher(request.user, course)
    
    if request.method == 'POST':
        course.name = request.POST.get('name', course.name)
        course.short_description = request.POST.get('short_description', course.short_description)
        course.description = request.POST.get('description', course.description)
        course.status = request.POST.get('status', course.status)
        course.course_type = request.POST.get('course_type', course.course_type)
        course.coach_name = request.POST.get('coach_name', course.coach_name)
        
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
            # Always include the current user (course creator)
            if request.user.id not in [int(tid) for tid in teacher_ids]:
                teacher_ids.append(str(request.user.id))
            if teacher_ids:
                from django.contrib.auth.models import User
                teachers = User.objects.filter(id__in=teacher_ids)
                course.teachers.set(teachers)
        else:
            # For pre-recorded, only keep the creator
            course.teachers.set([request.user])
        
        messages.success(request, 'Course updated successfully.')
        return redirect('teacher_course_detail', course_slug=course.slug)
    
    # Get all users who could be teachers
    from django.contrib.auth.models import User
    from django.db.models import Q
    potential_teachers = User.objects.filter(
        Q(is_staff=False) | Q(taught_courses__isnull=False)
    ).distinct().order_by('username')
    
    return render(request, 'teacher/course_detail.html', {
        'course': course,
        'potential_teachers': potential_teachers,
    })


@login_required
@teacher_required
@require_http_methods(["POST"])
def teacher_delete_course(request, course_slug):
    """Delete course (optional; or archive only)"""
    course = get_object_or_404(Course, slug=course_slug)
    require_course_teacher(request.user, course)
    
    course_name = course.name
    try:
        course.delete()
        messages.success(request, f'Course "{course_name}" has been deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting course: {str(e)}')
    
    return redirect('teacher_courses')


# ========== LESSON MANAGEMENT (OPTIONAL) ==========

@login_required
@teacher_required
def teacher_course_lessons(request, course_slug):
    """View all lessons for a course"""
    course = get_object_or_404(Course, slug=course_slug)
    require_course_teacher(request.user, course)
    
    lessons = course.lessons.all()
    modules = course.modules.all()
    
    return render(request, 'teacher/course_lessons.html', {
        'course': course,
        'lessons': lessons,
        'modules': modules,
    })


# ========== LIVE SESSION MANAGEMENT ==========

@login_required
@teacher_required
def teacher_live_sessions(request):
    """List all live sessions for teacher's courses"""
    courses = get_teacher_courses(request.user)
    sessions = LiveSession.objects.filter(
        course__in=courses
    ).select_related('course').order_by('-scheduled_at')
    
    # Filter by status if provided
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        sessions = sessions.filter(status=status_filter)
    
    # Filter by course if provided
    course_filter = request.GET.get('course', '')
    if course_filter:
        sessions = sessions.filter(course_id=course_filter)
    
    return render(request, 'teacher/live_sessions.html', {
        'sessions': sessions,
        'courses': courses,
        'status_filter': status_filter,
        'course_filter': course_filter,
    })


@login_required
@teacher_required
def teacher_live_session_create(request, course_slug):
    """Create a live class session"""
    course = get_object_or_404(Course, slug=course_slug)
    require_course_teacher(request.user, course)
    
    if request.method == 'POST':
        title = request.POST.get('title')
        scheduled_at_str = request.POST.get('scheduled_at')
        duration_minutes = request.POST.get('duration_minutes', 60)
        meeting_link = request.POST.get('meeting_link', '')
        meeting_password = request.POST.get('meeting_password', '')
        capacity = request.POST.get('capacity', '') or None
        description = request.POST.get('description', '')
        
        if not title or not scheduled_at_str:
            messages.error(request, 'Title and scheduled time are required.')
            return render(request, 'teacher/live_session_create.html', {
                'course': course,
            })
        
        try:
            from django.utils.dateparse import parse_datetime
            scheduled_at = parse_datetime(scheduled_at_str)
            if not scheduled_at:
                # Try parsing as date + time separately
                from datetime import datetime
                scheduled_at = datetime.strptime(scheduled_at_str, '%Y-%m-%dT%H:%M')
                scheduled_at = timezone.make_aware(scheduled_at)
        except Exception as e:
            messages.error(request, f'Invalid date/time format: {str(e)}')
            return render(request, 'teacher/live_session_create.html', {
                'course': course,
            })
        
        session = LiveSession.objects.create(
            course=course,
            title=title,
            description=description,
            scheduled_at=scheduled_at,
            duration_minutes=int(duration_minutes) if duration_minutes else 60,
            meeting_link=meeting_link,
            meeting_password=meeting_password,
            capacity=int(capacity) if capacity else None,
            created_by=request.user,
        )
        
        messages.success(request, f'Session "{session.title}" created successfully.')
        return redirect('teacher_live_session_detail', session_id=session.id)
    
    return render(request, 'teacher/live_session_create.html', {
        'course': course,
    })


@login_required
@teacher_required
def teacher_live_session_detail(request, session_id):
    """View session info + bookings list"""
    session = get_object_or_404(LiveSession, id=session_id)
    require_session_teacher(request.user, session)
    
    bookings = session.bookings.select_related('user').order_by('booked_at')
    
    return render(request, 'teacher/live_session_detail.html', {
        'session': session,
        'bookings': bookings,
    })


@login_required
@teacher_required
def teacher_live_session_edit(request, session_id):
    """Edit session (time, link, capacity, status)"""
    session = get_object_or_404(LiveSession, id=session_id)
    require_session_teacher(request.user, session)
    
    if request.method == 'POST':
        session.title = request.POST.get('title', session.title)
        session.description = request.POST.get('description', session.description)
        scheduled_at_str = request.POST.get('scheduled_at')
        if scheduled_at_str:
            try:
                from django.utils.dateparse import parse_datetime
                scheduled_at = parse_datetime(scheduled_at_str)
                if scheduled_at:
                    session.scheduled_at = scheduled_at
            except:
                pass
        
        session.duration_minutes = int(request.POST.get('duration_minutes', session.duration_minutes))
        session.meeting_link = request.POST.get('meeting_link', session.meeting_link)
        session.meeting_password = request.POST.get('meeting_password', session.meeting_password)
        capacity = request.POST.get('capacity', '')
        session.capacity = int(capacity) if capacity else None
        session.status = request.POST.get('status', session.status)
        session.notes = request.POST.get('notes', session.notes)
        session.save()
        
        messages.success(request, 'Session updated successfully.')
        return redirect('teacher_live_session_detail', session_id=session.id)
    
    return render(request, 'teacher/live_session_edit.html', {
        'session': session,
    })


@login_required
@teacher_required
@require_http_methods(["POST"])
def teacher_live_session_cancel(request, session_id):
    """Cancel session (doesn't delete; marks cancelled)"""
    session = get_object_or_404(LiveSession, id=session_id)
    require_session_teacher(request.user, session)
    
    session.status = 'cancelled'
    session.save()
    
    messages.success(request, 'Session cancelled successfully.')
    return redirect('teacher_live_session_detail', session_id=session.id)


@login_required
@teacher_required
def teacher_session_bookings(request, session_id):
    """View bookings (can be same as detail view)"""
    session = get_object_or_404(LiveSession, id=session_id)
    require_session_teacher(request.user, session)
    
    bookings = session.bookings.select_related('user').order_by('booked_at')
    
    return render(request, 'teacher/session_bookings.html', {
        'session': session,
        'bookings': bookings,
    })


@login_required
@teacher_required
@require_http_methods(["POST"])
def teacher_mark_attendance(request, booking_id):
    """Mark: attended / no-show"""
    booking = get_object_or_404(Booking, id=booking_id)
    require_booking_teacher(request.user, booking)
    
    action = request.POST.get('action')  # 'attended' or 'no_show'
    
    if action == 'attended':
        booking.mark_attended(request.user)
        messages.success(request, f'Marked {booking.user.username} as attended.')
    elif action == 'no_show':
        booking.mark_no_show(request.user)
        messages.success(request, f'Marked {booking.user.username} as no-show.')
    else:
        messages.error(request, 'Invalid action.')
    
    return redirect('teacher_live_session_detail', session_id=booking.session.id)

