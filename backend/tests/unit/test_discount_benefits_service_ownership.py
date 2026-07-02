from datetime import date

import pytest

from app.models.appointment import Appointment
from app.models.discount_benefits import (
    Benefit,
    LoyaltyProgram,
    PatientBenefit,
    PatientLoyalty,
)
from app.models.patient import Patient
from app.services.discount_benefits_service import DiscountBenefitsService


def _create_patient(db_session, *, first_name: str, phone: str) -> Patient:
    patient = Patient(
        first_name=first_name,
        last_name="Owner",
        phone=phone,
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _create_verified_patient_benefit(db_session, patient_id: int) -> PatientBenefit:
    benefit = Benefit(
        name="Ownership benefit",
        benefit_type="employee",
        discount_percentage=10,
        is_active=True,
    )
    patient_benefit = PatientBenefit(
        patient_id=patient_id,
        benefit=benefit,
        is_active=True,
        verified=True,
    )
    db_session.add_all([benefit, patient_benefit])
    db_session.commit()
    db_session.refresh(patient_benefit)
    return patient_benefit


def _create_loyalty_program(db_session) -> LoyaltyProgram:
    program = LoyaltyProgram(
        name="Ownership points",
        points_per_ruble=1,
        min_purchase_for_points=0,
        ruble_per_point=1,
        min_points_to_redeem=1,
        is_active=True,
    )
    db_session.add(program)
    db_session.commit()
    db_session.refresh(program)
    return program


def test_apply_benefit_rejects_visit_from_another_patient(
    db_session, test_patient, test_visit
):
    other_patient = _create_patient(
        db_session, first_name="BenefitOther", phone="+998901010101"
    )
    patient_benefit = _create_verified_patient_benefit(
        db_session, other_patient.id
    )

    service = DiscountBenefitsService(db_session)
    with pytest.raises(ValueError) as exc_info:
        service.apply_benefit(
            patient_benefit_id=patient_benefit.id,
            amount=1000,
            visit_id=test_visit.id,
        )

    assert str(exc_info.value) == (
        "Patient context does not match visit ownership"
    )


def test_earn_loyalty_points_rejects_appointment_from_another_patient(
    db_session, test_patient
):
    other_patient = _create_patient(
        db_session, first_name="LoyaltyOther", phone="+998902020202"
    )
    appointment = Appointment(
        patient_id=test_patient.id,
        appointment_date=date(2026, 3, 27),
    )
    program = _create_loyalty_program(db_session)
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)

    service = DiscountBenefitsService(db_session)
    with pytest.raises(ValueError) as exc_info:
        service.earn_loyalty_points(
            patient_id=other_patient.id,
            program_id=program.id,
            amount=1000,
            appointment_id=appointment.id,
        )

    assert str(exc_info.value) == (
        "Patient context does not match appointment ownership"
    )


def test_redeem_loyalty_points_rejects_visit_from_another_patient(
    db_session, test_patient, test_visit
):
    other_patient = _create_patient(
        db_session, first_name="RedeemOther", phone="+998903030303"
    )
    program = _create_loyalty_program(db_session)
    patient_loyalty = PatientLoyalty(
        patient_id=other_patient.id,
        program_id=program.id,
        current_balance=100,
    )
    db_session.add(patient_loyalty)
    db_session.commit()

    service = DiscountBenefitsService(db_session)
    with pytest.raises(ValueError) as exc_info:
        service.redeem_loyalty_points(
            patient_id=other_patient.id,
            program_id=program.id,
            points=10,
            visit_id=test_visit.id,
        )

    assert str(exc_info.value) == (
        "Patient context does not match visit ownership"
    )
