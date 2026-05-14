"""Retry orchestration for persisted failed crawl tasks."""
from __future__ import annotations

from dataclasses import dataclass

from ..logger import logger
from .crawl_programme_detail import crawl_programme_detail
from .crawl_programmes import crawl_programmes
from .crawl_universities import crawl_universities
from .failed_tasks import load_retryable_failed_tasks, mark_task_retry_failed, mark_task_success


@dataclass(frozen=True)
class RetryFailedResult:
    total: int
    success: int
    failed: int
    dead: int


def _retry_task(task) -> None:
    if task.task_type == "university_programmes":
        if task.source_id is None:
            raise ValueError(f"Failed task {task.id} is missing source_id")
        crawl_programmes(university_id=task.source_id)
        return

    if task.task_type == "programme_detail":
        if task.source_id is None:
            raise ValueError(f"Failed task {task.id} is missing source_id")
        success = crawl_programme_detail(programme_id=task.source_id)
        if not success:
            raise RuntimeError(f"Programme detail retry returned False for programme_id={task.source_id}")
        return

    if task.task_type == "university_list":
        country = task.source_name
        if not country:
            raise ValueError(f"Failed task {task.id} is missing source_name country")
        crawl_universities(country=country)
        return

    raise ValueError(f"Unsupported failed task type: {task.task_type}")


def retry_failed(limit: int) -> RetryFailedResult:
    tasks = load_retryable_failed_tasks(limit=limit)
    success_count = 0
    failed_count = 0
    dead_count = 0
    print(f"[retry-failed] loaded failed tasks: total={len(tasks)}, limit={limit}")

    for index, task in enumerate(tasks, start=1):
        print(
            f"[retry-failed] current task {index}/{len(tasks)}: "
            f"id={task.id}, task_type={task.task_type}, source_id={task.source_id}, retry_count={task.retry_count}"
        )
        try:
            _retry_task(task)
            mark_task_success(task.id)
            success_count += 1
            print(f"[retry-failed] task success: id={task.id}")
        except Exception as exc:  # noqa: BLE001 - one retry failure must not stop other tasks.
            logger.exception(
                "retry-failed task failed: id={}, task_type={}, source_id={}, error={}",
                task.id,
                task.task_type,
                task.source_id,
                exc,
            )
            mark_task_retry_failed(task.id, exc)
            failed_count += 1
            if (task.retry_count or 0) + 1 >= 3:
                dead_count += 1
            print(f"[retry-failed] task failed: id={task.id}, error={exc}")

    result = RetryFailedResult(total=len(tasks), success=success_count, failed=failed_count, dead=dead_count)
    print(
        "[retry-failed] summary: "
        f"total={result.total}, success={result.success}, failed={result.failed}, dead={result.dead}"
    )
    return result
