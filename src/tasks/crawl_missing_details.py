"""Crawl programme details only for rows that have not been detailed yet."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from ..db import session_scope
from ..logger import logger
from ..models import Programme
from .crawl_programme_detail import crawl_programme_detail
from .failed_tasks import record_failed_task


@dataclass(frozen=True)
class CrawlMissingDetailsResult:
    total: int
    success: int
    failed: int


def _load_missing_detail_programmes(limit: int) -> list[Programme]:
    with session_scope() as session:
        rows = session.execute(
            select(Programme)
            .where(Programme.detail_crawled_at.is_(None))
            .order_by(Programme.id.asc())
            .limit(limit)
        ).scalars().all()
        return [
            Programme(id=row.id, name=row.name, source_url=row.source_url, university_id=row.university_id)
            for row in rows
        ]


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


def crawl_missing_details(limit: int) -> CrawlMissingDetailsResult:
    programmes = _load_missing_detail_programmes(limit=limit)
    success_count = 0
    failed_count = 0
    print(f"[crawl-missing-details] loaded programmes missing detail: total={len(programmes)}, limit={limit}")

    for index, programme in enumerate(programmes, start=1):
        print(
            f"[crawl-missing-details] current programme {index}/{len(programmes)}: "
            f"id={programme.id}, university_id={programme.university_id}, name={programme.name}"
        )
        try:
            success = crawl_programme_detail(programme_id=programme.id)
            if success:
                success_count += 1
                print(
                    f"[crawl-missing-details] programme detail success: id={programme.id}, "
                    f"success count={success_count}, failed count={failed_count}"
                )
            else:
                failed_count += 1
                _record_programme_detail_failure(programme, message="Programme detail crawl returned False")
                print(
                    f"[crawl-missing-details] programme detail failed/skipped: id={programme.id}, "
                    f"success count={success_count}, failed count={failed_count}"
                )
        except Exception as exc:  # noqa: BLE001 - one failed programme must not stop the batch.
            failed_count += 1
            logger.exception(
                "crawl-missing-details programme-detail step failed: programme_id={}, programme_name={}, error={}",
                programme.id,
                programme.name,
                exc,
            )
            _record_programme_detail_failure(programme, exc=exc)
            print(
                f"[crawl-missing-details] programme detail failed: id={programme.id}, error={exc}, "
                f"success count={success_count}, failed count={failed_count}"
            )

    result = CrawlMissingDetailsResult(total=len(programmes), success=success_count, failed=failed_count)
    print(
        "[crawl-missing-details] summary: "
        f"total={result.total}, success={result.success}, failed={result.failed}"
    )
    return result
