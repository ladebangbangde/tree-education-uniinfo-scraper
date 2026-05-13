from __future__ import annotations
from urllib.parse import urljoin
from .programme_parser import parse_programmes

def build_programmes_url(university_url: str) -> str:
    return urljoin(university_url.rstrip("/") + "/", "programmes")

def parse(html: str, page_url: str, university_name: str | None = None) -> list[dict]:
    return parse_programmes(html, page_url, university_name=university_name)
