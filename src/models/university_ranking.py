from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base

class UniversityRanking(Base):
    __tablename__ = "university_ranking"
    __table_args__ = (UniqueConstraint("university_id", "ranking_system", "year", name="uq_ranking"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    university_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("university.id"))
    ranking_system: Mapped[str | None] = mapped_column(String(128))
    ranking_value: Mapped[str | None] = mapped_column(String(128))
    region_scope: Mapped[str | None] = mapped_column(String(128))
    year: Mapped[int | None] = mapped_column(Integer)
    trend_text: Mapped[str | None] = mapped_column(String(255))
    source_name: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
