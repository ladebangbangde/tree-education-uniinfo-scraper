"""Deduplication key builders used by persistence and tests."""
from __future__ import annotations


def university_key(item: dict) -> tuple:
    return item.get("source_site"), item.get("source_university_id")


def programme_key(item: dict) -> tuple:
    return item.get("university_id"), item.get("source_programme_id")


def ranking_key(item: dict) -> tuple:
    return item.get("university_id"), item.get("ranking_system"), item.get("year")


def scholarship_key(item: dict) -> tuple:
    return item.get("university_id"), item.get("name"), item.get("deadline_text")


def campus_key(item: dict) -> tuple:
    return item.get("university_id"), item.get("campus_name"), item.get("city")
