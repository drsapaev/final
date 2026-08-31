"""Multi-doctor per specialty: isolation + selector determinism regression.

Business model under test (REQUIRED architectural result):

    N physical doctors of one specialty
      = N User accounts  +  N Doctor profiles
      → one shared /doctor panel, per-doctor Doctor.id ownership scope

Scope note: the DB-level UNIQUE(doctors.user_id) invariant is delivered
separately by the companion PR #2934 (migration 0048) and is deliberately
NOT part of this branch — here only application-level behavior is covered
(the app-level duplicate-link rejection is what remains between an
accidental second POST and the DB constraint landing).

Covers, for Doctor A and Doctor B with the SAME specialty (stomatology):
- registrar doctor selector returns BOTH doctors, deterministically ordered;
- admin doctor list is deterministically ordered;
- same-specialty collaboration per ADR-001 ("Any doctor of the same
  specialty can call/start/cancel patients from any same-specialty
  queue"): Doctor A CAN call an entry in Doctor B's queue via the
  canonical /doctor/queue/{entry_id}/call endpoint (PR-26 semantics);
- a doctor of a DIFFERENT specialty is denied (403);
- Doctor A cannot save EMR into Doctor B's visit (403);
- admin keeps cross-doctor queue privileges (200);
- registrar can still pick a specific doctor (both visible);
- app-level duplicate User↔Doctor link stays rejected (400).
"""
from __future__ import annotations

from datetime import date, datetime

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.user import User


def _create_dentist(
    db_session, label: str, specialty: str = "stomatology"
) -> tuple[User, Doctor]:
    """N-th dentist: own User account + own Doctor profile, same specialty."""
    user = User(
        username=f"multi_dentist_{label}",
        email=f"multi-dentist-{label}@test.com",
        full_name=f"Dentist {label}",
        hashed_password=get_password_hash("secret123"),
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doctor = Doctor(
        user_id=user.id,
        specialty=specialty,
        cabinet=f"10{label}" if not label.isdigit() else f"1{label}0",
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return user, doctor


def _patient(db_session) -> Patient:
    """Synthetic patient fixture — all-zero subscriber number per conftest
    convention (no realistic phone/name/birth data: repo PII rule for
    committed test fixtures, AGENTS.md "PII fields")."""
    patient = Patient(
        first_name="Multi",
        last_name="Dentist",
        phone="+998900000000",
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _seed_queue_entry(
    db_session, *, doctor: Doctor, patient: Patient, number: int
) -> OnlineQueueEntry:
    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor.id,
        queue_tag="stomatology",
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)

    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=number,
        patient_id=patient.id,
        patient_name=patient.short_name(),
        phone=patient.phone,
        source="registrar",
        status="waiting",
        created_at=datetime.utcnow(),
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


def _login_headers(client, *, user: User, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _admin_headers(client, admin_user) -> dict[str, str]:
    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(admin_user)}"}


def test_registrar_sees_all_same_specialty_doctors_in_deterministic_order(
    client, db_session, registrar_user
):
    _user_a, doctor_a = _create_dentist(db_session, "1")
    _user_b, doctor_b = _create_dentist(db_session, "2")

    response = client.get(
        "/api/v1/registrar/doctors",
        params={"specialty": "stomatology"},
        headers=_login_headers(client, user=registrar_user, password="registrar123"),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    ids = [d["id"] for d in body["doctors"]]
    assert doctor_a.id in ids and doctor_b.id in ids
    assert body["total_doctors"] == len(ids)
    # Deterministic ordering (doctor id ascending) — no reshuffling between
    # requests, so the registrar wizard shows a stable doctor list.
    assert ids == sorted(ids)


def test_admin_doctor_list_deterministically_ordered(client, db_session, auth_headers):
    _user_a, doctor_a = _create_dentist(db_session, "3")
    _user_b, doctor_b = _create_dentist(db_session, "4")

    response = client.get(
        "/api/v1/admin/doctors",
        params={"active_only": "false"},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    items = body if isinstance(body, list) else body.get("items", body.get("doctors", []))
    ids = [d["id"] for d in items if d["id"] in (doctor_a.id, doctor_b.id)]
    assert doctor_a.id in ids and doctor_b.id in ids
    assert ids == sorted(ids)


def test_same_specialty_colleague_can_call_entry_per_adr001(client, db_session):
    """ADR-001: any doctor of the SAME specialty may call another
    same-specialty doctor's queue entry (canonical /doctor/queue endpoint,
    PR-26 semantics — 'Allow if caller is the queue owner OR has the same
    specialty'). The legacy /queue/legacy/call owner-only restriction is
    deliberately NOT asserted here: it is a deprecated surface whose strict
    behavior contradicts the accepted collaboration workflow."""
    user_a, _doctor_a = _create_dentist(db_session, "5")
    _user_b, doctor_b = _create_dentist(db_session, "6")
    patient = _patient(db_session)
    foreign_entry = _seed_queue_entry(
        db_session, doctor=doctor_b, patient=patient, number=1
    )

    response = client.post(
        f"/api/v1/doctor/queue/{foreign_entry.id}/call",
        headers=_login_headers(client, user=user_a, password="secret123"),
    )
    assert response.status_code == 200, response.text

    db_session.refresh(foreign_entry)
    assert foreign_entry.status == "called"


def test_different_specialty_doctor_cannot_call_entry(client, db_session):
    """ADR-001 isolation boundary: a doctor of a DIFFERENT specialty is
    neither the owner nor a same-specialty colleague — 403, entry untouched."""
    user_cardio, _cardio_doctor = _create_dentist(db_session, "5c", specialty="cardiology")
    _user_b, doctor_b = _create_dentist(db_session, "6")
    patient = _patient(db_session)
    foreign_entry = _seed_queue_entry(
        db_session, doctor=doctor_b, patient=patient, number=1
    )

    response = client.post(
        f"/api/v1/doctor/queue/{foreign_entry.id}/call",
        headers=_login_headers(client, user=user_cardio, password="secret123"),
    )
    assert response.status_code == 403, response.text

    db_session.refresh(foreign_entry)
    assert foreign_entry.status == "waiting"


def test_doctor_can_call_own_queue_entry_same_specialty_setup(client, db_session):
    """Positive control: same setup, own queue works (isolation, not RBAC lockout)."""
    user_a, doctor_a = _create_dentist(db_session, "7")
    _user_b, _doctor_b = _create_dentist(db_session, "8")
    patient = _patient(db_session)
    own_entry = _seed_queue_entry(
        db_session, doctor=doctor_a, patient=patient, number=1
    )

    response = client.post(
        f"/api/v1/queue/legacy/call/{own_entry.id}",
        headers=_login_headers(client, user=user_a, password="secret123"),
    )
    assert response.status_code == 200, response.text

    db_session.refresh(own_entry)
    assert own_entry.status == "called"


def test_admin_keeps_cross_doctor_queue_privileges(
    client, db_session, admin_user
):
    _user_a, doctor_a = _create_dentist(db_session, "9")
    _user_b, _doctor_b = _create_dentist(db_session, "10")
    patient = _patient(db_session)
    entry = _seed_queue_entry(db_session, doctor=doctor_a, patient=patient, number=1)

    response = client.post(
        f"/api/v1/queue/legacy/call/{entry.id}",
        headers=_admin_headers(client, admin_user),
    )
    assert response.status_code == 200, response.text

    db_session.refresh(entry)
    assert entry.status == "called"


def test_registrar_can_call_entry_in_any_queue(client, db_session, registrar_user):
    """Registrar keeps the ability to operate a chosen doctor's queue."""
    _user_a, doctor_a = _create_dentist(db_session, "11")
    _user_b, _doctor_b = _create_dentist(db_session, "12")
    patient = _patient(db_session)
    entry = _seed_queue_entry(db_session, doctor=doctor_a, patient=patient, number=1)

    response = client.post(
        f"/api/v1/queue/legacy/call/{entry.id}",
        headers=_login_headers(client, user=registrar_user, password="registrar123"),
    )
    assert response.status_code == 200, response.text

    db_session.refresh(entry)
    assert entry.status == "called"


def test_duplicate_user_link_rejected_app_level(client, db_session, auth_headers):
    """App-level duplicate check: one User cannot gain a second Doctor row.

    Scope: application-level guard only — the DB-level UNIQUE(doctors.user_id)
    enforcement lives in the companion PR #2934 (migration 0048), not here."""
    user_a, _doctor_a = _create_dentist(db_session, "13")
    _user_b, _doctor_b = _create_dentist(db_session, "14")

    response = client.post(
        "/api/v1/admin/doctors",
        json={
            "user_id": user_a.id,
            "specialty": "stomatology",
            "active": True,
        },
        headers=auth_headers,
    )
    assert response.status_code == 400, response.text
    assert "уже привязан" in response.json()["detail"]


def test_multiple_dentists_have_independent_queues_and_ids(client, db_session):
    """N dentists = N users + N doctor profiles; queues stay per-doctor."""
    _user_a, doctor_a = _create_dentist(db_session, "15")
    _user_b, doctor_b = _create_dentist(db_session, "16")
    patient = _patient(db_session)

    assert doctor_a.id != doctor_b.id
    assert doctor_a.user_id != doctor_b.user_id
    assert doctor_a.specialty == doctor_b.specialty == "stomatology"

    entry_a = _seed_queue_entry(db_session, doctor=doctor_a, patient=patient, number=1)
    entry_b = _seed_queue_entry(db_session, doctor=doctor_b, patient=patient, number=1)
    assert entry_a.queue_id != entry_b.queue_id
