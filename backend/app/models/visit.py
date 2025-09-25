from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Date, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="open"
    )  # open|closed|canceled
    notes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    
    # ✅ ПОЛЯ ДЛЯ МАСТЕРА РЕГИСТРАЦИИ
    discount_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="none", index=True
    )  # none|repeat|benefit|all_free
    approval_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="none", index=True
    )  # none|pending|approved|rejected
    doctor_price_override: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    doctor_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("doctors.id"), nullable=True, index=True
    )
    visit_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    visit_time: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    # ✅ ПОЛЯ ДЛЯ ПОДТВЕРЖДЕНИЯ ВИЗИТОВ
    confirmation_token: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    confirmation_channel: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # phone|telegram|pwa
    confirmation_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # user_id, telegram_id, или phone

    services: Mapped[list["VisitService"]] = relationship(
        back_populates="visit", cascade="all, delete-orphan"
    )
    
    # Связь с изменениями цен врачами
    price_overrides: Mapped[list["DoctorPriceOverride"]] = relationship(
        "DoctorPriceOverride", back_populates="visit", cascade="all, delete-orphan"
    )
    
    # Связь с корзиной через промежуточную таблицу
    payment_invoice_visits: Mapped[list["PaymentInvoiceVisit"]] = relationship(
        back_populates="visit", cascade="all, delete-orphan"
    )
    
    # Связь с врачом
    doctor: Mapped[Optional["Doctor"]] = relationship(back_populates="visits")


class VisitService(Base):
    __tablename__ = "visit_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int] = mapped_column(
        ForeignKey("visits.id", ondelete="CASCADE"), index=True
    )
    service_id: Mapped[int] = mapped_column(Integer, index=True)
    code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    visit: Mapped[Visit] = relationship(back_populates="services")
