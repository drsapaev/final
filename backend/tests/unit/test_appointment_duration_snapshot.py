from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi import HTTPException

from app.crud.appointment import appointment as appointment_crud
from app.models.service import Service
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate


def test_create_resolves_catalog_name_and_captures_duration_once(
    db_session, test_patient, test_doctor
):
    service = Service(
        name="Точная услуга",
        price=100000,
        duration_minutes=35,
        active=True,
    )
    db_session.add(service)
    db_session.flush()

    row = appointment_crud.create(
        db_session,
        obj_in=AppointmentCreate(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            appointment_date=date.today() + timedelta(days=3),
            appointment_time="10:00",
            services=["подменённое название"],
            service_ids=[service.id],
        ),
    )

    assert row.services == ["Точная услуга"]
    assert row.duration_minutes_snapshot == 35

    service.duration_minutes = 50
    db_session.commit()
    db_session.refresh(row)
    assert row.duration_minutes_snapshot == 35


def test_update_with_exact_service_id_refreshes_snapshot(
    db_session, test_patient, test_doctor, test_service
):
    row = appointment_crud.create(
        db_session,
        obj_in=AppointmentCreate(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            appointment_date=date.today() + timedelta(days=3),
            appointment_time="10:00",
        ),
    )

    updated = appointment_crud.update(
        db_session,
        db_obj=row,
        obj_in=AppointmentUpdate(service_ids=[test_service.id]),
    )

    assert updated.services == [test_service.name]
    assert updated.duration_minutes_snapshot == test_service.duration_minutes


def test_invalid_exact_service_selection_is_rejected_before_insert(
    db_session, test_patient, test_doctor
):
    with pytest.raises(HTTPException) as exc_info:
        appointment_crud.create(
            db_session,
            obj_in=AppointmentCreate(
                patient_id=test_patient.id,
                doctor_id=test_doctor.id,
                appointment_date=date.today() + timedelta(days=3),
                service_ids=[999999],
            ),
        )

    assert exc_info.value.status_code == 422


def test_ambiguous_or_doctor_incompatible_selection_keeps_duration_unknown(
    db_session, test_patient, test_doctor, test_doctor_user
):
    from app.models.clinic import Doctor

    other_doctor = Doctor(
        user_id=test_doctor_user.id,
        specialty="Тест",
        active=True,
    )
    db_session.add(other_doctor)
    db_session.flush()
    pinned = Service(
        name="Закреплённая услуга",
        price=100000,
        duration_minutes=30,
        doctor_id=other_doctor.id,
        active=True,
    )
    second = Service(
        name="Вторая услуга",
        price=100000,
        duration_minutes=20,
        active=True,
    )
    db_session.add_all([pinned, second])
    db_session.flush()

    incompatible = appointment_crud.create(
        db_session,
        obj_in=AppointmentCreate(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            appointment_date=date.today() + timedelta(days=3),
            service_ids=[pinned.id],
        ),
    )
    ambiguous = appointment_crud.create(
        db_session,
        obj_in=AppointmentCreate(
            patient_id=test_patient.id,
            doctor_id=test_doctor.id,
            appointment_date=date.today() + timedelta(days=4),
            service_ids=[pinned.id, second.id],
        ),
    )

    assert incompatible.duration_minutes_snapshot is None
    assert ambiguous.duration_minutes_snapshot is None
