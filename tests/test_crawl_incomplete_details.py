from src.models import Programme
from src.tasks import crawl_incomplete_details as crawl_incomplete_details_module


def test_crawl_incomplete_details_logs_and_continues(monkeypatch, capsys):
    programmes = [
        Programme(id=58, name="Accounting and Finance", source_url="https://example.test/p/58", detail_status="failed", detail_missing_fields="tuition,apply_date,start_date"),
        Programme(id=59, name="Broken", source_url="https://example.test/p/59", detail_status="incomplete", detail_missing_fields="teaching_language"),
    ]
    failures = []

    monkeypatch.setattr(crawl_incomplete_details_module, "_load_incomplete_detail_programmes", lambda limit: programmes)
    monkeypatch.setattr(crawl_incomplete_details_module, "_programme_status", lambda programme_id: "complete")
    monkeypatch.setattr(crawl_incomplete_details_module, "record_failed_task", lambda **kwargs: failures.append(kwargs))

    def fake_crawl_programme_detail(programme_id: int, record_failure: bool = True) -> bool:
        return programme_id == 58

    monkeypatch.setattr(crawl_incomplete_details_module, "crawl_programme_detail", fake_crawl_programme_detail)

    result = crawl_incomplete_details_module.crawl_incomplete_details(limit=100)

    assert result.total == 2
    assert result.success == 1
    assert result.failed == 1
    assert failures[0]["task_type"] == "programme_detail"
    assert failures[0]["source_id"] == 59

    output = capsys.readouterr().out
    assert "[crawl-incomplete-details] start limit=100" in output
    assert "[crawl-incomplete-details] found 2 programmes" in output
    assert "[crawl-incomplete-details] retry 1/2" in output
    assert "programme_id=58" in output
    assert "missing=tuition,apply_date,start_date" in output
    assert "[crawl-incomplete-details] summary" in output
