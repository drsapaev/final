from __future__ import annotations

from datetime import date, datetime, UTC

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class DermaProcedure(Base):
    __tablename__ = "derma_procedures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    visit_id: Mapped[int | None] = mapped_column(
        ForeignKey("visits.id", ondelete="SET NULL"), nullable=True, index=True
    )
    doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    procedure_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    procedure_type: Mapped[str] = mapped_column(Text, nullable=False)
    area_treated: Mapped[str | None] = mapped_column(Text, nullable=True)
    products_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    results: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
