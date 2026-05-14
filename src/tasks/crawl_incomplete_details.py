"""Crawl programme details for pending, incomplete, or failed detail rows."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from ..db import session_scope
from ..logger import logger
from ..models import Programme
from .crawl_programme_detail import crawl_programme_detail
from .failed_tasks import record_failed_task

RETRYABLE_DETAIL_STATUSES = ("pending", "incomplete", "failed")


@dataclass(frozen=True)
class CrawlIncompleteDetailsResult:
    total: int
    success: int
    failed: int


def _load_incomplete_detail_programmes(limit: int) -> list[Programme]:
    with session_scope() as session:
        rows = session.execute(
            select(Programme)
            .where(Programme.detail_status.in_(RETRYABLE_DETAIL_STATUSES))
            .order_by(Programme.id.asc())
            .limit(limit)
        ).scalars().all()
        return [
            Programme(
                id=row.id,
                name=row.name,
                source_url=row.source_url,
                university_id=row.university_id,
                detail_status=row.detail_status,
                detail_missing_fields=row.detail_missing_fields,
            )
            for row in rows
        ]


def _programme_status(programme_id: int) -> str | None:
    with session_scope() as session:
        return session.execute(select(Programme.detail_status).where(Programme.id == programme_id)).scalar_one_or_none()


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


def crawl_incomplete_details(limit: int) -> CrawlIncompleteDetailsResult:
    print(f"[crawl-incomplete-details] start limit={limit}")
    programmes = _load_incomplete_detail_programmes(limit=limit)
    print(f"[crawl-incomplete-details] found {len(programmes)} programmes")
    success_count = 0
    failed_count = 0

    for index, programme in enumerate(programmes, start=1):
        print(
            f"[crawl-incomplete-details] retry {index}/{len(programmes)}\n"
            f"programme_id={programme.id}\n"
            f"name={programme.name}\n"
            f"status={programme.detail_status}\n"
            f"missing={programme.detail_missing_fields}"
        )
        try:
            success = crawl_programme_detail(programme_id=programme.id, record_failure=False)
            status = _programme_status(programme.id)
            if success:
                success_count += 1
                print(f"[crawl-incomplete-details] success\nprogramme_id={programme.id}\nstatus={status}")
            else:
                failed_count += 1
                error_message = "Programme detail crawl did not complete"
                _record_programme_detail_failure(programme, message=error_message)
                print(f"[crawl-incomplete-details] failed\nprogramme_id={programme.id}\nerror={error_message}")
        except Exception as exc:  # noqa: BLE001 - one failed programme must not stop the batch.
            failed_count += 1
            logger.exception(
                "crawl-incomplete-details programme-detail step failed: programme_id={}, programme_name={}, error={}",
                programme.id,
                programme.name,
                exc,
            )
            _record_programme_detail_failure(programme, exc=exc)
            print(f"[crawl-incomplete-details] failed\nprogramme_id={programme.id}\nerror={exc}")

    result = CrawlIncompleteDetailsResult(total=len(programmes), success=success_count, failed=failed_count)
    print(
        "[crawl-incomplete-details] summary\n"
        f"total={result.total}\n"
        f"success={result.success}\n"
        f"failed={result.failed}"
    )
    return result
