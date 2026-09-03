"""Regression tests for the batch_patient_service active-entry filtering defect.

P2-2 (post-merge stabilization): the original defect was that
``BatchPatientService._update_entry`` and ``_cancel_entry`` could
mutate a terminal (cancelled/served/no_show) OnlineQueueEntry because
``_find_online_queue_entry_for_action`` had NO status filter and
``_update_entry``/``_cancel_entry`` directly set ``entry.status``
without checking terminal state.

Consequence:
- A cancelled queue entry could be RESURRECTED by a batch update
  action with status='called' (or any other active status).
- A double-cancel on a cancelled entry silently returned
  success='cancelled', misleading the caller.

Invariant:
  Terminal queue statuses ('cancelled', 'served', 'no_show',
  'incomplete', 'rescheduled') must NOT be silently regressed by
  a batch update or cancel action.

Fix:
- Added ``TERMINAL_QUEUE_STATUSES`` and ``is_terminal_queue()`` to
  ``app/services/queue_status.py`` (reuses existing canonical
  vocabulary — does NOT introduce a competing "active" definition).
- ``_update_entry`` and ``_cancel_entry`` now reject terminal queue
  entries with ``error_code='entry_already_terminal'``.

The visit path was already protected by ``VisitLifecycleService.transition_status``
(state machine enforces terminal→non-terminal rejection) — no change
needed there.

These regression tests use SQLite (sufficient for state-machine
semantics). Concurrency aspects are covered by Gate D.

Run:
    pytest backend/tests/regression/test_p2_2_batch_terminal_entry.py -v
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_p2_2_regression.db")
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-p2-2-regression-32-chars")
os.environ.setdefault("ALLOW_SQLITE_DATABASE_URL", "1")
os.environ.setdefault("TESTING", "1")

from app.db.base_class import Base  # noqa: E402
from app.models import (  # noqa: F401
    audit, appointment, clinic, emr_v2, lab, online_queue,
    payment, payment_invoice, payment_webhook, patient, user, visit,
)
from app.models import (  # noqa: F401
    authentication, billing, department, emr, file_system,
    role_permission, schedule, user_profile,
)
from app.models.clinic import Doctor  # noqa: E402
from app.models.online_queue import DailyQueue, OnlineQueueEntry  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.visit import Visit  # noqa: E402
from app.services.batch_patient_service import (  # noqa: E402
    BatchPatientService,
    BatchUpdateRequest,
    EntryAction,
)


# ─── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db_engine():
    db_path = BACKEND_DIR / "test_p2_2_regression.db"
    if db_path.exists():
        db_path.unlink()

    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    yield engine

    Base.metadata.drop_all(engine)
    engine.dispose()
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def session_factory(db_engine):
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)

    def _create():
        return Session()

    return _create


@pytest.fixture
def clean_db(db_engine):
    with db_engine.connect() as conn:
        for table in [
            "queue_entries",
            "visit_services",
            "visits",
            "daily_queues",
            "services",
            "doctors",
            "patients",
            "users",
        ]:
            conn.execute(__import__("sqlalchemy").text(f"DELETE FROM {table}"))
        conn.commit()


def _setup_patient_and_queue(session):
    """Create patient + doctor + daily_queue. Returns (patient_id, daily_queue_id, doctor_user_id)."""
    unique = uuid.uuid4().hex[:8]
    doctor_user = User(
        username=f"doctor_{unique}",
        full_name="Reg Doctor",
        email=f"doctor_{unique}@test.local",
        hashed_password="x",
        role="Doctor",
        is_active=True,
        is_superuser=False,
        must_change_password=False,
        created_at=datetime.now(UTC),
    )
    session.add(doctor_user)
    session.flush()

    doctor = Doctor(user_id=doctor_user.id, specialty="Cardiology", active=True)
    session.add(doctor)
    session.flush()

    patient = Patient(
        last_name="Reg",
        first_name="Patient",
        birth_date=date(1990, 1, 1),
        sex="M",
        phone=f"+998900000000",
        email=f"patient_{unique}@test.local",
        created_at=datetime.now(UTC),
        is_deleted=False,
    )
    session.add(patient)
    session.flush()

    daily_queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor_user.id,
        queue_tag=f"reg_cardio_{unique}",
        active=True,
    )
    session.add(daily_queue)
    session.flush()
    session.commit()
    # Return IDs (not ORM objects) to avoid DetachedInstanceError after close.
    return patient.id, daily_queue.id, doctor_user.id


# ─── Regression Tests ──────────────────────────────────────────────────

class TestP22BatchTerminalEntry:
    """P2-2: batch_patient_service terminal-entry filtering regression tests."""

    def test_update_on_cancelled_queue_entry_is_rejected(
        self, session_factory, clean_db
    ):
        """REGRESSION: update action on a cancelled queue entry must be rejected.

        Before fix: _find_online_queue_entry_for_action returned the cancelled
        entry (no status filter), _update_entry set entry.status = 'called',
        RESURRECTING the terminal entry.

        After fix: _update_entry checks is_terminal_queue(entry.status) and
        returns EntryResult(status='error', error_code='entry_already_terminal').
        """
        setup = session_factory()
        patient_id, daily_queue_id, _ = _setup_patient_and_queue(setup)
        setup.close()

        # Create a CANCELLED queue entry
        setup2 = session_factory()
        cancelled_entry = OnlineQueueEntry(
            queue_id=daily_queue_id,
            number=1,
            patient_id=patient_id,
            patient_name="Reg Patient",
            phone="+998900000000",
            source="desk",
            status="cancelled",
        )
        setup2.add(cancelled_entry)
        setup2.commit()
        setup2.refresh(cancelled_entry)
        entry_id = cancelled_entry.id
        setup2.close()

        # Reproducer: try to update the cancelled entry
        repro = session_factory()
        service = BatchPatientService(repro)
        request = BatchUpdateRequest(
            entries=[
                EntryAction(
                    id=entry_id,
                    entry_type="online_queue",
                    action="update",
                    status="called",
                )
            ]
        )
        result = service.batch_update(patient_id, date.today(), request)
        repro.close()

        # ─── THE REGRESSION ASSERTIONS ─────────────────────────────
        # 1. Batch must report failure (one entry errored).
        assert result.success is False, (
            "Batch update on a terminal queue entry must fail, not silently succeed."
        )
        # 2. EntryResult must be 'error' with 'entry_already_terminal' code.
        assert len(result.updated_entries) == 1
        er = result.updated_entries[0]
        assert er.status == "error", (
            f"Expected EntryResult.status='error', got {er.status!r}"
        )
        assert er.error_code == "entry_already_terminal", (
            f"Expected error_code='entry_already_terminal', got {er.error_code!r}"
        )

        # ─── NEW INDEPENDENT SESSION VERIFICATION ─────────────────
        verify = session_factory()
        entry = verify.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.id == entry_id
        ).first()
        assert entry.status == "cancelled", (
            f"Cancelled entry was RESURRECTED to {entry.status!r}. "
            f"Terminal queue status must NOT be mutated by batch update."
        )
        verify.close()

    def test_cancel_on_cancelled_queue_entry_is_rejected(
        self, session_factory, clean_db
    ):
        """REGRESSION: cancel action on an already-cancelled queue entry
        must be rejected (not silently idempotent).

        Before fix: double-cancel returned success='cancelled', misleading
        the caller into thinking a real mutation happened.

        After fix: returns EntryResult(status='error', error_code='entry_already_terminal').
        """
        setup = session_factory()
        patient_id, daily_queue_id, _ = _setup_patient_and_queue(setup)
        setup.close()

        setup2 = session_factory()
        cancelled_entry = OnlineQueueEntry(
            queue_id=daily_queue_id,
            number=1,
            patient_id=patient_id,
            patient_name="Reg Patient",
            phone="+998900000000",
            source="desk",
            status="cancelled",
        )
        setup2.add(cancelled_entry)
        setup2.commit()
        setup2.refresh(cancelled_entry)
        entry_id = cancelled_entry.id
        setup2.close()

        repro = session_factory()
        service = BatchPatientService(repro)
        request = BatchUpdateRequest(
            entries=[
                EntryAction(
                    id=entry_id,
                    entry_type="online_queue",
                    action="cancel",
                    reason="double cancel test",
                )
            ]
        )
        result = service.batch_update(patient_id, date.today(), request)
        repro.close()

        assert result.success is False, (
            "Double-cancel on a terminal queue entry must fail."
        )
        er = result.updated_entries[0]
        assert er.status == "error"
        assert er.error_code == "entry_already_terminal"

        # Verify status unchanged
        verify = session_factory()
        entry = verify.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.id == entry_id
        ).first()
        assert entry.status == "cancelled"
        verify.close()

    def test_update_on_served_queue_entry_is_rejected(
        self, session_factory, clean_db
    ):
        """REGRESSION: update on 'served' queue entry must be rejected.
        'served' is terminal (canonical status meaning the patient was served).
        """
        setup = session_factory()
        patient_id, daily_queue_id, _ = _setup_patient_and_queue(setup)
        setup.close()

        setup2 = session_factory()
        served_entry = OnlineQueueEntry(
            queue_id=daily_queue_id,
            number=1,
            patient_id=patient_id,
            patient_name="Reg Patient",
            phone="+998900000000",
            source="desk",
            status="served",  # terminal
        )
        setup2.add(served_entry)
        setup2.commit()
        setup2.refresh(served_entry)
        entry_id = served_entry.id
        setup2.close()

        repro = session_factory()
        service = BatchPatientService(repro)
        request = BatchUpdateRequest(
            entries=[
                EntryAction(
                    id=entry_id,
                    entry_type="online_queue",
                    action="update",
                    status="waiting",  # trying to resurrect
                )
            ]
        )
        result = service.batch_update(patient_id, date.today(), request)
        repro.close()

        assert result.success is False
        er = result.updated_entries[0]
        assert er.status == "error"
        assert er.error_code == "entry_already_terminal"

        verify = session_factory()
        entry = verify.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.id == entry_id
        ).first()
        assert entry.status == "served", (
            f"Served entry was RESURRECTED to {entry.status!r}"
        )
        verify.close()

    def test_update_on_active_queue_entry_still_works(
        self, session_factory, clean_db
    ):
        """NON-REGRESSION: update on an ACTIVE queue entry must still work.

        Ensures the terminal-status check doesn't accidentally reject
        legitimate updates on active entries.
        """
        setup = session_factory()
        patient_id, daily_queue_id, _ = _setup_patient_and_queue(setup)
        setup.close()

        setup2 = session_factory()
        active_entry = OnlineQueueEntry(
            queue_id=daily_queue_id,
            number=1,
            patient_id=patient_id,
            patient_name="Reg Patient",
            phone="+998900000000",
            source="desk",
            status="waiting",  # active
        )
        setup2.add(active_entry)
        setup2.commit()
        setup2.refresh(active_entry)
        entry_id = active_entry.id
        setup2.close()

        repro = session_factory()
        service = BatchPatientService(repro)
        request = BatchUpdateRequest(
            entries=[
                EntryAction(
                    id=entry_id,
                    entry_type="online_queue",
                    action="update",
                    status="called",  # legitimate active→active transition
                )
            ]
        )
        result = service.batch_update(patient_id, date.today(), request)
        repro.close()

        assert result.success is True, (
            f"Update on active entry must succeed. Got: {result}"
        )
        er = result.updated_entries[0]
        assert er.status == "updated"

        verify = session_factory()
        entry = verify.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.id == entry_id
        ).first()
        assert entry.status == "called", (
            f"Active entry was not updated. Got: {entry.status!r}"
        )
        verify.close()

    def test_cancel_on_active_queue_entry_still_works(
        self, session_factory, clean_db
    ):
        """NON-REGRESSION: cancel on an ACTIVE queue entry must still work."""
        setup = session_factory()
        patient_id, daily_queue_id, _ = _setup_patient_and_queue(setup)
        setup.close()

        setup2 = session_factory()
        active_entry = OnlineQueueEntry(
            queue_id=daily_queue_id,
            number=1,
            patient_id=patient_id,
            patient_name="Reg Patient",
            phone="+998900000000",
            source="desk",
            status="waiting",  # active
        )
        setup2.add(active_entry)
        setup2.commit()
        setup2.refresh(active_entry)
        entry_id = active_entry.id
        setup2.close()

        repro = session_factory()
        service = BatchPatientService(repro)
        request = BatchUpdateRequest(
            entries=[
                EntryAction(
                    id=entry_id,
                    entry_type="online_queue",
                    action="cancel",
                    reason="patient request",
                )
            ]
        )
        result = service.batch_update(patient_id, date.today(), request)
        repro.close()

        assert result.success is True
        er = result.updated_entries[0]
        assert er.status == "cancelled"

        verify = session_factory()
        entry = verify.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.id == entry_id
        ).first()
        assert entry.status == "cancelled"
        verify.close()

    def test_update_on_closed_visit_is_rejected_by_state_machine(
        self, session_factory, clean_db
    ):
        """NON-REGRESSION (visit path was already protected):
        update on a CLOSED visit must be rejected by VisitLifecycleService.

        This test documents that the visit path was already correctly
        protected by the state machine — no P2-2 fix was needed there.
        """
        setup = session_factory()
        patient_id, _, doctor_user_id = _setup_patient_and_queue(setup)

        # Create a closed visit
        setup2 = session_factory()
        closed_visit = Visit(
            patient_id=patient_id,
            doctor_id=doctor_user_id,
            status="closed",  # terminal visit status
            visit_date=date.today(),
            visit_time="10:00",
            discount_mode="none",
            department="cardiology",
            created_at=datetime.now(UTC),
        )
        setup2.add(closed_visit)
        setup2.commit()
        setup2.refresh(closed_visit)
        visit_id = closed_visit.id
        setup2.close()

        repro = session_factory()
        service = BatchPatientService(repro)
        request = BatchUpdateRequest(
            entries=[
                EntryAction(
                    id=visit_id,
                    entry_type="visit",
                    action="update",
                    status="in_progress",  # trying to reopen
                )
            ]
        )
        result = service.batch_update(patient_id, date.today(), request)
        repro.close()

        # Visit path: state machine rejects, batch records as error
        assert result.success is False
        er = result.updated_entries[0]
        assert er.status == "error"
        assert "Invalid status transition" in (er.error or "")

        # Verify visit remains closed
        verify = session_factory()
        v = verify.query(Visit).filter(Visit.id == visit_id).first()
        assert v.status == "closed"
        verify.close()
