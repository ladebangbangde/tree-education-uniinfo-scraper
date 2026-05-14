from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from ..config import settings
from ..crawler.browser import BrowserClient
from ..crawler.html_snapshot import save_html_snapshot
from ..db import session_scope
from ..logger import logger
from ..models import Programme
from ..pipelines.persist import (
    upsert_application_requirement,
    upsert_language_requirement,
    upsert_programme_detail,
    upsert_programme_intake,
)
from ..sources.bachelorsportal.programme_detail import parse


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


FACT_PROGRAMME_FIELDS = (
    "tuition_amount",
    "tuition_currency",
    "tuition_period",
    "tuition_text_raw",
    "scholarships_available",
    "duration_value",
    "duration_unit",
    "duration_text_raw",
    "apply_date_text",
    "start_date_text",
    "city",
    "country",
    "teaching_language",
)


FACTS_DIAG_KEYWORDS = (
    "Tuition fee",
    "Duration",
    "Apply date",
    "Start date",
    "Campus location",
    "Taught in",
    "Scholarships available",
)


def _facts_diag_context(html_text: str, keyword: str, context_chars: int = 300) -> str:
    index = html_text.find(keyword)
    if index < 0:
        return ""
    start = max(0, index - context_chars)
    end = min(len(html_text), index + len(keyword) + context_chars)
    return html_text[start:end].replace("\r", "\\r").replace("\n", "\\n")


def _print_facts_block_diagnostics(html_text: str) -> None:
    print(f"[FACTS_DIAG] html_length={len(html_text)}")

    found_any = False
    for keyword in FACTS_DIAG_KEYWORDS:
        found = keyword in html_text
        found_any = found_any or found
        print(f"[FACTS_DIAG] {keyword} found={str(found).lower()}")
        if found:
            print(f"[FACTS_DIAG] {keyword} context={_facts_diag_context(html_text, keyword)}")

    if not found_any:
        print("[FACTS_DIAG] facts block not present in fetched html")


def _location_parts(location_text: str | None) -> tuple[str | None, str | None]:
    if not location_text:
        return None, None
    parts = [part.strip() for part in location_text.split(",") if part.strip()]
    if len(parts) >= 2:
        return parts[0], parts[-1]
    return None, None


def _safe_programme_updates(
    parsed: dict,
    source_hash: str,
    crawled_at: datetime,
    existing_city: str | None = None,
    existing_country: str | None = None,
) -> dict:
    # The top facts card is the authority for these detail facts. Persist NULL
    # for missing facts instead of preserving stale values from earlier crawls.
    data = {field: parsed.get(field) for field in FACT_PROGRAMME_FIELDS}

    raw_location = (parsed.get("_raw_facts") or {}).get("location")
    city_from_location, country_from_location = _location_parts(raw_location)
    if not data.get("city") and city_from_location:
        data["city"] = city_from_location
    if not data.get("country") and country_from_location:
        data["country"] = country_from_location

    # Location facts should supplement existing rows, not overwrite a value that
    # was already populated by the programme-list crawl or a previous detail run.
    if existing_city:
        data.pop("city", None)
    if existing_country:
        data.pop("country", None)

    data["detail_crawled_at"] = crawled_at
    data["detail_source_hash"] = source_hash
    return data


def crawl_programme_detail(programme_id: int) -> bool:
    with session_scope() as session:
        programme = session.execute(select(Programme).where(Programme.id == programme_id)).scalar_one_or_none()
        if not programme:
            raise ValueError(f"Programme {programme_id} not found")
        if not programme.source_url:
            raise ValueError(f"Programme {programme_id} is missing source_url")
        source_url = programme.source_url
        programme_name = programme.name

    try:
        with BrowserClient() as browser:
            result = browser.fetch(source_url)
        if result is None:
            logger.warning("Programme detail fetch disallowed by robots.txt: programme_id={}, source_url={}", programme_id, source_url)
            return False

        html_text = result.html or ""
        _print_facts_block_diagnostics(html_text)

        source_hash, path = save_html_snapshot(html_text, settings.source_site)
        logger.info("Saved programme detail snapshot {}", path)
        parsed = parse(html_text, result.final_url)
        parsed_facts = parsed.get("facts", {})
        if not parsed_facts:
            logger.warning(
                "Programme detail facts summary block was not parsed: programme_id={}, source_url={}, html_length={}",
                programme_id,
                source_url,
                len(result.html or ""),
            )
        logger.info("parsed_facts programme_id={} parsed_facts={}", programme_id, parsed["programme"])
        now = _now()

        with session_scope() as session:
            programme = session.execute(select(Programme).where(Programme.id == programme_id)).scalar_one()
            if programme.name and len(programme.name) > 500:
                logger.warning("Programme name exceeds 500 chars; not updating name: programme_id={}", programme_id)

            updates = _safe_programme_updates(
                parsed["programme"],
                source_hash,
                now,
                existing_city=programme.city,
                existing_country=programme.country,
            )
            for key, value in updates.items():
                if hasattr(programme, key):
                    setattr(programme, key, value)
            programme.updated_at = now
            session.add(programme)
            session.flush()

            detail = dict(parsed["detail"])
            detail.update({"programme_id": programme_id, "source_hash": source_hash, "last_crawled_at": now})
            upsert_programme_detail(session, detail)

            intake = dict(parsed["intake"])
            if intake.get("apply_date_text") or intake.get("start_date_text") or intake.get("intake_date_text"):
                intake["programme_id"] = programme_id
                upsert_programme_intake(session, intake)

            language = dict(parsed["language_requirement"])
            if language.get("teaching_language") or language.get("raw_text"):
                language["programme_id"] = programme_id
                upsert_language_requirement(session, language)

            for requirement in parsed.get("application_requirements", []):
                requirement["programme_id"] = programme_id
                upsert_application_requirement(session, requirement)

        programme_fields = parsed["programme"]
        tuition = (
            f"{programme_fields.get('tuition_amount')} {programme_fields.get('tuition_currency')}/"
            f"{programme_fields.get('tuition_period')}"
            if programme_fields.get("tuition_amount") is not None
            else None
        )
        duration = (
            f"{programme_fields.get('duration_value')} {programme_fields.get('duration_unit')}"
            if programme_fields.get("duration_value") is not None
            else None
        )
        location = ", ".join(
            part for part in [programme_fields.get("city"), programme_fields.get("country")] if part
        ) or None
        logger.info(
            "Parsed programme detail:\nprogramme_id={}\nprogramme_name={}\nsource_url={}\n"
            "tuition={}\nduration={}\napply_date={}\nstart_date={}\nlocation={}\n"
            "teaching_language={}\nscholarships_available={}\nsource_hash={}",
            programme_id,
            programme_name,
            source_url,
            tuition,
            duration,
            programme_fields.get("apply_date_text"),
            programme_fields.get("start_date_text"),
            location,
            programme_fields.get("teaching_language"),
            programme_fields.get("scholarships_available") == 1,
            source_hash,
        )
        return True
    except Exception as exc:
        logger.exception("Programme detail crawl failed: programme_id={}, source_url={}, error={}", programme_id, source_url, exc)
        return False
