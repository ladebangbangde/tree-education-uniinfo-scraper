"""Robust parsers for public Bachelorsportal HTML.

The list parser intentionally uses multiple extraction strategies because public
search markup can change without notice: structured data first, then semantic
BeautifulSoup selectors, and finally a small regex fallback for local fixtures or
minimal HTML. All extracted fields are nullable except the source identity fields
required for persistence.
"""
from __future__ import annotations

import html as html_lib
import importlib.util
import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse

if importlib.util.find_spec("bs4"):
    from bs4 import BeautifulSoup
else:  # pragma: no cover - exercised only in dependency-limited environments.
    BeautifulSoup = None  # type: ignore[assignment]

from ...logger import logger
from ...pipelines.normalize import normalize_count, normalize_duration, normalize_rating, normalize_tuition

BASE_URL = "https://www.bachelorsportal.com"
SOURCE_SITE = "bachelorsportal"
SECTION_TYPES = {
    "overview": "overview",
    "history": "history",
    "education": "education",
    "research": "research",
    "career": "career",
    "housing": "housing",
    "library": "library",
    "campus life": "campus_life",
    "accreditation": "accreditation",
}


def soupify(html: str):
    if BeautifulSoup is None:
        raise RuntimeError("beautifulsoup4 is required for this parser path")
    return BeautifulSoup(html, "html.parser")


def clean_text(value: str | None) -> str | None:
    if not value:
        return None
    text = html_lib.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def source_id_from_url(url: str) -> str:
    """Extract a stable Bachelorsportal university id or slug from a source URL."""
    parsed = urlparse(url)
    match = re.search(r"/(?:universities|university)/(\d+)(?:/|$)|-(\d+)(?:\.html)?$", parsed.path)
    if match:
        return next(group for group in match.groups() if group)
    slug = parsed.path.strip("/").split("/")[-1]
    return slug or url


def _first_text(node, selectors: list[str]) -> str | None:
    if node is None:
        return None
    for selector in selectors:
        found = node.select_one(selector)
        if found:
            text = clean_text(found.get_text(" "))
            if text:
                return text
    return None


def _absolute(href: str | None, base_url: str = BASE_URL) -> str | None:
    if not href:
        return None
    return urljoin(base_url, href)


def _location_parts(location: str | None) -> tuple[str | None, str | None]:
    if not location:
        return None, None
    parts = [part.strip() for part in location.split(",") if part.strip()]
    if len(parts) >= 2:
        return parts[0], parts[-1]
    if location in {"United Kingdom", "England", "Scotland", "Wales", "Northern Ireland"}:
        return None, "United Kingdom" if location != "United Kingdom" else location
    return None, location


def _location_from_text(text: str) -> str | None:
    """Best-effort location fallback for card text."""
    labelled = re.search(
        r"(?:Location|City)\s*:?\s*(.*?)(?:\s+Attendance\b|\s+Global Ranking\b|\s+Institution type\b|\s+Bachelors?\b|\s+Masters?\b|\s+Scholarships?\b|$)",
        text,
        re.I,
    )
    if labelled:
        candidate = clean_text(labelled.group(1))
        if candidate:
            return candidate
    patterns = [
        r"([A-Z][A-Za-z .'-]+),\s*(United Kingdom|England|Scotland|Wales|Northern Ireland)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return f"{match.group(1)}, {match.group(2)}"
    if "United Kingdom" in text:
        return "United Kingdom"
    return None


def _name_from_card_text(text: str | None) -> str | None:
    """Extract the university name when an anchor wraps the whole result card."""
    cleaned = clean_text(text)
    if not cleaned:
        return None
    marker_match = re.search(
        r"\s+(?:\d(?:\.\d+)?\s*\(\d[\d,]*\)|Location\b|Attendance\b|Global Ranking\b|Institution type\b|Bachelors?\b|Masters?\b|Scholarships?\b)",
        cleaned,
        re.I,
    )
    name = cleaned[: marker_match.start()].strip() if marker_match else cleaned.strip()
    return name or None


def _programme_count_from_text(text: str) -> int | None:
    """Return the public programme count shown on university cards.

    The requested command is a Bachelorsportal URL, but Studyportals may redirect
    the public university list to a Mastersportal page whose cards display
    "Masters N". Persist this count in the existing bachelor_count column as the
    public list's programme-count snapshot instead of dropping the field.
    """
    return _count_near_label(text, "Bachelor") or _count_near_label(text, "Master")


def _count_near_label(text: str, label: str) -> int | None:
    escaped = re.escape(label)
    before_label = rf"(\d[\d,]*|\d+(?:\.\d+)?[KkMm])\s+{escaped}s?\b"
    after_label = rf"{escaped}s?\s*:?\s*(\d[\d,]*|\d+(?:\.\d+)?[KkMm])\b"
    # Bachelorsportal cards commonly show either "125 Bachelors" or
    # "Bachelors 42". Scholarship counts are sometimes adjacent to bachelor
    # counts ("Bachelors 42 Scholarships 7"), so prefer the label-before form
    # for scholarships to avoid accidentally taking the bachelor value.
    patterns = [before_label, after_label] if label.lower().startswith("bachelor") else [after_label, before_label]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return normalize_count(match.group(1))
    return None


def _rating_from_text(text: str) -> Any:
    patterns = [
        r"(?:Rating|Rated)\s*:?\s*(\d(?:\.\d+)?)",
        r"(\d(?:\.\d+)?)\s*/\s*5",
        r"\b(\d\.\d)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return normalize_rating(match.group(1))
    return None


def _review_count_from_text(text: str) -> int | None:
    patterns = [
        r"reviews?\s*:?\s*(\d[\d,]*|\d+(?:\.\d+)?[KkMm])\b",
        r"(\d[\d,]*|\d+(?:\.\d+)?[KkMm])\s+reviews?\b",
        r"\d(?:\.\d+)?\s*\((\d[\d,]*|\d+(?:\.\d+)?[KkMm])\)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return normalize_count(match.group(1))
    return None


def _record_from_values(*, url: str, name: str | None, text: str, location: str | None) -> dict | None:
    source_id = source_id_from_url(url)
    clean_name = clean_text(name)
    if not url or not source_id or not clean_name:
        return None
    city, country = _location_parts(location)
    institution_type_match = re.search(r"\b(Private|Public)\s+(?:University|Institution)\b", text, re.I)
    return {
        "source_site": SOURCE_SITE,
        "source_university_id": source_id,
        "source_url": url,
        "name": clean_name,
        "country": country,
        "city": city,
        "location_text": location,
        "institution_type": institution_type_match.group(0) if institution_type_match else None,
        "bachelor_count": _programme_count_from_text(text),
        "scholarship_count": _count_near_label(text, "Scholarship"),
        "ranking_text": None,
        "rating": _rating_from_text(text),
        "review_count": _review_count_from_text(text),
        "description": None,
        "official_website_url": None,
        "is_featured": 1 if re.search(r"featured", text, re.I) else 0,
    }


def _records_from_json(value: Any, page_url: str) -> list[dict]:
    records: list[dict] = []
    if isinstance(value, dict):
        possible_url = value.get("url") or value.get("sameAs") or value.get("source_url")
        possible_name = value.get("name") or value.get("title")
        if possible_url and possible_name and "universit" in str(possible_url):
            url = _absolute(str(possible_url), page_url)
            location_value = value.get("address") or value.get("location")
            if isinstance(location_value, dict):
                locality = location_value.get("addressLocality") or location_value.get("city")
                country = location_value.get("addressCountry") or location_value.get("country")
                location = ", ".join(str(part) for part in [locality, country] if part)
            else:
                location = clean_text(str(location_value)) if location_value else None
            text = clean_text(json.dumps(value, ensure_ascii=False)) or ""
            record = _record_from_values(url=url, name=str(possible_name), text=text, location=location)
            if record:
                records.append(record)
        for item in value.values():
            records.extend(_records_from_json(item, page_url))
    elif isinstance(value, list):
        for item in value:
            records.extend(_records_from_json(item, page_url))
    return records


def _parse_structured_records(html: str, page_url: str) -> list[dict]:
    records: list[dict] = []
    for match in re.finditer(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", html, re.I | re.S):
        try:
            value = json.loads(html_lib.unescape(match.group(1)).strip())
        except json.JSONDecodeError:
            continue
        records.extend(_records_from_json(value, page_url))
    return records


def _parse_university_cards_regex(html: str, page_url: str) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()
    anchor_pattern = re.compile(r"<a\b(?P<attrs>[^>]*href=[\"'][^\"']*(?:/universities/|/university/)[^\"']*[\"'][^>]*)>(?P<body>.*?)</a>", re.I | re.S)
    for match in anchor_pattern.finditer(html):
        href_match = re.search(r"href=[\"']([^\"']+)[\"']", match.group("attrs"), re.I)
        if not href_match:
            continue
        url = _absolute(href_match.group(1), page_url)
        if not url or url in seen:
            continue
        # Prefer the nearest enclosing article/list item/card-like block so sibling
        # metadata from adjacent results does not leak into this record. Fall back
        # to a bounded surrounding window for very small/minimal fixtures.
        open_match = None
        for candidate in re.finditer(r"<(article|li|section|div)\b[^>]*(?:university|card|result)[^>]*>", html[:match.start()], re.I | re.S):
            open_match = candidate
        if open_match:
            close_match = re.search(rf"</{open_match.group(1)}>", html[match.end():], re.I)
            start = open_match.start()
            end = match.end() + close_match.end() if close_match else min(len(html), match.end() + 1800)
        else:
            start = max(0, match.start() - 1200)
            end = min(len(html), match.end() + 1800)
        card_html = html[start:end]
        text = clean_text(card_html) or ""
        name = _name_from_card_text(match.group("body"))
        location_match = re.search(r"(?:data-testid=[\"']location[\"'][^>]*>|class=[\"'][^\"']*location[^\"']*[\"'][^>]*>)(.*?)<", card_html, re.I | re.S)
        location = clean_text(location_match.group(1)) if location_match else _location_from_text(text)
        record = _record_from_values(url=url, name=name, text=text, location=location)
        if record:
            records.append(record)
            seen.add(url)
    return records


def _university_card_nodes(soup) -> list:
    """Return likely university result containers without depending on one CSS class."""
    selectors = [
        '[data-testid*="university" i]',
        '[data-testid*="search-result" i]',
        'article',
        'li',
        'div.SearchResultItem',
        'div[class*="SearchResult"]',
        'div[class*="University"]',
        'div[class*="Card"]',
        'div[class*="Result"]',
    ]
    nodes = list(soup.select(", ".join(selectors)))
    for link in soup.select('a[href*="/universities/"], a[href*="/university/"]'):
        parent = link.find_parent(["article", "li", "section", "div"])
        if parent is not None:
            nodes.append(parent)
    return nodes


def parse_university_cards(html: str, page_url: str) -> list[dict]:
    """Parse university search cards and require non-empty identity fields."""
    records = _parse_structured_records(html, page_url)
    seen = {record["source_url"] for record in records}

    if BeautifulSoup is None:
        for record in _parse_university_cards_regex(html, page_url):
            if record["source_url"] not in seen:
                records.append(record)
                seen.add(record["source_url"])
        return records

    soup = soupify(html)
    for node in _university_card_nodes(soup):
        try:
            link = node.select_one('a[href*="/universities/"], a[href*="/university/"]')
            if not link:
                continue
            url = _absolute(link.get("href"), page_url)
            if not url or url in seen:
                continue
            text = clean_text(node.get_text(" ")) or ""
            name = (
                _first_text(node, ["h2", "h3", '[data-testid*="name" i]', '[data-testid*="title" i]', '[class*="Title"]', '[class*="title"]'])
                or _name_from_card_text(link.get_text(" "))
            )
            location = (
                _first_text(node, ['[data-testid*="location" i]', '[class*="Location"]', '[class*="location"]'])
                or _location_from_text(text)
            )
            record = _record_from_values(url=url, name=name, text=text, location=location)
            if not record:
                logger.warning("Skipping university card with missing identity fields: url={}, name={}", url, name)
                continue
            record["institution_type"] = record["institution_type"] or _first_text(node, ['[data-testid*="institution" i]', '[class*="Institution"]'])
            record["ranking_text"] = _first_text(node, ['[data-testid*="ranking" i]', '[class*="Ranking"]'])
            record["description"] = _first_text(node, ["p", '[class*="Description"]', '[class*="description"]'])
            records.append(record)
            seen.add(url)
        except Exception as exc:
            logger.exception("Failed to parse one university card: {}", exc)
    return records


def parse_university_detail(html: str, source_url: str) -> dict:
    soup = soupify(html)
    title = _first_text(soup, ["h1", '[data-testid*="title"]'])
    body_text = clean_text(soup.get_text(" ")) or ""
    website = soup.select_one('a[href^="http"][rel*=nofollow], a[href*="website" i]')
    return {
        "university": {"name": title, "description": _first_text(soup, ["main p", "article p"]), "official_website_url": website.get("href") if website else None},
        "statistics": parse_statistics_text(body_text),
        "sections": parse_content_sections(soup, source_url),
    }


def parse_statistics_text(text: str) -> dict:
    def after(label: str):
        m = re.search(label + r"\s*:?\s*([\d,.Kk]+)", text, re.I)
        return normalize_count(m.group(1)) if m else None
    return {
        "ranking": (re.search(r"#?\d+[^.]{0,40}ranking", text, re.I).group(0) if re.search(r"#?\d+[^.]{0,40}ranking", text, re.I) else None),
        "academic_staff_count": after("academic staff"),
        "total_students": after("total students|students"),
        "international_students": after("international students"),
        "female_students": after("female students"),
        "institution_type": None,
        "bachelor_count": after("bachelors"),
        "scholarship_count": after("scholarships"),
    }


def parse_content_sections(soup, source_url: str) -> list[dict]:
    sections = []
    for heading in soup.find_all(["h2", "h3"]):
        title = clean_text(heading.get_text(" "))
        if not title:
            continue
        section_type = None
        low = title.lower()
        for key, mapped in SECTION_TYPES.items():
            if key in low:
                section_type = mapped
                break
        if not section_type:
            continue
        texts = []
        for sib in heading.find_next_siblings(limit=6):
            if sib.name in {"h2", "h3"}:
                break
            txt = clean_text(sib.get_text(" "))
            if txt:
                texts.append(txt)
        content = "\n".join(texts)[:10000] if texts else None
        sections.append({"section_type": section_type, "title": title, "content_summary": content[:1000] if content else None, "source_content": content, "source_url": source_url})
    return sections


def parse_programmes(html: str, page_url: str) -> list[dict]:
    soup = soupify(html)
    records = []
    for node in soup.select('article, li, div[class*="Programme"], div[class*="SearchResult"], div[class*="Card"]'):
        link = node.select_one('a[href*="/studies/"], a[href*="/programme/"]')
        if not link:
            continue
        url = _absolute(link.get("href"), page_url)
        text = clean_text(node.get_text(" ")) or ""
        duration_match = re.search(r"\d+\s*(?:years?|months?)", text, re.I)
        tuition_match = re.search(r"(?:£|€|\$|GBP|EUR|USD)\s*[\d,]+(?:\.\d+)?\s*(?:/|per)?\s*(?:year|month|semester)?", text, re.I)
        duration_raw = duration_match.group(0) if duration_match else None
        tuition_raw = tuition_match.group(0) if tuition_match else None
        duration = normalize_duration(duration_raw)
        tuition = normalize_tuition(tuition_raw)
        records.append({
            "source_programme_id": source_id_from_url(url), "source_url": url,
            "name": clean_text(link.get_text(" ")) or _first_text(node, ["h2", "h3"]),
            "degree_type": "Bachelor" if re.search(r"bachelor", text, re.I) else None,
            "discipline": None, "attendance_mode": "Full-time" if re.search(r"full[ -]?time", text, re.I) else None,
            "delivery_mode": "On Campus" if re.search(r"on campus", text, re.I) else None,
            "duration_value": duration["duration_value"], "duration_unit": duration["duration_unit"],
            "tuition_amount": tuition["amount"], "tuition_currency": tuition["currency"], "tuition_period": tuition["period"],
            "city": None, "country": None, "is_featured": 1 if re.search(r"featured", text, re.I) else 0,
            "tuition_text_raw": tuition_raw, "duration_text_raw": duration_raw,
        })
    return records
