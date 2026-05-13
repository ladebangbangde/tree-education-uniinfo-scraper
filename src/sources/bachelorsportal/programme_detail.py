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
FACT_KEYWORDS = [
    "Tuition fee",
    "Duration",
    "Apply date",
    "Start date",
    "Campus location",
    "Taught in",
    "Scholarships available",
]
ORDERED_FACT_LABELS = [
    ("tuition", "Tuition fee"),
    ("scholarship", "Scholarships available"),
    ("duration", "Duration"),
    ("apply_date", "Apply date"),
    ("start_date", "Start date"),
    ("location", "Campus location"),
    ("teaching_language", "Taught in"),
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


def _debug_fact_keywords(html: str, final_url: str | None = None) -> None:
    page_text = clean_text(html) or ""
    found_any = False
    for keyword in FACT_KEYWORDS:
        match = re.search(re.escape(keyword), page_text, re.I)
        if not match:
            continue
        found_any = True
        start = max(match.start() - 300, 0)
        end = min(match.end() + 300, len(page_text))
        logger.info(
            "Programme detail keyword context: keyword={!r}, context={!r}",
            keyword,
            page_text[start:end],
        )
    if not found_any:
        logger.warning(
            "Programme detail fact keywords not found in page text: final_url={}, html_length={}",
            final_url,
            len(html or ""),
        )


def _fact_keyword_count(text: str | None) -> int:
    lowered = (clean_text(text) or "").lower()
    return sum(1 for keyword in FACT_KEYWORDS if keyword.lower() in lowered)


def _is_ignored_text_parent(node) -> bool:
    parent = getattr(node, "parent", None)
    return bool(parent and getattr(parent, "name", "") in {"script", "style", "noscript"})


def _container_from_tuition_keyword(soup) -> Any | None:
    """Locate a likely facts card by finding the Tuition fee text then walking up."""
    candidates: list[Any] = []
    for text_node in soup.find_all(string=re.compile(r"\bTuition\s+fee\b", re.I)):
        if _is_ignored_text_parent(text_node):
            continue
        node = getattr(text_node, "parent", None)
        while node is not None and getattr(node, "name", None) not in {"html", "body"}:
            if getattr(node, "name", None) in {"section", "article", "aside", "div", "dl", "ul", "ol", "main"}:
                text = clean_text(node.get_text(" ")) or ""
                if _fact_keyword_count(text) >= 5:
                    candidates.append(node)
                    break
            node = getattr(node, "parent", None)
    if not candidates:
        return None
    candidates.sort(key=lambda candidate: len(clean_text(candidate.get_text(" ")) or ""))
    return candidates[0]


def _looks_like_facts_container(text: str) -> bool:
    lowered = text.lower()
    score = sum(1 for labels in FACT_LABELS.values() if any(label in lowered for label in labels))
    if re.search(r"\bscholarships?\s+available\b", lowered):
        score += 1
    return score >= 2


def _fact_containers(soup) -> list[Any]:
    keyword_container = _container_from_tuition_keyword(soup)
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
    if keyword_container is not None:
        containers.append(keyword_container)
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
    merged: dict[str, str | None] = {}
    for container in _fact_containers(soup):
        for key, value in _facts_from_container(container).items():
            merged.setdefault(key, value)
    return merged


def _ordered_facts_from_page_text(html: str) -> dict[str, str | None]:
    """Fallback parser for pages where facts render without useful DOM markers."""
    text = clean_text(html) or ""
    positions: list[tuple[int, str, str]] = []
    for key, label in ORDERED_FACT_LABELS:
        match = re.search(rf"\b{re.escape(label)}\b", text, re.I)
        if match:
            positions.append((match.start(), key, label))
    positions.sort(key=lambda item: item[0])
    keys_in_order = [key for _, key, _ in positions]
    required_sequence = ["tuition", "duration", "apply_date", "start_date", "location", "teaching_language"]
    if not all(key in keys_in_order for key in required_sequence):
        return {}

    facts: dict[str, str | None] = {}
    for index, (start, key, label) in enumerate(positions):
        value_start = start + len(label)
        value_end = positions[index + 1][0] if index + 1 < len(positions) else min(len(text), value_start + 120)
        value = clean_text(text[value_start:value_end].strip(" :-"))
        if key == "scholarship":
            facts.setdefault("scholarship", label)
        elif value:
            facts.setdefault(key, value)
    return facts


def parse_facts_summary(html: str, final_url: str | None = None) -> dict[str, Any]:
    """Parse programme top facts summary fields from a scoped facts-card DOM first."""
    _debug_fact_keywords(html, final_url=final_url)
    soup = soupify(html)
    facts = _first_fact_map(soup)
    if not facts:
        facts = _ordered_facts_from_page_text(html)
    tuition = parse_tuition_fact(facts.get("tuition"))
    duration = parse_duration_fact(facts.get("duration"))
    apply_date = parse_apply_date_fact(facts.get("apply_date"))
    start_date = parse_start_date_fact(facts.get("start_date"))
    location = parse_location_fact(facts.get("location"))
    teaching_language = parse_teaching_language_fact(facts.get("teaching_language"))
    scholarships_available = parse_scholarship_fact(facts.get("scholarship"))
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
    facts_summary = parse_facts_summary(html, final_url=page_url)
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
