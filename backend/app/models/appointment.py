from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.department import Department


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )  # ✅ FIX: Appointments must always reference a patient (medical domain requirement)
    doctor_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("doctors.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )  # ✅ SECURITY: SET NULL to preserve appointment if doctor deleted
    department_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    appointment_time: Mapped[str | None] = mapped_column(
        String(8), nullable=True
    )  # HH:MM
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="scheduled")

    # Дополнительные поля для регистратуры
    visit_type: Mapped[str | None] = mapped_column(
        String(16), nullable=True, default="paid"
    )  # paid, repeat, free
    payment_type: Mapped[str | None] = mapped_column(
        String(16), nullable=True, default="cash"
    )  # cash, card, online
    services: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True
    )  # Список услуг в JSON

    # Поля для интеграции с платежами
    payment_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    payment_currency: Mapped[str | None] = mapped_column(
        String(3), nullable=True, default="UZS"
    )
    payment_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payment_transaction_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    payment_webhook_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    department: Mapped[Department] = relationship(back_populates="appointments")
