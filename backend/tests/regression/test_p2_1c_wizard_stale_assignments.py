"""Regression tests for P2-1c: stale queue_assignments in registrar wizard flow.

P2-1c (post-merge stabilization): same defect class as P2-1b, but in
registrar_wizard_queue_assignment_service.py instead of morning_assignment.py.

The original code called self._rollback_session() on per-queue_tag failure,
which discarded ALL staged work AND left stale dicts in queue_assignments.
The loop continued, and the visit was activated with stale data.

Fix: on failure, rollback + clear + break. Same contract as P2-1b.

Contract (consistent with P2-1b):
    Partial queue assignment is intentionally unsupported. On any
    queue-tag assignment failure, all assignments for the current
    visit are discarded and processing stops.

Run:
    pytest backend/tests/regression/test_p2_1c_wizard_stale_assignments.py -v
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_p2_1c_regression.db")
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-p2-1c-regression-32-chars")
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
from app.services.registrar_wizard_queue_assignment_service import (  # noqa: E402
    RegistrarWizardQueueAssignmentService,
)


@pytest.fixture(scope="module")
def db_engine():
    db_path = BACKEND_DIR / "test_p2_1c_regression.db"
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


def _make_service_with_failing_tag(session_factory, visit_id, fail_tag_fragment):
    """Create a RegistrarWizardQueueAssignmentService that raises ValueError
    for the fail tag during _materialize_prepared_assignment.

    The exception is injected at the _materialize_prepared_assignment level
    (after prepare_wizard_queue_assignment succeeds), so it triggers the
    except branch in _assign_same_day_queues_for_visit — exactly matching
    the production failure path.
    """
    from app.services.morning_assignment import MorningAssignmentService

    session = session_factory()
    real_morning_service = MorningAssignmentService(session)

    service = RegistrarWizardQueueAssignmentService(
        session,
        assignment_service_factory=lambda db: real_morning_service,
    )

    # Patch _materialize_prepared_assignment to fail on the target tag.
    # This is called AFTER prepare_wizard_queue_assignment returns
    # successfully, so the first tag's entry is already flushed —
    # exactly the scenario where stale data would be left.
    original_materialize = service._materialize_prepared_assignment

    def patched_materialize(prepared_assignment):
        # Check if this assignment is for the failing tag
        if prepared_assignment and prepared_assignment.create_handoff:
            tag = prepared_assignment.create_handoff.queue_tag
            if fail_tag_fragment in tag:
                raise ValueError(f"INJECTED ERROR for tag {tag}")
        return original_materialize(prepared_assignment)

    service._materialize_prepared_assignment = patched_materialize

    return session, service


@pytest.mark.unit
class TestP21cStaleDataFix:
    """P2-1c: stale queue_assignments fix in registrar wizard flow.

    Contract (rollback + clear + break):
        A succeeds → flushed
        B fails → rollback() → A destroyed → queue_assignments cleared → break
        C NOT attempted
        queue_assignments = [] (no stale data)
        visit NOT activated (status stays 'confirmed')
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

        session, service = _make_service_with_failing_tag(
            session_factory, visit_id, tags[1]
        )

        visit = session.query(Visit).filter(Visit.id == visit_id).first()
        from app.services.morning_assignment import MorningAssignmentService
        morning_service = MorningAssignmentService(session)

        queue_assignments = service._assign_same_day_queues_for_visit(
            morning_service, visit, date.today(), source="desk"
        )
        session.close()

        # queue_assignments must be EMPTY — no stale data
        assert len(queue_assignments) == 0, (
            f"Expected 0 assignments (stale data cleared), got {len(queue_assignments)}. "
            f"queue_assignments contains stale dicts for entries that were rolled back."
        )

    def test_failure_visit_not_activated(
        self, session_factory, clean_db
    ):
        """INVARIANT: when queue_assignments is empty after failure, the visit
        must NOT be activated (stays 'confirmed').

        This tests the assign_same_day_queue_numbers caller contract:
        if _assign_same_day_queues_for_visit returns [], visit.status
        is NOT set to 'open'.
        """
        setup = session_factory()
        visit_id, tags = _setup_visit_with_three_tags(setup)
        setup.close()

        session, service = _make_service_with_failing_tag(
            session_factory, visit_id, tags[1]
        )

        visit = session.query(Visit).filter(Visit.id == visit_id).first()
        from app.services.morning_assignment import MorningAssignmentService
        morning_service = MorningAssignmentService(session)

        # Call the top-level method that checks queue_assignments and
        # sets visit.status = "open" if non-empty
        queue_numbers = service.assign_same_day_queue_numbers(
            [visit], target_day=date.today(), source="desk"
        )
        session.close()

        # queue_numbers must NOT contain this visit
        assert visit_id not in queue_numbers, (
            f"Visit {visit_id} should NOT be in queue_numbers (assignment failed). "
            f"queue_numbers: {queue_numbers}"
        )

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

    def test_failure_no_db_entries_after_rollback(
        self, session_factory, clean_db
    ):
        """REGRESSION: after failure + rollback, DB must have 0 queue entries
        for this visit (rolled back entries are not persisted).
        """
        setup = session_factory()
        visit_id, tags = _setup_visit_with_three_tags(setup)
        setup.close()

        session, service = _make_service_with_failing_tag(
            session_factory, visit_id, tags[1]
        )

        visit = session.query(Visit).filter(Visit.id == visit_id).first()
        from app.services.morning_assignment import MorningAssignmentService
        morning_service = MorningAssignmentService(session)

        service._assign_same_day_queues_for_visit(
            morning_service, visit, date.today(), source="desk"
        )
        session.rollback()
        session.close()

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

    def test_all_tags_succeed_normal_operation(
        self, session_factory, clean_db
    ):
        """NON-REGRESSION: when all tags succeed, all entries are created."""
        setup = session_factory()
        visit_id, tags = _setup_visit_with_three_tags(setup)
        setup.close()

        session = session_factory()
        service = RegistrarWizardQueueAssignmentService(session)
        visit = session.query(Visit).filter(Visit.id == visit_id).first()

        from app.services.morning_assignment import MorningAssignmentService
        morning_service = MorningAssignmentService(session)

        queue_assignments = service._assign_same_day_queues_for_visit(
            morning_service, visit, date.today(), source="desk"
        )
        session.commit()
        session.close()

        assert len(queue_assignments) == 3, (
            f"Expected 3 assignments (all tags succeeded), got {len(queue_assignments)}"
        )

        verify = session_factory()
        try:
            entries = verify.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.visit_id == visit_id
            ).all()
            assert len(entries) == 3, (
                f"Expected 3 DB entries, got {len(entries)}"
            )
        finally:
            verify.close()

    def test_queue_assignments_match_db_on_success(
        self, session_factory, clean_db
    ):
        """INVARIANT: on success, queue_assignments count == DB entry count."""
        setup = session_factory()
        visit_id, tags = _setup_visit_with_three_tags(setup)
        setup.close()

        session = session_factory()
        service = RegistrarWizardQueueAssignmentService(session)
        visit = session.query(Visit).filter(Visit.id == visit_id).first()

        from app.services.morning_assignment import MorningAssignmentService
        morning_service = MorningAssignmentService(session)

        queue_assignments = service._assign_same_day_queues_for_visit(
            morning_service, visit, date.today(), source="desk"
        )
        session.commit()
        session.close()

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

    def test_caller_commit_does_not_persist_open_without_entries(
        self, session_factory, clean_db
    ):
        """INVARIANT: after _assign_same_day_queues_for_visit() with partial
        failure, the external db.commit() cannot persist visit in 'open'
        without queue entries.

        This tests the full caller path: assign_same_day_queue_numbers →
        _assign_same_day_queues_for_visit → (failure) → queue_assignments=[] →
        visit.status NOT set to 'open' → external commit → visit stays 'confirmed'.
        """
        setup = session_factory()
        visit_id, tags = _setup_visit_with_three_tags(setup)
        setup.close()

        session, service = _make_service_with_failing_tag(
            session_factory, visit_id, tags[1]
        )

        visit = session.query(Visit).filter(Visit.id == visit_id).first()

        # Call the top-level method (simulates _cart.py caller)
        queue_numbers = service.assign_same_day_queue_numbers(
            [visit], target_day=date.today(), source="desk"
        )

        # Simulate _cart.py L194: db.commit()
        session.commit()
        session.close()

        # Verify from NEW independent session
        verify = session_factory()
        try:
            db_visit = verify.query(Visit).filter(Visit.id == visit_id).first()
            entries = verify.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.visit_id == visit_id
            ).all()

            assert db_visit.status == "confirmed", (
                f"Visit should remain 'confirmed' after failed assignment + commit. "
                f"Got: {db_visit.status}"
            )
            assert len(entries) == 0, (
                f"Expected 0 DB entries after rollback + commit, got {len(entries)}"
            )
        finally:
            verify.close()
