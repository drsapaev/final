# app/models/payment_webhook.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class PaymentWebhook(Base):
    __tablename__ = "payment_webhooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Основная информация
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # click, payme, kaspi
    webhook_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    transaction_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Статус обработки
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending, processed, failed, ignored

    # Финансовая информация
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # в тийинах/копейках
    currency: Mapped[str] = mapped_column(String(3), default="UZS", nullable=False)

    # Данные webhook
    raw_data: Mapped[dict] = mapped_column(
        JSON, nullable=False
    )  # сырые данные от провайдера
    signature: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )  # подпись для верификации

    # Результат обработки
    # payment_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # статус платежа после обработки

    # Связи
    # payment_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("payments.id"), nullable=True, index=True)
    visit_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    patient_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Связи (временно отключены для отладки)
    # payment: Mapped[Optional["Payment"]] = relationship("Payment", back_populates="webhooks")


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    __table_args__ = (
        # ✅ SECURITY: Composite unique constraint for idempotency
        # Prevents duplicate processing of same transaction_id from same provider
        UniqueConstraint("transaction_id", "provider", name="uq_payment_transactions_transaction_provider"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Основная информация
    transaction_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # Removed unique=True - now part of composite constraint
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Финансовая информация
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # в тийинах/копейках
    currency: Mapped[str] = mapped_column(String(3), default="UZS", nullable=False)
    commission: Mapped[int] = mapped_column(Integer, default=0)  # комиссия провайдера

    # Статус
    status: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False
    )  # pending, processing, completed, failed, cancelled, refunded

    # Связи
    payment_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("payments.id"), nullable=True, index=True
    )
    webhook_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("payment_webhooks.id"), nullable=True, index=True
    )
    visit_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # Дополнительные данные
    provider_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class PaymentProvider(Base):
    __tablename__ = "payment_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Основная информация
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True
    )  # "Click", "Payme", "Kaspi Pay"
    code: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )  # "click", "payme", "kaspi"

    # Конфигурация
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    webhook_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Настройки безопасности
    api_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    secret_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    merchant_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    service_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Финансовые настройки
    commission_percent: Mapped[int] = mapped_column(
        Integer, default=0
    )  # комиссия в процентах * 100
    min_amount: Mapped[int] = mapped_column(
        Integer, default=100
    )  # минимальная сумма в тийинах
    max_amount: Mapped[int] = mapped_column(
        Integer, default=100000000
    )  # максимальная сумма в тийинах

    # Поддерживаемые валюты
    supported_currencies: Mapped[Optional[str]] = mapped_column(
        String(100), default="UZS"
    )  # "UZS,KZT,USD"

    # Дополнительные настройки
    config: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # дополнительные настройки провайдера

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
