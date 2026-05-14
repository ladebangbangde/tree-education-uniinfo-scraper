from src.models import Programme, University
from src.tasks import crawl_all as crawl_all_module


def test_country_name_maps_slug_to_display_name():
    assert crawl_all_module._country_name("united-kingdom") == "United Kingdom"
    assert crawl_all_module._country_name("new-zealand") == "New Zealand"


def test_crawl_all_continues_after_university_and_programme_failures(monkeypatch, capsys):
    universities = [University(id=1, name="Ok University"), University(id=2, name="Fail University")]
    programmes = [Programme(id=10, name="Ok Programme", university_id=1), Programme(id=20, name="Fail Programme", university_id=2)]

    monkeypatch.setattr(crawl_all_module, "polite_sleep", lambda: None)
    monkeypatch.setattr(crawl_all_module, "crawl_universities", lambda country, limit: 2)
    monkeypatch.setattr(crawl_all_module, "_load_universities", lambda country, limit: universities)
    monkeypatch.setattr(crawl_all_module, "_load_uncrawled_programmes", lambda country, limit: programmes)

    def fake_crawl_programmes(university_id: int, limit: int) -> int:
        if university_id == 2:
            raise RuntimeError("programme list boom")
        return 3

    def fake_crawl_programme_detail(programme_id: int) -> bool:
        return programme_id == 10

    monkeypatch.setattr(crawl_all_module, "crawl_programmes", fake_crawl_programmes)
    monkeypatch.setattr(crawl_all_module, "crawl_programme_detail", fake_crawl_programme_detail)

    result = crawl_all_module.crawl_all(
        country="united-kingdom",
        university_limit=10,
        programme_limit=20,
        detail_limit=100,
    )

    assert result.universities_persisted == 2
    assert result.programme_success_count == 1
    assert result.programme_failed_count == 1
    assert result.detail_success_count == 1
    assert result.detail_failed_count == 1

    output = capsys.readouterr().out
    assert "current university 1/2" in output
    assert "current programme 1/2" in output
    assert "success count=1, failed count=1" in output
