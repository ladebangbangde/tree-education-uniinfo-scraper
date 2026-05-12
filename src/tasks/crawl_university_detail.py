from __future__ import annotations
from datetime import datetime, timezone
from ..config import settings
from ..crawler.browser import BrowserClient
from ..crawler.html_snapshot import save_html_snapshot
from ..db import session_scope
from ..logger import logger
from ..pipelines.persist import get_university, upsert_campus, upsert_content_section, upsert_ranking, upsert_review_summary, upsert_scholarship, upsert_statistics, upsert_university
from ..sources.bachelorsportal import campus, ranking, review, scholarship, university_detail


def crawl_university_detail(university_id: int) -> None:
    with session_scope() as session:
        university = get_university(session, university_id)
        if not university or not university.source_url:
            raise ValueError(f"University {university_id} not found or missing source_url")
        url = university.source_url
    with BrowserClient() as browser:
        result = browser.fetch(url)
    if result is None:
        return
    source_hash, path = save_html_snapshot(result.html, settings.source_site)
    logger.info(f"Saved snapshot {path}")
    parsed = university_detail.parse(result.html, result.final_url)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with session_scope() as session:
        uni = get_university(session, university_id)
        update = {"source_site": uni.source_site, "source_university_id": uni.source_university_id, "source_url": uni.source_url, "source_hash": source_hash, "last_crawled_at": now}
        update.update({k: v for k, v in parsed.get("university", {}).items() if v is not None})
        upsert_university(session, update)
        stats = parsed.get("statistics") or {}
        if any(v is not None for v in stats.values()):
            stats["university_id"] = university_id
            upsert_statistics(session, stats)
        for section in parsed.get("sections", []):
            section["university_id"] = university_id
            upsert_content_section(session, section)
        for item in ranking.parse(result.html, result.final_url):
            item["university_id"] = university_id
            upsert_ranking(session, item)
        for item in scholarship.parse(result.html, result.final_url):
            item["university_id"] = university_id
            upsert_scholarship(session, item)
        for item in campus.parse(result.html, result.final_url):
            item["university_id"] = university_id
            upsert_campus(session, item)
        reviews = review.parse(result.html, result.final_url)
        if reviews:
            reviews["university_id"] = university_id
            upsert_review_summary(session, reviews)
