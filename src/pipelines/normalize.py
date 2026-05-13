"""Field normalization helpers. Missing or malformed values return None fields."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

CURRENCY_MAP = {"£": "GBP", "$": "USD", "€": "EUR", "GBP": "GBP", "EUR": "EUR", "USD": "USD", "CNY": "CNY"}


def normalize_count(text: str | None) -> int | None:
    if not text:
        return None
    value = text.strip().upper().replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)\s*([KM])?", value)
    if not match:
        return None
    number = float(match.group(1))
    suffix = match.group(2)
    if suffix == "K":
        number *= 1000
    elif suffix == "M":
        number *= 1_000_000
    return int(number)


def normalize_rating(text: str | None) -> Decimal | None:
    if not text:
        return None
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return Decimal(match.group(0)).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def normalize_duration(text: str | None) -> dict[str, int | str | None]:
    result = {"duration_value": None, "duration_unit": None}
    if not text:
        return result
    match = re.search(r"(\d+)\s*(year|years|yr|yrs|month|months|mo|mos)", text, re.I)
    if not match:
        return result
    unit = match.group(2).lower()
    result["duration_value"] = int(match.group(1))
    result["duration_unit"] = "year" if unit.startswith(("year", "yr")) else "month"
    return result


def normalize_tuition(text: str | None) -> dict[str, Decimal | str | None]:
    result = {"amount": None, "currency": None, "period": None}
    if not text:
        return result
    currency_match = re.search(r"(CNY|GBP|EUR|USD|£|€|\$)", text, re.I)
    if currency_match:
        token = currency_match.group(1).upper()
        result["currency"] = CURRENCY_MAP.get(token, CURRENCY_MAP.get(currency_match.group(1), token))
    amount_match = re.search(r"(\d[\d,]*(?:\.\d+)?)", text)
    if amount_match:
        try:
            result["amount"] = Decimal(amount_match.group(1).replace(",", "")).quantize(Decimal("0.01"))
        except InvalidOperation:
            result["amount"] = None
    period_match = re.search(r"/\s*(year|yr|month|semester|term)|per\s+(year|month|semester|term)", text, re.I)
    if period_match:
        period = next(group for group in period_match.groups() if group)
        result["period"] = "year" if period.lower() == "yr" else period.lower()
    return result
