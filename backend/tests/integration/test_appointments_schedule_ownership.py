"""Ownership tests for GET /appointments/doctor/{doctor_id}/schedule.

Contract (PR: fix/appointments-schedule-ownership):
- Admin/Registrar (+superuser): any doctor's schedule;
- doctor-capable roles (Doctor + legacy variants): only their own doctor_id
  — Doctor A must NOT be able to read Doctor B's schedule by substituting
  doctor_id (patient_id + reason leak otherwise);
- Patient and every other authenticated role: denied.

Regression for the HIGH-risk IDOR gap found in the ownership audit (the
endpoint previously accepted any authenticated user with no ownership check).
"""
from __future__ import annotations

from datetime import date, timedelta

from app.core.security import get_password_hash
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User


def _doctor_pair(db_session, label_a: str, label_b: str) -> tuple[User, Doctor, User, Doctor]:
    rows = []
    for label in (label_a, label_b):
        user = User(
            username=f"sched_{label}",
            email=f"sched-{label}@test.com",
            full_name=f"Schedule {label}",
            hashed_password=get_password_hash("secret123"),
            role="Doctor",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        doctor = Doctor(user_id=user.id, specialty="stomatology", active=True)
        db_session.add(doctor)
        db_session.commit()
        db_session.refresh(doctor)
        rows.append((user, doctor))
    return rows[0][0], rows[0][1], rows[1][0], rows[1][1]


def _schedule_appointment(db_session, doctor: Doctor, patient: Patient) -> Appointment:
    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=date.today() + timedelta(days=1),
        appointment_time="10:00",
        status="scheduled",
        notes="private reason",
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)
    return appointment


def _headers_for(user: User) -> dict[str, str]:
    """Mint an access token the same way conftest's auth_headers fixture does."""
    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(user)}"}


def _patient(db_session) -> Patient:
    """Synthetic patient fixture — all-zero subscriber number per conftest
    convention (no realistic phone/name/birth data: repo PII rule for
    committed test fixtures, AGENTS.md "PII fields")."""
    patient = Patient(
        first_name="Sched",
        last_name="Patient",
        phone="+998900000000",
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def test_doctor_cannot_read_other_doctor_schedule(client, db_session):
    user_a, _doctor_a, _user_b, doctor_b = _doctor_pair(db_session, "a", "b")
    patient = _patient(db_session)
    _schedule_appointment(db_session, doctor_b, patient)

    response = client.get(
        f"/api/v1/appointments/doctor/{doctor_b.id}/schedule",
        params={"date": str(date.today() + timedelta(days=1))},
        headers=_headers_for(user_a),
    )
    assert response.status_code == 403, response.text


def test_doctor_reads_own_schedule(client, db_session):
    user_a, doctor_a, _user_b, _doctor_b = _doctor_pair(db_session, "own_a", "own_b")
    patient = _patient(db_session)
    appointment = _schedule_appointment(db_session, doctor_a, patient)

    response = client.get(
        f"/api/v1/appointments/doctor/{doctor_a.id}/schedule",
        params={"date": str(date.today() + timedelta(days=1))},
        headers=_headers_for(user_a),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    entries = body if isinstance(body, list) else body.get("appointments", body.get("schedule", []))
    assert any(entry.get("id") == appointment.id for entry in entries)


def test_registrar_reads_any_doctor_schedule(client, db_session, registrar_user):
    _user_a, doctor_a, _user_b, _doctor_b = _doctor_pair(db_session, "reg_a", "reg_b")
    patient = _patient(db_session)
    appointment = _schedule_appointment(db_session, doctor_a, patient)

    response = client.get(
        f"/api/v1/appointments/doctor/{doctor_a.id}/schedule",
        params={"date": str(date.today() + timedelta(days=1))},
        headers=_headers_for(registrar_user),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    entries = body if isinstance(body, list) else body.get("appointments", body.get("schedule", []))
    assert any(entry.get("id") == appointment.id for entry in entries)


def test_patient_denied_doctor_schedule(client, db_session):
    _user_a, doctor_a, _user_b, _doctor_b = _doctor_pair(db_session, "pat_a", "pat_b")
    patient_user = User(
        username="sched_patient",
        email="sched-patient@test.com",
        full_name="Sched Patient User",
        hashed_password=get_password_hash("secret123"),
        role="Patient",
        is_active=True,
    )
    db_session.add(patient_user)
    db_session.commit()

    response = client.get(
        f"/api/v1/appointments/doctor/{doctor_a.id}/schedule",
        params={"date": str(date.today() + timedelta(days=1))},
        headers=_headers_for(patient_user),
    )
    assert response.status_code == 403, response.text


def _audit_rows(db_session, subject_patient_id: int):
    from app.models.patient_access_audit import PatientAccessAuditLog

    return (
        db_session.query(PatientAccessAuditLog)
        .filter(PatientAccessAuditLog.subject_patient_id == subject_patient_id)
        .all()
    )


def test_schedule_read_writes_per_patient_audit_trail(client, db_session, admin_user):
    """Threat model 'Audit log on every patient read': a successful staff
    read of a nonempty schedule must leave one audit row per returned
    patient, attributed to the acting staff user (not patient self-access)."""
    user_a, doctor_a, _user_b, _doctor_b = _doctor_pair(db_session, "aud_a", "aud_b")
    patient = _patient(db_session)
    appointment = _schedule_appointment(db_session, doctor_a, patient)

    response = client.get(
        f"/api/v1/appointments/doctor/{doctor_a.id}/schedule",
        params={"date": str(date.today() + timedelta(days=1))},
        headers=_headers_for(admin_user),
    )
    assert response.status_code == 200, response.text

    rows = _audit_rows(db_session, patient.id)
    assert len(rows) == 1
    row = rows[0]
    assert row.actor_type == "staff"
    assert row.actor_staff_user_id == admin_user.id
    assert row.actor_patient_id is None
    assert row.resource_type == "appointment"
    assert row.resource_id == str(appointment.id)
    assert row.action == "view"
    assert row.outcome == "success"


def test_doctor_own_schedule_read_also_audited(client, db_session):
    """Doctor self-read goes through the same per-patient audit trail."""
    user_a, doctor_a, _user_b, _doctor_b = _doctor_pair(db_session, "aud_c", "aud_d")
    patient = _patient(db_session)
    _schedule_appointment(db_session, doctor_a, patient)

    response = client.get(
        f"/api/v1/appointments/doctor/{doctor_a.id}/schedule",
        params={"date": str(date.today() + timedelta(days=1))},
        headers=_headers_for(user_a),
    )
    assert response.status_code == 200, response.text

    rows = _audit_rows(db_session, patient.id)
    assert len(rows) == 1
    assert rows[0].actor_type == "staff"
    assert rows[0].actor_staff_user_id == user_a.id


def test_denied_schedule_read_writes_no_audit_rows(client, db_session):
    """403 denials must not create patient-access audit entries (the read
    never happened; the guard rejects before any PHI is assembled)."""
    _user_a, _doctor_a, _user_b, doctor_b = _doctor_pair(db_session, "aud_e", "aud_f")
    patient = _patient(db_session)
    _schedule_appointment(db_session, doctor_b, patient)
    patient_user = User(
        username="sched_patient_aud",
        email="sched-patient-aud@test.com",
        full_name="Sched Patient Auditor",
        hashed_password=get_password_hash("secret123"),
        role="Patient",
        is_active=True,
    )
    db_session.add(patient_user)
    db_session.commit()

    response = client.get(
        f"/api/v1/appointments/doctor/{doctor_b.id}/schedule",
        params={"date": str(date.today() + timedelta(days=1))},
        headers=_headers_for(patient_user),
    )
    assert response.status_code == 403, response.text
    assert _audit_rows(db_session, patient.id) == []


def test_audit_trail_survives_oversized_request_metadata(client, db_session, admin_user):
    """Codex P1: oversized User-Agent / X-Forwarded-For must not make the
    audit insert fail (the non-blocking helper would roll back and silently
    drop the read trail). Metadata is truncated at write site; the audit row
    survives with bounded values."""
    user_a, doctor_a, _user_b, _doctor_b = _doctor_pair(db_session, "aud_g", "aud_h")
    patient = _patient(db_session)
    _schedule_appointment(db_session, doctor_a, patient)

    response = client.get(
        f"/api/v1/appointments/doctor/{doctor_a.id}/schedule",
        params={"date": str(date.today() + timedelta(days=1))},
        headers={
            **_headers_for(admin_user),
            "User-Agent": "A" * 6000,
            "X-Forwarded-For": f"{'9' * 200}, 10.0.0.1",
        },
    )
    assert response.status_code == 200, response.text

    rows = _audit_rows(db_session, patient.id)
    assert len(rows) == 1, "audit row must survive oversized metadata"
    assert rows[0].user_agent is not None and len(rows[0].user_agent) == 512
    assert rows[0].ip_address is not None and len(rows[0].ip_address) <= 45
