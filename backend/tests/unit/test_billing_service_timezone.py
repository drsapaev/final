from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.models.appointment import Appointment
from app.models.billing import PaymentReminder
from app.models.patient import Patient
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

    def test_create_invoice_rejects_visit_from_another_patient(
        self, db_session, test_patient, test_visit
    ):
        other_patient = Patient(
            first_name="Other",
            last_name="Patient",
            phone="+998901111111",
        )
        db_session.add(other_patient)
        db_session.commit()
        db_session.refresh(other_patient)

        service = BillingService(db_session)
        with pytest.raises(ValueError) as exc_info:
            service.create_invoice(
                patient_id=other_patient.id,
                visit_id=test_visit.id,
                services=[
                    {
                        "description": "Wrong owner service",
                        "quantity": 1,
                        "unit_price": 1000,
                    }
                ],
            )

        assert str(exc_info.value) == (
            "Invoice patient_id does not match visit ownership"
        )

    def test_create_invoice_rejects_appointment_from_another_patient(
        self, db_session, test_patient
    ):
        other_patient = Patient(
            first_name="Other",
            last_name="Patient",
            phone="+998902222222",
        )
        appointment = Appointment(
            patient_id=test_patient.id,
            appointment_date=datetime(2026, 3, 27).date(),
        )
        db_session.add_all([other_patient, appointment])
        db_session.commit()
        db_session.refresh(other_patient)
        db_session.refresh(appointment)

        service = BillingService(db_session)
        with pytest.raises(ValueError) as exc_info:
            service.create_invoice(
                patient_id=other_patient.id,
                appointment_id=appointment.id,
                services=[
                    {
                        "description": "Wrong owner service",
                        "quantity": 1,
                        "unit_price": 1000,
                    }
                ],
            )

        assert str(exc_info.value) == (
            "Invoice patient_id does not match appointment ownership"
        )
