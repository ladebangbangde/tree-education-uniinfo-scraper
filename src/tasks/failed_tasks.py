"""Persistence and retry helpers for failed crawl tasks."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from ..db import session_scope
from ..logger import logger
from ..models import CrawlFailedTask

FAILED_STATUS = "failed"
SUCCESS_STATUS = "success"
DEAD_STATUS = "dead"
MAX_RETRY_COUNT = 3


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _source_url_condition(source_url: str | None):
    if source_url is None:
        return CrawlFailedTask.source_url.is_(None)
    return CrawlFailedTask.source_url == source_url


def _find_failed_task(session, task_type: str, source_id: int | None, source_url: str | None) -> CrawlFailedTask | None:
    return session.execute(
        select(CrawlFailedTask).where(
            CrawlFailedTask.task_type == task_type,
            CrawlFailedTask.source_id == source_id,
            _source_url_condition(source_url),
            CrawlFailedTask.status == FAILED_STATUS,
        )
    ).scalar_one_or_none()


def _error_type(exc: BaseException | None, fallback: str | None = None) -> str | None:
    if exc is not None:
        return type(exc).__name__
    return fallback


def _error_message(exc: BaseException | None, fallback: str | None = None) -> str | None:
    if exc is not None:
        return str(exc)
    return fallback


def record_failed_task(
    *,
    task_type: str,
    source_id: int | None = None,
    source_name: str | None = None,
    source_url: str | None = None,
    error: BaseException | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    increment_retry: bool = True,
) -> CrawlFailedTask:
    """Insert or update a failed task without duplicating active failures."""
    now = _now()
    with session_scope() as session:
        task = _find_failed_task(session, task_type, source_id, source_url)
        if task is None:
            task = CrawlFailedTask(
                task_type=task_type,
                source_id=source_id,
                source_name=source_name,
                source_url=source_url,
                retry_count=0,
                status=FAILED_STATUS,
                created_at=now,
                updated_at=now,
            )
        elif increment_retry:
            task.retry_count = (task.retry_count or 0) + 1

        task.source_name = source_name
        task.source_url = source_url
        task.error_type = _error_type(error, error_type)
        task.error_message = _error_message(error, error_message)
        task.updated_at = now
        session.add(task)
        session.flush()
        task_id = task.id
        retry_count = task.retry_count

    logger.warning(
        "Recorded failed crawl task: id={}, task_type={}, source_id={}, status={}, retry_count={}",
        task_id,
        task_type,
        source_id,
        FAILED_STATUS,
        retry_count,
    )
    return CrawlFailedTask(
        id=task_id,
        task_type=task_type,
        source_id=source_id,
        source_name=source_name,
        source_url=source_url,
        error_type=_error_type(error, error_type),
        error_message=_error_message(error, error_message),
        retry_count=retry_count,
        status=FAILED_STATUS,
        created_at=now,
        updated_at=now,
    )


def load_retryable_failed_tasks(limit: int) -> list[CrawlFailedTask]:
    with session_scope() as session:
        rows = session.execute(
            select(CrawlFailedTask)
            .where(CrawlFailedTask.status == FAILED_STATUS, CrawlFailedTask.retry_count < MAX_RETRY_COUNT)
            .order_by(CrawlFailedTask.updated_at.asc(), CrawlFailedTask.id.asc())
            .limit(limit)
        ).scalars().all()
        return [
            CrawlFailedTask(
                id=row.id,
                task_type=row.task_type,
                source_id=row.source_id,
                source_name=row.source_name,
                source_url=row.source_url,
                error_type=row.error_type,
                error_message=row.error_message,
                retry_count=row.retry_count,
                status=row.status,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]


def mark_task_success(task_id: int) -> None:
    now = _now()
    with session_scope() as session:
        task = session.get(CrawlFailedTask, task_id)
        if task is None:
            return
        task.status = SUCCESS_STATUS
        task.updated_at = now
        session.add(task)


def mark_task_retry_failed(task_id: int, error: BaseException) -> None:
    now = _now()
    with session_scope() as session:
        task = session.get(CrawlFailedTask, task_id)
        if task is None:
            return
        task.retry_count = (task.retry_count or 0) + 1
        task.error_type = type(error).__name__
        task.error_message = str(error)
        task.status = DEAD_STATUS if task.retry_count >= MAX_RETRY_COUNT else FAILED_STATUS
        task.updated_at = now
        session.add(task)
