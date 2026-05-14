"""Full crawl orchestration across universities, programmes, and details."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select

from ..crawler.rate_limit import polite_sleep
from ..db import session_scope
from ..logger import logger
from ..models import Programme, University
from .crawl_programme_detail import crawl_programme_detail
from .crawl_programmes import crawl_programmes
from .crawl_universities import crawl_universities


COUNTRY_SLUG_TO_NAME = {
    "united-kingdom": "United Kingdom",
    "united-states": "United States",
    "australia": "Australia",
    "germany": "Germany",
    "canada": "Canada",
    "netherlands": "Netherlands",
    "ireland": "Ireland",
    "france": "France",
}


@dataclass(frozen=True)
class CrawlAllResult:
    universities_persisted: int
    programme_success_count: int
    programme_failed_count: int
    detail_success_count: int
    detail_failed_count: int


def _country_name(country: str) -> str:
    normalized = country.strip().lower()
    return COUNTRY_SLUG_TO_NAME.get(normalized, country.strip().replace("-", " ").title())


def _country_filter(country: str):
    requested = country.strip()
    display_name = _country_name(requested)
    values = {requested.lower(), display_name.lower()}
    return or_(*(func.lower(University.country) == value for value in values))


def _load_universities(country: str, limit: int) -> list[University]:
    with session_scope() as session:
        rows = session.execute(
            select(University)
            .where(_country_filter(country))
            .order_by(University.id.asc())
            .limit(limit)
        ).scalars().all()
        return [
            University(id=row.id, name=row.name, country=row.country, source_url=row.source_url)
            for row in rows
        ]


def _load_uncrawled_programmes(country: str, limit: int) -> list[Programme]:
    with session_scope() as session:
        rows = session.execute(
            select(Programme)
            .join(University, Programme.university_id == University.id)
            .where(_country_filter(country), Programme.detail_crawled_at.is_(None))
            .order_by(Programme.id.asc())
            .limit(limit)
        ).scalars().all()
        return [
            Programme(id=row.id, name=row.name, university_id=row.university_id, source_url=row.source_url)
            for row in rows
        ]


def crawl_all(
    *,
    country: str,
    university_limit: int,
    programme_limit: int,
    detail_limit: int,
    skip_universities: bool = False,
    skip_programmes: bool = False,
    skip_details: bool = False,
) -> CrawlAllResult:
    """Run the complete crawl pipeline without allowing item failures to abort it."""
    logger.info(
        "Starting crawl-all: country={}, university_limit={}, programme_limit={}, detail_limit={}, "
        "skip_universities={}, skip_programmes={}, skip_details={}",
        country,
        university_limit,
        programme_limit,
        detail_limit,
        skip_universities,
        skip_programmes,
        skip_details,
    )

    universities_persisted = 0
    if skip_universities:
        print("[crawl-all] skip-universities enabled; using existing university rows")
    else:
        print(f"[crawl-all] crawling universities: country={country}, limit={university_limit}")
        universities_persisted = crawl_universities(country=country, limit=university_limit)
        print(f"[crawl-all] universities persisted={universities_persisted}")
        polite_sleep()

    universities = _load_universities(country=country, limit=university_limit)
    print(f"[crawl-all] loaded universities for country={_country_name(country)}: total={len(universities)}")

    programme_success_count = 0
    programme_failed_count = 0
    if skip_programmes:
        print("[crawl-all] skip-programmes enabled; not crawling programme lists")
    else:
        for index, university in enumerate(universities, start=1):
            print(
                f"[crawl-all] current university {index}/{len(universities)}: "
                f"id={university.id}, name={university.name}"
            )
            try:
                count = crawl_programmes(university_id=university.id, limit=programme_limit)
                programme_success_count += 1
                print(
                    f"[crawl-all] university success: id={university.id}, programmes_persisted={count}, "
                    f"success count={programme_success_count}, failed count={programme_failed_count}"
                )
            except Exception as exc:  # noqa: BLE001 - item failures must not abort the full crawl.
                programme_failed_count += 1
                logger.exception(
                    "crawl-all programme-list step failed: university_id={}, university_name={}, error={}",
                    university.id,
                    university.name,
                    exc,
                )
                print(
                    f"[crawl-all] university failed: id={university.id}, error={exc}, "
                    f"success count={programme_success_count}, failed count={programme_failed_count}"
                )
            polite_sleep()

    detail_success_count = 0
    detail_failed_count = 0
    if skip_details:
        print("[crawl-all] skip-details enabled; not crawling programme details")
    else:
        programmes = _load_uncrawled_programmes(country=country, limit=detail_limit)
        print(f"[crawl-all] loaded programmes needing detail: total={len(programmes)}")
        for index, programme in enumerate(programmes, start=1):
            print(
                f"[crawl-all] current programme {index}/{len(programmes)}: "
                f"id={programme.id}, university_id={programme.university_id}, name={programme.name}"
            )
            try:
                success = crawl_programme_detail(programme_id=programme.id)
                if success:
                    detail_success_count += 1
                    print(
                        f"[crawl-all] programme detail success: id={programme.id}, "
                        f"success count={detail_success_count}, failed count={detail_failed_count}"
                    )
                else:
                    detail_failed_count += 1
                    print(
                        f"[crawl-all] programme detail failed/skipped: id={programme.id}, "
                        f"success count={detail_success_count}, failed count={detail_failed_count}"
                    )
            except Exception as exc:  # noqa: BLE001 - item failures must not abort the full crawl.
                detail_failed_count += 1
                logger.exception(
                    "crawl-all programme-detail step failed: programme_id={}, programme_name={}, error={}",
                    programme.id,
                    programme.name,
                    exc,
                )
                print(
                    f"[crawl-all] programme detail failed: id={programme.id}, error={exc}, "
                    f"success count={detail_success_count}, failed count={detail_failed_count}"
                )
            polite_sleep()

    result = CrawlAllResult(
        universities_persisted=universities_persisted,
        programme_success_count=programme_success_count,
        programme_failed_count=programme_failed_count,
        detail_success_count=detail_success_count,
        detail_failed_count=detail_failed_count,
    )
    logger.info("Finished crawl-all: {}", result)
    print(
        "[crawl-all] finished: "
        f"universities_persisted={result.universities_persisted}, "
        f"programme success count={result.programme_success_count}, "
        f"programme failed count={result.programme_failed_count}, "
        f"detail success count={result.detail_success_count}, "
        f"detail failed count={result.detail_failed_count}"
    )
    return result
