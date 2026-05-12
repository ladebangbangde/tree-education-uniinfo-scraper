from __future__ import annotations
import re
from bs4 import BeautifulSoup
from .parser import clean_text
from ...pipelines.normalize import normalize_count, normalize_rating

def parse(html: str, source_url: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    text = clean_text(soup.get_text(" ")) or ""
    if "review" not in text.lower() and "rating" not in text.lower():
        return None
    rating = re.search(r"(\d\.\d)\s*(?:/\s*5)?", text)
    reviews = re.search(r"(\d[\d,]*|\d+(?:\.\d+)?K)\s+reviews?", text, re.I)
    return {"overall_rating": normalize_rating(rating.group(1)) if rating else None, "review_count": normalize_count(reviews.group(1)) if reviews else None, "five_star_count": None, "four_star_count": None, "three_star_count": None, "two_star_count": None, "one_star_count": None, "student_teacher_interaction": None, "student_diversity": None, "admission_process": None, "quality_of_student_life": None, "career_development": None}
