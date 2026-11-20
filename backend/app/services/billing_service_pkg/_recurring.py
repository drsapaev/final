"""Recurring mixin for BillingService.

Split from billing_service.py.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import text

from app.services.billing_service_pkg._base import *  # noqa: F401, F403
from app.services.billing_service_pkg._base import BillingServiceMixinBase


class RecurringMixin(BillingServiceMixinBase):
    """Recurring methods for BillingService."""

    def create_recurring_invoices(self) -> int:
        """Issue each observed due occurrence in its own transaction."""

        now = self._get_local_timestamp_naive()
        due = (
            Invoice.is_recurring.is_(True),
            Invoice.next_invoice_date <= now,
            Invoice.status != InvoiceStatus.CANCELLED,
        )
        occurrences = (
            self.db.query(Invoice.id, Invoice.next_invoice_date)
            .filter(*due)
            .order_by(Invoice.id)
            .all()
        )

        created_count = 0
        for parent_id, due_at in occurrences:
            try:
                parent = (
                    self.db.query(Invoice)
                    .filter(*due, Invoice.id == parent_id, Invoice.next_invoice_date == due_at)
                    .with_for_update()
                    .populate_existing()
                    .first()
                )
                if parent is None:
                    self.db.rollback()
                    continue
                interval = parent.recurrence_interval
                if not isinstance(interval, int) or interval < 1:
                    raise ValueError("Invalid recurring invoice interval")
                next_due_at = self._calculate_next_recurrence_date(
                    due_at, parent.recurrence_type, interval
                )
                settings = self._lock_invoice_settings()
                new_invoice = Invoice(
                    invoice_number=self._reserve_invoice_number(settings),
                    patient_id=parent.patient_id,
                    invoice_type=parent.invoice_type,
                    subtotal=parent.subtotal,
                    tax_rate=parent.tax_rate,
                    tax_amount=parent.tax_amount,
                    total_amount=parent.total_amount,
                    balance=parent.total_amount,
                    issue_date=now,
                    due_date=now + timedelta(days=30),
                    description=parent.description,
                    payment_terms=parent.payment_terms,
                    is_auto_generated=True,
                    auto_send=parent.auto_send,
                    send_reminders=parent.send_reminders,
                    parent_invoice_id=parent_id,
                )

                self.db.add(new_invoice)
                self.db.flush()

                # Копируем позиции
                for item in parent.invoice_items:
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

                parent.next_invoice_date = next_due_at
                new_id, auto_send = new_invoice.id, new_invoice.auto_send
                self.db.commit()
            except Exception as exc:
                self.db.rollback()
                logger.error("Recurring invoice creation failed error_type=%s", type(exc).__name__)
                continue

            created_count += 1
            if auto_send:
                try:
                    self.send_invoice(new_id)
                except Exception as exc:
                    self.db.rollback()
                    logger.warning("Recurring invoice delivery failed error_type=%s", type(exc).__name__)

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
        settings = self.db.query(BillingSettings).order_by(BillingSettings.id).first()
        if settings is None:
            settings = self._lock_invoice_settings()
            self.db.commit()
            self.db.refresh(settings)
        return settings

    def _lock_invoice_settings(self, *, nowait: bool = False) -> BillingSettings:
        """Lock the number counter, creating its initial row in this transaction."""
        dialect = self.db.get_bind().dialect.name
        query = self.db.query(BillingSettings).order_by(BillingSettings.id).populate_existing()
        if dialect == "sqlite":
            self.db.execute(text("UPDATE billing_settings SET id=id WHERE 0"))
        if dialect == "postgresql":
            query = query.with_for_update(nowait=nowait)
        settings = query.first()
        if settings is not None:
            return settings

        if dialect == "postgresql":
            if self.db.execute(text("SHOW transaction_isolation")).scalar_one() != "read committed":
                raise HTTPException(status_code=409, detail="Инициализация счётчика требует READ COMMITTED")
            # There is no row to lock until the first successful creation.
            # Scope the initialization lock to this database relation.
            lock = "pg_try_advisory_xact_lock" if nowait else "pg_advisory_xact_lock"
            acquired = self.db.execute(text(f"""
                SELECT pg_catalog.{lock}(pg_catalog.hashtextextended(
                    'clinic.billing_settings.init:' ||
                    'billing_settings'::pg_catalog.regclass::pg_catalog.oid::pg_catalog.text, 0
                ))
            """)).scalar_one()
            if nowait and acquired is not True:
                raise HTTPException(status_code=409, detail="Настройки биллинга заняты, повторите запрос")
            settings = query.first()
            if settings is not None:
                return settings

        settings = BillingSettings()
        self.db.add(settings)
        self.db.flush()
        return settings

    def _reserve_invoice_number(self, settings: BillingSettings) -> str:
        """Advance the locked counter past a number used by the old recurring writer."""
        number = self._generate_invoice_number(settings)
        if self.db.query(Invoice.id).filter(Invoice.invoice_number == number).first() is not None:
            settings.next_invoice_number += 1
            number = self._generate_invoice_number(settings)
        settings.next_invoice_number += 1
        return number


