from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..db import Base


class ProgrammeLanguageRequirement(Base):
    __tablename__ = "programme_language_requirement"
    __table_args__ = (UniqueConstraint("programme_id", name="uk_programme_language_programme_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    programme_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("programme.id", ondelete="CASCADE"), nullable=False)
    teaching_language: Mapped[str | None] = mapped_column(String(128))
    ielts_overall: Mapped[float | None] = mapped_column(Numeric(3, 1))
    ielts_listening: Mapped[float | None] = mapped_column(Numeric(3, 1))
    ielts_reading: Mapped[float | None] = mapped_column(Numeric(3, 1))
    ielts_writing: Mapped[float | None] = mapped_column(Numeric(3, 1))
    ielts_speaking: Mapped[float | None] = mapped_column(Numeric(3, 1))
    toefl_overall: Mapped[int | None] = mapped_column(Integer)
    pte_overall: Mapped[int | None] = mapped_column(Integer)
    raw_text: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=False)

    programme = relationship("Programme", back_populates="language_requirement")
