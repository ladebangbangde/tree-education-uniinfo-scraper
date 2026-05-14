from src.models import Programme, University
from src.tasks import crawl_all as crawl_all_module


def test_country_name_maps_slug_to_display_name():
    assert crawl_all_module._country_name("united-kingdom") == "United Kingdom"
    assert crawl_all_module._country_name("new-zealand") == "New Zealand"


def test_crawl_all_continues_after_university_and_programme_failures(monkeypatch, capsys):
    universities = [
        University(id=1, name="Ok University", source_url="https://example.test/u/1"),
        University(id=2, name="Fail University", source_url="https://example.test/u/2"),
    ]
    programmes = [
        Programme(id=10, name="Ok Programme", university_id=1, source_url="https://example.test/p/10"),
        Programme(id=20, name="Fail Programme", university_id=2, source_url="https://example.test/p/20"),
    ]
    recorded_failures = []

    monkeypatch.setattr(crawl_all_module, "polite_sleep", lambda: None)
    monkeypatch.setattr(crawl_all_module, "crawl_universities", lambda country, limit: 2)
    monkeypatch.setattr(crawl_all_module, "_load_universities", lambda country, limit: universities)
    monkeypatch.setattr(crawl_all_module, "_load_uncrawled_programmes", lambda country, limit: programmes)
    monkeypatch.setattr(crawl_all_module, "record_failed_task", lambda **kwargs: recorded_failures.append(kwargs))

    def fake_crawl_programmes(university_id: int, limit: int) -> int:
        if university_id == 2:
            raise RuntimeError("programme list boom")
        return 3

    def fake_crawl_programme_detail(programme_id: int, record_failure: bool = True) -> bool:
        return programme_id == 10

    monkeypatch.setattr(crawl_all_module, "crawl_programmes", fake_crawl_programmes)
    monkeypatch.setattr(crawl_all_module, "crawl_programme_detail", fake_crawl_programme_detail)

    result = crawl_all_module.crawl_all(
        country="united-kingdom",
        university_limit=10,
        programme_limit=20,
        detail_limit=100,
    )

    assert result.universities_total == 2
    assert result.universities_success == 1
    assert result.universities_failed == 1
    assert result.programmes_success == 3
    assert result.programmes_failed == 1
    assert result.details_success == 1
    assert result.details_failed == 1
    assert [failure["task_type"] for failure in recorded_failures] == ["university_programmes", "programme_detail"]

    output = capsys.readouterr().out
    assert "current university 1/2" in output
    assert "current programme 1/2" in output
    assert "success count=1, failed count=1" in output
    assert "[crawl-all] summary:" in output


def test_record_failed_task_deduplicates_active_failures(monkeypatch):
    from contextlib import contextmanager

    from sqlalchemy import create_engine, select, text
    from sqlalchemy.orm import sessionmaker

    from src.models import CrawlFailedTask
    from src.tasks import failed_tasks

    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE crawl_failed_task (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type VARCHAR(64) NOT NULL,
                source_id BIGINT NULL,
                source_name VARCHAR(255) NULL,
                source_url VARCHAR(1024) NULL,
                error_type VARCHAR(128) NULL,
                error_message TEXT NULL,
                retry_count INT DEFAULT 0,
                status VARCHAR(32) DEFAULT 'failed',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """))
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    @contextmanager
    def sqlite_session_scope():
        session = Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(failed_tasks, "session_scope", sqlite_session_scope)

    failed_tasks.record_failed_task(
        task_type="programme_detail",
        source_id=123,
        source_name="Original",
        source_url="https://example.test/programme/123",
        error_type="TimeoutError",
        error_message="first timeout",
    )
    failed_tasks.record_failed_task(
        task_type="programme_detail",
        source_id=123,
        source_name="Updated",
        source_url="https://example.test/programme/123",
        error_type="TimeoutError",
        error_message="second timeout",
    )

    with sqlite_session_scope() as session:
        rows = session.execute(select(CrawlFailedTask)).scalars().all()
        assert len(rows) == 1
        assert rows[0].source_name == "Updated"
        assert rows[0].error_message == "second timeout"
        assert rows[0].retry_count == 1
        assert rows[0].status == "failed"
