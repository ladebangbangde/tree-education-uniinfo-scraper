from __future__ import annotations
import re
from bs4 import BeautifulSoup
from .parser import clean_text
from ...pipelines.normalize import normalize_tuition

def parse(html: str, source_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for node in soup.find_all(string=re.compile("scholarship", re.I))[:20]:
        parent = node.find_parent(["article", "li", "section", "div"])
        text = clean_text(parent.get_text(" ") if parent else str(node))
        if not text:
            continue
        amount = normalize_tuition(text)
        results.append({"name": text[:255], "provider_type": None, "provider_name": None, "scholarship_type": None, "amount_text": text[:255], "amount_value": amount["amount"], "currency": amount["currency"], "deadline_text": None, "deadline_date": None, "location_text": None, "source_url": source_url})
    return results
