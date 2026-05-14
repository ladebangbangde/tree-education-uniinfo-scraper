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
        success = crawl_programme_detail(programme_id=task.source_id, record_failure=False)
        if not success:
            raise RuntimeError(f"Programme detail retry did not complete for programme_id={task.source_id}")
        return

    if task.task_type == "university_list":
        country = task.source_name
        if not country:
            raise ValueError(f"Failed task {task.id} is missing source_name country")
        crawl_universities(country=country)
        return

    raise ValueError(f"Unsupported failed task type: {task.task_type}")


def retry_failed(limit: int) -> RetryFailedResult:
    print(f"[retry-failed] start limit={limit}")
    tasks = load_retryable_failed_tasks(limit=limit)
    success_count = 0
    failed_count = 0
    dead_count = 0
    print(f"[retry-failed] found {len(tasks)} failed tasks")

    for index, task in enumerate(tasks, start=1):
        print(
            f"[retry-failed] retry {index}/{len(tasks)}\n"
            f"task_id={task.id}\n"
            f"task_type={task.task_type}\n"
            f"source_id={task.source_id}\n"
            f"source_name={task.source_name}\n"
            f"retry_count={task.retry_count}"
        )
        try:
            _retry_task(task)
            mark_task_success(task.id)
            success_count += 1
            print(f"[retry-failed] success\ntask_id={task.id}\nsource_id={task.source_id}")
        except Exception as exc:  # noqa: BLE001 - one retry failure must not stop other tasks.
            logger.exception(
                "retry-failed task failed: id={}, task_type={}, source_id={}, error={}",
                task.id,
                task.task_type,
                task.source_id,
                exc,
            )
            next_retry_count = (task.retry_count or 0) + 1
            mark_task_retry_failed(task.id, exc)
            if next_retry_count >= 3:
                dead_count += 1
                print(f"[retry-failed] dead\ntask_id={task.id}\nsource_id={task.source_id}\nretry_count={next_retry_count}")
            else:
                failed_count += 1
                print(
                    f"[retry-failed] failed\n"
                    f"task_id={task.id}\n"
                    f"source_id={task.source_id}\n"
                    f"retry_count={next_retry_count}\n"
                    f"error={exc}"
                )

    result = RetryFailedResult(total=len(tasks), success=success_count, failed=failed_count, dead=dead_count)
    print(
        "[retry-failed] summary\n"
        f"total={result.total}\n"
        f"success={result.success}\n"
        f"failed={result.failed}\n"
        f"dead={result.dead}"
    )
    return result
