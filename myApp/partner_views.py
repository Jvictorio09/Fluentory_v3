from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta

from myApp.models import PartnerProfile, PartnerCourseSale, CoursePurchase, CourseAccess, AnalyticsEvent


@login_required
def partner_dashboard(request):
    profile = PartnerProfile.objects.filter(user=request.user, is_active=True).first()
    if not profile and not request.user.is_staff:
        return JsonResponse({"success": False, "error": "Partner profile not found"}, status=403)
    if request.user.is_staff and not profile:
        profile = PartnerProfile(partner_name="Platform", user=request.user, region="Global", commission_rate=0)

    sales = PartnerCourseSale.objects.filter(partner=profile) if profile.pk else PartnerCourseSale.objects.none()
    total_revenue = sales.aggregate(total=Sum("purchase__amount"))["total"] or 0
    active_students = CourseAccess.objects.filter(status="unlocked").values("user_id").distinct().count()
    courses_sold = sales.values("purchase__course_id").distinct().count()
    last_week = timezone.now() - timedelta(days=7)
    weekly_growth = sales.filter(created_at__gte=last_week).count()
    regional = (
        sales.values("region")
        .annotate(total=Sum("purchase__amount"), count=Count("id"))
        .order_by("-total")
    )
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

