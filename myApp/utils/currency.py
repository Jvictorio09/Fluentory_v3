from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


# Common country -> currency defaults for auto-detection.
COUNTRY_TO_CURRENCY = {
    "AE": "AED",
    "AU": "AUD",
    "BH": "BHD",
    "CA": "CAD",
    "CH": "CHF",
    "CN": "CNY",
    "DE": "EUR",
    "DK": "DKK",
    "EG": "EGP",
    "ES": "EUR",
    "FR": "EUR",
    "GB": "GBP",
    "HK": "HKD",
    "ID": "IDR",
    "IE": "EUR",
    "IN": "INR",
    "IT": "EUR",
    "JP": "JPY",
    "JO": "JOD",
    "KR": "KRW",
    "KW": "KWD",
    "MY": "MYR",
    "NL": "EUR",
    "NO": "NOK",
    "NZ": "NZD",
    "OM": "OMR",
    "PH": "PHP",
    "PK": "PKR",
    "PL": "PLN",
    "QA": "QAR",
    "SA": "SAR",
    "SE": "SEK",
    "SG": "SGD",
    "TH": "THB",
    "TR": "TRY",
    "US": "USD",
    "VN": "VND",
    "ZA": "ZAR",
}


def _to_decimal(value, fallback=Decimal("0")):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return fallback


def build_rate_lookup(currency_rows):
    rates = {}
    symbols = {}
    for row in currency_rows or []:
        code = str(row.get("code", "")).upper().strip()
        if not code:
            continue
        rate = _to_decimal(row.get("conversion_rate_to_usd"), Decimal("0"))
        if rate > 0:
            rates[code] = rate
        symbols[code] = (row.get("symbol") or "").strip()
    return rates, symbols


def convert_currency_amount(amount, source_currency, target_currency, currency_rows):
    """
    Convert `amount` from source_currency to target_currency using
    conversion_rate_to_usd values.
    """
    source = (source_currency or "USD").upper().strip()
    target = (target_currency or source).upper().strip()
    base_amount = _to_decimal(amount, Decimal("0"))
    rates, symbols = build_rate_lookup(currency_rows)

    if base_amount <= 0:
        return base_amount, target, symbols.get(target, "")
    if source == target:
        return base_amount, target, symbols.get(target, "")
    if source not in rates or target not in rates:
        return base_amount, source, symbols.get(source, "")

    amount_usd = base_amount * rates[source]
    converted = amount_usd / rates[target]
    return converted, target, symbols.get(target, "")


def format_currency_amount(amount, currency_code, symbol=""):
    value = _to_decimal(amount, Decimal("0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    numeric = f"{value:,.2f}"
    if symbol:
        clean_symbol = str(symbol).strip()
        clean_code = str(currency_code).strip().upper()
        # Avoid duplicate output like "PHP7,329.55 PHP" when symbol is already a code.
        if clean_symbol.upper() == clean_code:
            return f"{clean_symbol} {numeric}"
        return f"{clean_symbol}{numeric} {clean_code}"
    return f"{numeric} {currency_code}"


def map_country_to_currency(country_code):
    code = (country_code or "").upper().strip()
    return COUNTRY_TO_CURRENCY.get(code)

