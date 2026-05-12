from __future__ import annotations
from datetime import datetime, timezone
from ..config import settings
from ..crawler.browser import BrowserClient
from ..crawler.html_snapshot import save_html_snapshot
from ..db import session_scope
from ..logger import logger
from ..pipelines.persist import upsert_university
from ..sources.bachelorsportal.university_list import build_university_search_url, parse


def crawl_universities(country: str = "united-kingdom", limit: int = 10) -> int:
    url = build_university_search_url(country=country)
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
            record["source_hash"] = source_hash
            record["last_crawled_at"] = now
            upsert_university(session, record)
    logger.info(f"Persisted {len(records)} universities")
    return len(records)
