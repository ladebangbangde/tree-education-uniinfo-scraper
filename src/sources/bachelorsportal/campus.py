from __future__ import annotations
import re
from bs4 import BeautifulSoup
from .parser import clean_text

def parse(html: str, source_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    locations = []
    for node in soup.find_all(string=re.compile("campus|location", re.I))[:20]:
        parent = node.find_parent(["article", "li", "section", "div"])
        text = clean_text(parent.get_text(" ") if parent else str(node))
        if text and len(text) > 5:
            locations.append({"campus_name": text[:255], "country": None, "city": None, "map_url": None, "address_text": text[:512]})
    return locations
