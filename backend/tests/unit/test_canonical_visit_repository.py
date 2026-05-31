from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.visit import Visit
from app.repositories.canonical_visit_repository import CanonicalVisitRepository


def _suffix() -> str:
    return uuid4().hex[:10]


def test_list_visits_for_appointment_requires_matching_time(db_session) -> None:
    suffix = _suffix()
    patient = Patient(
        first_name="Canonical",
        last_name=f"TimeGuard{suffix}",
        phone=f"+99890{suffix[:7]}",
        birth_date=date(1990, 1, 1),
    )
    doctor = Doctor(specialty="cardiology", active=True)
    db_session.add_all([patient, doctor])
    db_session.commit()
    db_session.refresh(patient)
    db_session.refresh(doctor)

    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=date(2026, 3, 17),
        appointment_time="10:00",
        status="paid",
        created_at=datetime(2026, 3, 17, 9, 0, 0),
    )
    wrong_time_visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=appointment.appointment_date,
        visit_time="09:00",
        status="open",
        source="desk",
        created_at=datetime(2026, 3, 17, 8, 30, 0),
    )
    matching_visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=appointment.appointment_date,
        visit_time="10:00:00",
        status="open",
        source="desk",
        created_at=datetime(2026, 3, 17, 9, 30, 0),
    )
    db_session.add_all([appointment, wrong_time_visit, matching_visit])
    db_session.commit()
    db_session.refresh(appointment)
    db_session.refresh(wrong_time_visit)
    db_session.refresh(matching_visit)

    matches = CanonicalVisitRepository(db_session).list_visits_for_appointment(
        appointment
    )

    assert [visit.id for visit in matches] == [matching_visit.id]


def test_list_visits_for_appointment_does_not_match_timed_visit_when_appointment_time_missing(
    db_session,
) -> None:
    suffix = _suffix()
    patient = Patient(
        first_name="Canonical",
        last_name=f"NoTime{suffix}",
        phone=f"+99891{suffix[:7]}",
        birth_date=date(1990, 1, 1),
    )
    doctor = Doctor(specialty="cardiology", active=True)
    db_session.add_all([patient, doctor])
    db_session.commit()
    db_session.refresh(patient)
    db_session.refresh(doctor)

    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=date(2026, 3, 18),
        appointment_time=None,
        status="paid",
        created_at=datetime(2026, 3, 18, 9, 0, 0),
    )
    timed_visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=appointment.appointment_date,
        visit_time="09:00",
        status="open",
        source="desk",
    )
    db_session.add_all([appointment, timed_visit])
    db_session.commit()
    db_session.refresh(appointment)
    db_session.refresh(timed_visit)

    matches = CanonicalVisitRepository(db_session).list_visits_for_appointment(
        appointment
    )

    assert matches == []
