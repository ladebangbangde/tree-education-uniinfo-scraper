"""Persistence helpers with SQLAlchemy upsert-like behavior."""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import (
    University, Programme, UniversityStatistics, UniversityContentSection,
    UniversityRanking, Scholarship, CampusLocation, UniversityReviewSummary,
    ProgrammeDetail, ProgrammeIntake, ProgrammeLanguageRequirement, ProgrammeApplicationRequirement,
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _apply(instance, data: dict, preserve_created: bool = True):
    now = _now()
    for key, value in data.items():
        if hasattr(instance, key):
            setattr(instance, key, value)
    if not preserve_created or getattr(instance, "created_at", None) is None:
        instance.created_at = now
    instance.updated_at = now
    if hasattr(instance, "last_crawled_at"):
        instance.last_crawled_at = data.get("last_crawled_at") or now
    return instance


def upsert_university(session: Session, data: dict) -> University:
    stmt = select(University).where(
        University.source_site == data.get("source_site"),
        University.source_university_id == data.get("source_university_id"),
    )
    instance = session.execute(stmt).scalar_one_or_none() or University()
    _apply(instance, data)
    session.add(instance)
    session.flush()
    return instance


def get_university(session: Session, university_id: int) -> University | None:
    return session.get(University, university_id)


def upsert_by_unique(session: Session, model, data: dict, unique_fields: list[str]):
    conditions = [getattr(model, field) == data.get(field) for field in unique_fields]
    instance = session.execute(select(model).where(*conditions)).scalar_one_or_none() or model()
    _apply(instance, data)
    session.add(instance)
    session.flush()
    return instance


def upsert_statistics(session: Session, data: dict):
    return upsert_by_unique(session, UniversityStatistics, data, ["university_id"])


def upsert_content_section(session: Session, data: dict):
    return upsert_by_unique(session, UniversityContentSection, data, ["university_id", "section_type"])


def upsert_programme(session: Session, data: dict):
    return upsert_by_unique(session, Programme, data, ["university_id", "source_programme_id"])


def upsert_ranking(session: Session, data: dict):
    return upsert_by_unique(session, UniversityRanking, data, ["university_id", "ranking_system", "year"])


def upsert_scholarship(session: Session, data: dict):
    return upsert_by_unique(session, Scholarship, data, ["university_id", "name", "deadline_text"])


def upsert_campus(session: Session, data: dict):
    return upsert_by_unique(session, CampusLocation, data, ["university_id", "campus_name", "city"])


def upsert_review_summary(session: Session, data: dict):
    return upsert_by_unique(session, UniversityReviewSummary, data, ["university_id"])


def upsert_programme_detail(session: Session, data: dict):
    return upsert_by_unique(session, ProgrammeDetail, data, ["programme_id"])


def upsert_programme_intake(session: Session, data: dict):
    return upsert_by_unique(session, ProgrammeIntake, data, ["programme_id", "apply_date_text", "start_date_text"])


def upsert_language_requirement(session: Session, data: dict):
    return upsert_by_unique(session, ProgrammeLanguageRequirement, data, ["programme_id"])


def upsert_application_requirement(session: Session, data: dict):
    return upsert_by_unique(session, ProgrammeApplicationRequirement, data, ["programme_id", "requirement_type", "title"])
