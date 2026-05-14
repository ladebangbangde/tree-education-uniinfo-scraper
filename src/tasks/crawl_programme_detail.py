from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

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
from .failed_tasks import record_failed_task


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


KEY_FIELD_LABELS = {
    "tuition_amount": "tuition",
    "duration_value": "duration",
    "apply_date_text": "apply_date",
    "start_date_text": "start_date",
    "city": "city",
    "country": "country",
    "teaching_language": "teaching_language",
}


FACTS_DIAG_KEYWORDS = (
    "Tuition fee",
    "Duration",
    "Apply date",
    "Start date",
    "Campus location",
    "Taught in",
    "Scholarships available",
)


INVALID_SNAPSHOT_KEYWORDS = (
    "Tuition fee",
    "Duration",
    "Apply date",
    "Start date",
    "Taught in",
)


INVALID_SNAPSHOT_MESSAGE = "QuickFacts missing or invalid snapshot"
CLOUDFLARE_HARD_BLOCK_MESSAGE = "Cloudflare hard block detected"


class CloudflareHardBlockError(RuntimeError):
    """Raised when Cloudflare returns a hard-block page."""


def is_cloudflare_block(html: str | None) -> bool:
    if not html:
        return False
    return any(
        marker in html
        for marker in (
            "Attention Required! | Cloudflare",
            "Sorry, you have been blocked",
            "Cloudflare Ray ID",
        )
    )


def _log_cloudflare_hard_block(programme_id: int, source_url: str | None) -> None:
    print("[cloudflare-hard-block]\nip_blocked=true\nstop_crawl=true")
    logger.error(
        "[cloudflare-hard-block] ip_blocked=true stop_crawl=true programme_id={} source_url={} cooldown_hours={}",
        programme_id,
        source_url,
        settings.cloudflare_block_cooldown_hours,
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


def _has_quick_facts(html_text: str) -> bool:
    return bool(re.search(r"QuickFacts?|QuickFactComponent|quickFact|quick-fact", html_text))


def _invalid_snapshot_reasons(html_text: str, facts: dict[str, Any]) -> list[str]:
    reasons = []
    if len(html_text) < 80_000:
        reasons.append("html_length_lt_80000")
    if not facts:
        reasons.append("facts_keys_empty")
    if not _has_quick_facts(html_text):
        reasons.append("quickfacts_missing")
    if not any(keyword in html_text for keyword in INVALID_SNAPSHOT_KEYWORDS):
        reasons.append("all_core_fact_labels_missing")
    return reasons


def _existing_values(programme: Programme) -> dict[str, Any]:
    return {field: getattr(programme, field, None) for field in FACT_PROGRAMME_FIELDS}


def _safe_programme_updates(
    parsed: dict,
    source_hash: str,
    crawled_at: datetime,
    existing_city: str | None = None,
    existing_country: str | None = None,
    existing_values: dict[str, Any] | None = None,
) -> dict:
    existing_values = dict(existing_values or {})
    if existing_city is not None:
        existing_values.setdefault("city", existing_city)
    if existing_country is not None:
        existing_values.setdefault("country", existing_country)

    parsed_values = dict(parsed)
    raw_location = (parsed.get("_raw_facts") or {}).get("location")
    city_from_location, country_from_location = _location_parts(raw_location)
    if not parsed_values.get("city") and city_from_location:
        parsed_values["city"] = city_from_location
    if not parsed_values.get("country") and country_from_location:
        parsed_values["country"] = country_from_location

    logger.info(
        "parsed_location_raw={} parsed_city={} parsed_country={}",
        raw_location,
        parsed_values.get("city"),
        parsed_values.get("country"),
    )

    data: dict[str, Any] = {}
    for field in FACT_PROGRAMME_FIELDS:
        value = parsed_values.get(field)
        if value is None:
            continue
        if field in {"city", "country"} and existing_values.get(field):
            continue
        data[field] = value

    data["detail_source_hash"] = source_hash
    return data


def _effective_detail_values(programme: Programme, updates: dict[str, Any]) -> dict[str, Any]:
    values = {field: getattr(programme, field, None) for field in KEY_FIELD_LABELS}
    for field in KEY_FIELD_LABELS:
        if field in updates and updates[field] is not None:
            values[field] = updates[field]
    return values


def _missing_key_fields(values: dict[str, Any]) -> list[str]:
    return [label for field, label in KEY_FIELD_LABELS.items() if values.get(field) in (None, "")]


def _record_detail_failure(
    *,
    programme_id: int,
    programme_name: str | None,
    source_url: str | None,
    error_type: str,
    error_message: str,
) -> None:
    record_failed_task(
        task_type="programme_detail",
        source_id=programme_id,
        source_name=programme_name,
        source_url=source_url,
        error_type=error_type,
        error_message=error_message,
    )


def _mark_programme_detail_failed(programme_id: int, error_message: str, source_hash: str | None = None) -> None:
    now = _now()
    with session_scope() as session:
        programme = session.execute(select(Programme).where(Programme.id == programme_id)).scalar_one_or_none()
        if not programme:
            return
        programme.detail_status = "failed"
        programme.detail_missing_fields = None
        programme.detail_error_message = error_message
        programme.detail_crawled_at = None
        if source_hash:
            programme.detail_source_hash = source_hash
        programme.updated_at = now
        session.add(programme)


def crawl_programme_detail(programme_id: int, *, record_failure: bool = True) -> bool:
    source_url: str | None = None
    programme_name: str | None = None
    try:
        with session_scope() as session:
            programme = session.execute(select(Programme).where(Programme.id == programme_id)).scalar_one_or_none()
            if not programme:
                raise ValueError(f"Programme {programme_id} not found")
            if not programme.source_url:
                raise ValueError(f"Programme {programme_id} is missing source_url")
            source_url = programme.source_url
            programme_name = programme.name

        with BrowserClient() as browser:
            result = browser.fetch(source_url)
        if result is None:
            error_message = "Programme detail fetch disallowed by robots.txt"
            logger.warning("{}: programme_id={}, source_url={}", error_message, programme_id, source_url)
            _mark_programme_detail_failed(programme_id, error_message)
            if record_failure:
                _record_detail_failure(
                    programme_id=programme_id,
                    programme_name=programme_name,
                    source_url=source_url,
                    error_type="RobotsDisallowed",
                    error_message=error_message,
                )
            return False

        html_text = result.html or ""
        if is_cloudflare_block(html_text):
            _log_cloudflare_hard_block(programme_id, source_url)
            _mark_programme_detail_failed(programme_id, CLOUDFLARE_HARD_BLOCK_MESSAGE)
            _record_detail_failure(
                programme_id=programme_id,
                programme_name=programme_name,
                source_url=source_url,
                error_type="CloudflareHardBlock",
                error_message=CLOUDFLARE_HARD_BLOCK_MESSAGE,
            )
            raise CloudflareHardBlockError(CLOUDFLARE_HARD_BLOCK_MESSAGE)

        _print_facts_block_diagnostics(html_text)

        source_hash, path = save_html_snapshot(html_text, settings.source_site)
        logger.info("Saved programme detail snapshot {}", path)
        parsed = parse(html_text, result.final_url)
        parsed_facts = parsed.get("facts", {}) or {}
        facts_keys = sorted(parsed_facts.keys())
        logger.info(
            "programme_detail_snapshot programme_id={} url={} final_url={} html_length={} facts_keys={} quickfacts_present={}",
            programme_id,
            source_url,
            result.final_url,
            len(html_text),
            facts_keys,
            _has_quick_facts(html_text),
        )
        if not parsed_facts:
            logger.warning(
                "Programme detail facts summary block was not parsed: programme_id={}, source_url={}, html_length={}",
                programme_id,
                source_url,
                len(html_text),
            )
        logger.info("parsed_facts programme_id={} parsed_facts={}", programme_id, parsed["programme"])

        invalid_reasons = _invalid_snapshot_reasons(html_text, parsed_facts)
        if invalid_reasons:
            error_message = INVALID_SNAPSHOT_MESSAGE
            logger.warning(
                "Programme detail invalid snapshot: programme_id={} reasons={} html_length={} facts_keys={}",
                programme_id,
                invalid_reasons,
                len(html_text),
                facts_keys,
            )
            _mark_programme_detail_failed(programme_id, error_message, source_hash=source_hash)
            if record_failure:
                _record_detail_failure(
                    programme_id=programme_id,
                    programme_name=programme_name,
                    source_url=source_url,
                    error_type="InvalidSnapshot",
                    error_message=error_message,
                )
            return False

        now = _now()
        with session_scope() as session:
            programme = session.execute(select(Programme).where(Programme.id == programme_id)).scalar_one()
            if programme.name and len(programme.name) > 500:
                logger.warning("Programme name exceeds 500 chars; not updating name: programme_id={}", programme_id)

            updates = _safe_programme_updates(
                parsed["programme"],
                source_hash,
                now,
                existing_values=_existing_values(programme),
            )
            effective_values = _effective_detail_values(programme, updates)
            missing_fields = _missing_key_fields(effective_values)
            detail_status = "complete" if not missing_fields else "incomplete"

            for key, value in updates.items():
                if hasattr(programme, key):
                    setattr(programme, key, value)
            programme.detail_status = detail_status
            programme.detail_missing_fields = ",".join(missing_fields) if missing_fields else None
            programme.detail_error_message = None
            programme.detail_crawled_at = now if detail_status == "complete" else None
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

        programme_fields = {**parsed["programme"], **effective_values}
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
            "teaching_language={}\nscholarships_available={}\ndetail_status={}\nmissing_fields={}\nsource_hash={}",
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
            detail_status,
            missing_fields,
            source_hash,
        )
        return detail_status == "complete"
    except CloudflareHardBlockError:
        raise
    except Exception as exc:
        logger.exception("Programme detail crawl failed: programme_id={}, source_url={}, error={}", programme_id, source_url, exc)
        _mark_programme_detail_failed(programme_id, str(exc))
        if record_failure:
            _record_detail_failure(
                programme_id=programme_id,
                programme_name=programme_name,
                source_url=source_url,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        return False
