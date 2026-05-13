from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..db import Base


class ProgrammeIntake(Base):
    __tablename__ = "programme_intake"
    __table_args__ = (UniqueConstraint("programme_id", "apply_date_text", "start_date_text", name="uk_programme_intake"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    programme_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("programme.id", ondelete="CASCADE"), nullable=False)
    intake_date_text: Mapped[str | None] = mapped_column(String(128))
    apply_date_text: Mapped[str | None] = mapped_column(String(128))
    start_date_text: Mapped[str | None] = mapped_column(String(128))
    intake_year: Mapped[int | None] = mapped_column(Integer)
    intake_month: Mapped[int | None] = mapped_column(Integer)
    source_url: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=False)

    programme = relationship("Programme", back_populates="intakes")
