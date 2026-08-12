"""Regression tests for P2-1b: over-broad rollback in _assign_queues_for_visit.

P2-1b (post-merge stabilization): the original code called self.db.rollback()
on any per-queue_tag failure, which discarded ALL staged work — including
successful entries from earlier tags. The loop then continued with stale
queue_assignments, causing the visit to be activated with incomplete
queue entries.

Fix: use savepoints (begin_nested) per queue_tag so that a failure in
one tag only rolls back that tag's work, not the whole transaction.

Target contract (confirmed by user):
    A succeeds → A exists in DB
    B fails (flush-time IntegrityError) → B does NOT exist in DB
    C succeeds → C exists in DB
    queue_assignments = [A, C] (no stale data)
    visit may become open (existing business policy: partial assignment OK)
    final commit persists exactly A + C

Critical invariant for PostgreSQL:
    flush failure in queue_tag B
    → SAVEPOINT rollback
    → Session remains usable
    → queue_tag C can execute
    → final commit succeeds

Run:
    pytest backend/tests/regression/test_p2_1b_over_broad_rollback.py -v
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_p2_1b_regression.db")
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-p2-1b-regression-32-chars")
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
from app.models.service import Service  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.visit import Visit, VisitService  # noqa: E402
from app.services.morning_assignment import MorningAssignmentService  # noqa: E402


@pytest.fixture(scope="module")
def db_engine():
    db_path = BACKEND_DIR / "test_p2_1b_regression.db"
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
            "queue_entries", "visit_services", "visits",
            "daily_queues", "services", "doctors", "patients", "users",
        ]:
            conn.execute(__import__("sqlalchemy").text(f"DELETE FROM {table}"))
        conn.commit()


def _setup_visit_with_three_tags(session):
    """Create a visit with 3 services (A, B, C), each with a different queue_tag
    and a corresponding DailyQueue. Returns (visit_id, [tag_a, tag_b, tag_c]).
    """
    unique = uuid.uuid4().hex[:8]
    doctor_user = User(
        username=f"doctor_{unique}", full_name="Dr", email=f"d_{unique}@t.local",
        hashed_password="x", role="Doctor", is_active=True, is_superuser=False,
        must_change_password=False, created_at=datetime.now(UTC),
    )
    session.add(doctor_user)
    session.flush()
    doctor = Doctor(user_id=doctor_user.id, specialty="Cardiology", active=True)
    session.add(doctor)
    session.flush()
    patient = Patient(
        last_name="P", first_name="Patient", birth_date=date(1990, 1, 1),
        sex="M", phone="+998901234567", email=f"p_{unique}@t.local",
        created_at=datetime.now(UTC), is_deleted=False,
    )
    session.add(patient)
    session.flush()

    tags = []
    services = []
    queues = []
    for label in ["a", "b", "c"]:
        tag = f"tag_{label}_{unique}"
        tags.append(tag)
        svc = Service(
            code=f"SVC_{label}_{unique}", name=f"Service {label}", price=10000,
            duration_minutes=30, active=True, requires_doctor=True,
            queue_tag=tag, is_consultation=True,
            allow_doctor_price_override=False,
        )
        services.append(svc)
        session.add(svc)
        session.flush()
        q = DailyQueue(day=date.today(), specialist_id=doctor_user.id,
                       queue_tag=tag, active=True)
        queues.append(q)
        session.add(q)
    session.flush()

    visit = Visit(
        patient_id=patient.id, doctor_id=doctor.id, status="confirmed",
        visit_date=date.today(), visit_time="10:00", discount_mode="none",
        department="cardiology", confirmation_token=f"tok-{unique}",
        confirmation_channel="telegram", confirmed_at=datetime.now(UTC),
        confirmation_expires_at=datetime.now(UTC), created_at=datetime.now(UTC),
    )
    session.add(visit)
    session.flush()
    for svc in services:
        vs = VisitService(visit_id=visit.id, service_id=svc.id, code=svc.code,
                          name=svc.name, qty=1, price=svc.price, currency="UZS")
        session.add(vs)
    session.commit()
    return visit.id, tags


def _patch_create_queue_entry_to_fail_on_tag(service_obj, fail_tag_fragment):
    """Monkey-patch _assign_single_queue to inject a real flush-time
    IntegrityError when processing the tag containing fail_tag_fragment.

    The patch intercepts _assign_single_queue and, for the failing tag,
    creates an OnlineQueueEntry with an invalid FK (queue_id=999999)
    and calls db.flush() — triggering a REAL IntegrityError at the
    DB level, exactly like a constraint violation on PostgreSQL.

    For non-failing tags, the original _assign_single_queue runs normally.

    This is NOT a post-success exception — the failure occurs DURING
    the flush, before _assign_single_queue returns.
    """
    original_assign = service_obj._assign_single_queue

    def patched_assign(visit, queue_tag, target_date, *, source="morning_assignment"):
        if fail_tag_fragment in queue_tag:
            # Create an entry with invalid FK → flush will fail
            entry = OnlineQueueEntry(
                queue_id=999999,  # non-existent FK → IntegrityError
                number=1,
                patient_id=visit.patient_id,
                patient_name="Test",
                visit_id=visit.id,
                source=source,
                status="waiting",
            )
            service_obj.db.add(entry)
            service_obj.db.flush()  # ← raises IntegrityError at flush time
            # This line is never reached — flush raises
            return {"queue_tag": queue_tag, "number": 1}
        return original_assign(visit, queue_tag, target_date, source=source)

    service_obj._assign_single_queue = patched_assign

    def restore():
        service_obj._assign_single_queue = original_assign

    return restore


@pytest.mark.unit
class TestP21bSavepointIsolation:
    """P2-1b: savepoint isolation prevents over-broad rollback.

    Target contract:
        A succeeds → A exists in DB
        B fails (flush-time IntegrityError) → B does NOT exist
        C succeeds → C exists in DB
        queue_assignments = [A, C] (no stale data)
        visit may become open (existing business policy)
        final commit persists exactly A + C
    """

    def test_flush_time_failure_preserves_successful_entry(
        self, session_factory, clean_db
    ):
        """REGRESSION: when tag B fails during flush (IntegrityError),
        tag A's entry must be preserved.

        Before fix: self.db.rollback() destroyed A's flushed entry.
        After fix: savepoint.rollback() only rolls back B; A survives.

        This test uses a REAL flush-time IntegrityError (invalid FK),
        not a post-success exception injection.
        """
        setup = session_factory()
        visit_id, tags = _setup_visit_with_three_tags(setup)
        setup.close()

        repro = session_factory()
        service = MorningAssignmentService(repro)

        # Patch create_queue_entry to fail on tag B with a real flush-time error
        restore = _patch_create_queue_entry_to_fail_on_tag(service, tags[1])

        visit = repro.query(Visit).filter(Visit.id == visit_id).first()
        queue_assignments = service._assign_queues_for_visit(visit, date.today())

        repro.commit()
        repro.close()
        restore()  # remove the monkey-patch

        # ─── Verify in NEW independent session ─────────────────────
        verify = session_factory()
        try:
            entries = verify.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.visit_id == visit_id
            ).all()

            # A and C must exist; B must NOT exist
            entry_tags = set()
            for entry in entries:
                queue = verify.query(DailyQueue).filter(
                    DailyQueue.id == entry.queue_id
                ).first()
                if queue:
                    entry_tags.add(queue.queue_tag)

            assert tags[0] in entry_tags, (
                f"Tag A ({tags[0]}) entry was NOT preserved after tag B failure. "
                f"The over-broad rollback destroyed it. "
                f"Entry tags found: {entry_tags}"
            )
            assert tags[1] not in entry_tags, (
                f"Tag B ({tags[1]}) entry exists — should have been rolled back. "
                f"Entry tags found: {entry_tags}"
            )
            assert tags[2] in entry_tags, (
                f"Tag C ({tags[2]}) entry was NOT created after tag B failure. "
                f"Session may be unusable after savepoint rollback. "
                f"Entry tags found: {entry_tags}"
            )

            # queue_assignments must contain only A and C (no stale B)
            assert len(queue_assignments) == 2, (
                f"Expected 2 assignments (A + C), got {len(queue_assignments)}. "
                f"queue_assignments may contain stale data for failed tag B."
            )
        finally:
            verify.close()

    def test_session_remains_usable_after_savepoint_rollback(
        self, session_factory, clean_db
    ):
        """CRITICAL: after a flush-time failure in tag B, the session must
        remain usable so tag C can execute.

        This is the PostgreSQL-specific concern: on PostgreSQL, a constraint
        violation during INSERT puts the transaction in an error state.
        With SAVEPOINT, the savepoint rollback restores the transaction to
        a usable state, allowing subsequent operations.

        Without savepoint (old code): self.db.rollback() rolls back the
        ENTIRE transaction, and subsequent flush calls would work but
        destroy earlier work. With savepoint: only B is rolled back;
        A is preserved and C can proceed.
        """
        setup = session_factory()
        visit_id, tags = _setup_visit_with_three_tags(setup)
        setup.close()

        repro = session_factory()
        service = MorningAssignmentService(repro)
        restore = _patch_create_queue_entry_to_fail_on_tag(service, tags[1])

        visit = repro.query(Visit).filter(Visit.id == visit_id).first()
        queue_assignments = service._assign_queues_for_visit(visit, date.today())

        repro.commit()
        repro.close()
        restore()

        # The fact that queue_assignments has entries for A and C proves
        # the session was usable after B's savepoint rollback.
        # If the session were unusable, C would have failed too.
        assert len(queue_assignments) >= 2, (
            f"Expected ≥2 assignments (A + C), got {len(queue_assignments)}. "
            f"Session may be unusable after savepoint rollback — "
            f"tag C could not execute after tag B's flush-time failure."
        )

    def test_queue_assignments_match_db_entries(
        self, session_factory, clean_db
    ):
        """INVARIANT: queue_assignments must exactly match the DB queue entries.

        Before fix: queue_assignments contained stale dicts for entries
        that were rolled back by the over-broad rollback.
        After fix: every dict in queue_assignments corresponds to a real
        DB entry.
        """
        setup = session_factory()
        visit_id, tags = _setup_visit_with_three_tags(setup)
        setup.close()

        repro = session_factory()
        service = MorningAssignmentService(repro)
        restore = _patch_create_queue_entry_to_fail_on_tag(service, tags[1])

        visit = repro.query(Visit).filter(Visit.id == visit_id).first()
        queue_assignments = service._assign_queues_for_visit(visit, date.today())
        repro.commit()
        repro.close()
        restore()

        verify = session_factory()
        try:
            entries = verify.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.visit_id == visit_id
            ).all()

            # queue_assignments count must match DB entry count
            assert len(queue_assignments) == len(entries), (
                f"queue_assignments ({len(queue_assignments)}) does not match "
                f"DB entries ({len(entries)}). Stale data detected."
            )
        finally:
            verify.close()

    def test_all_tags_fail_no_activation(
        self, session_factory, clean_db
    ):
        """INVARIANT: when ALL queue_tags fail, queue_assignments is empty
        and the visit must NOT be activated.

        This is the existing business policy: visit is activated only when
        queue_assignments is non-empty.
        """
        setup = session_factory()
        visit_id, tags = _setup_visit_with_three_tags(setup)
        setup.close()

        repro = session_factory()
        service = MorningAssignmentService(repro)

        # Patch _assign_single_queue to fail on ALL tags
        original_assign = service._assign_single_queue

        def fail_all(visit, queue_tag, target_date, *, source="morning_assignment"):
            entry = OnlineQueueEntry(
                queue_id=999999,  # invalid FK → IntegrityError
                number=1,
                patient_id=visit.patient_id,
                patient_name="Test",
                visit_id=visit.id,
                source=source,
                status="waiting",
            )
            service.db.add(entry)
            service.db.flush()  # raises IntegrityError
            return {"queue_tag": queue_tag, "number": 1}

        service._assign_single_queue = fail_all

        visit = repro.query(Visit).filter(Visit.id == visit_id).first()
        queue_assignments = service._assign_queues_for_visit(visit, date.today())
        repro.commit()
        repro.close()

        service._assign_single_queue = original_assign

        assert len(queue_assignments) == 0, (
            f"Expected 0 assignments (all tags failed), got {len(queue_assignments)}"
        )

        # Visit must remain 'confirmed' (not activated)
        verify = session_factory()
        try:
            db_visit = verify.query(Visit).filter(Visit.id == visit_id).first()
            assert db_visit.status == "confirmed", (
                f"Visit should remain 'confirmed' when all queue tags fail. "
                f"Got: {db_visit.status}"
            )
        finally:
            verify.close()

    def test_both_tags_succeed_without_savepoint_interference(
        self, session_factory, clean_db
    ):
        """NON-REGRESSION: when no tags fail, savepoints don't interfere
        with normal operation. All entries are created.
        """
        setup = session_factory()
        visit_id, tags = _setup_visit_with_three_tags(setup)
        setup.close()

        repro = session_factory()
        service = MorningAssignmentService(repro)
        visit = repro.query(Visit).filter(Visit.id == visit_id).first()
        queue_assignments = service._assign_queues_for_visit(visit, date.today())
        repro.commit()
        repro.close()

        verify = session_factory()
        try:
            entries = verify.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.visit_id == visit_id
            ).all()
            assert len(entries) == 3, (
                f"Expected 3 queue entries (all tags succeeded), got {len(entries)}"
            )
            assert len(queue_assignments) == 3
        finally:
            verify.close()
