"""Regression tests for Gate C bypass: direct visit.status mutations.

Gate C bypass fix: registrar_wizard_queue_assignment_service.py and
morning_assignment_api_service.py previously set visit.status = "open"
directly, bypassing VisitLifecycleService. This skipped state machine
validation, with_for_update() row lock, and audit logging.

Fix: both now delegate to VisitLifecycleService.activate_confirmed_visit(
commit=False), which:
- Validates the transition (confirmed → open)
- Acquires with_for_update() row lock
- Sets audit logging
- Uses commit=False to preserve caller-owned transaction

Run:
    pytest backend/tests/regression/test_gate_c_bypass.py -v
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

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_gate_c.db")
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-gate-c-regression-32")
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
from app.services.registrar_wizard_queue_assignment_service import (  # noqa: E402
    RegistrarWizardQueueAssignmentService,
)


@pytest.fixture(scope="module")
def db_engine():
    db_path = BACKEND_DIR / "test_gate_c.db"
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


def _setup_confirmed_visit(session, *, status: str = "confirmed"):
    """Create a visit with a queue_tag and DailyQueue.

    Args:
        status: Visit status to create. Defaults to "confirmed".
            Codex P1 tests need to create visits in non-confirmed statuses
            (closed, canceled, pending_confirmation) to verify rejection.
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
        sex="M",
        # Codex P1 fix: synthetic unique phone (AGENTS.md L377/L451 — no
        # real-looking phone numbers in committed test fixtures).
        # Pattern follows test_p1_1_overpayment_policy.py.
        phone=f"+9989012{uuid.uuid4().hex[:5]}",
        email=f"p_{unique}@t.local",
        created_at=datetime.now(UTC), is_deleted=False,
    )
    session.add(patient)
    session.flush()
    svc = Service(
        code=f"SVC_{unique}", name="Service", price=10000,
        duration_minutes=30, active=True, requires_doctor=True,
        queue_tag=f"tag_{unique}", is_consultation=True,
        allow_doctor_price_override=False,
    )
    session.add(svc)
    session.flush()
    q = DailyQueue(day=date.today(), specialist_id=doctor_user.id,
                   queue_tag=svc.queue_tag, active=True)
    session.add(q)
    session.flush()
    visit = Visit(
        patient_id=patient.id, doctor_id=doctor.id, status=status,
        visit_date=date.today(), visit_time="10:00", discount_mode="none",
        department="cardiology", confirmation_token=f"tok-{unique}",
        confirmation_channel="telegram", confirmed_at=datetime.now(UTC),
        confirmation_expires_at=datetime.now(UTC), created_at=datetime.now(UTC),
    )
    session.add(visit)
    session.flush()
    vs = VisitService(visit_id=visit.id, service_id=svc.id, code=svc.code,
                      name=svc.name, qty=1, price=svc.price, currency="UZS")
    session.add(vs)
    session.commit()
    return visit.id


@pytest.mark.unit
class TestGateCBypassFix:
    """Gate C bypass: visit.status must go through VisitLifecycleService."""

    def test_wizard_uses_lifecycle_service_not_direct_mutation(
        self, session_factory, clean_db
    ):
        """REGRESSION: registrar_wizard_queue_assignment_service must use
        VisitLifecycleService.activate_confirmed_visit() instead of
        direct visit.status = "open".

        Before fix: direct mutation bypassed state machine + row lock.
        After fix: delegates to VisitLifecycleService.
        """
        setup = session_factory()
        visit_id = _setup_confirmed_visit(setup)
        setup.close()

        session = session_factory()
        service = RegistrarWizardQueueAssignmentService(session)
        from app.services.morning_assignment import MorningAssignmentService
        morning_service = MorningAssignmentService(session)

        visit = session.query(Visit).filter(Visit.id == visit_id).first()
        assert visit.status == "confirmed"

        # Call the wizard service
        queue_numbers = service.assign_same_day_queue_numbers(
            [visit], target_day=date.today(), source="desk"
        )
        session.commit()
        session.close()

        # Visit should be 'open' via VisitLifecycleService (not direct mutation)
        verify = session_factory()
        try:
            db_visit = verify.query(Visit).filter(Visit.id == visit_id).first()
            assert db_visit.status == "open", (
                f"Visit should be 'open' after wizard assignment. "
                f"Got: {db_visit.status}"
            )
            assert visit_id in queue_numbers, (
                f"Visit {visit_id} should be in queue_numbers"
            )
        finally:
            verify.close()

    def test_manual_assignment_uses_lifecycle_service(
        self, session_factory, clean_db
    ):
        """REGRESSION: morning_assignment_api_service must use
        VisitLifecycleService.activate_confirmed_visit() instead of
        direct visit.status = "open".
        """
        setup = session_factory()
        visit_id = _setup_confirmed_visit(setup)
        setup.close()

        from app.services.morning_assignment_api_service import MorningAssignmentApiService
        from app.repositories.morning_assignment_api_repository import MorningAssignmentApiRepository

        session = session_factory()
        repository = MorningAssignmentApiRepository(session)
        api_service = MorningAssignmentApiService(db=session, repository=repository)

        result = api_service.manual_assignment_for_visits(
            visit_ids=[visit_id],
            force=False,
        )
        session.close()

        assert result["success"] is True
        assert result["results"][0]["success"] is True

        # Visit should be 'open' via VisitLifecycleService
        verify = session_factory()
        try:
            db_visit = verify.query(Visit).filter(Visit.id == visit_id).first()
            assert db_visit.status == "open", (
                f"Visit should be 'open' after manual assignment. "
                f"Got: {db_visit.status}"
            )
        finally:
            verify.close()

    def test_no_direct_visit_status_mutation_in_wizard_source(
        self, session_factory, clean_db
    ):
        """INVARIANT: registrar_wizard_queue_assignment_service.py must NOT
        contain direct visit.status = "open" assignment (excluding comments).

        This is a static source-level check that prevents regression.
        """
        import importlib
        import re
        mod = importlib.import_module(
            "app.services.registrar_wizard_queue_assignment_service"
        )
        import inspect
        source = inspect.getsource(mod)

        # Remove comment lines before checking
        lines = [line for line in source.split('\n') if not line.strip().startswith('#')]
        code_only = '\n'.join(lines)

        # The direct mutation line should NOT be present in code
        assert 'visit.status = "open"' not in code_only, (
            "registrar_wizard_queue_assignment_service.py still contains "
            "direct visit.status = \"open\". This is a Gate C bypass. "
            "Use VisitLifecycleService.activate_confirmed_visit() instead."
        )

    def test_no_direct_visit_status_mutation_in_manual_assignment_source(
        self, session_factory, clean_db
    ):
        """INVARIANT: morning_assignment_api_service.py must NOT contain
        direct visit.status = "open" assignment (excluding comments)."""
        import importlib
        mod = importlib.import_module(
            "app.services.morning_assignment_api_service"
        )
        import inspect
        source = inspect.getsource(mod)

        # Remove comment lines before checking
        lines = [line for line in source.split('\n') if not line.strip().startswith('#')]
        code_only = '\n'.join(lines)

        assert 'visit.status = "open"' not in code_only, (
            "morning_assignment_api_service.py still contains "
            "direct visit.status = \"open\". This is a Gate C bypass. "
            "Use VisitLifecycleService.activate_confirmed_visit() instead."
        )


@pytest.mark.unit
class TestGateCCodexFollowUp:
    """Codex review follow-up: P1 regressions + P2 audit attribution.

    Codex found that the Gate C bypass fix introduced 2 silent regressions
    (terminal visit + queue entry leak) and 1 attribution gap (current_user
    not threaded through). These tests verify the fixes.
    """

    def test_force_true_on_closed_visit_is_rejected(
        self, session_factory, clean_db
    ):
        """P1: force=true on a 'closed' visit MUST be rejected.

        Before fix: activate_confirmed_visit() was a no-op for non-confirmed
        statuses, but _assign_queues_for_visit() had already staged queue
        entries that get committed at end of method. Success reported, visit
        stayed 'closed' but had live queue entries — silent regression.

        After fix: terminal statuses are rejected BEFORE _assign_queues_for_visit().
        """
        from app.services.morning_assignment_api_service import MorningAssignmentApiService
        from app.repositories.morning_assignment_api_repository import (
            MorningAssignmentApiRepository,
        )

        setup = session_factory()
        visit_id = _setup_confirmed_visit(setup, status="closed")
        setup.close()

        session = session_factory()
        repository = MorningAssignmentApiRepository(session)
        api_service = MorningAssignmentApiService(db=session, repository=repository)

        result = api_service.manual_assignment_for_visits(
            visit_ids=[visit_id],
            force=True,  # Admin override — should still be rejected.
        )
        session.close()

        # Result: rejected, not silently successful.
        assert result["success"] is True  # Endpoint level (always True for batch)
        item = result["results"][0]
        assert item["success"] is False, (
            "force=true on a terminal visit must NOT succeed — "
            "activate_confirmed_visit() is a no-op for terminal statuses, "
            "but staged queue entries would be committed (silent regression)."
        )
        assert "терминальном статусе" in item["message"], (
            f"Rejection message should mention terminal status. Got: {item['message']}"
        )

        # Verify NO queue entries were committed.
        from app.models.online_queue import OnlineQueueEntry
        verify = session_factory()
        try:
            entries = verify.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.visit_id == visit_id
            ).all()
            assert entries == [], (
                f"Terminal visit must NOT have queue entries committed. "
                f"Found: {len(entries)} entries."
            )
            db_visit = verify.query(Visit).filter(Visit.id == visit_id).first()
            assert db_visit.status == "closed", (
                f"Terminal visit status should be unchanged. Got: {db_visit.status}"
            )
        finally:
            verify.close()

    def test_force_true_on_canceled_visit_is_rejected(
        self, session_factory, clean_db
    ):
        """P1: force=true on a 'canceled' visit MUST be rejected (same as closed)."""
        from app.services.morning_assignment_api_service import MorningAssignmentApiService
        from app.repositories.morning_assignment_api_repository import (
            MorningAssignmentApiRepository,
        )

        setup = session_factory()
        visit_id = _setup_confirmed_visit(setup, status="canceled")
        setup.close()

        session = session_factory()
        repository = MorningAssignmentApiRepository(session)
        api_service = MorningAssignmentApiService(db=session, repository=repository)

        result = api_service.manual_assignment_for_visits(
            visit_ids=[visit_id],
            force=True,
        )
        session.close()

        item = result["results"][0]
        assert item["success"] is False
        assert "терминальном статусе" in item["message"]

    def test_force_true_on_pending_confirmation_is_rejected_no_leak(
        self, session_factory, clean_db
    ):
        """P1: force=true on 'pending_confirmation' MUST be rejected without
        leaking queue entries.

        Before fix: activate_confirmed_visit() raised HTTP 409, broad except
        caught and marked as failed, but the unconditional commit at end of
        method persisted the staged queue entry anyway. Unconfirmed patient
        occupying a live queue number.

        After fix: pending_confirmation is rejected BEFORE _assign_queues_for_visit().
        """
        from app.services.morning_assignment_api_service import MorningAssignmentApiService
        from app.repositories.morning_assignment_api_repository import (
            MorningAssignmentApiRepository,
        )
        from app.models.online_queue import OnlineQueueEntry

        setup = session_factory()
        visit_id = _setup_confirmed_visit(setup, status="pending_confirmation")
        setup.close()

        session = session_factory()
        repository = MorningAssignmentApiRepository(session)
        api_service = MorningAssignmentApiService(db=session, repository=repository)

        result = api_service.manual_assignment_for_visits(
            visit_ids=[visit_id],
            force=True,
        )
        session.close()

        item = result["results"][0]
        assert item["success"] is False, (
            "force=true on pending_confirmation must NOT succeed — "
            "would leak a queue entry to an unconfirmed patient."
        )
        assert "ожидает подтверждения" in item["message"], (
            f"Rejection message should mention pending confirmation. Got: {item['message']}"
        )

        # CRITICAL: verify NO queue entries were committed (no leak).
        verify = session_factory()
        try:
            entries = verify.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.visit_id == visit_id
            ).all()
            assert entries == [], (
                f"pending_confirmation visit must NOT have queue entries committed. "
                f"Found: {len(entries)} entries — queue leak."
            )
        finally:
            verify.close()

    def test_manual_assignment_threads_current_user_to_lifecycle_service(
        self, session_factory, clean_db
    ):
        """P2: current_user must be threaded through to activate_confirmed_visit()
        for audit attribution.

        Before fix: current_user was not passed, so audit logs said
        'user_id=batch' even when an admin/registrar initiated the request.

        After fix: current_user is threaded through.
        """
        from app.services.morning_assignment_api_service import MorningAssignmentApiService
        from app.repositories.morning_assignment_api_repository import (
            MorningAssignmentApiRepository,
        )

        setup = session_factory()
        visit_id = _setup_confirmed_visit(setup)
        setup.close()

        # Fake current_user with id=42 to verify threading.
        class FakeUser:
            id = 42

        fake_user = FakeUser()

        session = session_factory()
        repository = MorningAssignmentApiRepository(session)
        api_service = MorningAssignmentApiService(db=session, repository=repository)

        # Capture the current_user passed to activate_confirmed_visit.
        captured_user = []
        original_activate = (
            __import__(
                "app.services.visit_lifecycle_service", fromlist=["VisitLifecycleService"]
            ).VisitLifecycleService.activate_confirmed_visit
        )

        def spy_activate(self, visit_id, current_user=None, *, commit=True):
            captured_user.append(current_user)
            return original_activate(self, visit_id, current_user, commit=commit)

        from app.services.visit_lifecycle_service import VisitLifecycleService
        original_method = VisitLifecycleService.activate_confirmed_visit
        VisitLifecycleService.activate_confirmed_visit = spy_activate
        try:
            api_service.manual_assignment_for_visits(
                visit_ids=[visit_id],
                force=False,
                current_user=fake_user,
            )
        finally:
            VisitLifecycleService.activate_confirmed_visit = original_method
        session.close()

        assert len(captured_user) == 1, (
            f"activate_confirmed_visit should be called exactly once. "
            f"Got: {len(captured_user)} calls."
        )
        assert captured_user[0] is fake_user, (
            "current_user should be threaded through to activate_confirmed_visit() "
            "for audit attribution (Codex P2 fix)."
        )

    def test_wizard_threads_current_user_to_lifecycle_service(
        self, session_factory, clean_db
    ):
        """P2: current_user must be threaded through wizard path too."""
        setup = session_factory()
        visit_id = _setup_confirmed_visit(setup)
        setup.close()

        class FakeUser:
            id = 99

        fake_user = FakeUser()

        session = session_factory()
        service = RegistrarWizardQueueAssignmentService(session)

        captured_user = []
        from app.services.visit_lifecycle_service import VisitLifecycleService
        original_method = VisitLifecycleService.activate_confirmed_visit

        def spy_activate(self, visit_id, current_user=None, *, commit=True):
            captured_user.append(current_user)
            return original_method(self, visit_id, current_user, commit=commit)

        VisitLifecycleService.activate_confirmed_visit = spy_activate
        try:
            visit = session.query(Visit).filter(Visit.id == visit_id).first()
            service.assign_same_day_queue_numbers(
                [visit],
                target_day=date.today(),
                source="desk",
                current_user=fake_user,
            )
            session.commit()
        finally:
            VisitLifecycleService.activate_confirmed_visit = original_method
        session.close()

        assert len(captured_user) == 1
        assert captured_user[0] is fake_user
