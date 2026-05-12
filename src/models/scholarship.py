from __future__ import annotations
from datetime import date, datetime
from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base

class Scholarship(Base):
    __tablename__ = "scholarship"
    __table_args__ = (UniqueConstraint("university_id", "name", "deadline_text", name="uq_scholarship"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    university_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("university.id"), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255))
    provider_type: Mapped[str | None] = mapped_column(String(128))
    provider_name: Mapped[str | None] = mapped_column(String(255))
    scholarship_type: Mapped[str | None] = mapped_column(String(128))
    amount_text: Mapped[str | None] = mapped_column(String(255))
    amount_value: Mapped[float | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(16))
    deadline_text: Mapped[str | None] = mapped_column(String(255))
    deadline_date: Mapped[date | None] = mapped_column(Date)
    location_text: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
