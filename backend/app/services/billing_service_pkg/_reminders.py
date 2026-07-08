"""Reminders mixin for BillingService.

Split from billing_service.py.
"""
from __future__ import annotations

from app.services.billing_service_pkg._base import *  # noqa: F401, F403
from app.services.billing_service_pkg._base import BillingServiceMixinBase


class RemindersMixin(BillingServiceMixinBase):
    """Reminders methods for BillingService."""

    def create_payment_reminders(self, invoice_id: int):
        """Создать напоминания об оплате для счета"""

        invoice = self.db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice or not invoice.send_reminders:
            return

        settings = self.get_billing_settings()
        due_date = self._normalize_datetime(invoice.due_date)
        if not due_date:
            return
        now = self._get_local_timestamp_naive()

        # Напоминания до срока оплаты
        if settings.reminder_days_before:
            days_before = [
                int(d.strip()) for d in settings.reminder_days_before.split(',')
            ]
            for days in days_before:
                reminder_date = due_date - timedelta(days=days)
                if reminder_date > now:
                    self._create_reminder(
                        invoice_id=invoice_id,
                        reminder_type='email',
                        scheduled_at=reminder_date,
                        days_before_due=days,
                        subject=f'Напоминание об оплате счета {invoice.invoice_number}',
                        message=f'Уважаемый пациент! Напоминаем, что через {days} дней истекает срок оплаты счета {invoice.invoice_number} на сумму {invoice.total_amount} {settings.currency_symbol}.',
                    )

        # Напоминания после просрочки
        if settings.reminder_days_after:
            days_after = [
                int(d.strip()) for d in settings.reminder_days_after.split(',')
            ]
            for days in days_after:
                reminder_date = due_date + timedelta(days=days)
                self._create_reminder(
                    invoice_id=invoice_id,
                    reminder_type='email',
                    scheduled_at=reminder_date,
                    days_after_due=days,
                    subject=f'Просроченный счет {invoice.invoice_number}',
                    message=f'Уважаемый пациент! Счет {invoice.invoice_number} на сумму {invoice.total_amount} {settings.currency_symbol} просрочен на {days} дней. Просим погасить задолженность.',
                )


    def send_due_reminders(self) -> int:
        """Отправить напоминания, которые пора отправлять"""

        now = self._get_local_timestamp_naive()

        # Получаем напоминания к отправке
        reminders = (
            self.db.query(PaymentReminder)
            .filter(
                PaymentReminder.is_sent == False, PaymentReminder.scheduled_at <= now
            )
            .all()
        )

        sent_count = 0

        for reminder in reminders:
            try:
                # Отправляем напоминание
                if reminder.reminder_type == 'email':
                    self._send_email_reminder(reminder)
                elif reminder.reminder_type == 'sms':
                    self._send_sms_reminder(reminder)

                # Отмечаем как отправленное
                reminder.is_sent = True
                reminder.sent_at = now
                reminder.delivery_status = 'delivered'
                sent_count += 1

            except Exception as e:
                reminder.delivery_status = 'failed'
                logger.error(
                    "Ошибка отправки напоминания %d: %s", reminder.id, e, exc_info=True
                )

        self.db.commit()
        return sent_count

    # === Периодические счета ===


    def _create_reminder(
        self,
        invoice_id: int,
        reminder_type: str,
        scheduled_at: datetime,
        days_before_due: int = 0,
        days_after_due: int = 0,
        subject: str = '',
        message: str = '',
    ):
        """Создать напоминание"""
        reminder = PaymentReminder(
            invoice_id=invoice_id,
            reminder_type=reminder_type,
            days_before_due=days_before_due,
            days_after_due=days_after_due,
            subject=subject,
            message=message,
            scheduled_at=scheduled_at,
        )
        self.db.add(reminder)


    def _send_email_reminder(self, reminder: PaymentReminder):
        """Отправить напоминание по email"""
        # Здесь интеграция с email сервисом
        pass


    def _send_sms_reminder(self, reminder: PaymentReminder):
        """Отправить напоминание по SMS"""
        # Здесь интеграция с SMS сервисом
        pass


