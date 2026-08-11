"""Regression tests for the confirmation_processing state-machine defect.

TH-2 (post-merge stabilization): the original defect was that
VisitLifecycleService.confirm_visit() did NOT accept the
"confirmation_processing" intermediate status set by
VisitConfirmationService._claim_pending_visit_for_confirmation().

This caused ALL confirmation flows (Telegram + PWA) to return HTTP 500:
1. _claim_pending_visit_for_confirmation() sets status to "confirmation_processing"
2. _confirm_visit() calls confirm_visit()
3. confirm_visit() sees "confirmation_processing" → hits else → HTTPException 409
4. confirm_by_telegram/confirm_by_pwa catches Exception → VisitConfirmationDomainError 500

Fix: confirm_visit() now accepts "confirmation_processing" as a valid
source status (logically equivalent to "pending_confirmation").

These regression tests verify:
1. Direct confirm_visit() with confirmation_processing source → confirmed
2. Telegram confirmation flow → success (not HTTP 500)
3. PWA confirmation flow → success (not HTTP 500)
4. Concurrent confirmation → exactly 1 succeeds, 1 rejected (the
   concurrency test from test_confirmation_split_flow_concurrency.py,
   preserved as a regression guard)

Run:
    pytest backend/tests/regression/test_th2_confirmation_processing.py -v
"""
from __future__ import annotations

import os
import sys
import threading
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_th2_regression.db")
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-th-2-regression-32-chars")
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
from app.models.online_queue import DailyQueue  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.models.service import Service  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.visit import Visit, VisitService  # noqa: E402
from app.services.visit_confirmation_service import (  # noqa: E402
    VisitConfirmationDomainError,
    VisitConfirmationService,
)
from app.services.visit_lifecycle_service import VisitLifecycleService  # noqa: E402


# ─── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db_engine():
    db_path = BACKEND_DIR / "test_th2_regression.db"
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


def _setup_pending_visit(session, channel="telegram"):
    """Create a pending_confirmation visit. Returns (token, visit_id)."""
    unique = uuid.uuid4().hex[:8]
    doctor_user = User(
        username=f"doctor_{unique}",
        full_name="Repro Doctor",
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
        last_name="Repro",
        first_name="Patient",
        birth_date=date(1990, 1, 1),
        sex="M",
        phone="+998901234567",
        email=f"patient_{unique}@test.local",
        created_at=datetime.now(UTC),
        is_deleted=False,
    )
    session.add(patient)
    session.flush()

    service = Service(
        code=f"REPRO_{unique}",
        name="Repro Consultation",
        price=100000.00,
        duration_minutes=30,
        active=True,
        requires_doctor=True,
        queue_tag=f"repro_cardio_{unique}",
        is_consultation=True,
        allow_doctor_price_override=False,
    )
    session.add(service)
    session.flush()

    daily_queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor_user.id,
        queue_tag=service.queue_tag,
        active=True,
    )
    session.add(daily_queue)
    session.flush()

    token = f"repro-token-{unique}"
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        status="pending_confirmation",
        visit_date=date.today(),
        visit_time="10:00",
        discount_mode="none",
        department="cardiology",
        confirmation_token=token,
        confirmation_channel=channel,
        confirmation_expires_at=datetime.now(UTC).replace(hour=23, minute=59),
        created_at=datetime.now(UTC),
    )
    session.add(visit)
    session.flush()

    vs = VisitService(
        visit_id=visit.id,
        service_id=service.id,
        code=service.code,
        name=service.name,
        qty=1,
        price=service.price,
        currency="UZS",
    )
    session.add(vs)
    session.commit()

    return token, visit.id


# ─── Regression Tests ──────────────────────────────────────────────────

@pytest.mark.unit
class TestConfirmationProcessingAcceptance:
    """TH-2: confirm_visit() must accept confirmation_processing status."""

    def test_confirm_visit_accepts_confirmation_processing(self, session_factory, clean_db):
        """REGRESSION: confirm_visit() with status='confirmation_processing' must
        transition to 'confirmed', not raise HTTPException 409.

        Before fix: raised HTTPException 409 → wrapped as VisitConfirmationDomainError 500.
        After fix: transitions to 'confirmed'.
        """
        setup = session_factory()
        token, visit_id = _setup_pending_visit(setup, channel="telegram")
        setup.close()

        # Simulate the claim: set status to confirmation_processing
        setup2 = session_factory()
        visit = setup2.query(Visit).filter(Visit.id == visit_id).first()
        visit.status = "confirmation_processing"
        setup2.commit()
        setup2.close()

        # Now call confirm_visit — should accept confirmation_processing
        repro = session_factory()
        try:
            lifecycle = VisitLifecycleService(repro)
            actor = type("U", (), {"id": "test"})()
            visit = lifecycle.confirm_visit(
                visit_id=visit_id,
                current_user=actor,
                confirmed_by="test",
                commit=True,
            )

            assert visit.status == "confirmed", (
                f"Expected 'confirmed', got '{visit.status}'. "
                f"confirm_visit() must accept 'confirmation_processing' as a valid source status."
            )
        finally:
            repro.close()

    def test_confirm_visit_still_accepts_pending_confirmation(self, session_factory, clean_db):
        """NON-REGRESSION: confirm_visit() with status='pending_confirmation' must
        still work (the fix must not break the existing path)."""
        setup = session_factory()
        token, visit_id = _setup_pending_visit(setup, channel="telegram")
        setup.close()

        repro = session_factory()
        try:
            lifecycle = VisitLifecycleService(repro)
            actor = type("U", (), {"id": "test"})()
            visit = lifecycle.confirm_visit(
                visit_id=visit_id,
                current_user=actor,
                confirmed_by="test",
                commit=True,
            )

            assert visit.status == "confirmed"
        finally:
            repro.close()

    def test_confirm_visit_rejects_active_status(self, session_factory, clean_db):
        """NON-REGRESSION: confirm_visit() with status='open' must still raise 409
        (the fix must not over-accept)."""
        setup = session_factory()
        token, visit_id = _setup_pending_visit(setup, channel="telegram")
        setup.close()

        # Set status to open (active)
        setup2 = session_factory()
        visit = setup2.query(Visit).filter(Visit.id == visit_id).first()
        visit.status = "open"
        setup2.commit()
        setup2.close()

        repro = session_factory()
        try:
            from fastapi import HTTPException
            lifecycle = VisitLifecycleService(repro)
            actor = type("U", (), {"id": "test"})()

            with pytest.raises(HTTPException) as exc_info:
                lifecycle.confirm_visit(
                    visit_id=visit_id,
                    current_user=actor,
                    confirmed_by="test",
                    commit=True,
                )

            assert exc_info.value.status_code == 409
            assert exc_info.value.detail["reason"] == "not_pending_confirmation"
        finally:
            repro.close()


@pytest.mark.unit
class TestTelegramConfirmationFlow:
    """TH-2: Telegram confirmation must succeed (not HTTP 500)."""

    def test_telegram_confirmation_succeeds(self, session_factory, clean_db):
        """REGRESSION: confirm_by_telegram() must return success, not HTTP 500.

        Before fix: HTTP 500 (confirmation_processing → 409 → 500).
        After fix: success=True, status=confirmed or open.
        """
        setup = session_factory()
        token, visit_id = _setup_pending_visit(setup, channel="telegram")
        setup.close()

        repro = session_factory()
        try:
            service = VisitConfirmationService(repro)
            result = service.confirm_by_telegram(
                token=token,
                telegram_user_id="123456789",
                source_ip="127.0.0.1",
                user_agent="Mozilla/5.0",
            )

            assert result["success"] is True, (
                f"Telegram confirmation must succeed. Got: {result}"
            )
            assert result["status"] in ("confirmed", "open"), (
                f"Expected 'confirmed' or 'open', got '{result['status']}'"
            )
        finally:
            repro.close()


@pytest.mark.unit
class TestPWAConfirmationFlow:
    """TH-2: PWA confirmation must succeed (not HTTP 500)."""

    def test_pwa_confirmation_succeeds(self, session_factory, clean_db):
        """REGRESSION: confirm_by_pwa() must return success, not HTTP 500.

        Before fix: HTTP 500 (confirmation_processing → 409 → 500).
        After fix: success=True, status=confirmed or open.
        """
        setup = session_factory()
        token, visit_id = _setup_pending_visit(setup, channel="pwa")
        setup.close()

        repro = session_factory()
        try:
            service = VisitConfirmationService(repro)
            result = service.confirm_by_pwa(
                token=token,
                patient_phone="+998901234567",
                source_ip="127.0.0.1",
                user_agent="Mozilla/5.0",
            )

            assert result["success"] is True, (
                f"PWA confirmation must succeed. Got: {result}"
            )
            assert result["status"] in ("confirmed", "open"), (
                f"Expected 'confirmed' or 'open', got '{result['status']}'"
            )
        finally:
            repro.close()


@pytest.mark.integration
class TestConcurrentConfirmationClaim:
    """TH-2: concurrent confirmation must allow exactly one mutation.

    This is the regression guard for the concurrency test from
    test_confirmation_split_flow_concurrency.py. It verifies that
    the atomic claim pattern (UPDATE WHERE status = 'pending_confirmation')
    correctly serializes concurrent confirmations.
    """

    def test_parallel_telegram_confirmation_allows_only_one(
        self, session_factory, clean_db
    ):
        """REGRESSION: two concurrent confirm_by_telegram() calls on the same
        visit must result in exactly 1 success and 1 rejection.

        The atomic claim (UPDATE WHERE status = 'pending_confirmation') ensures
        only one thread can transition to 'confirmation_processing'. The other
        thread sees updated == 0 → returns None → 404.
        """
        setup = session_factory()
        token, visit_id = _setup_pending_visit(setup, channel="telegram")
        setup.close()

        barrier = threading.Barrier(2)
        successes: list[int] = []
        failures: list[int] = []
        lock = threading.Lock()

        def worker():
            session = session_factory()
            try:
                barrier.wait()
                service = VisitConfirmationService(session)
                try:
                    result = service.confirm_by_telegram(
                        token=token,
                        telegram_user_id="123456789",
                        source_ip="127.0.0.1",
                        user_agent="Mozilla/5.0",
                    )
                    with lock:
                        successes.append(int(result["visit_id"]))
                except VisitConfirmationDomainError:
                    with lock:
                        failures.append(1)
            finally:
                session.close()

        threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        # Verify in NEW independent session
        verify = session_factory()
        try:
            visit = verify.query(Visit).filter(Visit.id == visit_id).first()
            # Exactly 1 success, 1 failure
            assert len(successes) == 1, (
                f"Expected exactly 1 success, got {len(successes)}. "
                f"Successes: {successes}, Failures: {len(failures)}"
            )
            assert len(failures) == 1, (
                f"Expected exactly 1 failure, got {len(failures)}. "
                f"Successes: {len(successes)}, Failures: {failures}"
            )
            # Visit is confirmed or open (same-day = open)
            assert visit.status in ("confirmed", "open"), (
                f"Expected 'confirmed' or 'open', got '{visit.status}'"
            )
        finally:
            verify.close()
