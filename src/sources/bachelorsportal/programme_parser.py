"""Programme-list parser for Bachelorsportal public university pages."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from ...logger import logger
from ...pipelines.normalize import normalize_duration, normalize_tuition
from .parser import clean_text, source_id_from_url, soupify

PROGRAMME_TITLE_SELECTORS = [
    '[data-testid*="programme-title" i]',
    '[data-testid*="program-title" i]',
    '[data-testid*="study-title" i]',
    '[data-testid*="title" i]',
    '[aria-label*="programme" i] h2',
    '[aria-label*="program" i] h2',
    'a[href*="/studies/"] h1',
    'a[href*="/studies/"] h2',
    'a[href*="/studies/"] h3',
    'h1',
    'h2',
    'h3',
]
LOCATION_SELECTORS = [
    '[data-testid*="location" i]',
    '[aria-label*="location" i]',
    '[class*="Location"]',
    '[class*="location"]',
]
DEGREE_PATTERN = re.compile(r"(?<![A-Za-z])(Bachelor|B\.\s?Sc\.|BSc|B\.\s?A\.|BA|LLB|L\.L\.B\.)(?![A-Za-z])", re.I)
ATTENDANCE_PATTERN = re.compile(r"\b(Full-time|Part-time)\b", re.I)
DELIVERY_PATTERN = re.compile(r"\b(On campus|Online|Distance Learning)\b", re.I)
DURATION_PATTERN = re.compile(r"\b\d+\s*(?:years?|months?)\b", re.I)
TUITION_PATTERN = re.compile(
    r"(?:\b(?:CNY|USD|GBP|EUR)\b|[£€$])\s*\d[\d,]*(?:\.\d+)?\s*(?:/|per)?\s*(?:year|month|semester|term)?"
    r"|\d[\d,]*(?:\.\d+)?\s*\b(?:CNY|USD|GBP|EUR)\b\s*(?:/|per)?\s*(?:year|month|semester|term)?",
    re.I,
)
LOCATION_PATTERN = re.compile(
    r"\b([A-Z][A-Za-z .'-]+),\s*(United Kingdom|England|Scotland|Wales|Northern Ireland|United States|Canada|Australia)\b"
)
REMOVE_FROM_NAME_PATTERNS = [
    DEGREE_PATTERN,
    ATTENDANCE_PATTERN,
    DELIVERY_PATTERN,
    TUITION_PATTERN,
    DURATION_PATTERN,
    re.compile(r"\bFeatured\b", re.I),
    LOCATION_PATTERN,
]


def _absolute(href: str | None, page_url: str) -> str | None:
    if not href:
        return None
    return urljoin(page_url, href)


def _first_text(node: Any, selectors: list[str]) -> str | None:
    for selector in selectors:
        found = node.select_one(selector)
        if found:
            text = clean_text(found.get_text(" "))
            if text:
                return text
    return None


def _card_nodes(soup) -> list:
    cards = []
    for link in soup.select('a[href*="/studies/"]'):
        card = link.find_parent(["article", "li", "section"])
        if card is None:
            card = link.find_parent("div") or link
        cards.append(card)
    if cards:
        return cards
    return list(soup.select('article, li, section, [data-testid*="programme" i], [data-testid*="program" i]'))


def _clean_programme_name(value: str | None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    for pattern in REMOVE_FROM_NAME_PATTERNS:
        match = pattern.search(text)
        if match:
            text = text[: match.start()]
            break
    text = re.sub(r"\s*(?:/|\||•)\s*$", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:500] if text else None


def _programme_name(card, link) -> str | None:
    selector_name = _first_text(card, PROGRAMME_TITLE_SELECTORS)
    if selector_name:
        return _clean_programme_name(selector_name)
    # Last resort is still scoped to the programme link/card and immediately
    # truncated at the first metadata token; never persist full card text.
    return _clean_programme_name(link.get_text(" "))


def _match_text(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return clean_text(match.group(1) if match.groups() else match.group(0)) if match else None


def _degree_type(text: str) -> str | None:
    value = _match_text(DEGREE_PATTERN, text)
    if not value:
        return None
    normalized = value.replace(" ", "").upper()
    mapping = {
        "B.SC.": "B.Sc.",
        "BSC": "B.Sc.",
        "B.A.": "B.A.",
        "BA": "B.A.",
        "LLB": "LLB",
        "L.L.B.": "LLB",
    }
    return mapping.get(normalized, "Bachelor" if value.lower() == "bachelor" else value)


def _attendance_mode(text: str) -> str | None:
    value = _match_text(ATTENDANCE_PATTERN, text)
    if not value:
        return None
    return "Full-time" if value.lower() == "full-time" else "Part-time"


def _delivery_mode(text: str) -> str | None:
    value = _match_text(DELIVERY_PATTERN, text)
    if not value:
        return None
    if value.lower() == "on campus":
        return "On Campus"
    if value.lower() == "distance learning":
        return "Distance Learning"
    return "Online"


def _tuition_text(text: str) -> str | None:
    match = TUITION_PATTERN.search(text)
    return clean_text(match.group(0)) if match else None


def _duration_text(text: str) -> str | None:
    match = DURATION_PATTERN.search(text)
    return clean_text(match.group(0)) if match else None


def _location_text(card, text: str) -> str | None:
    selector_location = _first_text(card, LOCATION_SELECTORS)
    if selector_location:
        return selector_location
    match = LOCATION_PATTERN.search(text)
    if match:
        return f"{match.group(1)}, {match.group(2)}"
    return None


def _location_parts(location: str | None) -> tuple[str | None, str | None]:
    if not location:
        return None, None
    parts = [part.strip() for part in location.split(",") if part.strip()]
    if len(parts) >= 2:
        country = parts[-1]
        if country in {"England", "Scotland", "Wales", "Northern Ireland"}:
            country = "United Kingdom"
        return parts[0], country
    if location in {"United Kingdom", "England", "Scotland", "Wales", "Northern Ireland"}:
        return None, "United Kingdom"
    return None, None


def parse_programmes(html: str, page_url: str) -> list[dict]:
    soup = soupify(html)
    records = []
    seen: set[str] = set()
    for card in _card_nodes(soup):
        link = card.select_one('a[href*="/studies/"]') if hasattr(card, "select_one") else None
        if link is None and getattr(card, "name", None) == "a":
            link = card
        if not link:
            continue
        url = _absolute(link.get("href"), page_url)
        if not url or url in seen:
            continue
        text = clean_text(card.get_text(" ")) or ""
        name = _programme_name(card, link)
        if not name:
            logger.warning("Skipping programme card with missing title: url={}", url)
            continue
        duration_raw = _duration_text(text)
        tuition_raw = _tuition_text(text)
        duration = normalize_duration(duration_raw)
        tuition = normalize_tuition(tuition_raw)
        location_raw = _location_text(card, text)
        city, country = _location_parts(location_raw)
        record = {
            "source_programme_id": source_id_from_url(url),
            "source_url": url,
            "name": name,
            "degree_type": _degree_type(text),
            "discipline": None,
            "attendance_mode": _attendance_mode(text),
            "delivery_mode": _delivery_mode(text),
            "duration_value": duration["duration_value"],
            "duration_unit": duration["duration_unit"],
            "tuition_amount": tuition["amount"],
            "tuition_currency": tuition["currency"],
            "tuition_period": tuition["period"],
            "city": city,
            "country": country,
            "is_featured": 1 if re.search(r"\bFeatured\b", text, re.I) else 0,
            "tuition_text_raw": tuition_raw,
            "duration_text_raw": duration_raw,
        }
        logger.info(
            "Programme parser debug: parsed_name={!r}, parsed_degree_type={!r}, parsed_tuition={!r}, "
            "parsed_duration={!r}, parsed_location={!r}",
            record["name"],
            record["degree_type"],
            tuition_raw,
            duration_raw,
            location_raw,
        )
        records.append(record)
        seen.add(url)
    logger.info("Programme parser: parsed_count={}", len(records))
    return records
