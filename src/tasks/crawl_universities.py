"""Task orchestration for the P0 university-list crawl."""
from __future__ import annotations

from datetime import datetime, timezone
from ..config import settings
from ..crawler.browser import BrowserClient
from ..crawler.html_snapshot import save_html_snapshot
from ..db import session_scope
from ..logger import logger
from ..pipelines.persist import upsert_university
from ..sources.bachelorsportal.university_list import build_university_search_url, parse


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def crawl_universities(country: str = "united-kingdom", limit: int = 10) -> int:
    """Crawl one Bachelorsportal country university-list page and persist rows.

    A single malformed card or database row should not abort the whole batch;
    those failures are logged and the remaining parsed records continue.
    """
    url = build_university_search_url(country=country)
    logger.info("Starting crawl-universities: country={}, limit={}, url={}", country, limit, url)

    try:
        with BrowserClient() as browser:
            result = browser.fetch(url)
    except Exception as exc:
        logger.exception("Failed to fetch university list {}: {}", url, exc)
        raise

    if result is None:
        logger.warning("University list URL skipped by robots.txt: {}", url)
        return 0

    source_hash, path = save_html_snapshot(result.html, settings.source_site)
    logger.info("Saved university list snapshot: path={}, hash={}", path, source_hash)

    try:
        records = parse(result.html, result.final_url)[:limit]
    except Exception as exc:
        logger.exception("Failed to parse university list {}: {}", result.final_url, exc)
        raise

    now = _utc_now_naive()
    persisted_count = 0
    with session_scope() as session:
        for index, record in enumerate(records, start=1):
            try:
                record["source_hash"] = source_hash
                record["last_crawled_at"] = now
                upsert_university(session, record)
                session.commit()
                persisted_count += 1
            except Exception as exc:
                logger.exception(
                    "Failed to persist university card #{}/{} from {}: {}",
                    index,
                    len(records),
                    result.final_url,
                    exc,
                )
                session.rollback()

    logger.info(
        "Finished crawl-universities: parsed={}, persisted={}, country={}, source_hash={}",
        len(records),
        persisted_count,
        country,
        source_hash,
    )
    return persisted_count
