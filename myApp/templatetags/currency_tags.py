from django import template

from myApp.utils.currency import convert_currency_amount, format_currency_amount

register = template.Library()


@register.simple_tag(takes_context=True)
def local_money(context, amount, source_currency="USD"):
    """
    Render amount using visitor preferred currency when conversion config exists.
    Usage:
      {% local_money course.price course.currency as localized_price %}
      {{ localized_price }}
    """
    preferred_currency = context.get("preferred_currency", "USD")
    currency_rows = context.get("platform_currencies", [])
    converted_amount, target_code, symbol = convert_currency_amount(
        amount=amount,
        source_currency=source_currency,
        target_currency=preferred_currency,
        currency_rows=currency_rows,
    )
    return format_currency_amount(converted_amount, target_code, symbol)

