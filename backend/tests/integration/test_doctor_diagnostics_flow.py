"""A diagnostics interruption must not replace or close the started visit."""

import secrets
from datetime import date

import pytest

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.user import User
from app.models.visit import Visit

pytestmark = pytest.mark.integration


def _fixture(
    client,
    db,
    doctor_user,
    patient,
    *,
    visit_status="in_progress",
    entry_status="in_progress",
    exact=True,
):
    doctor = Doctor(user_id=doctor_user.id, active=True, specialty="general")
    db.add(doctor)
    db.flush()
    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor.id,
        queue_tag="general",
        active=True,
    )
    db.add(queue)
    db.flush()
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id if exact else None,
        visit_date=date.today(),
        status=visit_status,
        visit_time="09:15",
        notes="SYNTHETIC UNCHANGED NOTE",
    )
    db.add(visit)
    db.flush()
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=1,
        status=entry_status,
        patient_id=patient.id,
        visit_id=visit.id,
        patient_name="SYNTHETIC",
    )
    db.add(entry)
    db.commit()
    login = client.post(
        "/api/v1/authentication/login",
        json={"username": doctor_user.username, "password": "doctor123"},
    )
    assert login.status_code == 200
    return entry, visit, {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_started_visit_can_pause_and_resume_without_restarting(
    client,
    db_session,
    test_doctor_user,
    test_patient,
):
    db = db_session
    entry, visit, headers = _fixture(client, db, test_doctor_user, test_patient)
    id_pair = entry.id, visit.id
    original_visit_count = db.query(Visit).count()
    original_visit_updated_at = visit.updated_at

    queue_url = "/api/v1/doctor/general/queue/today"
    row = client.get(queue_url, headers=headers).json()["entries"][0]
    assert row["can_send_to_diagnostics"] is True

    pause = client.post(f"/api/v1/queue/entry/{entry.id}/diagnostics", headers=headers)
    assert pause.status_code == 200
    assert pause.json()["new_status"] == "diagnostics"
    db.refresh(entry)
    assert entry.diagnostics_started_at is not None
    row = client.get(queue_url, headers=headers).json()["entries"][0]
    assert row["can_start_visit"] is True
    assert row["visit_id"] == id_pair[1]

    resume = client.post(
        f"/api/v1/doctor/queue/{entry.id}/start-visit", headers=headers
    )
    assert resume.status_code == 200
    assert resume.json()["visit_id"] == id_pair[1]
    assert resume.json()["patient_id"] == test_patient.id
    db.refresh(entry)
    db.refresh(visit)
    assert entry.status == "in_progress"
    assert entry.diagnostics_started_at is None
    assert visit.status == "in_progress"
    assert visit.visit_time == "09:15"
    assert visit.notes == "SYNTHETIC UNCHANGED NOTE"
    assert visit.updated_at == original_visit_updated_at
    assert db.query(Visit).count() == original_visit_count


@pytest.mark.parametrize(
    ("exact", "visit_status"), [(False, "in_progress"), (True, "completed")]
)
def test_bad_or_terminal_visit_is_not_offered_or_resumed(
    client,
    db_session,
    test_doctor_user,
    test_patient,
    exact,
    visit_status,
):
    db = db_session
    entry, visit, headers = _fixture(
        client,
        db,
        test_doctor_user,
        test_patient,
        exact=exact,
        visit_status=visit_status,
        entry_status="diagnostics",
    )
    row = client.get("/api/v1/doctor/general/queue/today", headers=headers).json()[
        "entries"
    ][0]
    assert row["can_start_visit"] is False
    old_count = db.query(Visit).count()
    response = client.post(
        f"/api/v1/doctor/queue/{entry.id}/start-visit", headers=headers
    )
    assert response.status_code == 409
    db.refresh(entry)
    db.refresh(visit)
    assert entry.status == "diagnostics"
    assert visit.status == visit_status
    assert db.query(Visit).count() == old_count


def test_same_specialty_doctor_cannot_resume_another_doctors_visit(
    client,
    db_session,
    test_doctor_user,
    test_patient,
):
    entry, _, _ = _fixture(
        client, db_session, test_doctor_user, test_patient, entry_status="diagnostics"
    )
    password = secrets.token_urlsafe(24)
    colleague = User(
        username="synthetic_diagnostics_colleague",
        email="diagnostics-colleague@example.test",
        role="Doctor",
        is_active=True,
        hashed_password=get_password_hash(password),
    )
    db_session.add(colleague)
    db_session.flush()
    db_session.add(Doctor(user_id=colleague.id, active=True, specialty="general"))
    db_session.commit()
    login = client.post(
        "/api/v1/authentication/login",
        json={"username": colleague.username, "password": password},
    )
    assert login.status_code == 200
    response = client.post(
        f"/api/v1/doctor/queue/{entry.id}/start-visit",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert response.status_code == 403
    db_session.refresh(entry)
    assert entry.status == "diagnostics"


def test_incomplete_cannot_strand_a_paused_doctor_visit(
    client, db_session, test_doctor_user, test_patient,
):
    db = db_session
    entry, visit, headers = _fixture(client, db, test_doctor_user, test_patient)
    target_visit_id = visit.id
    assert client.post(
        f"/api/v1/queue/entry/{entry.id}/diagnostics", headers=headers,
    ).status_code == 200
    db.refresh(entry)
    diagnostic_start = entry.diagnostics_started_at

    response = client.post(
        f"/api/v1/queue/entry/{entry.id}/incomplete",
        json={"reason": "SYNTHETIC UNFINISHED"},
        headers=headers,
    )
    assert response.status_code == 409
    db.refresh(entry)
    db.refresh(visit)
    assert entry.status == "diagnostics"
    assert entry.diagnostics_started_at == diagnostic_start
    assert entry.incomplete_reason is None
    assert visit.status == "in_progress"

    resume = client.post(
        f"/api/v1/doctor/queue/{entry.id}/start-visit", headers=headers,
    )
    assert resume.status_code == 200
    assert resume.json()["visit_id"] == target_visit_id


def test_only_exact_active_diagnostics_omits_queue_only_incomplete_action(
    client, db_session, test_doctor_user, test_patient,
):
    db = db_session
    entry, _, headers = _fixture(
        client, db, test_doctor_user, test_patient, entry_status="diagnostics",
    )
    url = "/api/v1/doctor/general/queue/today"
    exact = client.get(url, headers=headers).json()["entries"][0]
    assert exact["can_mark_incomplete"] is False
    assert "mark_incomplete" not in exact["available_actions"]
    assert exact["can_start_visit"] is True
    assert exact["can_complete"] is True

    entry.visit_id = None
    db.commit()
    legacy = client.get(url, headers=headers).json()["entries"][0]
    assert legacy["can_mark_incomplete"] is True
    assert legacy["can_start_visit"] is False
    response = client.post(
        f"/api/v1/queue/entry/{entry.id}/incomplete",
        json={"reason": "SYNTHETIC LEGACY"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["new_status"] == "incomplete"
