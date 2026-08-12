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


def _setup_confirmed_visit(session):
    """Create a confirmed visit with a queue_tag and DailyQueue."""
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
        patient_id=patient.id, doctor_id=doctor.id, status="confirmed",
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
