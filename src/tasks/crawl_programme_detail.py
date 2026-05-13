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


def _safe_programme_updates(parsed: dict, source_hash: str, crawled_at: datetime) -> dict:
    data = {key: value for key, value in parsed.items() if value is not None}
    # Detail-only scalar fields should reflect the latest visible detail page,
    # including NULL when a fact is absent. Older list-page fields are only
    # overwritten when the detail parser has a concrete value.
    for nullable_detail_field in (
        "scholarships_available",
        "apply_date_text",
        "start_date_text",
        "teaching_language",
    ):
        data[nullable_detail_field] = parsed.get(nullable_detail_field)
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

        source_hash, path = save_html_snapshot(result.html, settings.source_site)
        logger.info("Saved programme detail snapshot {}", path)
        parsed = parse(result.html, result.final_url)
        now = _now()

        with session_scope() as session:
            programme = session.execute(select(Programme).where(Programme.id == programme_id)).scalar_one()
            if programme.name and len(programme.name) > 500:
                logger.warning("Programme name exceeds 500 chars; not updating name: programme_id={}", programme_id)

            for key, value in _safe_programme_updates(parsed["programme"], source_hash, now).items():
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
