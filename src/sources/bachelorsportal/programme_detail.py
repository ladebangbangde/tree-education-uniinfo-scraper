"""Programme detail parser for public Bachelorsportal study pages."""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin

from ...logger import logger
from ...pipelines.normalize import normalize_duration, normalize_tuition
from .parser import clean_text, soupify

FACT_LABELS = {
    "tuition": ["tuition fee", "tuition"],
    "duration": ["duration"],
    "apply_date": ["apply date", "application deadline", "deadline"],
    "start_date": ["start date", "start dates", "starts"],
    "location": ["campus location", "location"],
    "teaching_language": ["taught in", "language", "languages"],
}
FACT_FIELD_KEYS = [
    "tuition_amount",
    "tuition_currency",
    "tuition_period",
    "tuition_text_raw",
    "scholarships_available",
    "duration_value",
    "duration_unit",
    "duration_text_raw",
    "apply_date_text",
    "start_date_text",
    "city",
    "country",
    "teaching_language",
]
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

HIDDEN_VALUE_SELECTORS = ".Hidden, .Unknown, .js-notAvailable"
TUITION_VALUE_RE = re.compile(
    r"\b(\d[\d,]*(?:\.\d+)?)\s+(USD|GBP|CNY|EUR)\s*/\s*(year|yr|month|semester|term)\b",
    re.I,
)


def _text_without_hidden_value_nodes(node) -> str | None:
    """Return node text after removing known hidden/unavailable value markers."""
    if node is None:
        return None
    fragment = soupify(str(node))
    for hidden in fragment.select(HIDDEN_VALUE_SELECTORS):
        hidden.decompose()
    return clean_text(fragment.get_text(" "))


def _extract_tuition_fee_text(text: str | None) -> str | None:
    """Extract a single tuition fee phrase from noisy QuickFact text."""
    cleaned = clean_text(text)
    if not cleaned:
        return None
    match = TUITION_VALUE_RE.search(cleaned)
    if not match:
        return cleaned
    amount, currency, period = match.groups()
    period = "year" if period.lower() == "yr" else period.lower()
    return f"{amount} {currency.upper()} / {period}"


def _tuition_has_amount(text: str | None) -> bool:
    return normalize_tuition(text)["amount"] is not None


def _tuition_has_currency(text: str | None) -> bool:
    return normalize_tuition(text)["currency"] is not None


def _tuition_has_period(text: str | None) -> bool:
    return normalize_tuition(text)["period"] is not None


def _tuition_text_with_currency(text: str | None, currency: str | None) -> str | None:
    cleaned = clean_text(text)
    if not cleaned or not currency or _tuition_has_currency(cleaned):
        return cleaned
    amount_match = re.search(r"\d[\d,]*(?:\.\d+)?", cleaned)
    if not amount_match:
        return cleaned
    start, end = amount_match.span()
    return clean_text(f"{cleaned[:end]} {currency.upper()} {cleaned[end:]}")


def _tuition_text_with_unit(text: str | None, unit: str | None) -> str | None:
    cleaned = clean_text(text)
    unit_text = clean_text(unit)
    if not cleaned or not unit_text or _tuition_has_period(cleaned):
        return cleaned
    return clean_text(f"{cleaned} {unit_text}")


def _valid_tuition_text(text: str | None) -> str | None:
    tuition_text = _extract_tuition_fee_text(text)
    if (
        tuition_text
        and _tuition_has_amount(tuition_text)
        and _tuition_has_currency(tuition_text)
        and _tuition_has_period(tuition_text)
    ):
        return tuition_text
    return None


def _quick_fact_tuition_text(component) -> str | None:
    """Extract tuition from the Tuition fee QuickFact value area."""
    print(component.prettify())
    unit_values = [_text_without_hidden_value_nodes(node) for node in component.select("span.Unit")]
    unit_text = clean_text(" ".join(filter(None, unit_values)))

    for selector in [".Value", ".ValueContainer", ".TuitionFeeContainer"]:
        value_node = component.select_one(selector)
        text = _tuition_text_with_unit(_text_without_hidden_value_nodes(value_node), unit_text)
        tuition_text = _valid_tuition_text(text)
        if tuition_text:
            return tuition_text

    for span in component.select("span[data-currency]"):
        text = _tuition_text_with_currency(_text_without_hidden_value_nodes(span), span.get("data-currency"))
        text = _tuition_text_with_unit(text, unit_text)
        tuition_text = _valid_tuition_text(text)
        if tuition_text:
            return tuition_text

    for span in component.select("span[data-original_html]"):
        text = _tuition_text_with_currency(span.get("data-original_html"), span.get("data-currency"))
        text = _tuition_text_with_unit(text, unit_text)
        tuition_text = _valid_tuition_text(text)
        if tuition_text:
            return tuition_text

    return None


def _quick_fact_value_text(component) -> str | None:
    """Extract visible value text from a Bachelorsportal QuickFactComponent."""
    for selector in [".Value", ".ValueContainer", ".TuitionFeeContainer", '[class*="Value" i]']:
        value_node = component.select_one(selector)
        text = _text_without_hidden_value_nodes(value_node)
        if text:
            return text
    label_node = component.select_one(".Label")
    fragment = soupify(str(component))
    for hidden in fragment.select(f"{HIDDEN_VALUE_SELECTORS}, .Label"):
        hidden.decompose()
    text = clean_text(fragment.get_text(" "))
    label = clean_text(label_node.get_text(" ")) if label_node else None
    if text and label and text.lower().startswith(label.lower()):
        text = clean_text(text[len(label) :])
    return text


def _quick_fact_label_value_map(soup) -> dict[str, str | None]:
    """Map QuickFactComponent labels to their visible values."""
    label_map: dict[str, str | None] = {}
    for component in soup.select(".QuickFactComponent"):
        label_node = component.select_one(".Label")
        label = clean_text(label_node.get_text(" ")) if label_node else None
        component_text = _text_without_hidden_value_nodes(component) or ""
        if not label and re.search(r"\bscholarships?\s+available\b", component_text, re.I):
            label = "Scholarships available"
        if not label:
            continue
        value = (
            _quick_fact_tuition_text(component)
            if _label_key(label) == "tuition"
            else _quick_fact_value_text(component)
        )
        if re.fullmatch(r"scholarships?\s+available", label, re.I) or re.search(
            r"\bscholarships?\s+available\b", component_text, re.I
        ):
            label_map.setdefault("Scholarships available", value or "Scholarships available")
            continue
        label_map.setdefault(label, value)
    logger.info("parsed_label_map={}", label_map)
    return label_map


def _facts_from_quick_fact_components(soup) -> dict[str, str | None]:
    label_map = _quick_fact_label_value_map(soup)
    facts: dict[str, str | None] = {}
    for label, value in label_map.items():
        key = _label_key(label)
        if key:
            facts.setdefault(key, value)
        elif re.fullmatch(r"scholarships?\s+available", label, re.I):
            facts.setdefault("scholarship", label)
    return facts


def parse_tuition_fact(value: str | None) -> dict[str, Decimal | str | None]:
    """Parse a tuition fact such as ``41,275 USD / year``."""
    text = clean_text(value)
    parsed = normalize_tuition(text)
    return {"amount": parsed["amount"], "currency": parsed["currency"], "period": parsed["period"], "raw": text}


def parse_duration_fact(value: str | None) -> dict[str, int | str | None]:
    """Parse a duration fact such as ``4 years``."""
    text = clean_text(value)
    parsed = normalize_duration(text)
    return {"value": parsed["duration_value"], "unit": parsed["duration_unit"], "raw": text}


def parse_apply_date_fact(value: str | None) -> str | None:
    return clean_text(value)


def parse_start_date_fact(value: str | None) -> str | None:
    return clean_text(value)


def parse_location_fact(value: str | None) -> dict[str, str | None]:
    text = clean_text(value)
    if not text:
        return {"city": None, "country": None, "raw": None}
    parts = [part.strip() for part in text.split(",") if part.strip()]
    if len(parts) >= 2:
        country = parts[-1]
        if country in {"England", "Scotland", "Wales", "Northern Ireland"}:
            country = "United Kingdom"
        return {"city": parts[0], "country": country, "raw": text}
    if text in {"United Kingdom", "England", "Scotland", "Wales", "Northern Ireland"}:
        return {"city": None, "country": "United Kingdom", "raw": text}
    return {"city": None, "country": None, "raw": text}


def parse_teaching_language_fact(value: str | None) -> str | None:
    return clean_text(value)


def parse_scholarship_fact(value: str | None) -> bool | None:
    text = clean_text(value)
    if not text:
        return None
    return True if re.search(r"\bscholarships?\s+available\b", text, re.I) else None


def _looks_like_facts_container(text: str) -> bool:
    lowered = text.lower()
    score = sum(1 for labels in FACT_LABELS.values() if any(label in lowered for label in labels))
    if re.search(r"\bscholarships?\s+available\b", lowered):
        score += 1
    return score >= 2


def _fact_containers(soup) -> list[Any]:
    selectors = [
        '[data-testid*="fact" i]',
        '[data-testid*="summary" i]',
        '[data-testid*="key-info" i]',
        '[class*="fact" i]',
        '[class*="summary" i]',
        '[class*="key-info" i]',
        'aside',
        'dl',
    ]
    containers: list[Any] = []
    for selector in selectors:
        for node in soup.select(selector):
            text = clean_text(node.get_text(" ")) or ""
            is_explicit_fact_scope = bool(
                re.search(r"fact", " ".join(node.get("class", [])), re.I)
                or re.search(r"fact", str(node.get("data-testid", "")), re.I)
            )
            has_any_fact = any(label in text.lower() for labels in FACT_LABELS.values() for label in labels)
            if ((_looks_like_facts_container(text) or (is_explicit_fact_scope and has_any_fact)) and node not in containers):
                containers.append(node)
    if containers:
        # Prefer the smallest matching DOM scopes to avoid parsing unrelated page text.
        containers.sort(key=lambda node: len(clean_text(node.get_text(" ")) or ""))
        return containers[:3]
    return []


def _split_label_value(text: str) -> tuple[str, str] | None:
    cleaned = clean_text(text) or ""
    if _label_key(cleaned):
        return None
    for key, labels in FACT_LABELS.items():
        for label in sorted(labels, key=len, reverse=True):
            match = re.match(rf"^({re.escape(label)})\s*:?\s+(.+)$", cleaned, re.I)
            if match:
                value = clean_text(match.group(2))
                return key, value or ""
    return None


def _label_key(text: str | None) -> str | None:
    label_norm = (clean_text(text) or "").lower().rstrip(":")
    if not label_norm:
        return None
    for key, labels in FACT_LABELS.items():
        if any(label_norm == candidate for candidate in labels):
            return key
    return None


def _fact_lines(container) -> list[str]:
    """Return visible fact-card lines without using whole-page text fallback."""
    raw_lines = container.get_text("\n") if hasattr(container, "get_text") else ""
    lines = []
    for raw in raw_lines.splitlines():
        line = clean_text(raw)
        if not line or line in {":", "-", "—", "|"}:
            continue
        lines.append(line.strip(" :-"))
    return [line for line in lines if line]


def _facts_from_container(container) -> dict[str, str | None]:
    facts: dict[str, str | None] = {}
    lines = _fact_lines(container)
    index = 0
    while index < len(lines):
        line = lines[index]
        if re.fullmatch(r"scholarships?\s+available", line, re.I):
            facts.setdefault("scholarship", line)
            index += 1
            continue

        split = _split_label_value(line)
        if split:
            key, value = split
            if value and not _label_key(value):
                facts.setdefault(key, value)
                index += 1
                continue

        key = _label_key(line)
        if key:
            next_index = index + 1
            while next_index < len(lines):
                candidate = lines[next_index]
                if re.fullmatch(r"scholarships?\s+available", candidate, re.I):
                    facts.setdefault("scholarship", candidate)
                    next_index += 1
                    continue
                if _label_key(candidate):
                    break
                candidate_split = _split_label_value(candidate)
                if candidate_split:
                    break
                facts.setdefault(key, candidate)
                break
            index = next_index if next_index > index + 1 else index + 1
            continue
        index += 1
    return facts


def _first_fact_map(soup) -> dict[str, str | None]:
    quick_facts = _facts_from_quick_fact_components(soup)
    if quick_facts:
        return quick_facts

    merged: dict[str, str | None] = {}
    for container in _fact_containers(soup):
        for key, value in _facts_from_container(container).items():
            merged.setdefault(key, value)
        if merged:
            break
    return merged


def parse_facts_summary(html: str) -> dict[str, Any]:
    """Parse programme top facts summary fields from a scoped facts-card DOM only."""
    soup = soupify(html)
    facts = _first_fact_map(soup)
    tuition = parse_tuition_fact(facts.get("tuition"))
    duration = parse_duration_fact(facts.get("duration"))
    apply_date = parse_apply_date_fact(facts.get("apply_date"))
    start_date = parse_start_date_fact(facts.get("start_date"))
    location = parse_location_fact(facts.get("location"))
    teaching_language = parse_teaching_language_fact(facts.get("teaching_language"))
    scholarships_available = parse_scholarship_fact(facts.get("scholarship"))
    logger.info("parsed_tuition={}", tuition)
    logger.info("parsed_dates={}", {"apply_date": apply_date, "start_date": start_date})
    logger.info("parsed_scholarships={}", scholarships_available is True)
    summary = {
        "tuition_amount": tuition["amount"],
        "tuition_currency": tuition["currency"],
        "tuition_period": tuition["period"],
        "tuition_text_raw": tuition["raw"],
        "scholarships_available": 1 if scholarships_available is True else None,
        "duration_value": duration["value"],
        "duration_unit": duration["unit"],
        "duration_text_raw": duration["raw"],
        "apply_date_text": apply_date,
        "start_date_text": start_date,
        "city": location["city"],
        "country": location["country"],
        "teaching_language": teaching_language,
        "_raw_facts": facts,
    }
    logger.info("Programme facts summary parsed: {}", {key: summary.get(key) for key in FACT_FIELD_KEYS})
    return summary


def _extract_section_text(soup, heading_patterns: list[str]) -> str | None:
    for heading in soup.find_all(re.compile("^h[1-6]$")):
        heading_text = clean_text(heading.get_text(" ")) or ""
        if not any(re.search(pattern, heading_text, re.I) for pattern in heading_patterns):
            continue
        chunks: list[str] = []
        for sibling in heading.find_next_siblings():
            if sibling.name and re.fullmatch(r"h[1-6]", sibling.name):
                break
            text = clean_text(sibling.get_text(" ")) if hasattr(sibling, "get_text") else clean_text(str(sibling))
            if text:
                chunks.append(text)
            if len(" ".join(chunks)) > 4000:
                break
        return clean_text(" ".join(chunks))
    return None


def _first_link(soup, patterns: list[str], page_url: str) -> str | None:
    for link in soup.select("a[href]"):
        text = clean_text(link.get_text(" ")) or ""
        href = link.get("href")
        if href and any(re.search(pattern, text, re.I) for pattern in patterns):
            return urljoin(page_url, href)
    return None


def _parse_month_year(value: str | None) -> tuple[int | None, int | None]:
    text = clean_text(value) or ""
    match = re.search(r"\b([A-Za-z]{3,9})\s+(20\d{2})\b", text)
    if not match:
        return None, None
    month = MONTHS.get(match.group(1).lower()[:4] if match.group(1).lower().startswith("sept") else match.group(1).lower()[:3])
    return int(match.group(2)), month


def parse_programme_detail(html: str, page_url: str) -> dict[str, Any]:
    soup = soupify(html)
    facts_summary = parse_facts_summary(html)
    facts = facts_summary.pop("_raw_facts")
    start_date = facts_summary.get("start_date_text")
    intake_year, intake_month = _parse_month_year(start_date)

    overview = _extract_section_text(soup, [r"overview", r"about"])
    description = _extract_section_text(soup, [r"programme", r"program", r"description"])
    career = _extract_section_text(soup, [r"career"])
    academic_requirements = _extract_section_text(soup, [r"academic requirements?", r"entry requirements?"])
    english_requirements = _extract_section_text(soup, [r"english requirements?", r"language requirements?"])
    other_requirements = _extract_section_text(soup, [r"other requirements?"])
    application_deadline = _extract_section_text(soup, [r"application deadline", r"deadline"])
    application_url = _first_link(soup, [r"apply", r"application"], page_url)
    official_url = _first_link(soup, [r"official", r"programme website", r"program website"], page_url)

    application_requirements = []
    for requirement_type, title, text in [
        ("academic", "Academic requirements", academic_requirements),
        ("english", "English requirements", english_requirements),
        ("other", "Other requirements", other_requirements),
    ]:
        if text:
            application_requirements.append(
                {"requirement_type": requirement_type, "title": title, "raw_text": text, "normalized_text": clean_text(text), "source_url": page_url}
            )

    record = {
        "programme": facts_summary,
        "detail": {
            "overview": overview,
            "description": description,
            "career_opportunities": career,
            "academic_requirements": academic_requirements,
            "english_requirements": english_requirements,
            "other_requirements": other_requirements,
            "application_deadline_text": application_deadline[:255] if application_deadline else None,
            "application_url": application_url,
            "official_programme_url": official_url,
            "source_url": page_url,
        },
        "intake": {
            "intake_date_text": start_date,
            "apply_date_text": facts_summary.get("apply_date_text"),
            "start_date_text": start_date,
            "intake_year": intake_year,
            "intake_month": intake_month,
            "source_url": page_url,
        },
        "language_requirement": {
            "teaching_language": facts_summary.get("teaching_language"),
            "raw_text": facts.get("teaching_language"),
            "source_url": page_url,
        },
        "application_requirements": application_requirements,
        "facts": facts,
    }
    logger.info("Programme detail parser: facts_keys={}", sorted(facts.keys()))
    return record


parse = parse_programme_detail
