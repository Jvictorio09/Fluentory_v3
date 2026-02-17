from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json
import secrets


class Course(models.Model):
    COURSE_TYPES = [
        ('sprint', 'Sprint'),
        ('speaking', 'Speaking'),
        ('consultancy', 'Consultancy'),
        ('special', 'Special'),
        ('positive_psychology', 'Positive Psychology'),
        ('nlp', 'NLP'),
        ('nutrition', 'Nutrition'),
        ('naturopathy', 'Naturopathy'),
        ('hypnotherapy', 'Hypnotherapy'),
        ('ayurveda', 'Ayurveda'),
        ('art_therapy', 'Art Therapy'),
        ('aroma_therapy', 'Aroma Therapy'),
        ('tawjehi', 'Tawjehi'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('locked', 'Locked'),
        ('coming_soon', 'Coming Soon'),
    ]
    
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    course_type = models.CharField(max_length=20, choices=COURSE_TYPES, default='sprint')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    description = models.TextField()
    short_description = models.CharField(max_length=300)
    thumbnail = models.ImageField(upload_to='course_thumbnails/', null=True, blank=True)
    preview_video_url = models.URLField(blank=True, help_text="Optional preview/promo video URL (YouTube, Vimeo, etc.)")
    coach_name = models.CharField(max_length=100, default='Sprint Coach')
    is_subscribers_only = models.BooleanField(default=False)
    is_accredible_certified = models.BooleanField(default=False)
    has_asset_templates = models.BooleanField(default=False)
    exam_unlock_days = models.IntegerField(default=120, help_text="Days after enrollment before exam unlocks")
    special_tag = models.CharField(max_length=100, blank=True, help_text="e.g., 'Black Friday 2025 Special'")
    
    # Course Delivery Type
    DELIVERY_TYPE_CHOICES = [
        ('pre_recorded', 'Pre-Recorded'),
        ('live', 'Live Course'),
    ]
    delivery_type = models.CharField(max_length=20, choices=DELIVERY_TYPE_CHOICES, default='pre_recorded', help_text="How the course is delivered")
    
    # Course Pricing
    is_paid = models.BooleanField(default=False, help_text="Whether this course requires payment")
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Course price")
    currency = models.CharField(max_length=3, default='USD', help_text="Currency code (e.g., USD, EUR, GBP)")
    
    # Course Availability & Access Rules
    VISIBILITY_CHOICES = [
        ('public', 'Public (visible to anyone)'),
        ('members_only', 'Members Only (visible to logged-in users)'),
        ('hidden', 'Hidden (not in catalog, direct link only)'),
        ('private', 'Private (manual assignment only)'),
    ]
    
    ENROLLMENT_METHOD_CHOICES = [
        ('open', 'Open Enrollment (free/lead magnet)'),
        ('purchase', 'Purchase Required'),
        ('invite_only', 'Invite/Assigned Only'),
        ('cohort_only', 'Cohort Only'),
        ('subscription_only', 'Subscription Only'),
    ]
    
    ACCESS_DURATION_CHOICES = [
        ('lifetime', 'Lifetime Access'),
        ('fixed_days', 'Fixed Duration (days)'),
        ('until_date', 'Access Until Date'),
        ('drip', 'Drip Schedule'),
    ]
    
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='public', help_text="Who can see this course exists")
    enrollment_method = models.CharField(max_length=20, choices=ENROLLMENT_METHOD_CHOICES, default='open', help_text="How students get access")
    access_duration_type = models.CharField(max_length=20, choices=ACCESS_DURATION_CHOICES, default='lifetime', help_text="Access duration rule")
    access_duration_days = models.IntegerField(null=True, blank=True, help_text="Fixed duration in days (if access_duration_type='fixed_days')")
    access_until_date = models.DateTimeField(null=True, blank=True, help_text="Access expires on this date (if access_duration_type='until_date')")
    prerequisite_courses = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='unlocks_courses', help_text="Courses that must be completed first")
    required_quiz_score = models.IntegerField(null=True, blank=True, help_text="Required quiz score to unlock (0-100)")
    
    # Teacher Assignment
    teachers = models.ManyToManyField(User, related_name='taught_courses', blank=True, help_text="Teachers assigned to this course")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def get_lesson_count(self):
        return self.lessons.count()
    
    def get_user_progress(self, user):
        if not user.is_authenticated:
            return 0
        completed = UserProgress.objects.filter(user=user, lesson__course=self, completed=True).count()
        total = self.lessons.count()
        if total == 0:
            return 0
        return int((completed / total) * 100)


class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order', 'id']
    
    def __str__(self):
        return f"{self.course.name} - {self.name}"


class Lesson(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='lessons')
    module = models.ForeignKey(Module, on_delete=models.SET_NULL, null=True, blank=True, related_name='lessons')
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    description = models.TextField()
    video_url = models.URLField(blank=True)
    video_duration = models.IntegerField(default=0, help_text="Duration in minutes")
    order = models.IntegerField(default=0)
    workbook_url = models.URLField(blank=True)
    resources_url = models.URLField(blank=True)
    lesson_type = models.CharField(max_length=50, default='video', choices=[
        ('video', 'Video'),
        ('live', 'Live Session'),
        ('replay', 'Replay'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Vimeo Integration Fields
    vimeo_url = models.URLField(blank=True, help_text="Full Vimeo URL (e.g., https://vimeo.com/123456789)")
    vimeo_id = models.CharField(max_length=50, blank=True, help_text="Vimeo video ID extracted from URL")
    vimeo_thumbnail = models.URLField(blank=True, help_text="Vimeo thumbnail URL")
    vimeo_duration_seconds = models.IntegerField(default=0, help_text="Duration in seconds from Vimeo")
    
    # Google Drive Integration Fields
    google_drive_url = models.URLField(blank=True, help_text="Google Drive video embed URL")
    google_drive_id = models.CharField(max_length=200, blank=True, help_text="Google Drive file ID")
    
    # Lesson Creation Fields
    working_title = models.CharField(max_length=200, blank=True, help_text="Rough title before AI generation")
    rough_notes = models.TextField(blank=True, help_text="Optional notes or outline for AI")
    
    # Transcription Fields
    # Note: Video files are NOT saved to the database - they are only used temporarily for transcription
    transcription = models.TextField(blank=True, help_text="Auto-generated transcription from video")
    transcription_status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ])
    transcription_error = models.TextField(blank=True, help_text="Error message if transcription fails")
    
    # AI Generated Content
    ai_generation_status = models.CharField(max_length=20, default='pending', choices=[
        ('pending', 'Pending'),
        ('generated', 'Generated'),
        ('approved', 'Approved'),
    ])
    ai_clean_title = models.CharField(max_length=200, blank=True, help_text="AI-generated polished title")
    ai_short_summary = models.TextField(blank=True, help_text="AI-generated short summary for lesson list")
    ai_full_description = models.TextField(blank=True, help_text="AI-generated full description for student page")
    ai_outcomes = models.JSONField(default=list, blank=True, help_text="List of outcomes this lesson will produce")
    ai_coach_actions = models.JSONField(default=list, blank=True, help_text="Recommended AI Coach actions for this lesson")
    
    # Editor.js Content
    content = models.JSONField(default=dict, blank=True, help_text="Editor.js content blocks for lesson content")
    
    # AI Chatbot Integration Fields
    ai_chatbot_enabled = models.BooleanField(default=False, help_text="Whether AI chatbot is enabled for this lesson")
    ai_chatbot_webhook_id = models.CharField(max_length=200, blank=True, help_text="Chatbot webhook ID from training")
    ai_chatbot_trained_at = models.DateTimeField(null=True, blank=True, help_text="When transcript was sent for training")
    ai_chatbot_training_status = models.CharField(
        max_length=20, 
        default='pending', 
        choices=[
            ('pending', 'Pending'),
            ('training', 'Training'),
            ('trained', 'Trained'),
            ('failed', 'Failed'),
        ],
        help_text="Status of AI training"
    )
    ai_chatbot_training_error = models.TextField(blank=True, help_text="Error message if training fails")
    
    class Meta:
        ordering = ['order', 'id']
        unique_together = ['course', 'slug']
    
    def __str__(self):
        return f"{self.course.name} - {self.title}"
    
    def get_vimeo_embed_url(self):
        """Convert Vimeo URL to embed format"""
        if self.vimeo_id:
            return f"https://player.vimeo.com/video/{self.vimeo_id}"
        return ""
    
    def get_formatted_duration(self):
        """Format duration in MM:SS format"""
        if self.vimeo_duration_seconds:
            minutes = self.vimeo_duration_seconds // 60
            seconds = self.vimeo_duration_seconds % 60
            return f"{minutes}:{seconds:02d}"
        elif self.video_duration:
            return f"{self.video_duration}:00"
        return "0:00"
    
    def get_outcomes_list(self):
        """Return outcomes as a list"""
        if isinstance(self.ai_outcomes, list):
            return self.ai_outcomes
        if isinstance(self.ai_outcomes, str):
            try:
                return json.loads(self.ai_outcomes)
            except:
                return []
        return []
    
    def get_coach_actions_list(self):
        """Return coach actions as a list"""
        if isinstance(self.ai_coach_actions, list):
            return self.ai_coach_actions
        if isinstance(self.ai_coach_actions, str):
            try:
                return json.loads(self.ai_coach_actions)
            except:
                return []
        return []


class LessonQuiz(models.Model):
    """Optional quiz that can be attached to a lesson."""
    lesson = models.OneToOneField(Lesson, on_delete=models.CASCADE, related_name='quiz')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_required = models.BooleanField(default=True, help_text="If true, quiz must be passed to complete the lesson.")
    passing_score = models.IntegerField(default=70, help_text="Score percentage required to pass (0–100)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['lesson__order', 'lesson__id']

    def __str__(self):
        return f"Quiz for {self.lesson.title}"


class LessonQuizQuestion(models.Model):
    """Multiple‑choice question for a lesson quiz."""
    OPTION_CHOICES = [
        ('A', 'Option A'),
        ('B', 'Option B'),
        ('C', 'Option C'),
        ('D', 'Option D'),
    ]

    quiz = models.ForeignKey(LessonQuiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    option_a = models.CharField(max_length=300)
    option_b = models.CharField(max_length=300)
    option_c = models.CharField(max_length=300, blank=True)
    option_d = models.CharField(max_length=300, blank=True)
    correct_option = models.CharField(max_length=1, choices=OPTION_CHOICES)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"Q{self.order} for {self.quiz.lesson.title}"


class LessonQuizAttempt(models.Model):
    """Track a student's attempts for a lesson quiz."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lesson_quiz_attempts')
    quiz = models.ForeignKey(LessonQuiz, on_delete=models.CASCADE, related_name='attempts')
    score = models.FloatField(null=True, blank=True, help_text="Score percentage (0–100)")
    passed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-completed_at']

    def __str__(self):
        status = "Passed" if self.passed else "Failed"
        return f"{self.user.username} - {self.quiz.lesson.title} - {status}"

class UserProgress(models.Model):
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='user_progress')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    progress_percentage = models.IntegerField(default=0, help_text="Overall lesson progress percentage")
    
    # Video Watch Progress Tracking
    video_watch_percentage = models.FloatField(default=0.0, help_text="Percentage of video watched (0-100)")
    last_watched_timestamp = models.FloatField(default=0.0, help_text="Last timestamp in seconds where video was watched")
    video_completion_threshold = models.FloatField(default=90.0, help_text="Required watch percentage to complete (default 90%)")
    
    last_accessed = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['user', 'lesson']
        ordering = ['-last_accessed']
    
    def __str__(self):
        return f"{self.user.username} - {self.lesson.title}"
    
    def update_status(self):
        """Automatically update status based on progress"""
        if self.video_watch_percentage >= self.video_completion_threshold:
            self.status = 'completed'
            self.completed = True
            if not self.completed_at:
                self.completed_at = timezone.now()
        elif self.video_watch_percentage > 0:
            self.status = 'in_progress'
            if not self.started_at:
                self.started_at = timezone.now()
        else:
            self.status = 'not_started'
        self.save()


class CourseEnrollment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    payment_type = models.CharField(max_length=20, choices=[
        ('full', 'Full Payment'),
        ('installment', 'Installment'),
    ], default='full')
    
    class Meta:
        unique_together = ['user', 'course']
    
    def __str__(self):
        return f"{self.user.username} - {self.course.name}"
    
    def days_until_exam(self):
        """Calculate days until exam is available"""
        if self.payment_type == 'full':
            return 0
        days_elapsed = (timezone.now() - self.enrolled_at).days
        return max(0, self.course.exam_unlock_days - days_elapsed)
    
    def is_exam_available(self):
        """Check if exam is available based on payment type and course completion"""
        if self.payment_type == 'full':
            # Check if all lessons are completed
            total_lessons = self.course.lessons.count()
            completed_lessons = UserProgress.objects.filter(
                user=self.user,
                lesson__course=self.course,
                completed=True
            ).count()
            return completed_lessons >= total_lessons and total_lessons > 0
        else:
            return self.days_until_exam() == 0


class FavoriteCourse(models.Model):
    """Track user's favorite courses"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_courses')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'course']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} favorited {self.course.name}"
    
    def days_until_exam(self):
        if self.payment_type == 'full':
            return 0
        days_elapsed = (timezone.now() - self.enrolled_at).days
        return max(0, self.course.exam_unlock_days - days_elapsed)
    
    def is_exam_available(self):
        """Check if exam is available based on payment type and course completion"""
        if self.payment_type == 'full':
            # Check if all lessons are completed
            total_lessons = self.course.lessons.count()
            completed_lessons = UserProgress.objects.filter(
                user=self.user,
                lesson__course=self.course,
                completed=True
            ).count()
            return completed_lessons >= total_lessons
        else:
            return self.days_until_exam() == 0
    
    def get_certification_status(self):
        """Get current certification status"""
        try:
            cert = Certification.objects.get(user=self.user, course=self.course)
            return cert.status
        except Certification.DoesNotExist:
            # Check if eligible
            if self.is_exam_available():
                return 'eligible'
            return 'not_eligible'


class Exam(models.Model):
    """Final exam for a course"""
    course = models.OneToOneField(Course, on_delete=models.CASCADE, related_name='exam')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    passing_score = models.IntegerField(default=70, help_text="Minimum score percentage to pass")
    max_attempts = models.IntegerField(default=3, help_text="Maximum number of attempts allowed (0 = unlimited)")
    time_limit_minutes = models.IntegerField(null=True, blank=True, help_text="Time limit in minutes (null = no limit)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.course.name} - {self.title}"


class ExamAttempt(models.Model):
    """Track individual exam attempts"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_attempts')
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='attempts')
    score = models.FloatField(null=True, blank=True, help_text="Score percentage (0-100)")
    passed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    time_taken_seconds = models.IntegerField(null=True, blank=True)
    answers = models.JSONField(default=dict, blank=True, help_text="Student's answers")
    is_final = models.BooleanField(default=False, help_text="Whether this is the final/current attempt")
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        status = "Passed" if self.passed else "Failed"
        return f"{self.user.username} - {self.exam.course.name} - Attempt {self.attempt_number()} - {status}"
    
    def attempt_number(self):
        """Get the attempt number for this user and exam"""
        return ExamAttempt.objects.filter(
            user=self.user,
            exam=self.exam,
            started_at__lte=self.started_at
        ).count()


class Certification(models.Model):
    """Track certification status and Accredible integration"""
    STATUS_CHOICES = [
        ('not_eligible', 'Not Eligible'),
        ('eligible', 'Eligible'),
        ('passed', 'Passed - Certified'),
        ('failed', 'Failed - Retry Allowed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='certifications')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='certifications')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_eligible')
    
    # Accredible Integration
    accredible_certificate_id = models.CharField(max_length=200, blank=True, help_text="Accredible certificate ID")
    accredible_certificate_url = models.URLField(blank=True, help_text="Link to Accredible certificate")
    issued_at = models.DateTimeField(null=True, blank=True)
    
    # Related exam attempt that resulted in certification
    passing_exam_attempt = models.ForeignKey(
        'ExamAttempt',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='certifications'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'course']
        ordering = ['-issued_at', '-created_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.course.name} - {self.get_status_display()}"

# ========== ACCESS CONTROL SYSTEM ==========

class Cohort(models.Model):
    """Groups of students (e.g., 'Black Friday 2025 Buyers', 'VIP Mastermind')"""
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def get_member_count(self):
        return self.members.count()
# ========== ACCESS CONTROL SYSTEM ==========

class Cohort(models.Model):
    """Groups of students (e.g., 'Black Friday 2025 Buyers', 'VIP Mastermind')"""
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def get_member_count(self):
        return self.members.count()


class Bundle(models.Model):
    """Product/Bundle that grants access to multiple courses"""
    BUNDLE_TYPES = [
        ('fixed', 'Fixed Bundle (curated set)'),
        ('pick_your_own', 'Pick Your Own (choose N courses)'),
        ('tiered', 'Tiered (Bronze/Silver/Gold)'),
    ]
    
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    bundle_type = models.CharField(max_length=20, choices=BUNDLE_TYPES, default='fixed')
    courses = models.ManyToManyField(Course, related_name='bundles', blank=True)
    max_course_selections = models.IntegerField(null=True, blank=True, help_text="For pick-your-own bundles")
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class BundlePurchase(models.Model):
    """Track bundle purchases"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bundle_purchases')
    bundle = models.ForeignKey(Bundle, on_delete=models.CASCADE, related_name='purchases')
    purchase_id = models.CharField(max_length=200, blank=True, help_text="External purchase/order ID")
    purchase_date = models.DateTimeField(auto_now_add=True)
    selected_courses = models.ManyToManyField(Course, blank=True, help_text="For pick-your-own bundles")
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-purchase_date']
    
    def __str__(self):
        return f"{self.user.username} - {self.bundle.name}"


class CourseAccess(models.Model):
    """Explicit access record - 'Access is a thing, not a side effect'"""
    ACCESS_TYPES = [
        ('purchase', 'Purchase'),
        ('manual', 'Manual (Admin-granted)'),
        ('cohort', 'Cohort/Group'),
        ('subscription', 'Subscription/Membership'),
        ('bundle', 'Bundle Purchase'),
    ]
    
    STATUS_CHOICES = [
        ('unlocked', 'Unlocked (Active)'),
        ('locked', 'Locked'),
        ('revoked', 'Revoked'),
        ('expired', 'Expired'),
        ('pending', 'Pending'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='course_accesses')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='accesses')
    access_type = models.CharField(max_length=20, choices=ACCESS_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unlocked')
    
    # Source tracking
    bundle_purchase = models.ForeignKey(
        BundlePurchase, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='granted_accesses'
    )
    course_purchase = models.ForeignKey(
        'CoursePurchase',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='granted_accesses',
        help_text="Source course purchase"
    )
    cohort = models.ForeignKey(
        Cohort,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='granted_accesses'
    )
    purchase_id = models.CharField(max_length=200, null=True, blank=True, help_text="External purchase ID (legacy)")
    
    # Dates
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='granted_accesses',
        help_text="Admin who granted access (for manual access)"
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revoked_accesses',
        help_text="Admin who revoked access"
    )
    revocation_reason = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True, help_text="Support notes, audit trail")
    
    class Meta:
        ordering = ['-granted_at']
        indexes = [
            models.Index(fields=['user', 'course', 'status']),
            models.Index(fields=['status', 'expires_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.course.name} - {self.get_access_type_display()}"
    
    def is_active(self):
        """Check if access is currently active"""
        if self.status != 'unlocked':
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True
    
    def get_source_display(self):
        """Get human-readable source of access"""
        if self.bundle_purchase:
            return f"Bundle: {self.bundle_purchase.bundle.name}"
        elif self.course_purchase:
            return f"Purchase: {self.course_purchase.provider_id or self.course_purchase.id}"
        elif self.cohort:
            return f"Cohort: {self.cohort.name}"
        elif self.access_type == 'manual':
            return f"Manual (by {self.granted_by.username if self.granted_by else 'Admin'})"
        elif self.purchase_id:
            return f"Purchase: {self.purchase_id}"
        return self.get_access_type_display()


class CoursePurchase(models.Model):
    """Track individual course purchases - proof of payment"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('refunded', 'Refunded'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='course_purchases')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='purchases')
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Purchase amount")
    currency = models.CharField(max_length=3, default='USD', help_text="Currency code")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Payment provider information
    provider = models.CharField(max_length=50, blank=True, help_text="Payment provider (e.g., 'stripe', 'paypal', 'manual')")
    provider_id = models.CharField(max_length=200, blank=True, help_text="Provider transaction/payment ID")
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True, help_text="When payment was confirmed")
    
    # Additional metadata
    notes = models.TextField(blank=True, help_text="Additional notes or metadata")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'course', 'status']),
            models.Index(fields=['status', 'paid_at']),
            models.Index(fields=['provider', 'provider_id']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.course.name} - {self.get_status_display()} - {self.amount} {self.currency}"


class GiftPurchase(models.Model):
    """Track course purchases made as gifts"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('redeemed', 'Redeemed'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Purchase information
    purchaser = models.ForeignKey(User, on_delete=models.CASCADE, related_name='gift_purchases', help_text="User who purchased the gift")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='gift_purchases')
    course_purchase = models.OneToOneField(CoursePurchase, on_delete=models.CASCADE, related_name='gift_purchase', null=True, blank=True, help_text="Linked purchase record")
    
    # Gift details
    recipient_email = models.EmailField(help_text="Email address of the gift recipient")
    recipient_name = models.CharField(max_length=200, blank=True, help_text="Name of the gift recipient")
    gift_message = models.TextField(blank=True, help_text="Optional message from the purchaser")
    
    # Gift status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    gift_token = models.CharField(max_length=64, unique=True, help_text="Unique token for gift redemption")
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True, help_text="When gift email was sent")
    redeemed_at = models.DateTimeField(null=True, blank=True, help_text="When gift was redeemed")
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Gift expiration date (optional)")
    
    # Recipient user (set when redeemed)
    recipient_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_gifts', help_text="User who redeemed the gift")
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['gift_token']),
            models.Index(fields=['recipient_email', 'status']),
            models.Index(fields=['status', 'expires_at']),
        ]
    
    def __str__(self):
        return f"Gift: {self.course.name} to {self.recipient_email} from {self.purchaser.username}"
    
    def save(self, *args, **kwargs):
        """Generate gift token if not set"""
        if not self.gift_token:
            self.gift_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)
    
    def is_expired(self):
        """Check if gift has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def can_be_redeemed(self):
        """Check if gift can be redeemed"""
        return self.status == 'sent' and not self.is_expired() and not self.recipient_user


class LiveSession(models.Model):
    """Live class session for a course"""
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='live_sessions')
    title = models.CharField(max_length=200, help_text="Session title (e.g., 'Week 1 Live Q&A')")
    description = models.TextField(blank=True, help_text="Session description or agenda")
    
    # Scheduling
    scheduled_at = models.DateTimeField(help_text="When the session is scheduled")
    duration_minutes = models.IntegerField(default=60, help_text="Session duration in minutes")
    
    # Session details
    meeting_link = models.URLField(blank=True, help_text="Zoom/Google Meet/etc. link")
    meeting_password = models.CharField(max_length=100, blank=True, help_text="Meeting password if required")
    capacity = models.IntegerField(null=True, blank=True, help_text="Maximum number of attendees (null = unlimited)")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_sessions')
    notes = models.TextField(blank=True, help_text="Internal notes for teacher")
    
    class Meta:
        ordering = ['scheduled_at']
        indexes = [
            models.Index(fields=['course', 'status', 'scheduled_at']),
            models.Index(fields=['status', 'scheduled_at']),
        ]
    
    def __str__(self):
        return f"{self.course.name} - {self.title} - {self.scheduled_at.strftime('%Y-%m-%d %H:%M')}"
    
    def get_bookings_count(self):
        """Get number of bookings for this session"""
        return self.bookings.count()
    
    def get_attended_count(self):
        """Get number of students who attended"""
        return self.bookings.filter(attended=True).count()
    
    def is_full(self):
        """Check if session is at capacity"""
        if self.capacity is None:
            return False
        return self.get_bookings_count() >= self.capacity
    
    def can_book(self):
        """Check if session can accept new bookings"""
        return self.status == 'scheduled' and not self.is_full()


class Booking(models.Model):
    """Student booking for a live session"""
    ATTENDANCE_CHOICES = [
        ('pending', 'Pending'),
        ('attended', 'Attended'),
        ('no_show', 'No Show'),
        ('cancelled', 'Cancelled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name='bookings')
    
    # Booking status
    status = models.CharField(max_length=20, choices=ATTENDANCE_CHOICES, default='pending')
    attended = models.BooleanField(default=False, help_text="Marked as attended by teacher")
    
    # Timestamps
    booked_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    attendance_marked_at = models.DateTimeField(null=True, blank=True)
    attendance_marked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marked_attendances',
        help_text="Teacher who marked attendance"
    )
    
    # Notes
    notes = models.TextField(blank=True, help_text="Teacher notes about this booking")
    
    class Meta:
        unique_together = ['user', 'session']
        ordering = ['booked_at']
        indexes = [
            models.Index(fields=['user', 'session']),
            models.Index(fields=['session', 'status']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.session.title} - {self.get_status_display()}"
    
    def mark_attended(self, marked_by):
        """Mark booking as attended"""
        from django.utils import timezone
        self.attended = True
        self.status = 'attended'
        self.attendance_marked_at = timezone.now()
        self.attendance_marked_by = marked_by
        self.save()
    
    def mark_no_show(self, marked_by):
        """Mark booking as no-show"""
        from django.utils import timezone
        self.attended = False
        self.status = 'no_show'
        self.attendance_marked_at = timezone.now()
        self.attendance_marked_by = marked_by
        self.save()


class CohortMember(models.Model):
    """Link users to cohorts"""
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cohorts')
    joined_at = models.DateTimeField(auto_now_add=True)
    remove_access_on_leave = models.BooleanField(
        default=True,
        help_text="If True, removing from cohort revokes access. If False, access persists."
    )
    
    class Meta:
        unique_together = ['cohort', 'user']
        ordering = ['-joined_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.cohort.name}"


class LearningPath(models.Model):
    """Curated learning journeys (e.g., '7-Figure Launch Path')"""
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    courses = models.ManyToManyField(Course, through='LearningPathCourse', related_name='learning_paths')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class LearningPathCourse(models.Model):
    """Ordered courses in a learning path"""
    learning_path = models.ForeignKey(LearningPath, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    order = models.IntegerField(default=0)
    is_required = models.BooleanField(default=True, help_text="Must complete to unlock next")
    
    class Meta:
        ordering = ['order']
        unique_together = ['learning_path', 'course']
    
    def __str__(self):
        return f"{self.learning_path.name} - {self.course.name} (#{self.order})"


# ============================================================================
# CRM LEAD MANAGEMENT MODELS
# ============================================================================

class Lead(models.Model):
    """CRM Lead model for tracking potential and enrolled students"""
    STATUS_CHOICES = [
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('qualified', 'Qualified'),
        ('enrolled', 'Enrolled'),
        ('converted', 'Converted'),
        ('lost', 'Lost'),
        ('nurturing', 'Nurturing'),
    ]
    
    SOURCE_CHOICES = [
        ('website', 'Website'),
        ('social_media', 'Social Media'),
        ('referral', 'Referral'),
        ('email_campaign', 'Email Campaign'),
        ('paid_ads', 'Paid Ads'),
        ('organic_search', 'Organic Search'),
        ('webinar', 'Webinar'),
        ('event', 'Event'),
        ('other', 'Other'),
    ]
    
    # Basic Information
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True, db_index=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # CRM Fields
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', db_index=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='website', db_index=True)
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='owned_leads', help_text="Assigned CRM owner")
    
    # Linked User Account (if lead has registered)
    linked_user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='lead_profile', help_text="Linked user account if lead has registered")
    
    # Notes and Activity
    notes = models.TextField(blank=True, help_text="Internal notes about the lead")
    last_contact_date = models.DateTimeField(null=True, blank=True, help_text="Last time lead was contacted")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    
    class Meta:
        ordering = ['-updated_at', '-created_at']
        indexes = [
            models.Index(fields=['status', 'source']),
            models.Index(fields=['email']),
            models.Index(fields=['owner', 'status']),
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_gift_enrollments(self):
        """Get all gift enrollments linked to this lead"""
        return GiftPurchase.objects.filter(leadgiftlink__lead=self)
    
    def get_enrollments(self):
        """Get all course enrollments linked to this lead"""
        return CourseEnrollment.objects.filter(leadenrollmentlink__lead=self)
    
    def update_status(self, new_status, actor=None, reason=''):
        """Update lead status and create timeline event"""
        old_status = self.status
        self.status = new_status
        self.updated_at = timezone.now()
        self.save()
        
        # Create timeline event
        LeadTimeline.objects.create(
            lead=self,
            event_type='LEAD_STATUS_CHANGED',
            actor=actor,
            description=f"Status changed from {old_status} to {new_status}" + (f": {reason}" if reason else ""),
            metadata={'old_status': old_status, 'new_status': new_status, 'reason': reason}
        )


class LeadTimeline(models.Model):
    """Timeline events for lead activity tracking"""
    EVENT_TYPES = [
        ('LEAD_CREATED', 'Lead Created'),
        ('LEAD_UPDATED', 'Lead Updated'),
        ('LEAD_STATUS_CHANGED', 'Status Changed'),
        ('LEAD_OWNER_CHANGED', 'Owner Changed'),
        ('LEAD_NOTE_ADDED', 'Note Added'),
        ('USER_LINKED_TO_LEAD', 'User Linked'),
        ('USER_UNLINKED_FROM_LEAD', 'User Unlinked'),
        ('GIFT_LINKED_TO_LEAD', 'Gift Linked'),
        ('GIFT_UNLINKED_FROM_LEAD', 'Gift Unlinked'),
        ('ENROLLMENT_LINKED_TO_LEAD', 'Enrollment Linked'),
        ('ENROLLMENT_UNLINKED_FROM_LEAD', 'Enrollment Unlinked'),
        ('ENROLLMENT_CREATED', 'Enrollment Created'),
    ]
    
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='timeline_events', related_query_name='timeline')
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, help_text="User who performed the action")
    description = models.TextField(help_text="Human-readable description of the event")
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional event data")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['lead', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.lead.get_full_name()} - {self.get_event_type_display()} - {self.created_at}"


class LeadEnrollmentLink(models.Model):
    """Link between leads and course enrollments"""
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='enrollment_links')
    enrollment = models.ForeignKey(CourseEnrollment, on_delete=models.CASCADE, related_name='lead_links')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        unique_together = ['lead', 'enrollment']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.lead.get_full_name()} - {self.enrollment.course.name}"


class LeadGiftLink(models.Model):
    """Link between leads and gift purchases"""
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='gift_links')
    gift = models.ForeignKey(GiftPurchase, on_delete=models.CASCADE, related_name='lead_links')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        unique_together = ['lead', 'gift']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.lead.get_full_name()} - Gift: {self.gift.course.name}"


class TeacherRequest(models.Model):
    """Model to track teacher registration requests"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='teacher_requests')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    bio = models.TextField(help_text="Brief bio and teaching experience")
    qualifications = models.TextField(help_text="Educational background and certifications")
    languages_spoken = models.CharField(max_length=200, help_text="Languages you can teach (comma-separated)")
    teaching_experience = models.TextField(help_text="Years of experience and areas of expertise")
    motivation = models.TextField(help_text="Why do you want to teach on this platform?")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_teacher_requests')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True, help_text="Internal notes for admin review")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.get_status_display()}"

