from django.urls import reverse
from myApp.models import Language, SocialLink, CurrencyConfig
from myApp.services.feature_flags import get_enabled_flags


def _user_dashboard_url(request):
    """Resolve the correct dashboard URL for the logged-in user (admin/teacher/student).

    Returns an empty string for anonymous visitors so templates can fall back to
    the Login link.
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return ""
    # Imported lazily to avoid a circular import (views imports models heavily).
    from myApp.views import _default_dashboard_for_user
    try:
        return reverse(_default_dashboard_for_user(user))
    except Exception:
        return reverse("student_dashboard")


def platform_context(_request):
    active_languages = list(Language.objects.filter(is_active=True).values("code", "name", "is_rtl"))
    social_links = list(
        SocialLink.objects.filter(is_active=True, location__in=["global", "footer"]).values("platform", "url", "location")
    )
    currencies = list(
        CurrencyConfig.objects.filter(is_active=True).values("code", "name", "symbol", "conversion_rate_to_usd", "is_default")
    )
    return {
        "platform_languages": active_languages,
        "platform_social_links": social_links,
        "platform_currencies": currencies,
        "enabled_feature_flags": list(get_enabled_flags()),
        "preferred_currency": getattr(_request, "preferred_currency", "USD"),
        "user_dashboard_url": _user_dashboard_url(_request),
    }

