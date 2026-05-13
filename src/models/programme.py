from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..db import Base

class Programme(Base):
    __tablename__ = "programme"
    __table_args__ = (UniqueConstraint("university_id", "source_programme_id", name="uq_programme_source"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    university_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("university.id"))
    source_programme_id: Mapped[str | None] = mapped_column(String(128))
    source_url: Mapped[str | None] = mapped_column(String(1024))
    name: Mapped[str | None] = mapped_column(String(500))
    degree_type: Mapped[str | None] = mapped_column(String(128))
    discipline: Mapped[str | None] = mapped_column(String(255))
    attendance_mode: Mapped[str | None] = mapped_column(String(128))
    delivery_mode: Mapped[str | None] = mapped_column(String(128))
    duration_value: Mapped[int | None] = mapped_column(Integer)
    duration_unit: Mapped[str | None] = mapped_column(String(64))
    tuition_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    tuition_currency: Mapped[str | None] = mapped_column(String(16))
    tuition_period: Mapped[str | None] = mapped_column(String(64))
    city: Mapped[str | None] = mapped_column(String(128))
    country: Mapped[str | None] = mapped_column(String(128))
    is_featured: Mapped[int | None] = mapped_column(Integer)
    tuition_text_raw: Mapped[str | None] = mapped_column(String(255))
    scholarships_available: Mapped[int | None] = mapped_column(SmallInteger)
    apply_date_text: Mapped[str | None] = mapped_column(String(128))
    start_date_text: Mapped[str | None] = mapped_column(String(128))
    teaching_language: Mapped[str | None] = mapped_column(String(128))
    detail_crawled_at: Mapped[datetime | None] = mapped_column(DateTime)
    detail_source_hash: Mapped[str | None] = mapped_column(String(64))
    duration_text_raw: Mapped[str | None] = mapped_column(String(255))
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime)
    source_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    university = relationship("University", back_populates="programmes")
    detail = relationship("ProgrammeDetail", back_populates="programme", uselist=False, cascade="all, delete-orphan")
    intakes = relationship("ProgrammeIntake", back_populates="programme", cascade="all, delete-orphan")
    language_requirement = relationship("ProgrammeLanguageRequirement", back_populates="programme", uselist=False, cascade="all, delete-orphan")
    application_requirements = relationship("ProgrammeApplicationRequirement", back_populates="programme", cascade="all, delete-orphan")
