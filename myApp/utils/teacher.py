"""
Teacher Permission Utilities
Core concept: Teachers can only manage courses they own/teach
"""
from django.core.exceptions import PermissionDenied
from ..models import Course, LiveSession, Booking


def is_teacher(user):
    """Check if user is a teacher (has at least one course assigned)"""
    if not user.is_authenticated:
        return False
    return user.taught_courses.exists() or user.is_staff


def is_course_teacher(user, course):
    """Check if user is a teacher for a specific course"""
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True  # Staff can manage all courses
    return course.teachers.filter(id=user.id).exists()


def require_course_teacher(user, course):
    """Raise PermissionDenied if user is not a teacher for the course"""
    if not is_course_teacher(user, course):
        raise PermissionDenied("You do not have permission to manage this course.")


def get_teacher_courses(user):
    """Get all courses the user teaches"""
    if not user.is_authenticated:
        return Course.objects.none()
    if user.is_staff:
        return Course.objects.all()  # Staff can see all courses
    return user.taught_courses.all()


def is_session_teacher(user, session):
    """Check if user is a teacher for the session's course"""
    return is_course_teacher(user, session.course)


def require_session_teacher(user, session):
    """Raise PermissionDenied if user is not a teacher for the session's course"""
    require_course_teacher(user, session.course)


def is_booking_teacher(user, booking):
    """Check if user is a teacher for the booking's session's course"""
    return is_course_teacher(user, booking.session.course)


def require_booking_teacher(user, booking):
    """Raise PermissionDenied if user is not a teacher for the booking's session's course"""
    require_course_teacher(user, booking.session.course)

