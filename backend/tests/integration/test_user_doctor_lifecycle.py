"""Lifecycle tests: User.is_active is mirrored onto the linked Doctor profile.

Ghost-doctor prevention contract (PR: fix/doctor-lifecycle-ghost-doctor):

- deleting a User deactivates (never deletes) their Doctor profile(s) in the
  same transaction; historical visits/EMR keep referencing the Doctor row;
- deactivating a User (single update or bulk action) deactivates the Doctor
  profile; reactivating restores it;
- /auth/me stops advertising specialty/doctor_id/cabinet once the Doctor
  profile is inactive (no clinical panel routing for deactivated doctors).
"""
from __future__ import annotations

from datetime import date

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit


def _create_doctor_with_profile(
    db_session, label: str, *, role: str = "Doctor"
) -> tuple[User, Doctor]:
    user = User(
        username=f"lc_{label}",
        email=f"lc-{label}@test.com",
        full_name=f"Lifecycle {label}",
        hashed_password=get_password_hash("secret123"),
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doctor = Doctor(user_id=user.id, specialty="stomatology", active=True)
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return user, doctor


def _create_visit(db_session, doctor: Doctor) -> Visit:
    patient = Patient(
        first_name="Life",
        last_name="Cycle",
        phone="+998900000999",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)

    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=date.today(),
        status="open",
        source="desk",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)
    return visit


def _doctor_headers(client, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "secret123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_delete_user_deactivates_doctor_and_preserves_history(
    client, db_session, auth_headers
):
    user, doctor = _create_doctor_with_profile(db_session, "del")
    visit = _create_visit(db_session, doctor)

    response = client.delete(
        f"/api/v1/users/users/{user.id}", headers=auth_headers
    )
    assert response.status_code == 200, response.text

    # User is gone
    assert db_session.query(User).filter(User.id == user.id).first() is None

    # Doctor row survives (FK SET NULL) but is deactivated — no ghost doctor
    db_session.expire_all()
    doctor_row = db_session.query(Doctor).filter(Doctor.id == doctor.id).first()
    assert doctor_row is not None
    assert doctor_row.active is False
    assert doctor_row.user_id is None

    # Historical clinical data untouched
    visit_row = db_session.query(Visit).filter(Visit.id == visit.id).first()
    assert visit_row is not None
    assert visit_row.doctor_id == doctor.id


def test_bulk_deactivate_then_activate_mirrors_to_doctor(
    client, db_session, auth_headers
):
    user, doctor = _create_doctor_with_profile(db_session, "bulk")

    response = client.post(
        "/api/v1/users/users/bulk-action",
        json={"user_ids": [user.id], "action": "deactivate"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert db_session.query(Doctor).filter(Doctor.id == doctor.id).one().active is False

    response = client.post(
        "/api/v1/users/users/bulk-action",
        json={"user_ids": [user.id], "action": "activate"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert db_session.query(Doctor).filter(Doctor.id == doctor.id).one().active is True


def test_bulk_delete_deactivates_doctor(client, db_session, auth_headers):
    user, doctor = _create_doctor_with_profile(db_session, "bulkdel")

    response = client.post(
        "/api/v1/users/users/bulk-action",
        json={"user_ids": [user.id], "action": "delete"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text

    db_session.expire_all()
    assert db_session.query(User).filter(User.id == user.id).first() is None
    doctor_row = db_session.query(Doctor).filter(Doctor.id == doctor.id).first()
    assert doctor_row is not None
    assert doctor_row.active is False


def test_update_user_is_active_mirrors_to_doctor(client, db_session, auth_headers):
    user, doctor = _create_doctor_with_profile(db_session, "upd")

    response = client.put(
        f"/api/v1/users/users/{user.id}",
        json={"is_active": False},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert db_session.query(Doctor).filter(Doctor.id == doctor.id).one().active is False

    response = client.put(
        f"/api/v1/users/users/{user.id}",
        json={"is_active": True},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert db_session.query(Doctor).filter(Doctor.id == doctor.id).one().active is True


def _patch_auth_me_sessionlocal(monkeypatch, db_session) -> None:
    """Route /auth/me's internal SessionLocal to the test DB.

    GET /auth/me builds a fresh SessionLocal() instead of using the get_db
    dependency, so in the test environment it must be pointed at the same
    connection-bound session factory the fixtures use.
    """
    from sqlalchemy.orm import sessionmaker

    from app.db import session as session_module

    def _fake_session_local():
        maker = sessionmaker(
            autocommit=False, autoflush=False, bind=db_session.get_bind()
        )
        return maker()

    monkeypatch.setattr(session_module, "SessionLocal", _fake_session_local)


def test_auth_me_hides_doctor_fields_for_inactive_doctor(
    client, db_session, monkeypatch
):
    user, doctor = _create_doctor_with_profile(db_session, "me")
    _patch_auth_me_sessionlocal(monkeypatch, db_session)

    headers = _doctor_headers(client, user)
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["doctor_id"] == doctor.id
    assert body["specialty"] == "stomatology"

    # Deactivate the Doctor profile (e.g. owner deactivated by admin)
    doctor.active = False
    db_session.commit()

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["doctor_id"] is None
    assert body["specialty"] is None
    assert body["cabinet"] is None
