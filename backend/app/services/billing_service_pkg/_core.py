"""Core mixin for BillingService.

Split from billing_service.py.
"""
from __future__ import annotations

from app.services.billing_service_pkg._base import *  # noqa: F401, F403
from app.services.billing_service_pkg._base import BillingServiceMixinBase

class CoreMixin(BillingServiceMixinBase):
    """Core methods for BillingService."""

    def __init__(self, db: Session):
        self.db = db


    def _get_local_timestamp_naive(
        self, db: Session | None = None, timezone: str | None = None
    ) -> datetime:
        """Получить локальный timestamp без tzinfo для DateTime-колонок БД."""
        local_timestamp = queue_service.get_local_timestamp(
            db or self.db, timezone=timezone
        )
        if local_timestamp.tzinfo is None:
            return local_timestamp
        return local_timestamp.replace(tzinfo=None)

    @staticmethod


    def _normalize_datetime(value: datetime | None) -> datetime | None:
        """Снять tzinfo с datetime, если он есть, чтобы сравнения были однородными."""
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.replace(tzinfo=None)

    # === Создание счетов ===


    def _generate_invoice_number(self, settings: BillingSettings) -> str:
        """Сгенерировать номер счета"""
        year = self._get_local_timestamp_naive().year
        number = settings.next_invoice_number

        return settings.invoice_number_format.format(
            prefix=settings.invoice_number_prefix, year=year, number=number
        )


    def _generate_payment_number(self) -> str:
        """Сгенерировать номер платежа"""
        now = self._get_local_timestamp_naive()
        return f"PAY-{now.year}-{now.month:02d}-{now.day:02d}-{now.hour:02d}{now.minute:02d}{now.second:02d}"


    def _get_default_template(self) -> str:
        """Получить базовый шаблон счета"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Счет {{ invoice.invoice_number }}</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .header { text-align: center; margin-bottom: 30px; }
                .invoice-info { margin-bottom: 20px; }
                .table { width: 100%; border-collapse: collapse; }
                .table th, .table td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                .table th { background-color: #f2f2f2; }
                .total { text-align: right; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{{ company.name }}</h1>
                <p>{{ company.address }}</p>
                <p>Тел: {{ company.phone }}, Email: {{ company.email }}</p>
            </div>

            <div class="invoice-info">
                <h2>Счет № {{ invoice.invoice_number }}</h2>
                <p>Дата: {{ invoice.issue_date.strftime('%d.%m.%Y') }}</p>
                <p>Срок оплаты: {{ invoice.due_date.strftime('%d.%m.%Y') }}</p>
                <p>Пациент: {{ patient.full_name }}</p>
            </div>

            <table class="table">
                <thead>
                    <tr>
                        <th>Услуга</th>
                        <th>Количество</th>
                        <th>Цена</th>
                        <th>Сумма</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in items %}
                    <tr>
                        <td>{{ item.description }}</td>
                        <td>{{ item.quantity }}</td>
                        <td>{{ item.unit_price }} {{ settings.currency_symbol }}</td>
                        <td>{{ item.total_amount }} {{ settings.currency_symbol }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

            <div class="total">
                <p>Итого: {{ invoice.total_amount }} {{ settings.currency_symbol }}</p>
                <p>{{ total_in_words }}</p>
            </div>
        </body>
        </html>
        """


# ===== Хелперы для работы с visit и appointment (SSOT) =====


def get_discount_mode_for_visit(db: Session, visit: Visit) -> str:
    """
    Получить registration discount_mode для визита (SSOT helper function).

    Args:
        db: Database session
        visit: Объект Visit

    Returns:
        discount_mode: none|repeat|benefit|all_free
    """
    billing_service = BillingService(db)
    return billing_service.get_discount_mode_for_visit(visit)


def is_appointment_paid(db: Session, appointment) -> bool:
    """
    Проверить, оплачен ли appointment (SSOT helper function).

    Args:
        db: Database session
        appointment: Объект Appointment

    Returns:
        True если appointment оплачен, False если нет
    """
    # Проверяем payment_processed_at
    if getattr(appointment, 'payment_processed_at', None):
        return True

    # [FIX:BILLING_PAYMENT_STATUS] visit_type='paid' means a paid service type, not completed payment.
    visit_type = getattr(appointment, 'visit_type', None) or ''
    if visit_type.lower() == 'paid':
        logger.debug(
            "[FIX:BILLING_PAYMENT_STATUS] Ignoring appointment.visit_type='paid' as payment proof: appointment_id=%s",
            getattr(appointment, 'id', None),
        )

    # Проверяем явный payment_status, если он есть в будущих/адаптерных моделях.
    explicit_payment_status = getattr(appointment, 'payment_status', None) or ''
    if str(explicit_payment_status).lower() == 'paid':
        return True

    # Проверяем наличие платежей
    from app.models.payment import Payment

    payment = (
        db.query(Payment)
        .filter(Payment.appointment_id == appointment.id)
        .order_by(Payment.created_at.desc())
        .first()
    )

    if payment:
        payment_status = str(payment.status).lower() if payment.status else ''
        if payment_status == 'paid' or payment.paid_at:
            return True

    return False


def update_appointment_payment_status(db: Session, appointment) -> bool:
    """
    Обновить статус оплаты appointment (SSOT helper function).

    Args:
        db: Database session
        appointment: Объект Appointment

    Returns:
        True если было выполнено обновление, False если нет
    """
    is_paid = is_appointment_paid(db, appointment)

    if is_paid and not getattr(appointment, 'payment_processed_at', None):
        appointment.payment_processed_at = datetime.now(UTC)
        logger.info(
            "[FIX:BILLING_PAYMENT_STATUS] Appointment payment marker updated without changing visit_type: appointment_id=%s",
            getattr(appointment, 'id', None),
        )
        try:
            db.commit()
            db.refresh(appointment)
            return True
        except Exception as e:
            db.rollback()
            raise ValueError(
                f"Не удалось сохранить payment_processed_at для Appointment {appointment.id}: {e}"
            )

    return False


def get_discount_mode_for_appointment(db: Session, appointment) -> str:
    """
    Получить registration discount_mode для appointment (SSOT helper function).

    Args:
        db: Database session
        appointment: Объект Appointment

    Returns:
        discount_mode: none|repeat|benefit|all_free
    """
    # Маппим visit_type в registration discount_mode без payment marker.
    visit_type = getattr(appointment, 'visit_type', None) or 'none'
    visit_type_lower = visit_type.lower()

    if visit_type_lower == 'paid':
        return 'none'
    elif visit_type_lower == 'repeat':
        return 'repeat'
    elif visit_type_lower == 'benefit':
        return 'benefit'
    elif visit_type_lower == 'free':
        return 'all_free'
    else:
        return _normalize_registration_discount_mode(visit_type_lower)


