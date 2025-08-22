from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class LabOrder(Base):
    __tablename__ = "lab_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("visits.id", ondelete="SET NULL"), nullable=True, index=True
    )
    patient_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ordered")  # ordered|in_progress|done|canceled
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class LabResult(Base):
    __tablename__ = "lab_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("lab_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )

    test_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    test_name: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    ref_range: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    abnormal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)