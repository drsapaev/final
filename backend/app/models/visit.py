from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")  # open|closed|canceled
    notes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    total_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    services: Mapped[list["VisitService"]] = relationship(
        back_populates="visit", cascade="all, delete-orphan"
    )


class VisitService(Base):
    __tablename__ = "visit_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int] = mapped_column(ForeignKey("visits.id", ondelete="CASCADE"), index=True)
    service_id: Mapped[int] = mapped_column(Integer, index=True)

    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    visit: Mapped[Visit] = relationship(back_populates="services")