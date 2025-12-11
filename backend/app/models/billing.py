"""
Модели для автоматического выставления счетов и биллинга.

ВНИМАНИЕ: Устаревшая модель BillingPayment, конфликтовавшая с Payment из
`app.models.payment`, полностью удалена. Единственным источником истины
для таблицы `payments` является модель `Payment`.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.visit import Visit
    from app.models.appointment import Appointment
    from app.models.user import User
    from app.models.service import Service


class InvoiceStatus(str, enum.Enum):
    """Статусы счетов"""

    DRAFT = "draft"  # Черновик
    PENDING = "pending"  # Ожидает оплаты
    PAID = "paid"  # Оплачен
    PARTIALLY_PAID = "partially_paid"  # Частично оплачен
    OVERDUE = "overdue"  # Просрочен
    CANCELLED = "cancelled"  # Отменен
    REFUNDED = "refunded"  # Возвращен


class InvoiceType(str, enum.Enum):
    """Типы счетов"""

    STANDARD = "standard"  # Обычный счет
    RECURRING = "recurring"  # Периодический счет
    ADVANCE = "advance"  # Авансовый счет
    CORRECTION = "correction"  # Корректировочный счет


class PaymentMethod(str, enum.Enum):
    """Способы оплаты"""

    CASH = "cash"  # Наличные
    CARD = "card"  # Банковская карта
    BANK_TRANSFER = "bank_transfer"  # Банковский перевод
    ONLINE = "online"  # Онлайн платеж
    INSURANCE = "insurance"  # Страховка
    INSTALLMENT = "installment"  # Рассрочка


class RecurrenceType(str, enum.Enum):
    """Типы периодичности"""

    DAILY = "daily"  # Ежедневно
    WEEKLY = "weekly"  # Еженедельно
    MONTHLY = "monthly"  # Ежемесячно
    QUARTERLY = "quarterly"  # Ежеквартально
    YEARLY = "yearly"  # Ежегодно


class Invoice(Base):
    """Счета"""

    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    # Связи - SECURITY: RESTRICT prevents deletion of patient with unpaid invoices
    patient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("patients.id", ondelete="RESTRICT"), nullable=False
    )
    visit_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("visits.id", ondelete="SET NULL"), nullable=True
    )
    appointment_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("appointments.id", ondelete="SET NULL"), nullable=True
    )

    # Основная информация
    invoice_type: Mapped[InvoiceType] = mapped_column(
        Enum(InvoiceType), default=InvoiceType.STANDARD
    )
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus), default=InvoiceStatus.DRAFT
    )

    # Финансовая информация
    subtotal: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # Сумма без НДС
    tax_rate: Mapped[float] = mapped_column(Float, default=0.0)  # Ставка НДС (%)
    tax_amount: Mapped[float] = mapped_column(Float, default=0.0)  # Сумма НДС
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0)  # Размер скидки
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # Итоговая сумма
    paid_amount: Mapped[float] = mapped_column(Float, default=0.0)  # Оплаченная сумма
    balance: Mapped[float] = mapped_column(Float, default=0.0)  # Остаток к доплате

    # Даты
    issue_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now()
    )  # Дата выставления
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime)  # Срок оплаты
    paid_date: Mapped[Optional[datetime]] = mapped_column(DateTime)  # Дата оплаты

    # Дополнительная информация
    description: Mapped[Optional[str]] = mapped_column(Text)  # Описание
    notes: Mapped[Optional[str]] = mapped_column(Text)  # Примечания
    payment_terms: Mapped[Optional[str]] = mapped_column(String(255))  # Условия оплаты

    # Автоматизация
    is_auto_generated: Mapped[bool] = mapped_column(Boolean, default=False)  # Автоматически создан
    auto_send: Mapped[bool] = mapped_column(Boolean, default=False)  # Автоматически отправлять
    send_reminders: Mapped[bool] = mapped_column(Boolean, default=True)  # Отправлять напоминания

    # Периодические счета
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence_type: Mapped[Optional[RecurrenceType]] = mapped_column(Enum(RecurrenceType))
    recurrence_interval: Mapped[int] = mapped_column(Integer, default=1)  # Интервал повторения
    next_invoice_date: Mapped[Optional[datetime]] = mapped_column(DateTime)  # Дата следующего счета
    parent_invoice_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True
    )  # Родительский счет

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Связи (без прямой связи c payments: используйте Payment через Visit)
    patient: Mapped["Patient"] = relationship("Patient")
    visit: Mapped[Optional["Visit"]] = relationship("Visit")
    appointment: Mapped[Optional["Appointment"]] = relationship("Appointment")
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    parent_invoice: Mapped[Optional["Invoice"]] = relationship("Invoice", remote_side=[id])
    child_invoices: Mapped[List["Invoice"]] = relationship("Invoice", back_populates="parent_invoice")
    invoice_items: Mapped[List["InvoiceItem"]] = relationship(
        "InvoiceItem", back_populates="invoice", cascade="all, delete-orphan"
    )
    payment_reminders: Mapped[List["PaymentReminder"]] = relationship(
        "PaymentReminder", back_populates="invoice"
    )


class InvoiceItem(Base):
    """Позиции счета"""

    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    invoice_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )

    # Информация о позиции
    service_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("services.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)  # Описание услуги/товара
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)  # Количество
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)  # Цена за единицу
    discount_rate: Mapped[float] = mapped_column(Float, default=0.0)  # Процент скидки
    discount_amount: Mapped[float] = mapped_column(Float, default=0.0)  # Сумма скидки
    tax_rate: Mapped[float] = mapped_column(Float, default=0.0)  # Ставка НДС
    tax_amount: Mapped[float] = mapped_column(Float, default=0.0)  # Сумма НДС
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)  # Итоговая сумма позиции

    # Дополнительная информация
    notes: Mapped[Optional[str]] = mapped_column(Text)  # Примечания к позиции
    sort_order: Mapped[int] = mapped_column(Integer, default=0)  # Порядок сортировки

    # Связи
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="invoice_items")
    service: Mapped[Optional["Service"]] = relationship("Service")


class InvoiceTemplate(Base):
    """Шаблоны счетов"""

    __tablename__ = "invoice_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Настройки шаблона
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Шаблон
    template_content: Mapped[str] = mapped_column(Text, nullable=False)  # HTML шаблон
    css_styles: Mapped[Optional[str]] = mapped_column(Text)  # CSS стили

    # Настройки автоматизации
    auto_generate_for_visits: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_generate_for_appointments: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_send_email: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_send_sms: Mapped[bool] = mapped_column(Boolean, default=False)

    # Условия применения
    service_types: Mapped[Optional[str]] = mapped_column(String(500))  # Типы услуг (JSON)
    patient_categories: Mapped[Optional[str]] = mapped_column(String(500))  # Категории пациентов (JSON)
    amount_threshold_min: Mapped[Optional[float]] = mapped_column(Float)  # Минимальная сумма
    amount_threshold_max: Mapped[Optional[float]] = mapped_column(Float)  # Максимальная сумма

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Связи
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    billing_rules: Mapped[List["BillingRule"]] = relationship("BillingRule", back_populates="template")


class BillingRule(Base):
    """Правила выставления счетов"""

    __tablename__ = "billing_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Условия срабатывания
    trigger_event: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # visit_completed, appointment_created, etc.
    service_types: Mapped[Optional[str]] = mapped_column(String(500))  # Типы услуг (JSON)
    patient_categories: Mapped[Optional[str]] = mapped_column(String(500))  # Категории пациентов (JSON)
    amount_threshold_min: Mapped[Optional[float]] = mapped_column(Float)  # Минимальная сумма
    amount_threshold_max: Mapped[Optional[float]] = mapped_column(Float)  # Максимальная сумма

    # Настройки счета
    invoice_type: Mapped[InvoiceType] = mapped_column(
        Enum(InvoiceType), default=InvoiceType.STANDARD
    )
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30)  # Срок оплаты в днях
    auto_send: Mapped[bool] = mapped_column(Boolean, default=False)
    send_reminders: Mapped[bool] = mapped_column(Boolean, default=True)

    # Шаблон
    template_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("invoice_templates.id", ondelete="SET NULL"), nullable=True
    )

    # Связи
    template: Mapped[Optional["InvoiceTemplate"]] = relationship(
        "InvoiceTemplate", back_populates="billing_rules"
    )

    # Приоритет
    priority: Mapped[int] = mapped_column(Integer, default=0)  # Чем больше, тем выше приоритет

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Связи
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])


class PaymentReminder(Base):
    """Напоминания об оплате"""

    __tablename__ = "payment_reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    invoice_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )

    # Настройки напоминания
    reminder_type: Mapped[str] = mapped_column(String(50), nullable=False)  # email, sms, call
    days_before_due: Mapped[int] = mapped_column(Integer, default=0)  # За сколько дней до срока
    days_after_due: Mapped[int] = mapped_column(Integer, default=0)  # Через сколько дней после срока

    # Содержимое
    subject: Mapped[Optional[str]] = mapped_column(String(255))  # Тема (для email)
    message: Mapped[str] = mapped_column(Text, nullable=False)  # Текст сообщения

    # Статус
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    delivery_status: Mapped[Optional[str]] = mapped_column(String(50))  # delivered, failed, pending

    # Метаданные
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # Когда отправить
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    # Связи
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payment_reminders")


class BillingSettings(Base):
    """Настройки биллинга"""

    __tablename__ = "billing_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Общие настройки
    invoice_number_prefix: Mapped[str] = mapped_column(String(10), default="INV")
    invoice_number_format: Mapped[str] = mapped_column(
        String(50), default="{prefix}-{year}-{number:06d}"
    )
    next_invoice_number: Mapped[int] = mapped_column(Integer, default=1)

    # Налоги
    default_tax_rate: Mapped[float] = mapped_column(Float, default=0.0)  # НДС по умолчанию
    tax_included_in_price: Mapped[bool] = mapped_column(Boolean, default=False)  # НДС включен в цену

    # Сроки оплаты
    default_payment_terms_days: Mapped[int] = mapped_column(Integer, default=30)
    overdue_threshold_days: Mapped[int] = mapped_column(
        Integer, default=7
    )  # Через сколько дней считать просроченным

    # Автоматизация
    auto_generate_invoices: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_send_invoices: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_send_reminders: Mapped[bool] = mapped_column(Boolean, default=True)

    # Напоминания
    reminder_days_before: Mapped[str] = mapped_column(
        String(50), default="7,3,1"
    )  # За сколько дней напоминать
    reminder_days_after: Mapped[str] = mapped_column(
        String(50), default="1,7,14,30"
    )  # Через сколько дней после просрочки

    # Валюта и формат
    currency_code: Mapped[str] = mapped_column(String(3), default="UZS")
    currency_symbol: Mapped[str] = mapped_column(String(5), default="сум")
    decimal_places: Mapped[int] = mapped_column(Integer, default=0)

    # Компания
    company_name: Mapped[Optional[str]] = mapped_column(String(255))
    company_address: Mapped[Optional[str]] = mapped_column(Text)
    company_phone: Mapped[Optional[str]] = mapped_column(String(50))
    company_email: Mapped[Optional[str]] = mapped_column(String(100))
    company_website: Mapped[Optional[str]] = mapped_column(String(100))
    company_logo_url: Mapped[Optional[str]] = mapped_column(String(500))

    # Банковские реквизиты
    bank_name: Mapped[Optional[str]] = mapped_column(String(255))
    bank_account: Mapped[Optional[str]] = mapped_column(String(50))
    bank_routing: Mapped[Optional[str]] = mapped_column(String(50))

    # Метаданные
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Связи
    updater: Mapped[Optional["User"]] = relationship("User", foreign_keys=[updated_by])
