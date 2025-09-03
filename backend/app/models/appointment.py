from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    doctor_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    department: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    appointment_time: Mapped[Optional[str]] = mapped_column(
        String(8), nullable=True
    )  # HH:MM
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="scheduled")

    # Поля для интеграции с платежами
    payment_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    payment_currency: Mapped[Optional[str]] = mapped_column(
        String(3), nullable=True, default="UZS"
    )
    payment_provider: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    payment_transaction_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )
    payment_webhook_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payment_processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
