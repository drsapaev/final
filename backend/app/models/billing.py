"""
Модели для автоматического выставления счетов
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


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

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(50), unique=True, nullable=False, index=True)

    # Связи
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    visit_id = Column(Integer, ForeignKey("visits.id"))
    appointment_id = Column(Integer, ForeignKey("appointments.id"))

    # Основная информация
    invoice_type = Column(Enum(InvoiceType), default=InvoiceType.STANDARD)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.DRAFT)

    # Финансовая информация
    subtotal = Column(Float, nullable=False, default=0.0)  # Сумма без НДС
    tax_rate = Column(Float, default=0.0)  # Ставка НДС (%)
    tax_amount = Column(Float, default=0.0)  # Сумма НДС
    discount_amount = Column(Float, default=0.0)  # Размер скидки
    total_amount = Column(Float, nullable=False, default=0.0)  # Итоговая сумма
    paid_amount = Column(Float, default=0.0)  # Оплаченная сумма
    balance = Column(Float, default=0.0)  # Остаток к доплате

    # Даты
    issue_date = Column(DateTime, server_default=func.now())  # Дата выставления
    due_date = Column(DateTime)  # Срок оплаты
    paid_date = Column(DateTime)  # Дата оплаты

    # Дополнительная информация
    description = Column(Text)  # Описание
    notes = Column(Text)  # Примечания
    payment_terms = Column(String(255))  # Условия оплаты

    # Автоматизация
    is_auto_generated = Column(Boolean, default=False)  # Автоматически создан
    auto_send = Column(Boolean, default=False)  # Автоматически отправлять
    send_reminders = Column(Boolean, default=True)  # Отправлять напоминания

    # Периодические счета
    is_recurring = Column(Boolean, default=False)
    recurrence_type = Column(Enum(RecurrenceType))
    recurrence_interval = Column(Integer, default=1)  # Интервал повторения
    next_invoice_date = Column(DateTime)  # Дата следующего счета
    parent_invoice_id = Column(Integer, ForeignKey("invoices.id"))  # Родительский счет

    # Метаданные
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Связи
    patient = relationship("Patient")
    visit = relationship("Visit")
    appointment = relationship("Appointment")
    creator = relationship("User", foreign_keys=[created_by])
    parent_invoice = relationship("Invoice", remote_side=[id])
    child_invoices = relationship("Invoice", back_populates="parent_invoice")
    invoice_items = relationship(
        "InvoiceItem", back_populates="invoice", cascade="all, delete-orphan"
    )
    payments = relationship("BillingPayment", back_populates="invoice")
    # invoice_templates = relationship("InvoiceTemplate", back_populates="invoices")  # Временно отключено
    payment_reminders = relationship("PaymentReminder", back_populates="invoice")


class InvoiceItem(Base):
    """Позиции счета"""

    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)

    # Информация о позиции
    service_id = Column(Integer, ForeignKey("services.id"))
    description = Column(String(500), nullable=False)  # Описание услуги/товара
    quantity = Column(Float, nullable=False, default=1.0)  # Количество
    unit_price = Column(Float, nullable=False)  # Цена за единицу
    discount_rate = Column(Float, default=0.0)  # Процент скидки
    discount_amount = Column(Float, default=0.0)  # Сумма скидки
    tax_rate = Column(Float, default=0.0)  # Ставка НДС
    tax_amount = Column(Float, default=0.0)  # Сумма НДС
    total_amount = Column(Float, nullable=False)  # Итоговая сумма позиции

    # Дополнительная информация
    notes = Column(Text)  # Примечания к позиции
    sort_order = Column(Integer, default=0)  # Порядок сортировки

    # Связи
    invoice = relationship("Invoice", back_populates="invoice_items")
    service = relationship("Service")


class BillingPayment(Base):
    """Платежи (устаревшая модель - используйте Payment из app.models.payment)"""

    __tablename__ = "payments"
    __table_args__ = {'extend_existing': True}
    # ✅ ИСПРАВЛЕНО: Явно указываем только нужные поля для BillingPayment, чтобы избежать конфликта с Payment
    __mapper_args__ = {
        'include_properties': [
            'id',
            'payment_number',
            'invoice_id',
            'patient_id',
            'amount',
            'payment_method',
            'payment_date',
            'reference_number',
            'description',
            'notes',
            'is_confirmed',
            'confirmed_at',
            'confirmed_by',
            'created_at',
            'created_by',
        ]
    }

    id = Column(Integer, primary_key=True, index=True)
    payment_number = Column(String(50), unique=True, nullable=False, index=True)

    # Связи
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)

    # Информация о платеже
    amount = Column(Float, nullable=False)  # Сумма платежа
    payment_method = Column(Enum(PaymentMethod), nullable=False)
    payment_date = Column(DateTime, server_default=func.now())

    # Дополнительная информация
    reference_number = Column(String(100))  # Номер ссылки/транзакции
    description = Column(Text)  # Описание платежа
    notes = Column(Text)  # Примечания

    # Статус
    is_confirmed = Column(Boolean, default=False)  # Подтвержден
    confirmed_at = Column(DateTime)  # Дата подтверждения
    confirmed_by = Column(Integer, ForeignKey("users.id"))  # Кто подтвердил

    # Метаданные
    created_at = Column(DateTime, server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Связи
    invoice = relationship("Invoice", back_populates="payments")
    patient = relationship("Patient")
    creator = relationship("User", foreign_keys=[created_by])
    confirmer = relationship("User", foreign_keys=[confirmed_by])


class InvoiceTemplate(Base):
    """Шаблоны счетов"""

    __tablename__ = "invoice_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Настройки шаблона
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Шаблон
    template_content = Column(Text, nullable=False)  # HTML шаблон
    css_styles = Column(Text)  # CSS стили

    # Настройки автоматизации
    auto_generate_for_visits = Column(Boolean, default=False)
    auto_generate_for_appointments = Column(Boolean, default=False)
    auto_send_email = Column(Boolean, default=False)
    auto_send_sms = Column(Boolean, default=False)

    # Условия применения
    service_types = Column(String(500))  # Типы услуг (JSON)
    patient_categories = Column(String(500))  # Категории пациентов (JSON)
    amount_threshold_min = Column(Float)  # Минимальная сумма
    amount_threshold_max = Column(Float)  # Максимальная сумма

    # Метаданные
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Связи
    creator = relationship("User", foreign_keys=[created_by])
    # invoices = relationship("Invoice", back_populates="invoice_templates")  # Временно отключено
    billing_rules = relationship("BillingRule", back_populates="template")


class BillingRule(Base):
    """Правила выставления счетов"""

    __tablename__ = "billing_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)

    # Условия срабатывания
    trigger_event = Column(
        String(50), nullable=False
    )  # visit_completed, appointment_created, etc.
    service_types = Column(String(500))  # Типы услуг (JSON)
    patient_categories = Column(String(500))  # Категории пациентов (JSON)
    amount_threshold_min = Column(Float)  # Минимальная сумма
    amount_threshold_max = Column(Float)  # Максимальная сумма

    # Настройки счета
    invoice_type = Column(Enum(InvoiceType), default=InvoiceType.STANDARD)
    payment_terms_days = Column(Integer, default=30)  # Срок оплаты в днях
    auto_send = Column(Boolean, default=False)
    send_reminders = Column(Boolean, default=True)

    # Шаблон
    template_id = Column(Integer, ForeignKey("invoice_templates.id"))

    # Связи
    template = relationship("InvoiceTemplate", back_populates="billing_rules")

    # Приоритет
    priority = Column(Integer, default=0)  # Чем больше, тем выше приоритет

    # Метаданные
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id"))

    # Связи
    template = relationship("InvoiceTemplate", back_populates="billing_rules")
    creator = relationship("User", foreign_keys=[created_by])


class PaymentReminder(Base):
    """Напоминания об оплате"""

    __tablename__ = "payment_reminders"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)

    # Настройки напоминания
    reminder_type = Column(String(50), nullable=False)  # email, sms, call
    days_before_due = Column(Integer, default=0)  # За сколько дней до срока
    days_after_due = Column(Integer, default=0)  # Через сколько дней после срока

    # Содержимое
    subject = Column(String(255))  # Тема (для email)
    message = Column(Text, nullable=False)  # Текст сообщения

    # Статус
    is_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime)
    delivery_status = Column(String(50))  # delivered, failed, pending

    # Метаданные
    scheduled_at = Column(DateTime, nullable=False)  # Когда отправить
    created_at = Column(DateTime, server_default=func.now())

    # Связи
    invoice = relationship("Invoice", back_populates="payment_reminders")


class BillingSettings(Base):
    """Настройки биллинга"""

    __tablename__ = "billing_settings"

    id = Column(Integer, primary_key=True, index=True)

    # Общие настройки
    invoice_number_prefix = Column(String(10), default="INV")
    invoice_number_format = Column(String(50), default="{prefix}-{year}-{number:06d}")
    next_invoice_number = Column(Integer, default=1)

    # Налоги
    default_tax_rate = Column(Float, default=0.0)  # НДС по умолчанию
    tax_included_in_price = Column(Boolean, default=False)  # НДС включен в цену

    # Сроки оплаты
    default_payment_terms_days = Column(Integer, default=30)
    overdue_threshold_days = Column(
        Integer, default=7
    )  # Через сколько дней считать просроченным

    # Автоматизация
    auto_generate_invoices = Column(Boolean, default=True)
    auto_send_invoices = Column(Boolean, default=False)
    auto_send_reminders = Column(Boolean, default=True)

    # Напоминания
    reminder_days_before = Column(
        String(50), default="7,3,1"
    )  # За сколько дней напоминать
    reminder_days_after = Column(
        String(50), default="1,7,14,30"
    )  # Через сколько дней после просрочки

    # Валюта и формат
    currency_code = Column(String(3), default="UZS")
    currency_symbol = Column(String(5), default="сум")
    decimal_places = Column(Integer, default=0)

    # Компания
    company_name = Column(String(255))
    company_address = Column(Text)
    company_phone = Column(String(50))
    company_email = Column(String(100))
    company_website = Column(String(100))
    company_logo_url = Column(String(500))

    # Банковские реквизиты
    bank_name = Column(String(255))
    bank_account = Column(String(50))
    bank_routing = Column(String(50))

    # Метаданные
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    updated_by = Column(Integer, ForeignKey("users.id"))

    # Связи
    updater = relationship("User", foreign_keys=[updated_by])
