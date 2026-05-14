from src.models import Programme
from src.tasks import crawl_missing_details as crawl_missing_details_module


def test_crawl_missing_details_continues_and_records_failures(monkeypatch, capsys):
    programmes = [
        Programme(id=1, name="Ok", university_id=10, source_url="https://example.test/p/1"),
        Programme(id=2, name="Skipped", university_id=10, source_url="https://example.test/p/2"),
        Programme(id=3, name="Boom", university_id=11, source_url="https://example.test/p/3"),
    ]
    failures = []

    monkeypatch.setattr(crawl_missing_details_module, "_load_missing_detail_programmes", lambda limit: programmes)
    monkeypatch.setattr(crawl_missing_details_module, "record_failed_task", lambda **kwargs: failures.append(kwargs))

    def fake_crawl_programme_detail(programme_id: int, record_failure: bool = True) -> bool:
        if programme_id == 3:
            raise TimeoutError("detail timeout")
        return programme_id == 1

    monkeypatch.setattr(crawl_missing_details_module, "crawl_programme_detail", fake_crawl_programme_detail)

    result = crawl_missing_details_module.crawl_missing_details(limit=100)

    assert result.total == 3
    assert result.success == 1
    assert result.failed == 2
    assert [failure["task_type"] for failure in failures] == ["programme_detail", "programme_detail"]
    assert failures[0]["source_id"] == 2
    assert failures[1]["source_id"] == 3
    assert "[crawl-missing-details] summary:" in capsys.readouterr().out
