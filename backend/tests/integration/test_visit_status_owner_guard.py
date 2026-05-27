from __future__ import annotations

from datetime import date
from uuid import uuid4

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit, VisitService


def _suffix() -> str:
    return uuid4().hex[:10]


def _create_doctor_user(db_session, *, label: str) -> tuple[User, Doctor]:
    suffix = _suffix()
    user = User(
        username=f"visit_status_{label}_{suffix}",
        email=f"visit-status-{label}-{suffix}@test.local",
        full_name=f"Visit Status {label}",
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


def _create_patient(db_session) -> Patient:
    suffix = _suffix()
    patient = Patient(
        first_name="Visit",
        last_name=f"Status{suffix}",
        phone=f"+99891{suffix[:7]}",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _doctor_headers(client, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "doctor123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_doctor_cannot_change_other_doctor_visit_status(client, db_session) -> None:
    own_user, _own_doctor = _create_doctor_user(db_session, label="own")
    _other_user, other_doctor = _create_doctor_user(db_session, label="other")
    other_patient = _create_patient(db_session)
    other_visit = Visit(
        patient_id=other_patient.id,
        doctor_id=other_doctor.id,
        visit_date=date.today(),
        status="open",
        source="desk",
    )
    db_session.add(other_visit)
    db_session.commit()
    db_session.refresh(other_visit)

    response = client.post(
        f"/api/v1/visits/visits/{other_visit.id}/status",
        params={"status_new": "closed"},
        headers=_doctor_headers(client, own_user),
    )

    assert response.status_code == 403
    db_session.refresh(other_visit)
    assert other_visit.status == "open"


def test_doctor_cannot_add_service_to_other_doctor_visit(client, db_session) -> None:
    own_user, _own_doctor = _create_doctor_user(db_session, label="svc_own")
    _other_user, other_doctor = _create_doctor_user(db_session, label="svc_other")
    other_patient = _create_patient(db_session)
    other_visit = Visit(
        patient_id=other_patient.id,
        doctor_id=other_doctor.id,
        visit_date=date.today(),
        status="open",
        source="desk",
    )
    db_session.add(other_visit)
    db_session.commit()
    db_session.refresh(other_visit)

    response = client.post(
        f"/api/v1/visits/visits/{other_visit.id}/services",
        json={
            "code": "CONSULT",
            "name": "Consultation",
            "price": 125000,
            "qty": 1,
        },
        headers=_doctor_headers(client, own_user),
    )

    assert response.status_code == 403
    assert (
        db_session.query(VisitService)
        .filter(VisitService.visit_id == other_visit.id)
        .count()
        == 0
    )
