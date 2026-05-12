"""Bachelorsportal bachelor university-list URL builder and parser facade."""
from __future__ import annotations

from urllib.parse import urlencode
from .parser import BASE_URL, parse_university_cards


def build_university_search_url(country: str | None = None, page: int = 1) -> str:
    """Build the public bachelor university search URL.

    Bachelorsportal country pages use a path segment, for example:
    `/search/universities/bachelor/united-kingdom`. Keep `page` as a query
    parameter so the first-page URL exactly matches the P0 requirement.
    """
    country_path = f"/{country.strip('/')}" if country else ""
    url = f"{BASE_URL}/search/universities/bachelor{country_path}"
    if page > 1:
        return f"{url}?{urlencode({'page': page})}"
    return url


def parse(html: str, page_url: str) -> list[dict]:
    """Parse university cards from a search result page."""
    return parse_university_cards(html, page_url)
