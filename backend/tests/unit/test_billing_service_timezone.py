from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.models.billing import PaymentReminder
from app.services import billing_service as billing_module
from app.services.billing_service import BillingService


@pytest.mark.unit
class TestBillingServiceTimezone:
    def test_create_invoice_handles_timezone_aware_clock(self, db_session, test_patient, monkeypatch):
        aware_now = datetime(2026, 3, 27, 10, 0, tzinfo=ZoneInfo("Asia/Tashkent"))

        monkeypatch.setattr(
            billing_module.queue_service,
            "get_local_timestamp",
            lambda db, timezone=None: aware_now,
        )

        service = BillingService(db_session)
        invoice = service.create_invoice(
            patient_id=test_patient.id,
            services=[
                {
                    "description": "Timezone Smoke Service",
                    "quantity": 1,
                    "unit_price": 1000,
                }
            ],
            due_days=10,
            auto_send=False,
        )

        service.create_payment_reminders(invoice.id)
        db_session.flush()

        reminders = (
            db_session.query(PaymentReminder)
            .filter(PaymentReminder.invoice_id == invoice.id)
            .all()
        )

        assert invoice.id is not None
        assert invoice.issue_date is not None
        assert invoice.issue_date.tzinfo is None
        assert invoice.due_date is not None
        assert invoice.due_date.tzinfo is None
        assert len(reminders) == 7
        assert all(reminder.scheduled_at.tzinfo is None for reminder in reminders)
