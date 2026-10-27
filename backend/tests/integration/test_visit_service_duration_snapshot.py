from __future__ import annotations

from datetime import date, timedelta

from app.crud.visit import add_visit_service, create_visit
from app.repositories.appointment_flow_api_repository import (
    AppointmentFlowApiRepository,
)


def test_registrar_visit_captures_exact_service_duration_at_creation(
    db_session, test_patient, test_doctor, test_service
):
    visit = create_visit(
        db_session,
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        visit_date=date.today() + timedelta(days=3),
        visit_time="10:00",
        services=[
            {
                "service_id": test_service.id,
                "name": "client supplied name is not authoritative",
                "quantity": 1,
            }
        ],
        status="open",
    )

    visit_service = visit.services[0]
    assert visit_service.service_id == test_service.id
    assert visit_service.duration_minutes_snapshot == test_service.duration_minutes

    test_service.duration_minutes = 45
    db_session.commit()
    db_session.refresh(visit_service)
    assert visit_service.duration_minutes_snapshot == 30


def test_adding_exact_service_to_existing_visit_captures_duration(
    db_session, test_patient, test_doctor, test_service
):
    visit = create_visit(
        db_session,
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        visit_date=date.today() + timedelta(days=4),
        visit_time="11:00",
        status="open",
    )

    added = add_visit_service(db_session, visit.id, test_service.id)
    assert added.service_id == test_service.id
    assert added.duration_minutes_snapshot == test_service.duration_minutes


def test_visit_to_appointment_conversion_carries_only_unambiguous_snapshot(
    db_session, test_patient, test_doctor, test_service
):
    visit = create_visit(
        db_session,
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        visit_date=date.today() + timedelta(days=5),
        visit_time="12:00",
        services=[{"service_id": test_service.id, "quantity": 1}],
        status="open",
    )

    appointment = AppointmentFlowApiRepository(
        db_session
    ).create_appointment_from_visit(visit)
    assert appointment.duration_minutes_snapshot == test_service.duration_minutes
