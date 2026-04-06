from django.contrib import admin
from .models import (
    Course, Module, Lesson, UserProgress, CourseEnrollment, Exam, ExamAttempt, Certification,
    Cohort, CohortMember, Bundle, BundlePurchase, CourseAccess, CoursePurchase, GiftPurchase,
    LearningPath, LearningPathCourse, LiveSession, Booking, TeacherRequest, TeacherProfile,
    FeatureFlag, SystemSetting, AuditLog, Language, CMSPage, CMSPageTranslation, CMSPageRevision,
    CurrencyConfig, PaymentTransaction, RefundRequest, Invoice, TeacherPayout, PartnerProfile, PartnerCourseSale,
    StudentTeacherNote, CourseBadge, VideoAccessToken, CourseReview, TeacherReview, Voucher, VoucherRedemption,
    CheckoutOffer, NotificationTemplate, NotificationEvent, EmailSequenceRule, EmailSequenceLog,
    PlacementTest, PlacementQuestion, PlacementAttempt, FAQItem, SocialLink, AnalyticsEvent
    , TeacherAvailability, BookingChangeRequest
)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['name', 'course_type', 'delivery_type', 'status', 'coach_name', 'is_paid', 'price', 'currency', 'is_subscribers_only', 'created_at']

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == 'teachers':
            from .utils.teacher import get_eligible_course_teacher_users
            kwargs['queryset'] = get_eligible_course_teacher_users()
        return super().formfield_for_manytomany(db_field, request, **kwargs)
    list_filter = ['course_type', 'delivery_type', 'status', 'is_paid', 'is_subscribers_only', 'is_accredible_certified']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ['teachers', 'prerequisite_courses']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'course_type', 'status', 'short_description', 'description')
        }),
        ('Media', {
            'fields': ('thumbnail', 'preview_video_url')
        }),
        ('Pricing', {
            'fields': ('is_paid', 'price', 'currency')
        }),
        ('Delivery', {
            'fields': ('delivery_type', 'teachers', 'coach_name', 'created_by')
        }),
        ('Access & Enrollment', {
            'fields': ('visibility', 'enrollment_method', 'access_duration_type', 'access_duration_days', 'access_until_date', 'prerequisite_courses')
        }),
        ('Features', {
            'fields': ('is_subscribers_only', 'is_accredible_certified', 'has_asset_templates', 'exam_unlock_days', 'special_tag')
        }),
    )


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'course', 'order']
    list_filter = ['course']
    ordering = ['course', 'order']


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'module', 'order', 'lesson_type', 'video_duration', 'ai_generation_status']
    list_filter = ['course', 'lesson_type', 'ai_generation_status']
    search_fields = ['title', 'description', 'working_title', 'vimeo_id']
    prepopulated_fields = {'slug': ('title',)}
    ordering = ['course', 'order']
    fieldsets = (
        ('Basic Information', {
            'fields': ('course', 'module', 'title', 'slug', 'order', 'lesson_type')
        }),
        ('Video', {
            'fields': ('video_url', 'vimeo_url', 'vimeo_id', 'vimeo_thumbnail', 'vimeo_duration_seconds', 'video_duration', 'google_drive_url', 'google_drive_id')
        }),
        ('Lesson Creation', {
            'fields': ('working_title', 'rough_notes')
        }),
        ('AI Generated Content', {
            'fields': ('ai_generation_status', 'ai_clean_title', 'ai_short_summary', 'ai_full_description', 'ai_outcomes', 'ai_coach_actions')
        }),
        ('Resources', {
            'fields': ('description', 'workbook_url', 'resources_url')
        }),
    )


@admin.register(UserProgress)
class UserProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'lesson', 'status', 'completed', 'video_watch_percentage', 'progress_percentage', 'last_accessed']
    list_filter = ['status', 'completed', 'last_accessed']
    search_fields = ['user__username', 'lesson__title']
    readonly_fields = ['last_accessed', 'started_at', 'completed_at']


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ['user', 'course', 'payment_type', 'enrolled_at']
    list_filter = ['payment_type', 'enrolled_at']
    search_fields = ['user__username', 'course__name']


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['course', 'title', 'passing_score', 'max_attempts', 'is_active']
    list_filter = ['is_active']
    search_fields = ['course__name', 'title']


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'exam', 'score', 'passed', 'started_at', 'completed_at', 'attempt_number']
    list_filter = ['passed', 'started_at', 'exam']
    search_fields = ['user__username', 'exam__course__name']
    readonly_fields = ['started_at', 'attempt_number']
    
    def attempt_number(self, obj):
        return obj.attempt_number()
    attempt_number.short_description = 'Attempt #'


@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'course', 'status', 'issued_at', 'accredible_certificate_id']
    list_filter = ['status', 'issued_at']
    search_fields = ['user__username', 'course__name', 'accredible_certificate_id']
    readonly_fields = ['created_at', 'updated_at']


# ========== ACCESS CONTROL ADMIN ==========

@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'get_member_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(CohortMember)
class CohortMemberAdmin(admin.ModelAdmin):
    list_display = ['user', 'cohort', 'joined_at', 'remove_access_on_leave']
    list_filter = ['cohort', 'joined_at', 'remove_access_on_leave']
    search_fields = ['user__username', 'cohort__name']


@admin.register(Bundle)
class BundleAdmin(admin.ModelAdmin):
    list_display = ['name', 'bundle_type', 'is_active', 'price', 'get_course_count', 'created_at']
    list_filter = ['bundle_type', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    filter_horizontal = ['courses']
    
    def get_course_count(self, obj):
        return obj.courses.count()
    get_course_count.short_description = 'Courses'


@admin.register(BundlePurchase)
class BundlePurchaseAdmin(admin.ModelAdmin):
    list_display = ['user', 'bundle', 'purchase_id', 'purchase_date']
    list_filter = ['bundle', 'purchase_date']
    search_fields = ['user__username', 'bundle__name', 'purchase_id']
    filter_horizontal = ['selected_courses']
    readonly_fields = ['purchase_date']


@admin.register(CoursePurchase)
class CoursePurchaseAdmin(admin.ModelAdmin):
    list_display = ['user', 'course', 'amount', 'currency', 'status', 'provider', 'paid_at', 'created_at']
    list_filter = ['status', 'provider', 'currency', 'paid_at', 'created_at']
    search_fields = ['user__username', 'course__name', 'provider_id', 'provider']
    readonly_fields = ['created_at', 'paid_at']
    fieldsets = (
        ('Purchase Information', {
            'fields': ('user', 'course', 'amount', 'currency', 'status')
        }),
        ('Payment Provider', {
            'fields': ('provider', 'provider_id')
        }),
        ('Dates', {
            'fields': ('created_at', 'paid_at')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )


@admin.register(CourseAccess)
class CourseAccessAdmin(admin.ModelAdmin):
    list_display = ['user', 'course', 'access_type', 'status', 'get_source', 'granted_at', 'expires_at']
    list_filter = ['access_type', 'status', 'granted_at', 'expires_at']
    search_fields = ['user__username', 'course__name', 'purchase_id']
    readonly_fields = ['granted_at', 'revoked_at']
    fieldsets = (
        ('Access Information', {
            'fields': ('user', 'course', 'access_type', 'status')
        }),
        ('Source', {
            'fields': ('bundle_purchase', 'course_purchase', 'cohort', 'purchase_id', 'granted_by')
        }),
        ('Dates', {
            'fields': ('granted_at', 'expires_at', 'revoked_at', 'revoked_by', 'revocation_reason')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )
    
    def get_source(self, obj):
        return obj.get_source_display()
    get_source.short_description = 'Source'


@admin.register(LearningPath)
class LearningPathAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'get_course_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    
    def get_course_count(self, obj):
        return obj.courses.count()
    get_course_count.short_description = 'Courses'


@admin.register(LearningPathCourse)
class LearningPathCourseAdmin(admin.ModelAdmin):
    list_display = ['learning_path', 'course', 'order', 'is_required']
    list_filter = ['learning_path', 'is_required']
    search_fields = ['learning_path__name', 'course__name']
    ordering = ['learning_path', 'order']


# ========== TEACHER & LIVE SESSIONS ADMIN ==========

@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'scheduled_at', 'duration_minutes', 'status', 'get_bookings_count', 'capacity', 'created_at']
    list_filter = ['status', 'scheduled_at', 'course']
    search_fields = ['title', 'description', 'course__name']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Session Information', {
            'fields': ('course', 'title', 'description', 'status')
        }),
        ('Scheduling', {
            'fields': ('scheduled_at', 'duration_minutes', 'capacity')
        }),
        ('Meeting Details', {
            'fields': ('meeting_link', 'meeting_password')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at', 'notes')
        }),
    )
    
    def get_bookings_count(self, obj):
        return obj.get_bookings_count()
    get_bookings_count.short_description = 'Bookings'


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['user', 'session', 'status', 'attended', 'booked_at', 'attendance_marked_at', 'attendance_marked_by']
    list_filter = ['status', 'attended', 'booked_at', 'session__course']
    search_fields = ['user__username', 'session__title', 'session__course__name']
    readonly_fields = ['booked_at', 'cancelled_at', 'attendance_marked_at']
    fieldsets = (
        ('Booking Information', {
            'fields': ('user', 'session', 'status', 'attended')
        }),
        ('Attendance', {
            'fields': ('attendance_marked_at', 'attendance_marked_by', 'notes')
        }),
        ('Timestamps', {
            'fields': ('booked_at', 'cancelled_at')
        }),
    )


@admin.register(GiftPurchase)
class GiftPurchaseAdmin(admin.ModelAdmin):
    list_display = ['course', 'purchaser', 'recipient_email', 'recipient_name', 'status', 'created_at', 'sent_at', 'redeemed_at']
    list_filter = ['status', 'course', 'created_at', 'sent_at', 'redeemed_at']
    search_fields = ['recipient_email', 'recipient_name', 'purchaser__username', 'course__name', 'gift_token']
    readonly_fields = ['gift_token', 'created_at', 'sent_at', 'redeemed_at']
    fieldsets = (
        ('Gift Information', {
            'fields': ('purchaser', 'course', 'course_purchase', 'gift_token')
        }),
        ('Recipient Details', {
            'fields': ('recipient_email', 'recipient_name', 'recipient_user', 'gift_message')
        }),
        ('Status', {
            'fields': ('status', 'expires_at')
        }),
        ('Dates', {
            'fields': ('created_at', 'sent_at', 'redeemed_at')
        }),
    )


@admin.register(TeacherRequest)
class TeacherRequestAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'email', 'status', 'languages_spoken', 'created_at', 'reviewed_at', 'reviewed_by']
    list_filter = ['status', 'created_at', 'reviewed_at']
    search_fields = ['first_name', 'last_name', 'email', 'user__username', 'languages_spoken']
    readonly_fields = ['created_at', 'updated_at', 'reviewed_at']
    fieldsets = (
        ('Personal Information', {
            'fields': ('user', 'first_name', 'last_name', 'email', 'phone')
        }),
        ('Teaching Information', {
            'fields': ('bio', 'qualifications', 'languages_spoken', 'teaching_experience', 'motivation')
        }),
        ('Review Status', {
            'fields': ('status', 'reviewed_by', 'reviewed_at', 'admin_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'headline', 'website', 'linkedin_url', 'updated_at']
    search_fields = ['user__username', 'user__first_name', 'user__last_name', 'headline', 'bio']
    readonly_fields = ['updated_at']


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ['key', 'is_enabled', 'rollout_percentage', 'updated_at']
    list_filter = ['is_enabled']
    search_fields = ['key', 'description']


@admin.register(SystemSetting)
class SystemSettingAdmin(admin.ModelAdmin):
    list_display = ['key', 'value_type', 'updated_at', 'updated_by']
    search_fields = ['key']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'actor', 'entity_type', 'entity_id', 'created_at']
    list_filter = ['action', 'entity_type', 'created_at']
    search_fields = ['action', 'entity_type', 'entity_id']
    readonly_fields = ['created_at']


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'is_active', 'is_default', 'is_rtl']
    list_filter = ['is_active', 'is_default', 'is_rtl']


@admin.register(CMSPage)
class CMSPageAdmin(admin.ModelAdmin):
    list_display = ['slug', 'title', 'is_published', 'updated_at', 'updated_by']
    list_filter = ['is_published']
    search_fields = ['slug', 'title']


@admin.register(CMSPageTranslation)
class CMSPageTranslationAdmin(admin.ModelAdmin):
    list_display = ['page', 'language', 'updated_at']
    list_filter = ['language']
    search_fields = ['page__slug']


@admin.register(CMSPageRevision)
class CMSPageRevisionAdmin(admin.ModelAdmin):
    list_display = ['page', 'editor', 'created_at', 'note']
    search_fields = ['page__slug', 'note']


@admin.register(CurrencyConfig)
class CurrencyConfigAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'symbol', 'is_active', 'is_default', 'conversion_rate_to_usd']
    list_filter = ['is_active', 'is_default']
    search_fields = ['code', 'name']


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ['provider', 'provider_payment_id', 'purchase', 'amount', 'currency', 'status', 'created_at']
    list_filter = ['provider', 'status', 'currency']
    search_fields = ['provider_payment_id', 'idempotency_key']


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = ['purchase', 'amount', 'status', 'requested_by', 'approved_by', 'created_at', 'processed_at']
    list_filter = ['status', 'created_at']
    search_fields = ['purchase__id', 'provider_refund_id', 'reason']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'purchase', 'amount', 'currency', 'issued_at']
    search_fields = ['invoice_number', 'purchase__id']


@admin.register(TeacherPayout)
class TeacherPayoutAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'period_start', 'period_end', 'amount', 'currency', 'status']
    list_filter = ['status', 'currency']


@admin.register(PartnerProfile)
class PartnerProfileAdmin(admin.ModelAdmin):
    list_display = ['partner_name', 'user', 'region', 'commission_rate', 'is_active']
    list_filter = ['is_active', 'region']
    search_fields = ['partner_name', 'user__username']


@admin.register(PartnerCourseSale)
class PartnerCourseSaleAdmin(admin.ModelAdmin):
    list_display = ['partner', 'purchase', 'commission_amount', 'region', 'created_at']
    list_filter = ['region']


@admin.register(StudentTeacherNote)
class StudentTeacherNoteAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'student', 'course', 'updated_at']
    search_fields = ['teacher__username', 'student__username', 'course__name']


@admin.register(CourseBadge)
class CourseBadgeAdmin(admin.ModelAdmin):
    list_display = ['course', 'badge_type', 'is_active', 'starts_at', 'ends_at']
    list_filter = ['badge_type', 'is_active']


@admin.register(VideoAccessToken)
class VideoAccessTokenAdmin(admin.ModelAdmin):
    list_display = ['lesson', 'user', 'expires_at', 'created_at']
    list_filter = ['expires_at']
    search_fields = ['token', 'user__username', 'lesson__title']


@admin.register(CourseReview)
class CourseReviewAdmin(admin.ModelAdmin):
    list_display = ['course', 'user', 'rating', 'status', 'created_at']
    list_filter = ['status', 'rating']


@admin.register(TeacherReview)
class TeacherReviewAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'user', 'rating', 'status', 'created_at']
    list_filter = ['status', 'rating']


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ['code', 'discount_type', 'discount_value', 'usage_limit', 'used_count', 'is_active', 'campaign']
    list_filter = ['discount_type', 'is_active', 'campaign']
    search_fields = ['code', 'campaign']


@admin.register(VoucherRedemption)
class VoucherRedemptionAdmin(admin.ModelAdmin):
    list_display = ['voucher', 'user', 'purchase', 'discounted_amount', 'created_at']
    list_filter = ['voucher']


@admin.register(CheckoutOffer)
class CheckoutOfferAdmin(admin.ModelAdmin):
    list_display = ['title', 'offer_type', 'trigger_course', 'target_course', 'discount_percent', 'is_active']
    list_filter = ['offer_type', 'is_active']


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ['event_key', 'channel', 'is_active', 'updated_at']
    list_filter = ['channel', 'is_active']


@admin.register(NotificationEvent)
class NotificationEventAdmin(admin.ModelAdmin):
    list_display = ['event_key', 'user', 'status', 'created_at', 'processed_at']
    list_filter = ['status', 'event_key']


@admin.register(EmailSequenceRule)
class EmailSequenceRuleAdmin(admin.ModelAdmin):
    list_display = ['trigger_key', 'delay_minutes', 'is_active', 'template']
    list_filter = ['is_active']


@admin.register(EmailSequenceLog)
class EmailSequenceLogAdmin(admin.ModelAdmin):
    list_display = ['rule', 'user', 'status', 'created_at', 'sent_at']
    list_filter = ['status']


@admin.register(PlacementTest)
class PlacementTestAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active']


@admin.register(PlacementQuestion)
class PlacementQuestionAdmin(admin.ModelAdmin):
    list_display = ['test', 'order', 'question_type', 'difficulty']
    list_filter = ['question_type', 'difficulty']


@admin.register(PlacementAttempt)
class PlacementAttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'test', 'score', 'level', 'recommended_course', 'created_at']
    list_filter = ['level', 'test']


@admin.register(FAQItem)
class FAQItemAdmin(admin.ModelAdmin):
    list_display = ['question', 'language', 'is_active', 'order']
    list_filter = ['is_active', 'language']


@admin.register(SocialLink)
class SocialLinkAdmin(admin.ModelAdmin):
    list_display = ['platform', 'location', 'url', 'is_active', 'order']
    list_filter = ['location', 'is_active']


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ['event_name', 'user', 'session_key', 'campaign', 'created_at']
    list_filter = ['event_name', 'campaign']
    search_fields = ['event_name', 'session_key', 'campaign']


@admin.register(TeacherAvailability)
class TeacherAvailabilityAdmin(admin.ModelAdmin):
    list_display = ['teacher', 'weekday', 'start_time', 'end_time', 'timezone_name', 'is_active']
    list_filter = ['weekday', 'is_active', 'timezone_name']


@admin.register(BookingChangeRequest)
class BookingChangeRequestAdmin(admin.ModelAdmin):
    list_display = ['booking', 'request_type', 'requested_by', 'status', 'requested_datetime', 'created_at']
    list_filter = ['request_type', 'status']

