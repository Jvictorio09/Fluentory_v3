"""
Teacher Permission Utilities
Core concept: Teachers can only manage courses they own/teach
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from ..models import Course, LiveSession, Booking, TeacherProfile, TeacherRequest


def get_eligible_course_teacher_users():
    """
    Users who may be assigned as course teachers (admin dashboard, teacher co-teacher picker, Django admin).
    Excludes regular students: only users with an approved teacher application or already listed as a course teacher.
    """
    User = get_user_model()
    approved_ids = TeacherRequest.objects.filter(status='approved').values_list('user_id', flat=True)
    return User.objects.filter(
        Q(id__in=approved_ids) | Q(taught_courses__isnull=False)
    ).distinct().order_by('username')


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


def get_teacher_course_scope(user):
    """Courses shown in teacher dashboard lists: assigned courses for teachers; all for staff."""
    if not user.is_authenticated:
        return Course.objects.none()
    return get_teacher_courses(user)


def split_teacher_owned_vs_company_courses(user, queryset=None):
    """
    Split courses into those created by this teacher vs company/catalog (assigned only).
    Uses created_by: teacher-created courses set it in teacher UI; dashboard/catalog courses often leave it blank.
    """
    qs = queryset if queryset is not None else get_teacher_course_scope(user)
    my_courses = qs.filter(created_by=user)
    company_courses = qs.exclude(created_by=user)
    return my_courses, company_courses


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


def get_course_instructors(course):
    """Build normalized instructor cards for course and lesson templates."""
    instructors = []
    teachers = course.teachers.all().order_by('first_name', 'last_name', 'username')

    for teacher in teachers:
        try:
            profile = teacher.teacher_profile
        except TeacherProfile.DoesNotExist:
            profile = None

        full_name = teacher.get_full_name().strip() or teacher.username
        accomplishments_lines = []
        if profile and profile.accomplishments:
            accomplishments_lines = [
                line.strip() for line in profile.accomplishments.splitlines() if line.strip()
            ]

        instructors.append({
            'user': teacher,
            'profile': profile,
            'display_name': full_name,
            'headline': profile.headline if profile else '',
            'bio': profile.bio if profile else '',
            'accomplishments_lines': accomplishments_lines,
            'website': profile.website if profile else '',
            'linkedin_url': profile.linkedin_url if profile else '',
            'photo_url': profile.photo if (profile and profile.photo) else '',
            'initials': (full_name[0] if full_name else 'T').upper(),
        })

    return instructors

