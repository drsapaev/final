"""
QPOSAUTH-BE-001 / QPOSAUTH-BE-002 (audit PR #3961 round 29) — fail-first.

- QPOSAUTH-BE-001 (P1): `GET /queue/position/stats/queue/{queue_id}` required
  only `get_current_user` — any authenticated user could iterate numeric queue
  IDs and enumerate every entry of any queue (entry IDs, numbers, statuses,
  priorities, timestamps, cabinet, specialist name). The response carries no
  patient name/diagnosis/phone (the dossier explicitly warns not to overclaim
  that), but the operational queue records themselves are not the caller's to
  read. Staff-only access mirrors the module's own policy for the notify
  endpoints (`require_roles("Admin", "Registrar", "Doctor")`).
- QPOSAUTH-BE-002 (P2): the per-entry and by-number endpoints ran the patient
  ownership check only when `entry.patient_id` was truthy, so a non-staff user
  could read ANY unlinked (QR walk-in / legacy) entry by global ID or by
  (number, specialist) scanning. Absence of a patient linkage is not proof of
  ownership — non-staff reads of unlinked entries fail closed.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from uuid import uuid4

import pytest

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.user import User
from app.crud.clinic import clinic_today

def _suffix() -> str:
    return uuid4().hex[:10]


# Synthetic-account passwords reuse the literals already accepted across
# the integration suites (tests/conftest.py) — no new credential material.
_ROLE_PASSWORDS = {
    "Patient": "patient123",
    "Registrar": "registrar123",
    "Doctor": "doctor123",
}


def _create_user(db_session, *, label: str, role: str) -> User:
    suffix = _suffix()
    user = User(
        username=f"qpos_{label}_{suffix}",
        email=f"qpos-{label}-{suffix}@test.local",
        full_name=f"Queue Position {label}",
        hashed_password=get_password_hash(_ROLE_PASSWORDS[role]),
        role=role,
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_patient_with_profile(db_session, *, label: str) -> tuple[User, Patient]:
    user = _create_user(db_session, label=label, role="Patient")
    patient = Patient(
        user_id=user.id,
        first_name=f"Patient {label}",
        last_name="QueuePosAuth",
        phone=f"+99890{_suffix()[:7]}",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return user, patient


def _create_queue_with_entries(
    db_session,
) -> tuple[Doctor, DailyQueue, OnlineQueueEntry, OnlineQueueEntry, OnlineQueueEntry]:
    suffix = _suffix()
    doctor_user = _create_user(db_session, label="doc", role="Doctor")
    doctor = Doctor(user_id=doctor_user.id, specialty="general", active=True, cabinet="101")
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)

    queue = DailyQueue(
        # The position endpoints resolve the day through the clinic_today SSOT
        # (queue settings timezone), not the host clock — bind the synthetic
        # queue to that day so the by-number lookup is wall-clock robust.
        day=clinic_today(db_session),
        specialist_id=doctor.id,
        queue_tag=f"qpos-auth-{suffix}",
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)

    base_time = datetime.combine(date.today(), time(9, 0))
    unlinked = OnlineQueueEntry(
        queue_id=queue.id,
        number=1,
        patient_name="Unlinked Walk-in",
        phone="+998900000001",
        source="desk",
        status="waiting",
        queue_time=base_time,
    )
    linked = OnlineQueueEntry(
        queue_id=queue.id,
        number=2,
        patient_name="Linked Patient",
        phone="+998900000002",
        source="desk",
        status="waiting",
        queue_time=base_time + timedelta(minutes=1),
    )
    db_session.add_all([unlinked, linked])
    db_session.commit()
    db_session.refresh(unlinked)
    db_session.refresh(linked)
    # A second, terminal-status entry so the stats payload has more than one row.
    served = OnlineQueueEntry(
        queue_id=queue.id,
        number=3,
        patient_name="Served Patient",
        phone="+998900000003",
        source="desk",
        status="served",
        queue_time=base_time + timedelta(minutes=2),
    )
    db_session.add(served)
    db_session.commit()
    db_session.refresh(served)
    return doctor, queue, unlinked, linked, served


def _headers(client, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={
            "username": user.username,
            "password": _ROLE_PASSWORDS[str(getattr(user, "role", ""))],
        },
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.integration
class TestQPOSAUTHBE001StatsEndpointAccess:
    def test_patient_is_denied_the_full_queue_stats_of_a_foreign_queue(self, client, db_session):
        """QPOSAUTH-BE-001: an unrelated patient cannot enumerate a queue."""
        patient_a_user, _patient_a = _create_patient_with_profile(db_session, label="A")
        _doctor, queue, _unlinked, _linked, _served = _create_queue_with_entries(db_session)

        response = client.get(
            f"/api/v1/queue/position/stats/queue/{queue.id}",
            headers=_headers(client, patient_a_user),
        )
        assert response.status_code == 403, response.text

    def test_registrar_still_reads_the_full_queue_stats(self, client, db_session):
        """Control: the intended staff audience keeps access."""
        registrar = _create_user(db_session, label="reg", role="Registrar")
        _doctor, queue, _unlinked, _linked, _served = _create_queue_with_entries(db_session)

        response = client.get(
            f"/api/v1/queue/position/stats/queue/{queue.id}",
            headers=_headers(client, registrar),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["queue_id"] == queue.id
        # The stats list carries the active (waiting) entries of the queue.
        assert body["total_entries"] >= 2


@pytest.mark.integration
class TestQPOSAUTHBE002UnlinkedEntryOwnership:
    def test_patient_is_denied_an_unlinked_entry_by_global_id(self, client, db_session):
        """QPOSAUTH-BE-002: patient_id=NULL entries fail closed for non-staff."""
        patient_a_user, _patient_a = _create_patient_with_profile(db_session, label="A")
        _doctor, queue, unlinked, _linked, _served = _create_queue_with_entries(db_session)
        assert unlinked.patient_id is None

        response = client.get(
            f"/api/v1/queue/position/{unlinked.id}",
            headers=_headers(client, patient_a_user),
        )
        assert response.status_code == 403, response.text
        assert unlinked.queue_id == queue.id

    def test_patient_is_denied_an_unlinked_entry_by_number_lookup(self, client, db_session):
        """QPOSAUTH-BE-002: number+specialist scanning cannot fetch walk-in rows."""
        patient_a_user, _patient_a = _create_patient_with_profile(db_session, label="A")
        doctor, _queue, unlinked, _linked, _served = _create_queue_with_entries(db_session)

        response = client.get(
            f"/api/v1/queue/position/by-number/{unlinked.number}?specialist_id={doctor.id}",
            headers=_headers(client, patient_a_user),
        )
        assert response.status_code == 403, response.text

    def test_patient_still_reads_their_own_linked_entry(self, client, db_session):
        """Control: the legitimate patient self-read path is untouched."""
        patient_a_user, patient_a = _create_patient_with_profile(db_session, label="A")
        _doctor, _queue, _unlinked, linked, _served = _create_queue_with_entries(db_session)
        linked.patient_id = patient_a.id
        db_session.commit()
        db_session.refresh(linked)

        response = client.get(
            f"/api/v1/queue/position/{linked.id}",
            headers=_headers(client, patient_a_user),
        )
        assert response.status_code == 200, response.text
        assert response.json()["entry_id"] == linked.id

    def test_patient_b_cannot_read_patient_a_linked_entry(self, client, db_session):
        """Control: cross-patient reads stay denied (pre-existing guard)."""
        _patient_a_user, patient_a = _create_patient_with_profile(db_session, label="A")
        patient_b_user, _patient_b = _create_patient_with_profile(db_session, label="B")
        _doctor, _queue, _unlinked, linked, _served = _create_queue_with_entries(db_session)
        linked.patient_id = patient_a.id
        db_session.commit()
        db_session.refresh(linked)

        response = client.get(
            f"/api/v1/queue/position/{linked.id}",
            headers=_headers(client, patient_b_user),
        )
        assert response.status_code == 403, response.text

    def test_registrar_still_reads_an_unlinked_entry(self, client, db_session):
        """Control: staff keeps full read access to walk-in rows."""
        registrar = _create_user(db_session, label="reg2", role="Registrar")
        _doctor, _queue, unlinked, _linked, _served = _create_queue_with_entries(db_session)

        response = client.get(
            f"/api/v1/queue/position/{unlinked.id}",
            headers=_headers(client, registrar),
        )
        assert response.status_code == 200, response.text
        assert response.json()["entry_id"] == unlinked.id
