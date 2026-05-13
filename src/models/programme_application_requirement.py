from __future__ import annotations
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..db import Base


class ProgrammeApplicationRequirement(Base):
    __tablename__ = "programme_application_requirement"
    __table_args__ = (Index("idx_programme_requirement_programme_id", "programme_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    programme_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("programme.id", ondelete="CASCADE"), nullable=False)
    requirement_type: Mapped[str | None] = mapped_column(String(128))
    title: Mapped[str | None] = mapped_column(String(255))
    raw_text: Mapped[str | None] = mapped_column(Text)
    normalized_text: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=False)

    programme = relationship("Programme", back_populates="application_requirements")
