from __future__ import annotations

from datetime import date

import pytest

from app.models.appointment import Appointment
from app.models.payment import Payment
from app.models.visit import VisitService
from app.services.payment_create_service import (
    PaymentCreateDomainError,
    PaymentCreateService,
)


@pytest.mark.unit
class TestPaymentCreateService:
    def test_create_payment_requires_visit_or_appointment(self, db_session):
        service = PaymentCreateService(db_session)

        with pytest.raises(PaymentCreateDomainError) as exc_info:
            service.create_payment(
                visit_id=None,
                appointment_id=None,
                amount=10_000.0,
                currency="UZS",
                method="cash",
                note=None,
            )

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Не указан visit_id или appointment_id"

    def test_create_payment_resolves_visit_from_appointment(
        self, db_session, test_patient, test_visit
    ):
        appointment = Appointment(
            patient_id=test_patient.id,
            appointment_date=test_visit.visit_date or date.today(),
        )
        db_session.add(appointment)
        db_session.commit()
        db_session.refresh(appointment)

        service = PaymentCreateService(db_session)
        result = service.create_payment(
            visit_id=None,
            appointment_id=appointment.id,
            amount=50_000.0,
            currency="UZS",
            method="cash",
            note="unit test",
        )

        payment = db_session.query(Payment).filter(Payment.id == result["payment_id"]).first()
        assert payment is not None
        assert payment.visit_id == test_visit.id
        assert result["status"] == "paid"

    def test_create_payment_marks_visit_paid_when_fully_covered(
        self, db_session, test_visit, test_service
    ):
        test_visit.status = "open"
        test_visit.discount_mode = "none"
        db_session.add(
            VisitService(
                visit_id=test_visit.id,
                service_id=test_service.id,
                code=test_service.code,
                name=test_service.name,
                qty=1,
                price=100_000.0,
                currency="UZS",
            )
        )
        db_session.commit()

        service = PaymentCreateService(db_session)
        service.create_payment(
            visit_id=test_visit.id,
            appointment_id=None,
            amount=100_000.0,
            currency="UZS",
            method="cash",
            note=None,
        )

        db_session.refresh(test_visit)
        assert test_visit.status == "paid"
        assert test_visit.discount_mode == "paid"
