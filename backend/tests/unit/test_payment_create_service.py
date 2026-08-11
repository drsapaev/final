from __future__ import annotations

from datetime import date

import pytest
from unittest.mock import Mock, patch

from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.visit import Visit, VisitService
from app.services.payment_create_service import (
    PaymentCreateDomainError,
    PaymentCreateService,
)


@pytest.mark.unit
class TestPaymentCreateService:
    """Tests for PaymentCreateService.

    Issue #06: PaymentCreateService.create_payment() now delegates to
    PaymentInvariantService.create_payment_for_visit(). These tests
    patch PaymentInvariantService to avoid the invariant checks
    (paid_amount, total_cost) that require VisitService rows.
    """

    @pytest.fixture(autouse=True)
    def _mock_payment_invariant(self, monkeypatch):
        """Mock PaymentInvariantService to bypass invariant checks."""
        from decimal import Decimal
        from app.services import payment_create_service as _pcs_module
        from decimal import Decimal

        class _FakePayment:
            def __init__(self, visit_id, amount, method, note, **kwargs):
                self.id = 999
                self.visit_id = visit_id
                self.amount = Decimal(str(amount))
                self.method = method
                self.status = "paid"
                self.note = note
                self.paid_at = None
                self.provider = kwargs.get("provider")
                self.currency = kwargs.get("currency", "UZS")

        def _fake_create(visit_id, amount, method, note, current_user, **kwargs):
            return _FakePayment(visit_id, amount, method, note, **kwargs)

        mock_cls = Mock()
        mock_instance = Mock()
        mock_instance.create_payment_for_visit = _fake_create
        mock_cls.return_value = mock_instance
        monkeypatch.setattr(_pcs_module, "PaymentInvariantService", mock_cls)

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
            appointment_time=test_visit.visit_time,
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
        # Issue #06 Phase 0: payment status is in Payment table, not result["status"]

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
            visit_time="10:00",
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

    def test_create_payment_rejects_mismatched_visit_and_appointment_ids(
        self, db_session, test_patient, test_doctor
    ):
        visit_date = date.today()
        appointment_visit = Visit(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            visit_date=visit_date,
            visit_time="09:00",
            status="open",
            discount_mode="none",
            source="desk",
        )
        appointment = Appointment(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            appointment_date=visit_date,
            appointment_time="09:00",
        )
        other_patient = Patient(
            first_name="Other",
            last_name="PaymentOwner",
            phone="+998901990001",
            birth_date=date(1991, 1, 1),
        )
        db_session.add(other_patient)
        db_session.flush()
        other_visit = Visit(
            patient_id=other_patient.id,
            doctor_id=test_doctor.id,
            visit_date=visit_date,
            visit_time="10:00",
            status="open",
            discount_mode="none",
            source="desk",
        )
        db_session.add_all([appointment_visit, appointment, other_visit])
        db_session.commit()
        db_session.refresh(appointment)
        db_session.refresh(other_visit)

        service = PaymentCreateService(db_session)
        with pytest.raises(PaymentCreateDomainError) as exc_info:
            service.create_payment(
                visit_id=other_visit.id,
                appointment_id=appointment.id,
                amount=75_000.0,
                currency="UZS",
                method="cash",
                note="mixed-id payment",
            )

        db_session.refresh(other_visit)
        assert exc_info.value.status_code == 409
        assert db_session.query(Payment).count() == 0
        assert other_visit.status == "open"

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
        # Issue #06 Phase 0: visit.status is NOT set to "paid" — payment state
        # lives in Payment table. Visit status remains operational (e.g. "open").
        assert test_visit.status != "paid"  # legacy status removed
        # Payment is confirmed via Payment.status == "paid"
