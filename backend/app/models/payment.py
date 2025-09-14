from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, Integer, Numeric, String, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

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
    provider: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)  # click|payme|kaspi
    provider_payment_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)  # ID у провайдера
    provider_transaction_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)  # ID транзакции
    payment_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # URL для оплаты
    
    # Дополнительные данные от провайдера
    provider_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Данные от провайдера
    commission: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True, default=0)  # Комиссия
    
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
    
    # Связи (временно отключены для отладки)
    # webhooks: Mapped[list["PaymentWebhook"]] = relationship(
    #     "PaymentWebhook", 
    #     back_populates="payment", 
    #     cascade="all, delete-orphan"
    # )
