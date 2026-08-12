"""Regression tests for P2-1b: stale queue_assignments after over-broad rollback.

P2-1b (post-merge stabilization): the original code called self.db.rollback()
on per-queue_tag failure, which discarded ALL staged work AND left stale dicts
in queue_assignments. The loop continued, and the visit was activated with
stale data (non-empty queue_assignments but 0 real DB entries).

Fix: on failure, rollback restores the session, queue_assignments is CLEARED
to remove stale dicts, and the loop BREAKS. The visit is NOT activated.

Contract:
    A succeeds → flushed
    B fails → rollback() → A destroyed → queue_assignments cleared → break
    C NOT attempted (loop broke)
    queue_assignments = [] (empty — no stale data)
    visit NOT activated (queue_assignments is empty)

Note: tests use ValueError (pre-flush error) instead of IntegrityError
(flush-time error) to avoid SQLAlchemy DEACTIVE state complications.
The stale-data fix (clear + break) is the same regardless of error type.

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


def _patch_to_fail_on_tag(service_obj, fail_tag_fragment):
    """Monkey-patch _assign_single_queue to raise ValueError when processing
    the tag containing fail_tag_fragment.

    Uses ValueError (pre-flush error) instead of IntegrityError (flush-time
    error) to avoid SQLAlchemy DEACTIVE state complications. The stale-data
    fix (clear + break) is the same regardless of error type — the key
    invariant is that queue_assignments must NOT contain stale dicts after
    a rollback.
    """
    original_assign = service_obj._assign_single_queue

    def patched_assign(visit, queue_tag, target_date, *, source="morning_assignment"):
        if fail_tag_fragment in queue_tag:
            raise ValueError(f"INJECTED ERROR for tag {queue_tag}")
        return original_assign(visit, queue_tag, target_date, source=source)

    service_obj._assign_single_queue = patched_assign

    def restore():
        service_obj._assign_single_queue = original_assign

    return restore


@pytest.mark.unit
class TestP21bStaleDataFix:
    """P2-1b: stale queue_assignments fix.

    Contract (rollback + clear + break):
        A succeeds → flushed
        B fails → rollback() → A destroyed → queue_assignments cleared → break
        C NOT attempted
        queue_assignments = [] (no stale data)
        visit NOT activated
    """

    def test_failure_clears_stale_queue_assignments(
        self, session_factory, clean_db
    ):
        """REGRESSION: when tag B fails, queue_assignments must NOT contain
        stale dicts for tag A.

        Before fix: rollback destroyed A's DB entry, but queue_assignments
        still contained A's dict → visit activated with 0 real entries.
        After fix: queue_assignments is cleared on failure → no stale data.
        """
        setup = session_factory()
        visit_id, tags = _setup_visit_with_three_tags(setup)
        setup.close()

        repro = session_factory()
        service = MorningAssignmentService(repro)
        restore = _patch_to_fail_on_tag(service, tags[1])

        visit = repro.query(Visit).filter(Visit.id == visit_id).first()
        queue_assignments = service._assign_queues_for_visit(visit, date.today())
        repro.close()
        restore()

        # queue_assignments must be EMPTY — no stale data
        assert len(queue_assignments) == 0, (
            f"Expected 0 assignments (stale data cleared), got {len(queue_assignments)}. "
            f"queue_assignments contains stale dicts for entries that were rolled back."
        )

    def test_failure_no_db_entries_after_rollback(
        self, session_factory, clean_db
    ):
        """REGRESSION: after failure + rollback, DB must have 0 queue entries
        for this visit (rolled back entries are not persisted).
        """
        setup = session_factory()
        visit_id, tags = _setup_visit_with_three_tags(setup)
        setup.close()

        repro = session_factory()
        service = MorningAssignmentService(repro)
        restore = _patch_to_fail_on_tag(service, tags[1])

        visit = repro.query(Visit).filter(Visit.id == visit_id).first()
        service._assign_queues_for_visit(visit, date.today())
        repro.rollback()
        repro.close()
        restore()

        verify = session_factory()
        try:
            entries = verify.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.visit_id == visit_id
            ).all()
            assert len(entries) == 0, (
                f"Expected 0 DB entries (all rolled back), got {len(entries)}"
            )
        finally:
            verify.close()

    def test_failure_visit_not_activated(
        self, session_factory, clean_db
    ):
        """INVARIANT: when queue_assignments is empty after failure, the visit
        must NOT be activated (stays 'confirmed').

        This is the existing business policy: visit is activated only when
        queue_assignments is non-empty.
        """
        setup = session_factory()
        visit_id, tags = _setup_visit_with_three_tags(setup)
        setup.close()

        repro = session_factory()
        service = MorningAssignmentService(repro)
        restore = _patch_to_fail_on_tag(service, tags[1])

        visit = repro.query(Visit).filter(Visit.id == visit_id).first()
        queue_assignments = service._assign_queues_for_visit(visit, date.today())
        repro.close()
        restore()

        # queue_assignments must be empty → visit NOT activated
        assert len(queue_assignments) == 0

        # Visit status should remain 'confirmed' (not 'open')
        verify = session_factory()
        try:
            db_visit = verify.query(Visit).filter(Visit.id == visit_id).first()
            assert db_visit.status == "confirmed", (
                f"Visit should remain 'confirmed' when queue_assignments is empty. "
                f"Got: {db_visit.status}"
            )
        finally:
            verify.close()

    def test_all_tags_succeed_normal_operation(
        self, session_factory, clean_db
    ):
        """NON-REGRESSION: when all tags succeed, all entries are created."""
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
                f"Expected 3 entries (all tags succeeded), got {len(entries)}"
            )
            assert len(queue_assignments) == 3
        finally:
            verify.close()

    def test_queue_assignments_match_db_on_success(
        self, session_factory, clean_db
    ):
        """INVARIANT: on success, queue_assignments count == DB entry count."""
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
            assert len(queue_assignments) == len(entries), (
                f"queue_assignments ({len(queue_assignments)}) != DB entries ({len(entries)})"
            )
        finally:
            verify.close()
