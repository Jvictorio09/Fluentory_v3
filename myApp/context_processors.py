from myApp.models import Language, SocialLink, CurrencyConfig
from myApp.services.feature_flags import get_enabled_flags


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
    }

