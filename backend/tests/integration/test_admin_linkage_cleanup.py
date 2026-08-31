from datetime import date

from app.api.v1.endpoints import admin_doctors
from app.core.security import get_password_hash
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue
from app.models.user import User


def test_admin_doctors_stats_route_dispatches_before_doctor_id(
    client,
    auth_headers,
    monkeypatch,
):
    class FakeAdminDoctorsStatsService:
        def __init__(self, db):
            self.db = db

        def get_doctors_stats(self):
            return {
                "total": 2,
                "active": 1,
                "inactive": 1,
                "by_specialty": {"cardiology": 1},
            }

    monkeypatch.setattr(
        admin_doctors,
        "AdminDoctorsStatsService",
        FakeAdminDoctorsStatsService,
    )

    response = client.get("/api/v1/admin/doctors/stats", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["by_specialty"] == {"cardiology": 1}


def test_available_doctor_users_excludes_already_linked_accounts(
    client,
    db_session,
    auth_headers,
):
    linked_user = User(
        username="linked_doc",
        email="linked@test.com",
        full_name="Linked Doctor",
        hashed_password=get_password_hash("secret123"),
        role="Doctor",
        is_active=True,
    )
    free_user = User(
        username="free_doc",
        email="free@test.com",
        full_name="Free Doctor",
        hashed_password=get_password_hash("secret123"),
        role="Doctor",
        is_active=True,
    )
    db_session.add_all([linked_user, free_user])
    db_session.commit()
    db_session.refresh(linked_user)
    db_session.refresh(free_user)

    doctor = Doctor(
        user_id=linked_user.id,
        specialty="cardiology",
        cabinet="101",
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)

    response = client.get("/api/v1/admin/doctors/available-users", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    returned_ids = {item["id"] for item in payload}
    assert free_user.id in returned_ids
    assert linked_user.id not in returned_ids

    response = client.get(
        f"/api/v1/admin/doctors/available-users?doctor_id={doctor.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    returned_ids = {item["id"] for item in payload}
    assert linked_user.id in returned_ids
    assert free_user.id in returned_ids


def test_admin_appointments_returns_enriched_doctor_and_effective_cabinet(
    client,
    db_session,
    auth_headers,
    test_patient,
):
    doctor_user = User(
        username="enriched_doc",
        email="enriched@test.com",
        full_name="Enriched Doctor",
        hashed_password=get_password_hash("secret123"),
        role="Doctor",
        is_active=True,
    )
    db_session.add(doctor_user)
    db_session.commit()
    db_session.refresh(doctor_user)

    doctor = Doctor(
        user_id=doctor_user.id,
        specialty="cardiology",
        cabinet="201",
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)

    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor.id,
        queue_tag="cardiology",
        cabinet_number="202",
        active=True,
    )
    db_session.add(queue)

    appointment = Appointment(
        patient_id=test_patient.id,
        doctor_id=doctor.id,
        appointment_date=date.today(),
        appointment_time="09:30",
        notes="Контрольный визит",
        status="pending",
    )
    db_session.add(appointment)
    db_session.commit()

    response = client.get("/api/v1/admin/appointments", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload

    item = next((row for row in payload if row["id"] == appointment.id), None)
    assert item is not None
    assert item["doctorName"] == "Enriched Doctor"
    assert item["doctorSpecialization"] == "cardiology"
    assert item["doctorCabinet"] == "201"
    assert item["queueCabinet"] == "202"
    assert item["effectiveCabinet"] == "202"
    assert item["hasIntegrityWarnings"] is True
    assert "queue_cabinet_stale" in item["integrityWarnings"]


def test_queue_cabinet_info_reports_sync_status_and_rejects_manual_canonical_changes(
    client,
    db_session,
    auth_headers,
):
    doctor_user = User(
        username="queue_doc",
        email="queue@test.com",
        full_name="Queue Doctor",
        hashed_password=get_password_hash("secret123"),
        role="Doctor",
        is_active=True,
    )
    db_session.add(doctor_user)
    db_session.commit()
    db_session.refresh(doctor_user)

    doctor = Doctor(
        user_id=doctor_user.id,
        specialty="dermatology",
        cabinet="305",
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)

    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor.id,
        queue_tag="dermatology",
        cabinet_number="399",
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)

    response = client.get("/api/v1/admin/queues/cabinet-info", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    item = next((row for row in payload if row["id"] == queue.id), None)
    assert item is not None
    assert item["doctor_cabinet"] == "305"
    assert item["effective_cabinet"] == "399"
    assert item["sync_status"] == "stale"

    response = client.put(
        f"/api/v1/admin/queues/{queue.id}/cabinet-info",
        json={"cabinet_number": "777"},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Канонический номер кабинета" in response.json()["detail"]

    response = client.post(
        "/api/v1/admin/queues/sync-cabinet-info",
        headers=auth_headers,
    )
    assert response.status_code == 200

    db_session.refresh(queue)
    assert queue.cabinet_number == "305"


# ---------------------------------------------------------------------------
# Codex P2 round-6 (#2934): concurrent doctor-link race must surface the
# duplicate-link client error, not HTTP 500 from the DB UNIQUE constraint.
# Two requests can both pass the get_doctor_by_user_id pre-check before
# either commits; the losing commit raises IntegrityError from
# UNIQUE(doctors.user_id) (migration 0048: uq_doctors_user_id).
# ---------------------------------------------------------------------------


def _create_doctor_role_user(db_session, username: str) -> User:
    user = User(
        username=username,
        email=f"{username}@test.com",
        full_name=username.replace("_", " ").title(),
        hashed_password=get_password_hash("secret123"),
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_create_doctor_returns_duplicate_link_error_on_commit_race(
    client,
    db_session,
    auth_headers,
    monkeypatch,
):
    """Losing create_doctor commit under a concurrent link must return the
    same 400 the pre-check yields — not a 500 from the UNIQUE constraint."""
    from app.crud import clinic as crud_clinic

    user = _create_doctor_role_user(db_session, "race_create_user")
    # The "winning" concurrent request already committed this link.
    winner = Doctor(user_id=user.id, specialty="cardiology", active=True)
    db_session.add(winner)
    db_session.commit()
    db_session.refresh(winner)

    # Race window: the pre-check runs before the winner commits, so it
    # misses the link and lets the losing INSERT reach the DB constraint.
    monkeypatch.setattr(
        crud_clinic, "get_doctor_by_user_id", lambda db, user_id: None
    )

    response = client.post(
        "/api/v1/admin/doctors",
        headers=auth_headers,
        json={"user_id": user.id, "specialty": "dermatology"},
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Пользователь уже привязан к другому врачу"

    # The rollback must leave the session usable for subsequent requests.
    follow_up = client.get("/api/v1/admin/doctors", headers=auth_headers)
    assert follow_up.status_code == 200


def test_update_doctor_returns_duplicate_link_error_on_commit_race(
    client,
    db_session,
    auth_headers,
    monkeypatch,
):
    """Losing update_doctor commit under a concurrent link must return the
    duplicate-link 400 — not a 500 from the UNIQUE constraint."""
    from app.crud import clinic as crud_clinic

    user = _create_doctor_role_user(db_session, "race_update_user")
    winner = Doctor(user_id=user.id, specialty="cardiology", active=True)
    db_session.add(winner)
    db_session.commit()
    db_session.refresh(winner)

    # The doctor being updated still looks userless to the pre-check.
    target = Doctor(user_id=None, specialty="dermatology", active=True)
    db_session.add(target)
    db_session.commit()
    db_session.refresh(target)

    monkeypatch.setattr(
        crud_clinic, "get_doctor_by_user_id", lambda db, user_id: None
    )

    response = client.put(
        f"/api/v1/admin/doctors/{target.id}",
        headers=auth_headers,
        json={"user_id": user.id},
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Пользователь уже привязан к другому врачу"

    db_session.refresh(target)
    assert target.user_id is None, "losing update must not partially apply"


def test_unique_violation_matcher_discriminates_constraint_types():
    """The IntegrityError matcher must accept UNIQUE(doctors.user_id) on
    both backends and reject foreign-key violations on the same column."""
    from sqlalchemy.exc import IntegrityError

    from app.api.v1.endpoints.admin_doctors import (
        _is_doctor_user_id_unique_violation,
    )

    pg_unique = IntegrityError(
        "stmt",
        None,
        Exception(
            'duplicate key value violates unique constraint "uq_doctors_user_id"'
        ),
    )
    sqlite_unique = IntegrityError(
        "stmt",
        None,
        Exception("UNIQUE constraint failed: doctors.user_id"),
    )
    pg_fk = IntegrityError(
        "stmt",
        None,
        Exception(
            'insert or update on table "doctors" violates foreign key '
            'constraint "doctors_user_id_fkey"'
        ),
    )
    sqlite_fk = IntegrityError(
        "stmt",
        None,
        Exception("FOREIGN KEY constraint failed"),
    )

    assert _is_doctor_user_id_unique_violation(pg_unique) is True
    assert _is_doctor_user_id_unique_violation(sqlite_unique) is True
    assert _is_doctor_user_id_unique_violation(pg_fk) is False
    assert _is_doctor_user_id_unique_violation(sqlite_fk) is False
