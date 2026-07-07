from __future__ import annotations

from datetime import date, datetime, UTC
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.clinic import Doctor
    from app.models.patient import Patient


class FinanceTransaction(Base):
    """Clinical finance ledger entry used by the admin finance panel."""

    __tablename__ = "finance_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    patient_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    doctor_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("doctors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    payment_method: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False
    )

    patient: Mapped[Patient | None] = relationship(
        "Patient", foreign_keys=[patient_id]
    )
    doctor: Mapped[Doctor | None] = relationship(
        "Doctor", foreign_keys=[doctor_id]
    )
