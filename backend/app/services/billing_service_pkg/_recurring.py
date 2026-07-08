"""Recurring mixin for BillingService.

Split from billing_service.py.
"""
from __future__ import annotations

from app.services.billing_service_pkg._base import *  # noqa: F401, F403
from app.services.billing_service_pkg._base import BillingServiceMixinBase

class RecurringMixin(BillingServiceMixinBase):
    """Recurring methods for BillingService."""

    def create_recurring_invoices(self) -> int:
        """Создать периодические счета"""

        now = self._get_local_timestamp_naive()

        # Получаем счета для создания периодических
        recurring_invoices = (
            self.db.query(Invoice)
            .filter(
                Invoice.is_recurring == True,
                Invoice.next_invoice_date <= now,
                Invoice.status != InvoiceStatus.CANCELLED,
            )
            .all()
        )

        created_count = 0

        for parent_invoice in recurring_invoices:
            try:
                # Создаем новый счет на основе родительского
                new_invoice = Invoice(
                    invoice_number=self._generate_invoice_number(
                        self.get_billing_settings()
                    ),
                    patient_id=parent_invoice.patient_id,
                    invoice_type=parent_invoice.invoice_type,
                    subtotal=parent_invoice.subtotal,
                    tax_rate=parent_invoice.tax_rate,
                    tax_amount=parent_invoice.tax_amount,
                    total_amount=parent_invoice.total_amount,
                    balance=parent_invoice.total_amount,
                    issue_date=now,
                    due_date=now + timedelta(days=30),
                    description=parent_invoice.description,
                    payment_terms=parent_invoice.payment_terms,
                    is_auto_generated=True,
                    auto_send=parent_invoice.auto_send,
                    send_reminders=parent_invoice.send_reminders,
                    parent_invoice_id=parent_invoice.id,
                )

                self.db.add(new_invoice)
                self.db.flush()

                # Копируем позиции
                for item in parent_invoice.invoice_items:
                    new_item = InvoiceItem(
                        invoice_id=new_invoice.id,
                        service_id=item.service_id,
                        description=item.description,
                        quantity=item.quantity,
                        unit_price=item.unit_price,
                        discount_rate=item.discount_rate,
                        discount_amount=item.discount_amount,
                        tax_rate=item.tax_rate,
                        tax_amount=item.tax_amount,
                        total_amount=item.total_amount,
                        sort_order=item.sort_order,
                    )
                    self.db.add(new_item)

                # Обновляем дату следующего счета
                next_invoice_date = self._normalize_datetime(
                    parent_invoice.next_invoice_date
                )
                if not next_invoice_date:
                    next_invoice_date = now
                parent_invoice.next_invoice_date = self._calculate_next_recurrence_date(
                    next_invoice_date,
                    parent_invoice.recurrence_type,
                    parent_invoice.recurrence_interval,
                )

                created_count += 1

                # Автоматически отправляем если нужно
                if new_invoice.auto_send:
                    self.send_invoice(new_invoice.id)

            except Exception as e:
                logger.error(
                    "Ошибка создания периодического счета для %d: %s",
                    parent_invoice.id,
                    e,
                    exc_info=True,
                )

        self.db.commit()
        return created_count

    # === Утилиты ===


    def _calculate_next_recurrence_date(
        self, current_date: datetime, recurrence_type: RecurrenceType, interval: int
    ) -> datetime:
        """Рассчитать дату следующего периодического счета"""
        if recurrence_type == RecurrenceType.DAILY:
            return current_date + timedelta(days=interval)
        elif recurrence_type == RecurrenceType.WEEKLY:
            return current_date + timedelta(weeks=interval)
        elif recurrence_type == RecurrenceType.MONTHLY:
            return current_date + timedelta(days=30 * interval)  # Упрощенно
        elif recurrence_type == RecurrenceType.QUARTERLY:
            return current_date + timedelta(days=90 * interval)  # Упрощенно
        elif recurrence_type == RecurrenceType.YEARLY:
            return current_date + timedelta(days=365 * interval)  # Упрощенно
        else:
            return current_date + timedelta(days=30)


    def get_billing_settings(self) -> BillingSettings:
        """Получить настройки биллинга"""
        settings = self.db.query(BillingSettings).first()
        if not settings:
            # Создаем настройки по умолчанию
            settings = BillingSettings()
            self.db.add(settings)
            self.db.commit()
            self.db.refresh(settings)
        return settings


