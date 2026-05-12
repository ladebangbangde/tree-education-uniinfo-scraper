from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..db import Base

class UniversityReviewSummary(Base):
    __tablename__ = "university_review_summary"
    __table_args__ = (UniqueConstraint("university_id", name="uq_review_summary_university"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    university_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("university.id"))
    overall_rating: Mapped[float | None] = mapped_column(Numeric(3, 2))
    review_count: Mapped[int | None] = mapped_column(Integer)
    five_star_count: Mapped[int | None] = mapped_column(Integer)
    four_star_count: Mapped[int | None] = mapped_column(Integer)
    three_star_count: Mapped[int | None] = mapped_column(Integer)
    two_star_count: Mapped[int | None] = mapped_column(Integer)
    one_star_count: Mapped[int | None] = mapped_column(Integer)
    student_teacher_interaction: Mapped[float | None] = mapped_column(Numeric(3, 2))
    student_diversity: Mapped[float | None] = mapped_column(Numeric(3, 2))
    admission_process: Mapped[float | None] = mapped_column(Numeric(3, 2))
    quality_of_student_life: Mapped[float | None] = mapped_column(Numeric(3, 2))
    career_development: Mapped[float | None] = mapped_column(Numeric(3, 2))
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime)
