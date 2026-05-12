from __future__ import annotations
import re
from bs4 import BeautifulSoup
from .parser import clean_text

def parse(html: str, source_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rankings = []
    text = clean_text(soup.get_text(" ")) or ""
    for match in re.finditer(r"(QS|THE|Shanghai|ARWU|U\.S\. News)[^#\d]{0,40}(#?\d+[\-–]?\d*)[^\d]{0,20}(20\d{2})?", text, re.I):
        rankings.append({"ranking_system": match.group(1), "ranking_value": match.group(2), "region_scope": None, "year": int(match.group(3)) if match.group(3) else None, "trend_text": None, "source_name": match.group(1), "source_url": source_url})
    return rankings
