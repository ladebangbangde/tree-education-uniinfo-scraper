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
        '[class*="fact" i]',
        '[class*="key-info" i]',
        '[class*="overview" i]',
        'aside',
        'section',
        'article',
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
    match = re.match(r"^([A-Za-z][A-Za-z ]{1,40})\s*:?\s+(.+)$", cleaned)
    if not match:
        return None
    return match.group(1).strip().lower(), match.group(2).strip()


def _facts_from_container(container) -> dict[str, str | None]:
    facts: dict[str, str | None] = {}
    nodes = container.select("dt, dd, li, p, div, span") if hasattr(container, "select") else []

    # Definition-list pass: dt label followed by dd value.
    for dt in container.select("dt") if hasattr(container, "select") else []:
        label = clean_text(dt.get_text(" ")) or ""
        dd = dt.find_next_sibling("dd")
        value = clean_text(dd.get_text(" ")) if dd else None
        _assign_fact(facts, label, value)

    for node in nodes:
        text = clean_text(node.get_text(" ")) or ""
        if re.search(r"\bscholarships?\s+available\b", text, re.I):
            facts.setdefault("scholarship", text)
        split = _split_label_value(text)
        if split:
            label, value = split
            _assign_fact(facts, label, value)
            continue
        aria = clean_text(node.get("aria-label")) if hasattr(node, "get") else None
        if aria:
            split = _split_label_value(aria)
            if split:
                label, value = split
                _assign_fact(facts, label, value)
    return facts


def _assign_fact(facts: dict[str, str | None], label: str, value: str | None) -> None:
    label_norm = (clean_text(label) or "").lower().rstrip(":")
    if not value:
        return
    for key, labels in FACT_LABELS.items():
        if any(candidate == label_norm or candidate in label_norm for candidate in labels):
            facts.setdefault(key, clean_text(value))
            return


def _first_fact_map(soup) -> dict[str, str | None]:
    merged: dict[str, str | None] = {}
    for container in _fact_containers(soup):
        for key, value in _facts_from_container(container).items():
            merged.setdefault(key, value)
    return merged


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
    facts = _first_fact_map(soup)

    tuition = parse_tuition_fact(facts.get("tuition"))
    duration = parse_duration_fact(facts.get("duration"))
    apply_date = parse_apply_date_fact(facts.get("apply_date"))
    start_date = parse_start_date_fact(facts.get("start_date"))
    location = parse_location_fact(facts.get("location"))
    teaching_language = parse_teaching_language_fact(facts.get("teaching_language"))
    scholarships_available = parse_scholarship_fact(facts.get("scholarship"))
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
        "programme": {
            "tuition_amount": tuition["amount"],
            "tuition_currency": tuition["currency"],
            "tuition_period": tuition["period"],
            "tuition_text_raw": tuition["raw"],
            "duration_value": duration["value"],
            "duration_unit": duration["unit"],
            "duration_text_raw": duration["raw"],
            "apply_date_text": apply_date,
            "start_date_text": start_date,
            "city": location["city"],
            "country": location["country"],
            "teaching_language": teaching_language,
            "scholarships_available": 1 if scholarships_available is True else None,
        },
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
            "apply_date_text": apply_date,
            "start_date_text": start_date,
            "intake_year": intake_year,
            "intake_month": intake_month,
            "source_url": page_url,
        },
        "language_requirement": {
            "teaching_language": teaching_language,
            "raw_text": facts.get("teaching_language"),
            "source_url": page_url,
        },
        "application_requirements": application_requirements,
        "facts": facts,
    }
    logger.info("Programme detail parser: facts_keys={}", sorted(facts.keys()))
    return record


parse = parse_programme_detail
