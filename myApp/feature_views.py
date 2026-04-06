import json
from decimal import Decimal
from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from myApp.models import (
    Course,
    CoursePurchase,
    CourseReview,
    TeacherReview,
    Voucher,
    VoucherRedemption,
    CheckoutOffer,
    PlacementTest,
    PlacementQuestion,
    PlacementAttempt,
    LearningPath,
    FAQItem,
    SocialLink,
    CMSPage,
    CMSPageTranslation,
    CMSPageRevision,
    NotificationEvent,
    StudentTeacherNote,
    VideoAccessToken,
    AnalyticsEvent,
    TeacherAvailability,
    Booking,
    BookingChangeRequest,
)
from myApp.services.audit import write_audit_log
from myApp.services.automation import queue_sequence
from myApp.services.invoicing import issue_invoice_for_purchase
from myApp.services.notifications import queue_notification
from myApp.services.payments import request_refund, process_refund


@login_required
@require_http_methods(["POST"])
def create_refund_request(request, purchase_id):
    purchase = get_object_or_404(CoursePurchase, id=purchase_id)
    if request.user != purchase.user and not request.user.is_staff:
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)
    amount_raw = request.POST.get("amount") or (purchase.amount if request.user == purchase.user else 0)
    try:
        amount = Decimal(str(amount_raw))
    except Exception:
        return JsonResponse({"success": False, "error": "Invalid refund amount"}, status=400)
    reason = request.POST.get("reason", "")
    refund = request_refund(purchase=purchase, amount=amount, actor=request.user, reason=reason)
    return JsonResponse({"success": True, "refund_id": refund.id, "status": refund.status})


@staff_member_required
@require_http_methods(["POST"])
def process_refund_request(request, refund_id):
    from myApp.models import RefundRequest

    refund = get_object_or_404(RefundRequest, id=refund_id)
    response = process_refund(refund, actor=request.user)
    return JsonResponse({"success": bool(response.get("success")), "details": response})


@login_required
@require_http_methods(["POST"])
def apply_voucher(request, course_slug):
    course = get_object_or_404(Course, slug=course_slug)
    code = (request.POST.get("code") or "").strip().upper()
    if not code:
        return JsonResponse({"success": False, "error": "Voucher code is required"}, status=400)
    voucher = Voucher.objects.filter(code=code, is_active=True).first()
    if not voucher or not voucher.can_use():
        return JsonResponse({"success": False, "error": "Voucher is not valid"}, status=400)

    base_price = Decimal(course.price or 0)
    if voucher.discount_type == "percent":
        discounted_amount = (base_price * Decimal(voucher.discount_value) / Decimal("100")).quantize(Decimal("0.01"))
    else:
        discounted_amount = Decimal(voucher.discount_value).quantize(Decimal("0.01"))
    final_price = max(Decimal("0.00"), base_price - discounted_amount)
    purchase = CoursePurchase.objects.create(
        user=request.user,
        course=course,
        amount=final_price,
        currency=course.currency,
        status="pending",
        provider="discount",
        notes=f"Voucher {voucher.code} applied",
    )
    VoucherRedemption.objects.create(
        voucher=voucher,
        user=request.user,
        purchase=purchase,
        discounted_amount=discounted_amount,
    )
    voucher.used_count += 1
    voucher.save(update_fields=["used_count"])
    write_audit_log(
        action="voucher.applied",
        actor=request.user,
        entity_type="Voucher",
        entity_id=voucher.id,
        metadata={"course_id": course.id, "purchase_id": purchase.id, "discounted_amount": str(discounted_amount)},
    )
    return JsonResponse(
        {
            "success": True,
            "purchase_id": purchase.id,
            "original_price": str(base_price),
            "discounted_amount": str(discounted_amount),
            "final_price": str(final_price),
        }
    )


@login_required
@require_http_methods(["POST"])
def submit_course_review(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    rating = int(request.POST.get("rating", 0))
    if rating < 1 or rating > 5:
        return JsonResponse({"success": False, "error": "Rating must be between 1 and 5"}, status=400)
    review_text = request.POST.get("review_text", "").strip()
    review, _ = CourseReview.objects.update_or_create(
        user=request.user,
        course=course,
        defaults={"rating": rating, "review_text": review_text, "status": "pending"},
    )
    return JsonResponse({"success": True, "review_id": review.id, "status": review.status})


@login_required
@require_http_methods(["POST"])
def submit_teacher_review(request, teacher_id):
    from django.contrib.auth.models import User

    teacher = get_object_or_404(User, id=teacher_id)
    rating = int(request.POST.get("rating", 0))
    if rating < 1 or rating > 5:
        return JsonResponse({"success": False, "error": "Rating must be between 1 and 5"}, status=400)
    review_text = request.POST.get("review_text", "").strip()
    course_id = request.POST.get("course_id")
    course = Course.objects.filter(id=course_id).first() if course_id else None
    review, _ = TeacherReview.objects.update_or_create(
        user=request.user,
        teacher=teacher,
        course=course,
        defaults={"rating": rating, "review_text": review_text, "status": "pending"},
    )
    return JsonResponse({"success": True, "review_id": review.id, "status": review.status})


@staff_member_required
@require_http_methods(["POST"])
def moderate_review(request, review_type, review_id):
    status = request.POST.get("status", "approved")
    if status not in {"approved", "rejected", "pending"}:
        return JsonResponse({"success": False, "error": "Invalid status"}, status=400)
    model = CourseReview if review_type == "course" else TeacherReview
    review = get_object_or_404(model, id=review_id)
    review.status = status
    review.moderated_by = request.user
    review.save(update_fields=["status", "moderated_by"])
    return JsonResponse({"success": True, "status": review.status})


@login_required
@require_http_methods(["GET", "POST"])
def placement_test_view(request):
    test = PlacementTest.objects.filter(is_active=True).first()
    if not test:
        return JsonResponse({"success": False, "error": "No active test configured"}, status=404)
    questions = list(test.questions.all().values("id", "question_text", "question_type", "options", "difficulty"))
    if request.method == "GET":
        return JsonResponse({"success": True, "test_id": test.id, "questions": questions})

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)
    answers = data.get("answers", {})
    correct = 0
    total = max(len(questions), 1)
    for q in test.questions.all():
        if str(answers.get(str(q.id), "")).strip().lower() == str(q.correct_answer).strip().lower():
            correct += 1
    score = (correct / total) * 100
    if score < 35:
        level = "A1"
    elif score < 55:
        level = "A2"
    elif score < 70:
        level = "B1"
    elif score < 85:
        level = "B2"
    else:
        level = "C1"
    recommended_path = LearningPath.objects.filter(is_active=True).first()
    recommended_course = Course.objects.filter(status="active").order_by("-created_at").first()
    attempt = PlacementAttempt.objects.create(
        user=request.user,
        test=test,
        answers=answers,
        score=round(score, 2),
        level=level,
        recommended_course=recommended_course,
        recommended_learning_path=recommended_path,
    )
    queue_sequence(
        trigger_key="placement.completed",
        user=request.user,
        payload={"attempt_id": attempt.id, "level": level},
    )
    return JsonResponse(
        {
            "success": True,
            "attempt_id": attempt.id,
            "score": attempt.score,
            "level": attempt.level,
            "recommended_course": recommended_course.name if recommended_course else "",
            "recommended_learning_path": recommended_path.name if recommended_path else "",
        }
    )


@require_http_methods(["GET"])
def faq_page(request):
    lang = request.GET.get("lang", "")
    qs = FAQItem.objects.filter(is_active=True)
    if lang:
        qs = qs.filter(language__code=lang)
    items = list(qs.values("question", "answer", "short_video_url"))
    return JsonResponse({"success": True, "items": items})


@require_http_methods(["GET"])
def social_links(request):
    location = request.GET.get("location", "global")
    items = list(
        SocialLink.objects.filter(is_active=True, location__in=[location, "global"]).values("platform", "url", "location")
    )
    return JsonResponse({"success": True, "items": items})


@staff_member_required
@require_http_methods(["GET", "POST"])
def cms_page_editor(request, slug):
    page, _ = CMSPage.objects.get_or_create(slug=slug, defaults={"title": slug.replace("-", " ").title(), "body": {}})
    if request.method == "POST":
        title = request.POST.get("title", page.title)
        body_raw = request.POST.get("body", "{}")
        try:
            body = json.loads(body_raw)
        except Exception:
            body = {"raw": body_raw}
        page.title = title
        page.body = body
        page.seo_title = request.POST.get("seo_title", page.seo_title)
        page.seo_description = request.POST.get("seo_description", page.seo_description)
        page.updated_by = request.user
        page.save()
        CMSPageRevision.objects.create(
            page=page,
            editor=request.user,
            snapshot={
                "title": page.title,
                "body": page.body,
                "seo_title": page.seo_title,
                "seo_description": page.seo_description,
                "is_published": page.is_published,
            },
            note=request.POST.get("note", "Manual update"),
        )
        return redirect("cms_page_editor", slug=page.slug)
    return render(request, "dashboard/cms_page_editor.html", {"page": page})


@require_http_methods(["GET"])
def cms_public_page(request, slug):
    page = get_object_or_404(CMSPage, slug=slug, is_published=True)
    lang_code = request.GET.get("lang") or getattr(request, "LANGUAGE_CODE", "")
    translation = None
    if lang_code:
        translation = CMSPageTranslation.objects.filter(page=page, language__code=lang_code).first()
    title = translation.title if translation else page.title
    body = translation.body if translation else page.body
    seo_title = translation.seo_title if translation and translation.seo_title else page.seo_title
    seo_description = (
        translation.seo_description if translation and translation.seo_description else page.seo_description
    )
    return JsonResponse(
        {
            "success": True,
            "slug": page.slug,
            "language": lang_code or "default",
            "title": title,
            "body": body,
            "seo_title": seo_title,
            "seo_description": seo_description,
        }
    )


@staff_member_required
@require_http_methods(["GET"])
def analytics_snapshot(request):
    since = timezone.now() - timedelta(days=30)
    visitors = AnalyticsEvent.objects.filter(event_name="page_view", created_at__gte=since).count()
    leads = AnalyticsEvent.objects.filter(event_name="lead_created", created_at__gte=since).count()
    purchases = CoursePurchase.objects.filter(status="paid", paid_at__gte=since).count()
    conversion_rate = (purchases / visitors * 100) if visitors else 0
    course_dropoff = (
        AnalyticsEvent.objects.filter(event_name="lesson_dropoff", created_at__gte=since)
        .values("course_id")
        .annotate(count=models.Count("id"))
        .order_by("-count")[:10]
    )
    campaigns = (
        AnalyticsEvent.objects.filter(campaign__isnull=False, created_at__gte=since)
        .exclude(campaign="")
        .values("campaign")
        .annotate(visits=models.Count("id"))
    )
    return JsonResponse(
        {
            "success": True,
            "visitors_30d": visitors,
            "leads_30d": leads,
            "purchases_30d": purchases,
            "conversion_rate_30d": round(conversion_rate, 2),
            "dropoff_points": list(course_dropoff),
            "campaigns": list(campaigns),
        }
    )


@login_required
@require_http_methods(["POST"])
def teacher_note_create(request, student_id, course_id):
    if not request.user.is_staff and not request.user.taught_courses.filter(id=course_id).exists():
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)
    from django.contrib.auth.models import User

    student = get_object_or_404(User, id=student_id)
    course = get_object_or_404(Course, id=course_id)
    note = StudentTeacherNote.objects.create(
        teacher=request.user,
        student=student,
        course=course,
        note=request.POST.get("note", "").strip(),
    )
    return JsonResponse({"success": True, "note_id": note.id})


@login_required
@require_http_methods(["GET"])
def checkout_offers(request, course_id):
    offers = list(
        CheckoutOffer.objects.filter(is_active=True, trigger_course_id=course_id).values(
            "id", "title", "offer_type", "target_course_id", "discount_percent"
        )
    )
    return JsonResponse({"success": True, "offers": offers})


@login_required
@require_http_methods(["GET"])
def issue_video_token(request, lesson_id):
    from myApp.models import Lesson

    lesson = get_object_or_404(Lesson, id=lesson_id)
    token = VideoAccessToken.issue(lesson=lesson, user=request.user, ttl_seconds=900)
    return JsonResponse({"success": True, "token": token.token, "expires_at": token.expires_at.isoformat()})


@require_http_methods(["GET"])
def available_teacher_slots(request, teacher_id):
    date_str = request.GET.get("date")
    tz_name = request.GET.get("tz", "UTC")
    if not date_str:
        return JsonResponse({"success": False, "error": "date is required (YYYY-MM-DD)"}, status=400)
    try:
        target_date = timezone.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"success": False, "error": "Invalid date format"}, status=400)
    weekday = target_date.weekday()
    windows = TeacherAvailability.objects.filter(teacher_id=teacher_id, weekday=weekday, is_active=True)
    slots = []
    for w in windows:
        slots.append(
            {
                "start_time": w.start_time.strftime("%H:%M"),
                "end_time": w.end_time.strftime("%H:%M"),
                "teacher_timezone": w.timezone_name,
                "viewer_timezone": tz_name,
            }
        )
    return JsonResponse({"success": True, "date": date_str, "slots": slots})


@login_required
@require_http_methods(["POST"])
def booking_change_request(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    if request.user != booking.user and not request.user.is_staff:
        return JsonResponse({"success": False, "error": "Permission denied"}, status=403)
    request_type = request.POST.get("request_type", "cancel")
    if request_type not in {"cancel", "reschedule"}:
        return JsonResponse({"success": False, "error": "Invalid request_type"}, status=400)
    requested_datetime = None
    requested_datetime_raw = request.POST.get("requested_datetime", "")
    if requested_datetime_raw:
        try:
            requested_datetime = timezone.datetime.fromisoformat(requested_datetime_raw)
            if timezone.is_naive(requested_datetime):
                requested_datetime = timezone.make_aware(requested_datetime)
        except ValueError:
            return JsonResponse({"success": False, "error": "Invalid requested_datetime"}, status=400)
    change = BookingChangeRequest.objects.create(
        booking=booking,
        request_type=request_type,
        requested_by=request.user,
        reason=request.POST.get("reason", "").strip(),
        requested_datetime=requested_datetime,
    )
    queue_notification(
        event_key=f"booking.{request_type}_requested",
        user=request.user,
        payload={"booking_id": booking.id, "change_request_id": change.id},
    )
    return JsonResponse({"success": True, "change_request_id": change.id, "status": change.status})


@staff_member_required
@require_http_methods(["POST"])
def trigger_notification_event(request):
    event_key = request.POST.get("event_key", "").strip()
    if not event_key:
        return JsonResponse({"success": False, "error": "event_key is required"}, status=400)
    payload = {}
    payload_raw = request.POST.get("payload", "")
    if payload_raw:
        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError:
            payload = {"raw": payload_raw}
    event = queue_notification(event_key=event_key, user=request.user, payload=payload)
    return JsonResponse({"success": True, "event_id": event.id, "status": event.status})


@staff_member_required
@require_http_methods(["POST"])
def regenerate_invoice(request, purchase_id):
    purchase = get_object_or_404(CoursePurchase, id=purchase_id)
    invoice = issue_invoice_for_purchase(purchase)
    return JsonResponse({"success": True, "invoice_number": invoice.invoice_number})

