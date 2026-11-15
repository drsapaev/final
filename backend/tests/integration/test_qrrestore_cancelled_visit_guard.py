"""QRRESTORE-BE-001 (audit #3892 group 26) — restore-next vs cascade-cancelled visit.

``POST /queue/entry/{entry_id}/restore-next`` restores ``no_show`` AND
``cancelled`` tickets by setting ``status='waiting'``/``priority=1`` —
without ever reading the linked Visit. The canonical
``OnlineQueueNewService.cancel_entry`` cancels a queue entry AND its
linked Visit (cascade ``_cascade_linked_visit_cancel``: visit →
``canceled``) and releases the pending invoice in one transaction.
Restoring just the queue row afterwards leaves ``entry.status='waiting'``
anchored to ``Visit.status='canceled'`` — a state the irreversible visit
lifecycle cannot start — while the operator has already been told the
ticket is restored.

Policy enforced here (audit's deny branch): a ``cancelled`` entry whose
linked Visit is ``canceled`` is NOT restorable — actionable 409, zero
mutation, operator should create a new appointment. Positive controls:
``no_show`` → ``waiting`` (no cancelled visit) and a ``cancelled`` entry
WITHOUT a cascade-cancelled visit keep restoring as before.

Run: pytest backend/tests/integration/test_qrrestore_cancelled_visit_guard.py -v
"""
from __future__ import annotations

import asyncio
from datetime import date
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit
from app.services.online_queue_new_service import OnlineQueueNewService


def _mk_user(db, role: str = "Registrar") -> User:
    suffix = uuid4().hex[:8]
    user = User(
        username=f"{role.lower()}_{suffix}",
        email=f"{role.lower()}_{suffix}@t.local",
        full_name=f"Test {role}",
        hashed_password="x",
        role=role,
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.flush()
    return user


def _mk_doctor(db, user: User, specialty: str = "cardiology") -> Doctor:
    doctor = Doctor(user_id=user.id, specialty=specialty, active=True)
    db.add(doctor)
    db.flush()
    return doctor


def _mk_patient(db) -> Patient:
    patient = Patient(
        last_name="Тестов",
        first_name="Пациент",
        birth_date=date(1990, 1, 1),
        sex="M",
        # synthetic fixed phone — no real-looking numbers in fixtures
        phone="+998900000000",
        email=f"p_{uuid4().hex[:8]}@t.local",
        is_deleted=False,
    )
    db.add(patient)
    db.flush()
    return patient


def _mk_visit(db, patient: Patient, doctor: Doctor) -> Visit:
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=date.today(),
        status="open",
        source="desk",
    )
    db.add(visit)
    db.flush()
    return visit


def _mk_queue(db, owner: Doctor) -> DailyQueue:
    queue = DailyQueue(
        day=date.today(),
        specialist_id=owner.id,
        queue_tag=f"tag_{uuid4().hex[:8]}",
        active=True,
    )
    db.add(queue)
    db.flush()
    return queue


def _mk_entry(db, queue: DailyQueue, patient: Patient, *, visit: Visit | None,
              status: str = "waiting", number: int = 1) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=number,
        patient_id=patient.id,
        visit_id=visit.id if visit else None,
        status=status,
    )
    db.add(entry)
    db.flush()
    return entry


class FakeManager:
    """Silences display broadcasts inside tests.

    Module-level so the class identity is stable; installed via the
    ``monkeypatch`` fixture ONLY — never with patch().start()/stop():
    mock silently tolerates stop() on an unstarted patcher, so a
    start/stop pair built from two separate helper calls leaks the fake
    into every later test in the worker (poisons the display-manager
    singleton path used by real WS e2e tests).
    """

    connections: list = []

    async def broadcast_queue_update(self, **kwargs):
        pass


def _install_fake_ws(monkeypatch):
    """Silence display/admin websocket broadcasts (unit-scope side effects)."""
    from app.services import display_websocket as dw
    from app.ws import queue_ws

    monkeypatch.setattr(dw, "get_display_manager", lambda: FakeManager())
    monkeypatch.setattr(queue_ws, "broadcast_queue_update", lambda **k: None)


@pytest.mark.integration
class TestRestoreNextCancelledVisitGuard:
    def test_cancelled_entry_with_cascade_cancelled_visit_denied(
        self, db_session, monkeypatch
    ):
        """QRRESTORE-BE-001 RED: canonical cancel cascades the linked Visit
        to canceled; restore-next must NOT resurrect the ticket — 409,
        entry stays cancelled, visit stays canceled."""
        _install_fake_ws(monkeypatch)
        owner = _mk_user(db_session, role="Doctor")
        doctor = _mk_doctor(db_session, owner)
        patient = _mk_patient(db_session)
        visit = _mk_visit(db_session, patient, doctor)
        queue = _mk_queue(db_session, doctor)
        entry = _mk_entry(db_session, queue, patient, visit=visit, number=1)
        db_session.commit()

        service = OnlineQueueNewService(db_session)
        service.cancel_entry(entry_id=entry.id, current_user=owner, reason="test cascade")
        db_session.refresh(entry)
        db_session.refresh(visit)
        assert entry.status == "cancelled"
        assert visit.status == "canceled"

        from app.api.v1.endpoints.qr_queue._entries import restore_entry_to_next
        from app.api.v1.endpoints.qr_queue._tokens import RestoreToNextRequest

        async def scenario():
            return await restore_entry_to_next(
                entry.id,
                request=RestoreToNextRequest(reason="вернулся"),
                db=db_session,
                current_user=owner,
            )

        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(scenario())
        assert excinfo.value.status_code == 409, excinfo.value.detail

        db_session.refresh(entry)
        db_session.refresh(visit)
        assert entry.status == "cancelled", entry.status
        assert visit.status == "canceled", visit.status

    def test_no_show_without_cancelled_visit_still_restores(
        self, db_session, monkeypatch
    ):
        """Positive control (audit): no_show → waiting keeps working."""
        _install_fake_ws(monkeypatch)
        owner = _mk_user(db_session, role="Doctor")
        doctor = _mk_doctor(db_session, owner)
        patient = _mk_patient(db_session)
        queue = _mk_queue(db_session, doctor)
        entry = _mk_entry(
            db_session, queue, patient, visit=None, status="no_show", number=1
        )
        db_session.commit()

        from app.api.v1.endpoints.qr_queue._entries import restore_entry_to_next
        from app.api.v1.endpoints.qr_queue._tokens import RestoreToNextRequest

        result = asyncio.run(
            restore_entry_to_next(
                entry.id,
                request=RestoreToNextRequest(reason="вернулся"),
                db=db_session,
                current_user=owner,
            )
        )
        assert result["success"] is True
        db_session.refresh(entry)
        assert entry.status == "waiting"
        assert entry.priority == 1

    def test_cancelled_entry_without_cascade_visit_still_restores(
        self, db_session, monkeypatch
    ):
        """Positive: a cancelled entry WITHOUT a cascade-cancelled visit
        (no visit link) is not falsely denied — restore keeps working."""
        _install_fake_ws(monkeypatch)
        owner = _mk_user(db_session, role="Doctor")
        doctor = _mk_doctor(db_session, owner)
        patient = _mk_patient(db_session)
        queue = _mk_queue(db_session, doctor)
        entry = _mk_entry(db_session, queue, patient, visit=None, status="waiting", number=1)
        db_session.commit()

        service = OnlineQueueNewService(db_session)
        service.cancel_entry(entry_id=entry.id, current_user=owner, reason="no visit link")
        db_session.refresh(entry)
        assert entry.status == "cancelled"

        from app.api.v1.endpoints.qr_queue._entries import restore_entry_to_next
        from app.api.v1.endpoints.qr_queue._tokens import RestoreToNextRequest

        result = asyncio.run(
            restore_entry_to_next(
                entry.id,
                request=RestoreToNextRequest(reason="вернулся"),
                db=db_session,
                current_user=owner,
            )
        )
        assert result["success"] is True
        db_session.refresh(entry)
        assert entry.status == "waiting"
