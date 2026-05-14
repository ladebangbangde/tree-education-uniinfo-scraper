from src.tasks.crawl_programme_detail import _print_facts_block_diagnostics


def test_facts_block_diagnostics_prints_keyword_contexts(capsys):
    html_text = "x" * 350 + "Apply date" + "y" * 350

    _print_facts_block_diagnostics(html_text)

    output = capsys.readouterr().out
    assert "[FACTS_DIAG] html_length=710" in output
    assert "[FACTS_DIAG] Tuition fee found=false" in output
    assert "[FACTS_DIAG] Apply date found=true" in output
    assert "[FACTS_DIAG] Apply date context=" in output
    assert "x" * 300 + "Apply date" + "y" * 300 in output
    assert "[FACTS_DIAG] facts block not present in fetched html" not in output


def test_facts_block_diagnostics_prints_absent_message(capsys):
    _print_facts_block_diagnostics("<html><body>No summary card</body></html>")

    output = capsys.readouterr().out
    assert "[FACTS_DIAG] html_length=41" in output
    assert "[FACTS_DIAG] Tuition fee found=false" in output
    assert "[FACTS_DIAG] Scholarships available found=false" in output
    assert "[FACTS_DIAG] facts block not present in fetched html" in output


def test_safe_programme_updates_supplements_city_from_raw_location_without_overwriting_country():
    from datetime import datetime

    from src.tasks.crawl_programme_detail import _safe_programme_updates

    updates = _safe_programme_updates(
        {
            "city": None,
            "country": "United Kingdom",
            "_raw_facts": {"location": "Glasgow, United Kingdom"},
        },
        source_hash="abc123",
        crawled_at=datetime(2026, 1, 1),
        existing_city=None,
        existing_country="United Kingdom",
    )

    assert updates["city"] == "Glasgow"
    assert "country" not in updates


def test_safe_programme_updates_does_not_overwrite_existing_city():
    from datetime import datetime

    from src.tasks.crawl_programme_detail import _safe_programme_updates

    updates = _safe_programme_updates(
        {
            "city": "Glasgow",
            "country": "United Kingdom",
            "_raw_facts": {"location": "Glasgow, United Kingdom"},
        },
        source_hash="abc123",
        crawled_at=datetime(2026, 1, 1),
        existing_city="Edinburgh",
        existing_country=None,
    )

    assert "city" not in updates
    assert updates["country"] == "United Kingdom"
