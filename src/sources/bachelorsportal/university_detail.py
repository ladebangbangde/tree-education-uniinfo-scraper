from __future__ import annotations
from .parser import parse_university_detail

def parse(html: str, source_url: str) -> dict:
    return parse_university_detail(html, source_url)
