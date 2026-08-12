"""Regression tests for P2-1b: over-broad rollback in _assign_queues_for_visit.

P2-1b (post-merge stabilization): the original code called self.db.rollback()
on any per-queue_tag failure, which discarded ALL staged work — including
successful entries from earlier tags. The loop then continued with stale
queue_assignments, causing the visit to be activated with incomplete
queue entries.

Fix: use savepoints (begin_nested) per queue_tag so that a failure in
one tag only rolls back that tag's work, not the whole transaction.

These tests verify:
1. A successful queue entry is PRESERVED when a subsequent tag fails.
2. The failed tag's entry is NOT created.
3. queue_assignments contains only the successful entries.
4. After commit, the DB has the successful entry but not the failed one.

Run:
    pytest backend/tests/regression/test_p2_1b_over_broad_rollback.py -v
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch

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


def _setup_visit_with_two_tags(session):
    """Create a visit with 2 services (cardio + lab), both with DailyQueues."""
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

    s1 = Service(
        code=f"CARDIO_{unique}", name="Cardio", price=100000,
        duration_minutes=30, active=True, requires_doctor=True,
        queue_tag=f"cardio_{unique}", is_consultation=True,
        allow_doctor_price_override=False,
    )
    s2 = Service(
        code=f"LAB_{unique}", name="Lab", price=50000,
        duration_minutes=15, active=True, requires_doctor=True,
        queue_tag=f"lab_{unique}", is_consultation=False,
        allow_doctor_price_override=False,
    )
    session.add_all([s1, s2])
    session.flush()

    q1 = DailyQueue(day=date.today(), specialist_id=doctor_user.id,
                    queue_tag=s1.queue_tag, active=True)
    q2 = DailyQueue(day=date.today(), specialist_id=doctor_user.id,
                    queue_tag=s2.queue_tag, active=True)
    session.add_all([q1, q2])
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
    vs1 = VisitService(visit_id=visit.id, service_id=s1.id, code=s1.code,
                       name=s1.name, qty=1, price=s1.price, currency="UZS")
    vs2 = VisitService(visit_id=visit.id, service_id=s2.id, code=s2.code,
                       name=s2.name, qty=1, price=s2.price, currency="UZS")
    session.add_all([vs1, vs2])
    session.commit()
    return visit.id


@pytest.mark.unit
class TestP21bSavepointIsolation:
    """P2-1b: savepoint isolation prevents over-broad rollback."""

    def test_successful_entry_preserved_when_subsequent_tag_fails(
        self, session_factory, clean_db
    ):
        """REGRESSION: when the second queue_tag fails, the first tag's
        entry must be preserved (not rolled back by the over-broad rollback).

        Before fix: self.db.rollback() discarded the first entry.
        After fix: savepoint.rollback() only discards the second tag's work.
        """
        setup = session_factory()
        visit_id = _setup_visit_with_two_tags(setup)
        setup.close()

        repro = session_factory()
        service = MorningAssignmentService(repro)

        # Monkey-patch _assign_single_queue to fail on the lab tag
        original = service._assign_single_queue

        def patched(visit, queue_tag, target_date, *, source="morning_assignment"):
            result = original(visit, queue_tag, target_date, source=source)
            if "lab_" in queue_tag:
                raise RuntimeError("INJECTED ERROR for lab tag")
            return result

        service._assign_single_queue = patched

        visit = repro.query(Visit).filter(Visit.id == visit_id).first()
        queue_assignments = service._assign_queues_for_visit(visit, date.today())

        # Commit to simulate run_morning_assignment's final commit
        repro.commit()
        repro.close()

        # ─── Verify in NEW independent session ─────────────────────
        verify = session_factory()
        try:
            entries = verify.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.visit_id == visit_id
            ).all()

            # The cardio entry must be preserved (not rolled back by lab failure)
            assert len(entries) >= 1, (
                f"Expected ≥1 queue entry (cardio preserved), got {len(entries)}. "
                f"The over-broad rollback destroyed the successful cardio entry."
            )

            # queue_assignments should contain only the cardio entry
            assert len(queue_assignments) == 1, (
                f"Expected 1 assignment (cardio only), got {len(queue_assignments)}. "
                f"queue_assignments: {queue_assignments}"
            )
        finally:
            verify.close()

    def test_failed_tag_entry_not_created(self, session_factory, clean_db):
        """REGRESSION: the failed tag's entry must NOT be in the DB."""
        setup = session_factory()
        visit_id = _setup_visit_with_two_tags(setup)
        setup.close()

        repro = session_factory()
        service = MorningAssignmentService(repro)

        original = service._assign_single_queue

        def patched(visit, queue_tag, target_date, *, source="morning_assignment"):
            result = original(visit, queue_tag, target_date, source=source)
            if "lab_" in queue_tag:
                raise RuntimeError("INJECTED ERROR for lab tag")
            return result

        service._assign_single_queue = patched
        visit = repro.query(Visit).filter(Visit.id == visit_id).first()
        service._assign_queues_for_visit(visit, date.today())
        repro.commit()
        repro.close()

        verify = session_factory()
        try:
            entries = verify.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.visit_id == visit_id
            ).all()
            # All entries should have cardio queue_tag, not lab
            for entry in entries:
                queue = verify.query(DailyQueue).filter(
                    DailyQueue.id == entry.queue_id
                ).first()
                assert "cardio_" in queue.queue_tag, (
                    f"Found lab queue entry that should have been rolled back: "
                    f"queue_tag={queue.queue_tag}"
                )
        finally:
            verify.close()

    def test_both_tags_succeed_without_savepoint_interference(
        self, session_factory, clean_db
    ):
        """NON-REGRESSION: when both tags succeed, savepoints don't interfere."""
        setup = session_factory()
        visit_id = _setup_visit_with_two_tags(setup)
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
            assert len(entries) == 2, (
                f"Expected 2 queue entries (both tags succeeded), got {len(entries)}"
            )
            assert len(queue_assignments) == 2
        finally:
            verify.close()
