from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class PaymentInvoice(Base):
    """
    Счёт для корзины - единый платёж за несколько визитов
    """
    __tablename__ = "payment_invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Финансовая информация
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="UZS")

    # Способ и статус платежа
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )  # pending|processing|paid|failed|cancelled|refunded
    payment_method: Mapped[str] = mapped_column(
        String(32), nullable=False, default="cash"
    )  # cash|card|online|click|payme

    # Онлайн-платежи
    provider: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)  # click|payme
    provider_payment_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    provider_transaction_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    payment_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    
    # Дополнительные данные
    provider_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    commission: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True, default=0)
    notes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=datetime.utcnow
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Связи
    visits: Mapped[list["PaymentInvoiceVisit"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class PaymentInvoiceVisit(Base):
    """
    Связь между счётом и визитами (many-to-many с дополнительными данными)
    """
    __tablename__ = "payment_invoice_visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("payment_invoices.id", ondelete="CASCADE"), index=True
    )
    visit_id: Mapped[int] = mapped_column(
        ForeignKey("visits.id", ondelete="CASCADE"), index=True
    )
    visit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Связи
    invoice: Mapped[PaymentInvoice] = relationship(back_populates="visits")
    visit: Mapped["Visit"] = relationship()  # Forward reference для Visit
