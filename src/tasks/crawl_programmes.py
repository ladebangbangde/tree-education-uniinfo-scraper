from __future__ import annotations
from datetime import datetime, timezone
from ..config import settings
from ..crawler.browser import BrowserClient
from ..crawler.html_snapshot import save_html_snapshot
from ..db import session_scope
from ..pipelines.persist import get_university, upsert_programme
from ..sources.bachelorsportal.programme_list import build_programmes_url, parse
from ..logger import logger


def crawl_programmes(university_id: int, limit: int = 20) -> int:
    with session_scope() as session:
        university = get_university(session, university_id)
        if not university or not university.source_url:
            raise ValueError(f"University {university_id} not found or missing source_url")
        url = build_programmes_url(university.source_url)
    with BrowserClient() as browser:
        result = browser.fetch(url)
    if result is None:
        return 0
    source_hash, path = save_html_snapshot(result.html, settings.source_site)
    logger.info(f"Saved snapshot {path}")
    records = parse(result.html, result.final_url)[:limit]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with session_scope() as session:
        for record in records:
            record["university_id"] = university_id
            record["source_hash"] = source_hash
            record["last_crawled_at"] = now
            upsert_programme(session, record)
    return len(records)
