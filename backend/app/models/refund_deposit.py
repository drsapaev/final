"""
Модели для системы заявок на возврат и баланса депозитов
согласно ONLINE_QUEUE_SYSTEM_V2.md раздел 20.4
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    DateTime, Enum as SQLEnum, ForeignKey, Integer, 
    Numeric, String, Text, Boolean
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.payment import Payment
    from app.models.user import User
    from app.models.visit import Visit


class RefundRequestStatus(str, Enum):
    """Статусы заявок на возврат"""
    PENDING = "pending"          # Ожидает рассмотрения
    APPROVED = "approved"        # Одобрен
    REJECTED = "rejected"        # Отклонён
    PROCESSING = "processing"    # В обработке (деньги переводятся)
    COMPLETED = "completed"      # Завершён (деньги возвращены)
    CANCELLED = "cancelled"      # Отменён пациентом


class RefundType(str, Enum):
    """Тип возврата"""
    BANK_TRANSFER = "bank_transfer"  # Возврат на карту/счёт
    DEPOSIT = "deposit"              # На баланс депозита в клинике
    CASH = "cash"                    # Наличными в кассе


class DepositTransactionType(str, Enum):
    """Тип транзакции депозита"""
    CREDIT = "credit"    # Пополнение (начисление)
    DEBIT = "debit"      # Списание


class RefundRequest(Base):
    """
    Заявка на возврат средств
    
    Создаётся когда пациент отменяет визит онлайн (через Telegram/приложение)
    и хочет вернуть деньги.
    """
    __tablename__ = "refund_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Связь с пациентом и оплатой
    patient_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("patients.id", ondelete="RESTRICT"), 
        nullable=False, 
        index=True
    )  # Нельзя удалить пациента с активной заявкой
    payment_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("payments.id", ondelete="RESTRICT"), 
        nullable=False, 
        index=True
    )  # Нельзя удалить платёж с заявкой
    visit_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("visits.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )
    
    # Суммы
    original_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Оригинальная сумма платежа"
    )
    refund_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Сумма к возврату (может быть частичной)"
    )
    commission_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=0, nullable=False,
        comment="Комиссия за возврат (банковская и т.д.)"
    )
    
    # Тип возврата
    refund_type: Mapped[str] = mapped_column(
        String(20), default=RefundType.DEPOSIT.value, nullable=False
    )
    
    # Статус заявки
    status: Mapped[str] = mapped_column(
        String(20), default=RefundRequestStatus.PENDING.value, 
        nullable=False, index=True
    )
    
    # Причина возврата
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Ручной или автоматический возврат
    is_automatic: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="True если возврат автоматический (форс-мажор)"
    )
    
    # Данные для банковского перевода (если refund_type = bank_transfer)
    bank_card_number: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="Номер карты для возврата (маскированный)"
    )
    bank_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    card_holder_name: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )
    
    # Обработка заявки
    processed_by: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Примечания менеджера
    manager_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    
    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", foreign_keys=[patient_id])
    payment: Mapped["Payment"] = relationship("Payment", foreign_keys=[payment_id])
    visit: Mapped[Optional["Visit"]] = relationship("Visit", foreign_keys=[visit_id])
    processor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[processed_by])


class PatientDeposit(Base):
    """
    Баланс депозита пациента в клинике
    
    Используется для хранения возвратов на балансе клиники
    для оплаты будущих визитов.
    """
    __tablename__ = "patient_deposits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    patient_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("patients.id", ondelete="RESTRICT"), 
        nullable=False, 
        unique=True,  # Один депозит на пациента
        index=True
    )
    
    # Текущий баланс
    balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=0, nullable=False,
        comment="Текущий баланс депозита"
    )
    currency: Mapped[str] = mapped_column(
        String(8), default="UZS", nullable=False
    )
    
    # Лимиты
    max_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=10000000, nullable=False,
        comment="Максимальный баланс (по умолчанию 10 млн UZS)"
    )
    
    # Активность
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    
    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", foreign_keys=[patient_id])
    transactions: Mapped[list["DepositTransaction"]] = relationship(
        "DepositTransaction", back_populates="deposit", cascade="all, delete-orphan"
    )


class DepositTransaction(Base):
    """
    Транзакции депозита (пополнения и списания)
    """
    __tablename__ = "deposit_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    deposit_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("patient_deposits.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # Тип транзакции
    transaction_type: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # credit / debit
    
    # Сумма
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    
    # Баланс после транзакции
    balance_after: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    
    # Описание
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Связанные сущности
    refund_request_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("refund_requests.id", ondelete="SET NULL"), 
        nullable=True
    )
    payment_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("payments.id", ondelete="SET NULL"), 
        nullable=True
    )
    visit_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("visits.id", ondelete="SET NULL"), 
        nullable=True
    )
    
    # Кто выполнил (сотрудник клиники, если есть)
    performed_by: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    
    # Relationships
    deposit: Mapped["PatientDeposit"] = relationship(
        "PatientDeposit", back_populates="transactions"
    )
    refund_request: Mapped[Optional["RefundRequest"]] = relationship(
        "RefundRequest", foreign_keys=[refund_request_id]
    )
    payment: Mapped[Optional["Payment"]] = relationship(
        "Payment", foreign_keys=[payment_id]
    )
    visit: Mapped[Optional["Visit"]] = relationship(
        "Visit", foreign_keys=[visit_id]
    )
    performer: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[performed_by]
    )
