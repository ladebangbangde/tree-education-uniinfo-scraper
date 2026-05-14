"""Full crawl orchestration across universities, programmes, and details."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select

from ..crawler.rate_limit import polite_sleep
from ..db import session_scope
from ..logger import logger
from ..models import Programme, University
from ..sources.bachelorsportal.programme_list import build_programmes_url
from ..sources.bachelorsportal.university_list import build_university_search_url
from .crawl_programme_detail import CloudflareHardBlockError, crawl_programme_detail
from .crawl_programmes import crawl_programmes
from .crawl_universities import crawl_universities
from .failed_tasks import record_failed_task


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
    universities_total: int
    universities_success: int
    universities_failed: int
    programmes_success: int
    programmes_failed: int
    details_success: int
    details_failed: int
    universities_persisted: int = 0


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


def _programme_list_url(university: University) -> str | None:
    if not university.source_url:
        return None
    return build_programmes_url(university.source_url)


def _record_university_programmes_failure(university: University, exc: BaseException) -> None:
    record_failed_task(
        task_type="university_programmes",
        source_id=university.id,
        source_name=university.name,
        source_url=_programme_list_url(university),
        error=exc,
    )


def _record_programme_detail_failure(programme: Programme, exc: BaseException | None = None, message: str | None = None) -> None:
    record_failed_task(
        task_type="programme_detail",
        source_id=programme.id,
        source_name=programme.name,
        source_url=programme.source_url,
        error=exc,
        error_type=None if exc else "CrawlFailed",
        error_message=message,
    )


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
        try:
            universities_persisted = crawl_universities(country=country, limit=university_limit)
            print(f"[crawl-all] universities persisted={universities_persisted}")
        except Exception as exc:  # noqa: BLE001 - this step must not abort the full crawl.
            logger.exception("crawl-all university-list step failed: country={}, error={}", country, exc)
            record_failed_task(
                task_type="university_list",
                source_name=country,
                source_url=build_university_search_url(country=country),
                error=exc,
            )
            print(f"[crawl-all] university list failed: country={country}, error={exc}; continuing with existing rows")
        polite_sleep()

    universities = _load_universities(country=country, limit=university_limit)
    universities_total = len(universities)
    print(f"[crawl-all] loaded universities for country={_country_name(country)}: total={universities_total}")

    universities_success = 0
    universities_failed = 0
    programmes_success = 0
    programmes_failed = 0
    if skip_programmes:
        print("[crawl-all] skip-programmes enabled; not crawling programme lists")
    else:
        for index, university in enumerate(universities, start=1):
            print(
                f"[crawl-all] current university {index}/{universities_total}: "
                f"id={university.id}, name={university.name}"
            )
            try:
                count = crawl_programmes(university_id=university.id, limit=programme_limit)
                universities_success += 1
                programmes_success += count
                print(
                    f"[crawl-all] university success: id={university.id}, programmes_persisted={count}, "
                    f"success count={universities_success}, failed count={universities_failed}"
                )
            except Exception as exc:  # noqa: BLE001 - item failures must not abort the full crawl.
                universities_failed += 1
                programmes_failed += 1
                logger.exception(
                    "crawl-all programme-list step failed: university_id={}, university_name={}, error={}",
                    university.id,
                    university.name,
                    exc,
                )
                _record_university_programmes_failure(university, exc)
                print(
                    f"[crawl-all] university failed: id={university.id}, error={exc}, "
                    f"success count={universities_success}, failed count={universities_failed}"
                )
            polite_sleep()

    details_success = 0
    details_failed = 0
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
                success = crawl_programme_detail(programme_id=programme.id, record_failure=False)
                if success:
                    details_success += 1
                    print(
                        f"[crawl-all] programme detail success: id={programme.id}, "
                        f"success count={details_success}, failed count={details_failed}"
                    )
                else:
                    details_failed += 1
                    _record_programme_detail_failure(programme, message="Programme detail crawl returned False")
                    print(
                        f"[crawl-all] programme detail failed/skipped: id={programme.id}, "
                        f"success count={details_success}, failed count={details_failed}"
                    )
            except CloudflareHardBlockError as exc:
                details_failed += 1
                logger.error(
                    "crawl-all stopping because Cloudflare hard block was detected: programme_id={}, programme_name={}, error={}",
                    programme.id,
                    programme.name,
                    exc,
                )
                print(
                    f"[crawl-all] stopping due to Cloudflare hard block: id={programme.id}, error={exc}, "
                    f"success count={details_success}, failed count={details_failed}"
                )
                break
            except Exception as exc:  # noqa: BLE001 - item failures must not abort the full crawl.
                details_failed += 1
                logger.exception(
                    "crawl-all programme-detail step failed: programme_id={}, programme_name={}, error={}",
                    programme.id,
                    programme.name,
                    exc,
                )
                _record_programme_detail_failure(programme, exc=exc)
                print(
                    f"[crawl-all] programme detail failed: id={programme.id}, error={exc}, "
                    f"success count={details_success}, failed count={details_failed}"
                )
            polite_sleep()

    result = CrawlAllResult(
        universities_total=universities_total,
        universities_success=universities_success,
        universities_failed=universities_failed,
        programmes_success=programmes_success,
        programmes_failed=programmes_failed,
        details_success=details_success,
        details_failed=details_failed,
        universities_persisted=universities_persisted,
    )
    logger.info("Finished crawl-all: {}", result)
    print(
        "[crawl-all] summary: "
        f"universities_total={result.universities_total}, "
        f"universities_success={result.universities_success}, "
        f"universities_failed={result.universities_failed}, "
        f"programmes_success={result.programmes_success}, "
        f"programmes_failed={result.programmes_failed}, "
        f"details_success={result.details_success}, "
        f"details_failed={result.details_failed}"
    )
    return result
