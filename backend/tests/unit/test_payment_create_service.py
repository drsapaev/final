from __future__ import annotations

from datetime import date

import pytest

from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.payment import Payment
from app.models.visit import Visit, VisitService
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
            doctor_id=test_visit.doctor_id,
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

    def test_create_payment_from_appointment_uses_canonical_visit_not_first_same_day(
        self, db_session, test_patient, test_visit
    ):
        matching_doctor = Doctor(specialty="dermatology", active=True)
        db_session.add(matching_doctor)
        db_session.flush()
        matching_visit = Visit(
            patient_id=test_patient.id,
            doctor_id=matching_doctor.id,
            visit_date=test_visit.visit_date or date.today(),
            visit_time="12:00",
            status="open",
            discount_mode="none",
            source="desk",
        )
        appointment = Appointment(
            patient_id=test_patient.id,
            doctor_id=matching_doctor.id,
            appointment_date=matching_visit.visit_date,
            appointment_time="12:00",
        )
        db_session.add_all([matching_visit, appointment])
        db_session.commit()
        db_session.refresh(matching_visit)
        db_session.refresh(appointment)

        service = PaymentCreateService(db_session)
        result = service.create_payment(
            visit_id=None,
            appointment_id=appointment.id,
            amount=75_000.0,
            currency="UZS",
            method="cash",
            note="canonical appointment payment",
        )

        payment = db_session.query(Payment).filter(Payment.id == result["payment_id"]).first()
        assert payment is not None
        assert payment.visit_id == matching_visit.id
        assert payment.visit_id != test_visit.id

    def test_create_payment_from_appointment_rejects_ambiguous_visit_candidates(
        self, db_session, test_patient, test_doctor
    ):
        visit_date = date.today()
        first_visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=visit_date,
            visit_time="09:00",
            status="open",
            discount_mode="none",
            source="desk",
        )
        second_visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=visit_date,
            visit_time="10:00",
            status="open",
            discount_mode="none",
            source="desk",
        )
        appointment = Appointment(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            appointment_date=visit_date,
            appointment_time="10:00",
        )
        db_session.add_all([first_visit, second_visit, appointment])
        db_session.commit()
        db_session.refresh(appointment)

        service = PaymentCreateService(db_session)
        with pytest.raises(PaymentCreateDomainError) as exc_info:
            service.create_payment(
                visit_id=None,
                appointment_id=appointment.id,
                amount=75_000.0,
                currency="UZS",
                method="cash",
                note="ambiguous appointment payment",
            )

        assert exc_info.value.status_code == 409
        assert db_session.query(Payment).count() == 0

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
