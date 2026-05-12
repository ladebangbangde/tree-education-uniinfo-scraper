from __future__ import annotations

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from ..db import Base


class University(Base):
    __tablename__ = "university"
    __table_args__ = (UniqueConstraint("source_site", "source_university_id", name="uq_university_source"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_site: Mapped[str | None] = mapped_column(String(64))
    source_university_id: Mapped[str | None] = mapped_column(String(128))
    source_url: Mapped[str | None] = mapped_column(String(1024))
    name: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(128))
    city: Mapped[str | None] = mapped_column(String(128))
    location_text: Mapped[str | None] = mapped_column(String(255))
    institution_type: Mapped[str | None] = mapped_column(String(128))
    bachelor_count: Mapped[int | None] = mapped_column(Integer)
    scholarship_count: Mapped[int | None] = mapped_column(Integer)
    ranking_text: Mapped[str | None] = mapped_column(String(255))
    rating: Mapped[float | None] = mapped_column(Numeric(3, 2))
    review_count: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    official_website_url: Mapped[str | None] = mapped_column(String(1024))
    is_featured: Mapped[int | None] = mapped_column(Integer)
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime)
    source_hash: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    programmes = relationship("Programme", back_populates="university")
