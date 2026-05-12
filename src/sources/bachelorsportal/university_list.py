from __future__ import annotations
from urllib.parse import urlencode
from .parser import BASE_URL, parse_university_cards


def build_university_search_url(country: str | None = None, page: int = 1) -> str:
    params = {"page": page}
    if country:
        params["country"] = country
    return f"{BASE_URL}/search/universities/bachelor?{urlencode(params)}"


def parse(html: str, page_url: str) -> list[dict]:
    return parse_university_cards(html, page_url)
