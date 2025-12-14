from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class PaymentVisit(Base):
    """
    Связь между платежом и визитами.
    Позволяет одному платежу покрывать несколько визитов.
    """

    __tablename__ = "payment_visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    visit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("visits.id", ondelete="CASCADE"), nullable=False, index=True
    )  # ✅ FIX: Junction table requires both FKs to be NOT NULL for referential integrity
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=0,
        comment="Часть общей суммы платежа за этот конкретный визит",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    payment: Mapped["Payment"] = relationship(
        "Payment", back_populates="payment_visits"
    )
    visit: Mapped["Visit"] = relationship("Visit", foreign_keys=[visit_id])


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("visits.id", ondelete="RESTRICT"), 
        nullable=False, 
        index=True
    )  # ✅ SECURITY: RESTRICT to prevent visit deletion if payment exists (financial integrity)

    # Финансовая информация
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="UZS")

    # Способ и статус платежа
    method: Mapped[str] = mapped_column(
        String(32), nullable=False, default="cash"
    )  # cash|card|transfer|online|click|payme|kaspi
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="paid"
    )  # pending|processing|paid|failed|cancelled|refunded|void

    # Данные чека/квитанции
    receipt_no: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # Онлайн-платежи
    provider: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, index=True
    )  # click|payme|kaspi
    provider_payment_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True
    )  # ID у провайдера
    provider_transaction_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True
    )  # ID транзакции
    payment_url: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )  # URL для оплаты

    # Дополнительные данные от провайдера
    provider_data: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # Данные от провайдера
    commission: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True, default=0
    )  # Комиссия

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=datetime.utcnow
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    
    # Возврат средств
    refunded_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True, default=None,
        comment="Сумма возврата (может быть частичной)"
    )
    refund_reason: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True,
        comment="Причина возврата"
    )
    refunded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Дата и время возврата"
    )
    refunded_by: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="ID кассира, выполнившего возврат"
    )

    # Relationships
    payment_visits: Mapped[list["PaymentVisit"]] = relationship(
        "PaymentVisit",
        back_populates="payment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Связи (временно отключены для отладки)
    # webhooks: Mapped[list["PaymentWebhook"]] = relationship(
    #     "PaymentWebhook",
    #     back_populates="payment",
    #     cascade="all, delete-orphan"
    # )
