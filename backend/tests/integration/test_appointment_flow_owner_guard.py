from __future__ import annotations

from datetime import date
from uuid import uuid4

from app.core.security import get_password_hash
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit


def _suffix() -> str:
    return uuid4().hex[:10]


def _create_doctor_user(db_session, *, label: str) -> tuple[User, Doctor]:
    suffix = _suffix()
    user = User(
        username=f"appt_flow_{label}_{suffix}",
        email=f"appt-flow-{label}-{suffix}@test.local",
        full_name=f"Appointment Flow {label}",
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doctor = Doctor(
        user_id=user.id,
        specialty="therapy",
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return user, doctor


def _create_patient(db_session, *, label: str) -> Patient:
    suffix = _suffix()
    patient = Patient(
        first_name=f"Patient {label}",
        last_name="OwnerGuard",
        phone=f"+99890{suffix[:7]}",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _create_appointment(db_session, *, patient: Patient, doctor: Doctor) -> Appointment:
    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=date.today(),
        appointment_time="10:00",
        status="paid",
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)
    return appointment


def _doctor_headers(client, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "doctor123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_patient_user(db_session, *, label: str) -> tuple[User, Patient]:
    suffix = _suffix()
    user = User(
        username=f"appt_patient_{label}_{suffix}",
        email=f"appt-patient-{label}-{suffix}@test.local",
        full_name=f"Appointment Patient {label}",
        hashed_password=get_password_hash("patient123"),
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    patient = Patient(
        user_id=user.id,
        first_name=f"Patient {label}",
        last_name="LegacyAppointmentGuard",
        phone=f"+99891{suffix[:7]}",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return user, patient


def _patient_headers(client, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "patient123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_doctor_cannot_read_other_doctor_appointment_flow_status(
    client,
    db_session,
) -> None:
    own_user, _own_doctor = _create_doctor_user(db_session, label="own")
    _other_user, other_doctor = _create_doctor_user(db_session, label="other")
    other_patient = _create_patient(db_session, label="other")
    other_appointment = _create_appointment(
        db_session,
        patient=other_patient,
        doctor=other_doctor,
    )
    headers = _doctor_headers(client, own_user)

    other_response = client.get(
        f"/api/v1/appointments/{other_appointment.id}/status",
        headers=headers,
    )
    assert other_response.status_code == 403

    leaked_visit = (
        db_session.query(Visit)
        .filter(
            Visit.patient_id == other_patient.id,
            Visit.doctor_id == other_doctor.id,
        )
        .first()
    )
    assert leaked_visit is None


def test_patient_cannot_read_other_patient_legacy_appointment(
    client,
    db_session,
) -> None:
    own_user, _own_patient = _create_patient_user(db_session, label="own_read")
    _other_user, other_patient = _create_patient_user(db_session, label="other_read")
    other_appointment = Appointment(
        patient_id=other_patient.id,
        appointment_date=date.today(),
        appointment_time="11:00",
        status="scheduled",
    )
    db_session.add(other_appointment)
    db_session.commit()
    db_session.refresh(other_appointment)

    response = client.get(
        f"/api/v1/appointments/{other_appointment.id}",
        headers=_patient_headers(client, own_user),
    )

    assert response.status_code == 403


def test_patient_can_read_own_legacy_appointment(
    client,
    db_session,
) -> None:
    own_user, own_patient = _create_patient_user(db_session, label="own_allow")
    own_appointment = Appointment(
        patient_id=own_patient.id,
        appointment_date=date.today(),
        appointment_time="10:30",
        status="scheduled",
    )
    db_session.add(own_appointment)
    db_session.commit()
    db_session.refresh(own_appointment)

    response = client.get(
        f"/api/v1/appointments/{own_appointment.id}",
        headers=_patient_headers(client, own_user),
    )

    assert response.status_code == 200
    assert response.json()["id"] == own_appointment.id


def test_patient_legacy_appointment_list_is_limited_to_own_records(
    client,
    db_session,
) -> None:
    own_user, own_patient = _create_patient_user(db_session, label="own_list")
    _other_user, other_patient = _create_patient_user(db_session, label="other_list")
    own_appointment = Appointment(
        patient_id=own_patient.id,
        appointment_date=date.today(),
        appointment_time="09:00",
        status="scheduled",
    )
    other_appointment = Appointment(
        patient_id=other_patient.id,
        appointment_date=date.today(),
        appointment_time="09:30",
        status="scheduled",
    )
    db_session.add_all([own_appointment, other_appointment])
    db_session.commit()
    db_session.refresh(own_appointment)
    db_session.refresh(other_appointment)

    response = client.get(
        "/api/v1/appointments/",
        headers=_patient_headers(client, own_user),
    )

    assert response.status_code == 200
    appointment_ids = {item["id"] for item in response.json()}
    assert own_appointment.id in appointment_ids
    assert other_appointment.id not in appointment_ids


def test_patient_cannot_create_legacy_appointment_for_another_patient(
    client,
    db_session,
) -> None:
    own_user, _own_patient = _create_patient_user(db_session, label="own_create")
    _other_user, other_patient = _create_patient_user(db_session, label="other_create")
    before_count = db_session.query(Appointment).count()

    response = client.post(
        "/api/v1/appointments/",
        json={
            "patient_id": other_patient.id,
            "appointment_date": date.today().isoformat(),
            "appointment_time": "14:00",
            "status": "scheduled",
        },
        headers=_patient_headers(client, own_user),
    )

    assert response.status_code == 403
    assert db_session.query(Appointment).count() == before_count


def test_patient_cannot_read_legacy_pending_payments(
    client,
    db_session,
) -> None:
    own_user, _own_patient = _create_patient_user(db_session, label="pending")

    response = client.get(
        "/api/v1/appointments/pending-payments",
        headers=_patient_headers(client, own_user),
    )

    assert response.status_code == 403


def test_patient_cannot_update_other_patient_legacy_appointment(
    client,
    db_session,
) -> None:
    own_user, _own_patient = _create_patient_user(db_session, label="own_update")
    _other_user, other_patient = _create_patient_user(db_session, label="other_update")
    other_appointment = Appointment(
        patient_id=other_patient.id,
        appointment_date=date.today(),
        appointment_time="12:00",
        status="scheduled",
        notes="original",
    )
    db_session.add(other_appointment)
    db_session.commit()
    db_session.refresh(other_appointment)

    response = client.put(
        f"/api/v1/appointments/{other_appointment.id}",
        json={"notes": "tampered"},
        headers=_patient_headers(client, own_user),
    )

    assert response.status_code == 403
    db_session.refresh(other_appointment)
    assert other_appointment.notes == "original"


def test_patient_cannot_mutate_own_legacy_appointment_payment_fields(
    client,
    db_session,
) -> None:
    own_user, own_patient = _create_patient_user(db_session, label="own_payment")
    own_appointment = Appointment(
        patient_id=own_patient.id,
        appointment_date=date.today(),
        appointment_time="12:30",
        status="scheduled",
        notes="original",
        payment_amount=None,
        payment_transaction_id=None,
        payment_provider=None,
    )
    db_session.add(own_appointment)
    db_session.commit()
    db_session.refresh(own_appointment)

    response = client.put(
        f"/api/v1/appointments/{own_appointment.id}",
        json={
            "notes": "keep me out",
            "status": "paid",
            "payment_amount": 100000,
            "payment_provider": "cash",
            "payment_transaction_id": "patient-forged",
        },
        headers=_patient_headers(client, own_user),
    )

    assert response.status_code == 403
    db_session.refresh(own_appointment)
    assert own_appointment.status == "scheduled"
    assert own_appointment.notes == "original"
    assert own_appointment.payment_amount is None
    assert own_appointment.payment_provider is None
    assert own_appointment.payment_transaction_id is None


def test_admin_can_update_legacy_appointment_payment_fields(
    client,
    auth_headers,
    db_session,
) -> None:
    patient = _create_patient(db_session, label="admin_payment")
    appointment = Appointment(
        patient_id=patient.id,
        appointment_date=date.today(),
        appointment_time="15:00",
        status="scheduled",
        payment_amount=None,
        payment_transaction_id=None,
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)

    response = client.put(
        f"/api/v1/appointments/{appointment.id}",
        json={
            "status": "paid",
            "payment_amount": 100000,
            "payment_provider": "cash",
            "payment_transaction_id": "admin-marked",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    db_session.refresh(appointment)
    assert appointment.status == "paid"
    assert appointment.payment_amount == 100000
    assert appointment.payment_provider == "cash"
    assert appointment.payment_transaction_id == "admin-marked"


def test_patient_cannot_delete_other_patient_legacy_appointment(
    client,
    db_session,
) -> None:
    own_user, _own_patient = _create_patient_user(db_session, label="own_delete")
    _other_user, other_patient = _create_patient_user(db_session, label="other_delete")
    other_appointment = Appointment(
        patient_id=other_patient.id,
        appointment_date=date.today(),
        appointment_time="13:00",
        status="scheduled",
    )
    db_session.add(other_appointment)
    db_session.commit()
    db_session.refresh(other_appointment)
    appointment_id = other_appointment.id

    response = client.delete(
        f"/api/v1/appointments/{appointment_id}",
        headers=_patient_headers(client, own_user),
    )

    assert response.status_code == 403
    assert db_session.get(Appointment, appointment_id) is not None
