import json
import os
from ipaddress import ip_address
from urllib.error import URLError
from urllib.request import urlopen

from django.conf import settings
from django.core.cache import cache
from django.utils import translation

from myApp.models import AnalyticsEvent, CurrencyConfig, Language
from myApp.services.feature_flags import get_enabled_flags
from myApp.utils.currency import map_country_to_currency


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
    SOURCE_KEY = "preferred_currency_source"

    COUNTRY_HEADER_KEYS = (
        "HTTP_CF_IPCOUNTRY",
        "HTTP_X_COUNTRY_CODE",
        "HTTP_X_VERCEL_IP_COUNTRY",
        "HTTP_X_APPENGINE_COUNTRY",
    )
    IP_HEADER_KEYS = (
        "HTTP_CF_CONNECTING_IP",
        "HTTP_TRUE_CLIENT_IP",
        "HTTP_X_REAL_IP",
        "HTTP_X_FORWARDED_FOR",
        "REMOTE_ADDR",
    )

    COUNTRY_LOOKUP_URL = os.getenv("GEOIP_LOOKUP_URL", "https://ipapi.co/{ip}/json/")
    COUNTRY_LOOKUP_TIMEOUT = float(os.getenv("GEOIP_LOOKUP_TIMEOUT", "1.5") or 1.5)
    DEFAULT_CURRENCY_SEED = {
        "USD": {"name": "US Dollar", "symbol": "$", "rate": "1.000000", "default": True},
        "EUR": {"name": "Euro", "symbol": "EUR", "rate": "1.090000", "default": False},
        "GBP": {"name": "British Pound", "symbol": "GBP", "rate": "1.275000", "default": False},
        "AED": {"name": "UAE Dirham", "symbol": "AED", "rate": "0.272300", "default": False},
        "SAR": {"name": "Saudi Riyal", "symbol": "SAR", "rate": "0.266700", "default": False},
        "JOD": {"name": "Jordanian Dinar", "symbol": "JOD", "rate": "1.410000", "default": False},
        "PHP": {"name": "Philippine Peso", "symbol": "PHP", "rate": "0.017600", "default": False},
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def _ensure_currency_seed(self):
        supported = {
            code.strip().upper()
            for code in getattr(settings, "SUPPORTED_CURRENCIES", ["USD"])
            if str(code).strip()
        }
        if "USD" not in supported:
            supported.add("USD")

        existing_codes = set(
            CurrencyConfig.objects.values_list("code", flat=True)
        )
        rows = []
        for code in sorted(supported):
            if code in existing_codes:
                continue
            seed = self.DEFAULT_CURRENCY_SEED.get(
                code,
                {"name": code, "symbol": code, "rate": "1.000000", "default": code == "USD"},
            )
            rows.append(
                CurrencyConfig(
                    code=code,
                    name=seed["name"],
                    symbol=seed["symbol"],
                    conversion_rate_to_usd=seed["rate"],
                    is_active=True,
                    is_default=bool(seed.get("default", False)),
                )
            )
        if rows:
            CurrencyConfig.objects.bulk_create(rows, ignore_conflicts=True)
        # Ensure one default exists.
        if not CurrencyConfig.objects.filter(is_active=True, is_default=True).exists():
            CurrencyConfig.objects.filter(code="USD").update(is_default=True)

    def _active_currency_codes(self):
        self._ensure_currency_seed()
        return set(
            CurrencyConfig.objects.filter(is_active=True).values_list("code", flat=True)
        )

    def _default_currency_code(self):
        default = (
            CurrencyConfig.objects.filter(is_active=True, is_default=True)
            .values_list("code", flat=True)
            .first()
        )
        return (default or "USD").upper()

    def _extract_client_ip(self, request):
        candidates = []

        for key in self.IP_HEADER_KEYS:
            raw = (request.META.get(key) or "").strip()
            if not raw:
                continue
            if key == "HTTP_X_FORWARDED_FOR":
                candidates.extend([part.strip() for part in raw.split(",") if part.strip()])
            else:
                candidates.append(raw)

        # Prefer the first publicly-routable IP in the chain.
        for candidate in candidates:
            if self._is_public_ip(candidate):
                return candidate

        # Fallback to first syntactically valid IP if all are private/reserved.
        for candidate in candidates:
            try:
                ip_address(candidate)
                return candidate
            except ValueError:
                continue
        return ""

    def _is_public_ip(self, value):
        try:
            parsed = ip_address(value)
            return not (
                parsed.is_private
                or parsed.is_loopback
                or parsed.is_link_local
                or parsed.is_reserved
                or parsed.is_multicast
            )
        except ValueError:
            return False

    def _country_code_from_headers(self, request):
        for key in self.COUNTRY_HEADER_KEYS:
            raw = (request.META.get(key) or "").strip().upper()
            if len(raw) == 2 and raw.isalpha():
                return raw
        return ""

    def _country_code_from_accept_language(self, request):
        header = request.META.get("HTTP_ACCEPT_LANGUAGE", "") or ""
        tokens = [t.strip() for t in header.split(",") if t.strip()]
        for token in tokens:
            lang = token.split(";")[0].strip()
            if "-" in lang:
                region = lang.split("-")[-1].upper()
                if len(region) == 2 and region.isalpha():
                    return region
        return ""

    def _country_code_from_lookup(self, ip_value):
        if not ip_value or not self._is_public_ip(ip_value):
            return ""

        cache_key = f"geo_country:{ip_value}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            url = self.COUNTRY_LOOKUP_URL.format(ip=ip_value)
            with urlopen(url, timeout=self.COUNTRY_LOOKUP_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError, ValueError, KeyError, OSError):
            return ""

        country = (
            payload.get("country_code")
            or payload.get("country")
            or payload.get("countryCode")
            or ""
        )
        country = str(country).strip().upper()
        if len(country) == 2 and country.isalpha():
            cache.set(cache_key, country, timeout=60 * 60 * 24)
            return country
        return ""

    def _auto_detect_currency(self, request, active_codes, default_code):
        manual_country = (request.GET.get("country") or "").strip().upper()
        country = manual_country if len(manual_country) == 2 and manual_country.isalpha() else ""
        if not country:
            country = self._country_code_from_headers(request)
        if not country:
            country = self._country_code_from_lookup(self._extract_client_ip(request))
        if not country:
            country = self._country_code_from_accept_language(request)
        if not country:
            return default_code

        mapped = map_country_to_currency(country)
        if mapped and mapped in active_codes:
            request.currency_auto_country = country
            return mapped
        return default_code

    def __call__(self, request):
        active_codes = self._active_currency_codes()
        default_code = self._default_currency_code()

        currency = (request.GET.get("currency") or "").upper().strip()
        if currency and currency in active_codes:
            request.session[self.SESSION_KEY] = currency
            request.session[self.SOURCE_KEY] = "manual"

        country_hint = (request.GET.get("country") or "").strip()
        if country_hint and not currency:
            hinted_currency = self._auto_detect_currency(request, active_codes, default_code)
            request.session[self.SESSION_KEY] = hinted_currency
            request.session[self.SOURCE_KEY] = "auto"

        selected_in_session = request.session.get(self.SESSION_KEY)
        source_in_session = request.session.get(self.SOURCE_KEY)
        if not selected_in_session:
            auto_currency = self._auto_detect_currency(request, active_codes, default_code)
            request.session[self.SESSION_KEY] = auto_currency
            request.session[self.SOURCE_KEY] = "auto"
        elif source_in_session == "auto" and not currency and not country_hint:
            refreshed_auto_currency = self._auto_detect_currency(request, active_codes, default_code)
            request.session[self.SESSION_KEY] = refreshed_auto_currency

        selected = (request.session.get(self.SESSION_KEY) or default_code).upper()
        if selected not in active_codes:
            selected = default_code
            request.session[self.SESSION_KEY] = selected
            if self.SOURCE_KEY not in request.session:
                request.session[self.SOURCE_KEY] = "default"

        request.preferred_currency = selected
        request.preferred_currency_source = request.session.get(self.SOURCE_KEY, "default")
        return self.get_response(request)

