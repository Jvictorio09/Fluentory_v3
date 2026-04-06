from django.utils import translation

from myApp.models import AnalyticsEvent, Language
from myApp.services.feature_flags import get_enabled_flags


class FeatureFlagMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.enabled_feature_flags = set(get_enabled_flags())
        return self.get_response(request)


class LanguageSwitchMiddleware:
    """Simple language switch with persisted preference."""

    SESSION_KEY = "preferred_language"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang_code = request.GET.get("lang") or request.session.get(self.SESSION_KEY)
        if lang_code and Language.objects.filter(code=lang_code, is_active=True).exists():
            request.session[self.SESSION_KEY] = lang_code
            translation.activate(lang_code)
            request.LANGUAGE_CODE = lang_code
        return self.get_response(request)


class AnalyticsEventMiddleware:
    """Stores lightweight page-view events for analytics dashboards."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method == "GET" and response.status_code < 400 and not request.path.startswith("/static/"):
            if not request.session.session_key:
                request.session.save()
            AnalyticsEvent.objects.create(
                event_name="page_view",
                user=request.user if request.user.is_authenticated else None,
                session_key=request.session.session_key or "",
                metadata={
                    "path": request.path,
                    "query": dict(request.GET),
                    "referrer": request.META.get("HTTP_REFERER", ""),
                },
                campaign=request.GET.get("utm_campaign", "") or "",
            )
        return response


class CurrencySwitchMiddleware:
    """Persist user-selected currency in session."""

    SESSION_KEY = "preferred_currency"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        currency = request.GET.get("currency")
        if currency:
            request.session[self.SESSION_KEY] = currency.upper().strip()
        request.preferred_currency = request.session.get(self.SESSION_KEY, "USD")
        return self.get_response(request)

