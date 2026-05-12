from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base

class UniversityStatistics(Base):
    __tablename__ = "university_statistics"
    __table_args__ = (UniqueConstraint("university_id", name="uq_statistics_university"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    university_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("university.id"))
    ranking: Mapped[str | None] = mapped_column(String(255))
    academic_staff_count: Mapped[int | None] = mapped_column(Integer)
    total_students: Mapped[int | None] = mapped_column(Integer)
    international_students: Mapped[int | None] = mapped_column(Integer)
    female_students: Mapped[int | None] = mapped_column(Integer)
    institution_type: Mapped[str | None] = mapped_column(String(128))
    bachelor_count: Mapped[int | None] = mapped_column(Integer)
    scholarship_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
