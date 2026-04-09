from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import re

from myApp.models import PartnerProfile, PartnerCourseSale, CoursePurchase, CourseAccess, AnalyticsEvent


def _extract_partner_id_from_notes(notes):
    if not notes:
        return None
    match = re.search(r'partner_profile_id:(\d+)', notes)
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _sync_partner_sales(profile):
    """
    Backfill PartnerCourseSale rows from paid purchases.
    - For normal partners: only purchases attributed to their partner id in notes.
    - For Platform profile: all paid purchases not attributed to any partner sale.
    """
    paid_qs = CoursePurchase.objects.filter(status='paid').exclude(partner_sales__isnull=False)

    if profile.partner_name.strip().lower() == 'platform':
        target_purchases = paid_qs
    else:
        target_ids = []
        for p in paid_qs.only('id', 'notes'):
            if _extract_partner_id_from_notes(p.notes or '') == profile.id:
                target_ids.append(p.id)
        # Also include purchases made directly by the partner user account.
        own_purchase_ids = list(
            paid_qs.filter(user_id=profile.user_id).values_list('id', flat=True)
        )
        target_ids.extend(own_purchase_ids)
        target_purchases = CoursePurchase.objects.filter(id__in=target_ids)

    commission_rate = Decimal(str(profile.commission_rate or 0))
    for purchase in target_purchases:
        amount = Decimal(str(purchase.amount or 0))
        commission = (amount * commission_rate / Decimal('100')).quantize(Decimal('0.01'))
        PartnerCourseSale.objects.get_or_create(
            partner=profile,
            purchase=purchase,
            defaults={
                'commission_amount': commission,
                'region': profile.region or '',
            },
        )


@login_required
def partner_dashboard(request):
    profile = PartnerProfile.objects.filter(user=request.user, is_active=True).first()
    if not profile and not request.user.is_staff:
        return JsonResponse({"success": False, "error": "Partner profile not found"}, status=403)
    if request.user.is_staff and not profile:
        profile, _ = PartnerProfile.objects.get_or_create(
            user=request.user,
            defaults={
                "partner_name": "Platform",
                "region": "Global",
                "commission_rate": 0,
                "is_active": True,
            },
        )
        if not profile.is_active:
            profile.is_active = True
            profile.save(update_fields=['is_active'])

    _sync_partner_sales(profile)

    sales = (
        PartnerCourseSale.objects.filter(partner=profile).select_related("purchase__course", "purchase__user")
        if profile.pk
        else PartnerCourseSale.objects.none()
    )
    total_revenue = sales.aggregate(total=Sum("purchase__amount"))["total"] or 0
    active_students = (
        CourseAccess.objects.filter(
            status="unlocked",
            course_purchase__partner_sales__partner=profile,
        )
        .values("user_id")
        .distinct()
        .count()
    )
    courses_sold = sales.values("purchase__course_id").distinct().count()
    last_week = timezone.now() - timedelta(days=7)
    weekly_growth = sales.filter(purchase__paid_at__gte=last_week).count()
    regional = (
        sales.values("region")
        .annotate(total=Sum("purchase__amount"), count=Count("id"))
        .order_by("-total")
    )
    course_performance = (
        sales.values("purchase__course_id", "purchase__course__name", "purchase__course__slug")
        .annotate(
            revenue=Sum("purchase__amount"),
            sales_count=Count("id"),
            commission_total=Sum("commission_amount"),
        )
        .order_by("-revenue", "-sales_count")
    )
    recent_sales = sales.order_by("-purchase__paid_at", "-created_at")[:10]
    recent_sales_revenue = sum((sale.purchase.amount or 0) for sale in recent_sales)
    return render(
        request,
        "partner/dashboard.html",
        {
            "profile": profile,
            "total_revenue": total_revenue,
            "active_students": active_students,
            "courses_sold": courses_sold,
            "weekly_growth": weekly_growth,
            "regional_performance": list(regional),
            "course_performance": list(course_performance),
            "recent_sales": recent_sales,
            "recent_sales_revenue": recent_sales_revenue,
        },
    )


@staff_member_required
def partner_dashboard_api(request):
    since = timezone.now() - timedelta(days=30)
    purchases = CoursePurchase.objects.filter(status="paid", paid_at__gte=since)
    visitors = AnalyticsEvent.objects.filter(event_name="page_view", created_at__gte=since).count()
    conversions = purchases.count()
    conversion_rate = (conversions / visitors * 100) if visitors else 0
    return JsonResponse(
        {
            "success": True,
            "revenue_30d": str(purchases.aggregate(total=Sum("amount"))["total"] or 0),
            "paid_orders_30d": conversions,
            "visitors_30d": visitors,
            "conversion_rate_30d": round(conversion_rate, 2),
        }
    )

