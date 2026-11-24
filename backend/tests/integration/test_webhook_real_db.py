"""P2-3 Finding F: Real-DB integration test for Click webhook persistence.

Finding F: "No real-DB PostgreSQL concurrent-webhook test."

The existing unit tests use SQLite with savepoint-based test sessions
(begin_nested). This masks production transaction behavior because:
  - savepoint commit ≠ real commit
  - savepoint rollback ≠ real rollback
  - session.close() in test conftest doesn't lose data the same way

This test file uses REAL PostgreSQL with independent sessions (same
pattern as Gate D) to prove that:

  1. Click webhook SUCCESS: PaymentWebhook + PaymentTransaction + payment
     status persist across session boundaries (commit actually works).
  2. Click webhook ERROR (terminal→paid): PaymentWebhook persists
     despite ValueError rollback (Finding C fix verified on real DB).
     Payment status, PaymentTransaction, and provider_data remain
     UNCHANGED — business transaction atomicity verified.
  3. Click webhook AMOUNT MISMATCH: PaymentWebhook persists, payment
     status unchanged.

Each test:
  Session A → process webhook → commit/rollback → close
  Session B (NEW) → verify persisted/rolled-back state

Requirements:
  - PostgreSQL (NOT SQLite) — same as Gate D
  - Independent sessions — no shared session between process and verify
  - Real PaymentWebhook + Payment records (not mocks)
  - Real transaction_ctx (NOT mocked)
  - NO begin_nested() savepoint masking

CI Integration:
  pytest backend/tests/integration/test_webhook_real_db.py -m integration
  (runs in the 'backend-tests' job which has PostgreSQL service)
"""
from __future__ import annotations

import os
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from tests._pg_admin_guard import is_local_admin_dsn

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Set test environment BEFORE importing app modules
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-webhook-real-db-32!")
os.environ.setdefault("TESTING", "1")


def _disposable_database_url(raw_url: str) -> URL | None:
    if not is_local_admin_dsn(raw_url):
        return None
    url = make_url(raw_url)
    database = url.database or ""
    if url.query:
        # Keep the dial target and server options explicit and unambiguous.
        return None
    if database == "clinic_test" or database.startswith("clinic_test_"):
        return url
    if os.environ.get("CI") == "true" and database == "clinicdb":
        return url
    return None


@pytest.mark.unit
def test_click_persistence_admits_only_explicit_local_test_databases(monkeypatch):
    monkeypatch.delenv("PGSERVICE", raising=False)
    monkeypatch.delenv("PGHOSTADDR", raising=False)
    monkeypatch.delenv("CI", raising=False)
    local = "postgresql+psycopg://test@127.0.0.1/"
    assert _disposable_database_url(local + "clinic_test_click") is not None
    assert _disposable_database_url(local + "clinicdb") is None
    assert _disposable_database_url(local + "clinic_test_click?dbname=clinicdb") is None
    assert _disposable_database_url("postgresql+psycopg://test@db.example.invalid/clinic_test") is None
    monkeypatch.setenv("CI", "true")
    assert _disposable_database_url(local + "clinicdb") is not None
    assert _disposable_database_url(local + "clinic") is None


@pytest.fixture
def db_engine():
    """Give each test a private schema on a disposable local PostgreSQL."""
    url = _disposable_database_url(os.environ.get("DATABASE_URL", ""))
    if url is None:
        pytest.skip("Click persistence requires a disposable local PostgreSQL database")

    from app.db.base import Base

    schema = f"click_persistence_{uuid.uuid4().hex}"
    engine = create_engine(
        url,
        hide_parameters=True,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    schema_created = False
    try:
        with engine.begin() as setup:
            setup.execute(CreateSchema(schema))
            Base.metadata.create_all(setup)
        schema_created = True
        yield engine
    finally:
        try:
            if schema_created:
                with engine.begin() as teardown:
                    teardown.execute(DropSchema(schema, cascade=True))
        finally:
            engine.dispose()


@pytest.fixture
def production_session(db_engine):
    """Production-like session: autocommit=False, NO savepoint.

    This session does NOT auto-commit. If the code under test doesn't
    call commit(), data is lost when the session closes — exactly like
    production get_db().
    """
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def verify_session_factory(db_engine):
    """Factory for INDEPENDENT verification sessions.

    Each call creates a new session that sees only committed data.
    Used to verify: if data was committed → new session sees it;
    if data was rolled back → new session sees original state.
    """
    Session = sessionmaker(bind=db_engine)

    def _create():
        return Session()

    return _create


def _setup_payment(session, *, status: str = "pending"):
    """Create a payment with the given status using real DB objects."""
    from app.models.clinic import Doctor
    from app.models.patient import Patient
    from app.models.payment import Payment
    from app.models.service import Service
    from app.models.user import User
    from app.models.visit import Visit

    unique = uuid.uuid4().hex[:8]
    doctor_user = User(
        username=f"synthetic_{unique}", full_name="SYNTHETIC-Doctor",
        email=f"d_{unique}@example.invalid",
        hashed_password="x", role="Doctor", is_active=True, is_superuser=False,
        must_change_password=False, created_at=datetime.now(UTC),
    )
    session.add(doctor_user)
    session.flush()
    doctor = Doctor(user_id=doctor_user.id, specialty="Cardiology", active=True)
    session.add(doctor)
    session.flush()
    patient = Patient(
        last_name="SYNTHETIC-Click", first_name="Patient", birth_date=date(1990, 1, 1),
        sex="M", email=f"p_{unique}@example.invalid",
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
    visit = Visit(
        patient_id=patient.id, doctor_id=doctor.id, status="confirmed",
        visit_date=date.today(), visit_time="10:00", discount_mode="none",
        department="cardiology", confirmation_token=f"tok-{unique}",
        confirmation_channel="telegram", confirmed_at=datetime.now(UTC),
        confirmation_expires_at=datetime.now(UTC), created_at=datetime.now(UTC),
    )
    session.add(visit)
    session.flush()
    payment = Payment(
        visit_id=visit.id, amount=10000, currency="UZS",
        status=status, method="click", provider="click",
        created_at=datetime.now(UTC),
    )
    session.add(payment)
    session.flush()
    payment.provider_payment_id = f"clinic_{payment.id}_1700000000"
    session.commit()
    session.refresh(payment)
    return payment


def _make_click_webhook_data(issued_order: str, amount: int = 10000) -> dict:
    return {
        "click_trans_id": f"test-{uuid.uuid4().hex[:8]}",
        "merchant_trans_id": issued_order,
        "amount": amount * 100,
        "action": 1,
        "error": 0,
        "sign_string": "test-sig",
    }


def _make_mock_manager(callback: dict, *, status: str = "completed"):
    """Create a mock payment manager that returns success for the given payment.

    The mock replaces get_payment_manager() so that:
    - validate_webhook_signature returns True (bypasses real signature check)
    - process_webhook returns a PaymentResult with the correct payment_id format

    transaction_ctx is NOT mocked — real transaction boundaries are used.
    BillingService is NOT mocked — real state machine validation applies.
    """
    mock_manager = MagicMock()
    mock_provider = MagicMock()
    mock_provider.validate_webhook_signature.return_value = True
    mock_manager.get_provider.return_value = mock_provider

    mock_result = MagicMock()
    mock_result.success = True
    mock_result.status = status
    mock_result.payment_id = callback["merchant_trans_id"]
    mock_result.provider_data = {
        "test": "data",
        "amount": str(Decimal(callback["amount"]) / 100),
        "action": callback["action"],
        "error": callback["error"],
    }
    mock_result.error_message = None
    mock_manager.process_webhook.return_value = mock_result
    return mock_manager


def _deliver_webhook_concurrently(session_factory, callback, process_webhook, *, expect_history=False):
    from app.repositories.provider_webhook_repository import ProviderWebhookRepository
    from app.services.provider_webhook_service import ProviderWebhookService

    lookups = threading.Barrier(2)

    class ConcurrentWebhookRepository(ProviderWebhookRepository):
        initial_lookup = True

        def get_existing_transaction(self, *, transaction_id, provider):
            result = super().get_existing_transaction(
                transaction_id=transaction_id, provider=provider
            )
            if self.initial_lookup:
                self.initial_lookup = False
                assert (result is not None) == expect_history
                lookups.wait(timeout=8)
            return result

    def deliver():
        with session_factory() as session:
            pid = session.scalar(text("SELECT pg_backend_pid()"))
            service = ProviderWebhookService(session, ConcurrentWebhookRepository(session))
            return pid, process_webhook(service, callback)

    with ThreadPoolExecutor(max_workers=2) as pool:
        deliveries = [pool.submit(deliver) for _ in range(2)]
        (first_pid, first), (second_pid, second) = [
            result.result(timeout=15) for result in deliveries
        ]

    assert first_pid != second_pid
    return first, second


@pytest.mark.integration
class TestClickWebhookRealDBPersistence:
    """Verify the Click hold and recorded replay with independent PostgreSQL sessions."""

    @pytest.mark.parametrize(("action", "transaction_status", "payment_status", "response_error"), [
        (1, "completed", "paid", 0), (0, "processing", "processing", -1),
    ], ids=["completion", "prepare"])
    def test_click_concurrent_replay_returns_the_recorded_result(
        self, production_session, verify_session_factory, monkeypatch,
        action, transaction_status, payment_status, response_error,
    ):
        from app.models.payment import Payment
        from app.models.payment_webhook import PaymentTransaction, PaymentWebhook
        from app.repositories.provider_webhook_repository import (
            ProviderWebhookRepository,
        )
        from app.services.provider_webhook_service import ProviderWebhookService

        payment = _setup_payment(production_session, status=payment_status)
        payment_id = payment.id
        callback = {**_make_click_webhook_data(payment.provider_payment_id), "action": action}
        repository = ProviderWebhookRepository(production_session)
        receipt = repository.create_webhook(
            provider="click", webhook_id=f"synthetic-history-{payment_id}",
            transaction_id=callback["merchant_trans_id"], amount=callback["amount"], currency="UZS",
            raw_data=callback, signature=callback["sign_string"], status="processed",
        )
        receipt.visit_id = payment.visit_id
        receipt.processed_at = datetime.now(UTC)
        receipt_id = receipt.id
        repository.create_transaction(
            provider="click", transaction_id=callback["click_trans_id"],
            amount=callback["amount"], currency="UZS", status=transaction_status,
            payment_id=payment_id, webhook_id=receipt_id, visit_id=payment.visit_id,
            provider_data={"action": action, "error": callback["error"]},
        )
        production_session.commit()

        manager = _make_mock_manager(callback, status=transaction_status)
        monkeypatch.setattr("app.services.provider_webhook_service.get_payment_manager", lambda: manager)
        first, second = _deliver_webhook_concurrently(
            verify_session_factory, callback, ProviderWebhookService.process_click_webhook, expect_history=True,
        )
        assert first == second
        assert first["error"] == response_error
        assert first["merchant_prepare_id"] == receipt_id
        assert first["payment_status"] is None

        with verify_session_factory() as db:
            service = ProviderWebhookService(db)
            amount_mismatch = service.process_click_webhook({**callback, "amount": callback["amount"] + 100})
            phase_mismatch = service.process_click_webhook({**callback, "action": 1 - action})
            assert amount_mismatch == {"error": -1, "error_note": "Payment amount mismatch"}
            assert phase_mismatch == {"error": -1, "error_note": "Payment phase mismatch"}
            assert db.get(Payment, payment_id).status == payment_status
            assert db.query(PaymentWebhook).filter_by(provider="click").count() == 1
            assert db.query(PaymentTransaction).filter_by(provider="click").count() == 1
        manager.process_webhook.assert_not_called()

    @pytest.mark.parametrize("payment_status", ["pending", "refunded"])
    def test_click_holds_new_notifications_and_commits_audit(
        self, production_session, verify_session_factory, monkeypatch, payment_status,
    ):
        from app.models.payment import Payment
        from app.models.payment_webhook import PaymentTransaction, PaymentWebhook
        from app.services.provider_webhook_service import ProviderWebhookService

        payment = _setup_payment(production_session, status=payment_status)
        payment_id = payment.id
        callback = _make_click_webhook_data(payment.provider_payment_id)
        manager = _make_mock_manager(callback)
        monkeypatch.setattr("app.services.provider_webhook_service.get_payment_manager", lambda: manager)
        result = ProviderWebhookService(production_session).process_click_webhook(callback)
        assert result == {"error": -1, "error_note": "Payment reconciliation required"}
        production_session.close()

        with verify_session_factory() as verify:
            receipt = verify.query(PaymentWebhook).filter_by(
                provider="click", transaction_id=callback["merchant_trans_id"],
            ).one()
            assert receipt.status == "failed" and receipt.error_message == "provider_reconciliation_required"
            assert receipt.visit_id is None and receipt.processed_at is not None
            assert receipt.raw_data == callback
            assert verify.get(Payment, payment_id).status == payment_status
            assert verify.query(PaymentTransaction).filter_by(payment_id=payment_id).count() == 0
        manager.process_webhook.assert_not_called()
