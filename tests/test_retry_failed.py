from src.models import CrawlFailedTask
from src.tasks import retry_failed as retry_failed_module


def test_retry_failed_marks_success_and_dead(monkeypatch, capsys):
    tasks = [
        CrawlFailedTask(id=1, task_type="programme_detail", source_id=10, retry_count=0),
        CrawlFailedTask(id=2, task_type="university_programmes", source_id=20, retry_count=2),
    ]
    successes = []
    failures = []

    monkeypatch.setattr(retry_failed_module, "load_retryable_failed_tasks", lambda limit: tasks)
    monkeypatch.setattr(retry_failed_module, "crawl_programme_detail", lambda programme_id: True)

    def fail_programmes(university_id: int):
        raise TimeoutError("retry timeout")

    monkeypatch.setattr(retry_failed_module, "crawl_programmes", fail_programmes)
    monkeypatch.setattr(retry_failed_module, "mark_task_success", lambda task_id: successes.append(task_id))
    monkeypatch.setattr(retry_failed_module, "mark_task_retry_failed", lambda task_id, error: failures.append((task_id, type(error).__name__)))

    result = retry_failed_module.retry_failed(limit=10)

    assert result.total == 2
    assert result.success == 1
    assert result.failed == 1
    assert result.dead == 1
    assert successes == [1]
    assert failures == [(2, "TimeoutError")]
    assert "[retry-failed] summary:" in capsys.readouterr().out
