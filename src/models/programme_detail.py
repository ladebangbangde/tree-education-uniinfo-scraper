from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..db import Base


class ProgrammeDetail(Base):
    __tablename__ = "programme_detail"
    __table_args__ = (UniqueConstraint("programme_id", name="uk_programme_detail_programme_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    programme_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("programme.id", ondelete="CASCADE"), nullable=False)
    overview: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    career_opportunities: Mapped[str | None] = mapped_column(Text)
    academic_requirements: Mapped[str | None] = mapped_column(Text)
    english_requirements: Mapped[str | None] = mapped_column(Text)
    other_requirements: Mapped[str | None] = mapped_column(Text)
    application_deadline_text: Mapped[str | None] = mapped_column(String(255))
    application_url: Mapped[str | None] = mapped_column(String(1024))
    official_programme_url: Mapped[str | None] = mapped_column(String(1024))
    source_url: Mapped[str | None] = mapped_column(String(1024))
    source_hash: Mapped[str | None] = mapped_column(String(64))
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=False)

    programme = relationship("Programme", back_populates="detail")
