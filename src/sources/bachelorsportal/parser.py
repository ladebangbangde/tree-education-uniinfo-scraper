"""Robust BeautifulSoup parsers for public Bachelorsportal HTML.

Selectors intentionally use a layered strategy because public page markup can change:
semantic attributes/text first, common CSS/card selectors second, regex fallbacks last.
All functions tolerate missing fields and return partial dictionaries.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from ...logger import logger
from ...pipelines.normalize import normalize_count, normalize_rating, normalize_duration, normalize_tuition

BASE_URL = "https://www.bachelorsportal.com"
SOURCE_SITE = "bachelorsportal"
SECTION_TYPES = {
    "overview": "overview", "history": "history", "education": "education", "research": "research",
    "career": "career", "housing": "housing", "library": "library", "campus life": "campus_life",
    "accreditation": "accreditation",
}


def soupify(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def clean_text(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"\s+", " ", value).strip()
    return text or None


def source_id_from_url(url: str) -> str:
    parsed = urlparse(url)
    match = re.search(r"/(?:universities|university)/(?:[^/]+/)?(\d+)|-(\d+)(?:\.html)?$", parsed.path)
    if match:
        return next(group for group in match.groups() if group)
    slug = parsed.path.strip("/").split("/")[-1]
    return slug or url


def _first_text(node, selectors: list[str]) -> str | None:
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


def _location_from_text(text: str) -> str | None:
    """Best-effort location fallback for card text."""
    match = re.search(r"([A-Z][A-Za-z .'-]+),\s*(United Kingdom|England|Scotland|Wales|Northern Ireland)", text)
    if match:
        return f"{match.group(1)}, {match.group(2)}"
    if "United Kingdom" in text:
        return "United Kingdom"
    return None


def _university_card_nodes(soup: BeautifulSoup) -> list:
    """Return likely university result containers without depending on one CSS class."""
    selectors = [
        '[data-testid*="university" i]',
        'article',
        'li',
        'div.SearchResultItem',
        'div[class*="SearchResult"]',
        'div[class*="University"]',
        'div[class*="Card"]',
    ]
    nodes = list(soup.select(", ".join(selectors)))
    # Fallback: if the page uses only anchors inside a client-rendered list, use
    # each anchor's nearest useful parent as the parse container.
    for link in soup.select('a[href*="/universities/"], a[href*="/university/"]'):
        parent = link.find_parent(["article", "li", "section", "div"])
        if parent is not None:
            nodes.append(parent)
    return nodes


def parse_university_cards(html: str, page_url: str) -> list[dict]:
    soup = soupify(html)
    seen: set[str] = set()
    records: list[dict] = []
    for node in _university_card_nodes(soup):
        try:
            link = node.select_one('a[href*="/universities/"], a[href*="/university/"]')
            if not link:
                continue
            url = _absolute(link.get("href"), page_url)
            if not url or url in seen:
                continue
            seen.add(url)
            text = clean_text(node.get_text(" ")) or ""
            name = _first_text(node, ["h2", "h3", '[data-testid*="name" i]', "[class*=title]", "[class*=Title]"]) or clean_text(link.get_text(" "))
            location = _first_text(node, ['[data-testid*="location" i]', '[class*="Location"]', '[class*="location"]']) or _location_from_text(text)
            country = None
            city = None
            if location and "," in location:
                parts = [part.strip() for part in location.split(",") if part.strip()]
                city, country = parts[0], parts[-1]
            elif location:
                country = location
            bachelor_match = re.search(r"(\d[\d,]*|\d+(?:\.\d+)?K)\s+Bachelors?", text, re.I)
            scholarship_match = re.search(r"(\d[\d,]*|\d+(?:\.\d+)?K)\s+Scholarships?", text, re.I)
            rating_match = re.search(r"(?:rating|rated)?\s*(\d\.\d)", text, re.I)
            review_match = re.search(r"(\d[\d,]*|\d+(?:\.\d+)?K)\s+reviews?", text, re.I)
            institution_type_match = re.search(r"\b(Private|Public)\s+(?:University|Institution)\b", text, re.I)
            records.append({
                "source_site": SOURCE_SITE,
                "source_university_id": source_id_from_url(url),
                "source_url": url,
                "name": name,
                "country": country,
                "city": city,
                "location_text": location,
                "institution_type": _first_text(node, ['[data-testid*="institution" i]', '[class*="Institution"]']) or (institution_type_match.group(0) if institution_type_match else None),
                "bachelor_count": normalize_count(bachelor_match.group(1)) if bachelor_match else None,
                "scholarship_count": normalize_count(scholarship_match.group(1)) if scholarship_match else None,
                "ranking_text": _first_text(node, ['[data-testid*="ranking" i]', '[class*="Ranking"]']),
                "rating": normalize_rating(rating_match.group(1)) if rating_match else None,
                "review_count": normalize_count(review_match.group(1)) if review_match else None,
                "description": _first_text(node, ["p", '[class*="Description"]', '[class*="description"]']),
                "official_website_url": None,
                "is_featured": 1 if re.search(r"featured", text, re.I) else 0,
            })
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


def parse_content_sections(soup: BeautifulSoup, source_url: str) -> list[dict]:
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
        url = _absolute(link.get("href"))
        text = clean_text(node.get_text(" ")) or ""
        duration_raw = (re.search(r"\d+\s*(?:years?|months?)", text, re.I).group(0) if re.search(r"\d+\s*(?:years?|months?)", text, re.I) else None)
        tuition_raw = (re.search(r"(?:£|€|\$|GBP|EUR|USD)\s*[\d,]+(?:\.\d+)?\s*(?:/|per)?\s*(?:year|month|semester)?", text, re.I).group(0) if re.search(r"(?:£|€|\$|GBP|EUR|USD)\s*[\d,]+(?:\.\d+)?\s*(?:/|per)?\s*(?:year|month|semester)?", text, re.I) else None)
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
