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
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
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
        "sign_string": "test-sig",
    }


def _make_mock_manager(callback: dict):
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
    mock_result.status = "completed"
    mock_result.payment_id = callback["merchant_trans_id"]
    mock_result.provider_data = {"test": "data", "amount": str(Decimal(callback["amount"]) / 100)}
    mock_result.error_message = None
    mock_manager.process_webhook.return_value = mock_result
    return mock_manager


@pytest.mark.integration
class TestClickWebhookRealDBPersistence:
    """Finding F: Real PostgreSQL tests for Click webhook persistence.

    These tests use real PostgreSQL with independent sessions to prove
    that commit/rollback/session-close behavior matches production.

    Pattern:
        Session A → process webhook → close
        Session B (NEW) → verify persisted state

    Contract verified (from PR #2730):

        Click webhook
              │
              ├── create PaymentWebhook
              ├── COMMIT audit transaction
              └── business transaction
                     │
                     ├── success → COMMIT payment changes
                     │
                     └── error → ROLLBACK payment changes
                                  │
                                  └── PaymentWebhook remains persisted
    """

    def test_click_success_persists_across_sessions(
        self, production_session, verify_session_factory
    ):
        """Click SUCCESS: PaymentWebhook AND payment status AND PaymentTransaction persist.

        Session A: process Click webhook (success)
        Session A: close
        Session B (NEW): verify PaymentWebhook exists, payment status='paid',
                         PaymentTransaction exists.

        This proves that transaction_ctx commits on the success path and
        the data survives session close — real production commit semantics.
        """
        from app.services.provider_webhook_service import ProviderWebhookService
        from app.repositories.provider_webhook_repository import ProviderWebhookRepository
        from app.models.payment import Payment
        from app.models.payment_webhook import PaymentTransaction, PaymentWebhook

        # Setup: create payment in pending state
        payment = _setup_payment(production_session, status="pending")
        payment_id = payment.id
        webhook_data = _make_click_webhook_data(payment.provider_payment_id)
        production_session.expunge_all()

        # Process Click webhook
        mock_manager = _make_mock_manager(webhook_data)

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=mock_manager,
        ):
            repo = ProviderWebhookRepository(production_session)
            service = ProviderWebhookService(production_session, repository=repo)
            result = service.process_click_webhook(webhook_data)
            with verify_session_factory() as retry_session:
                replay = ProviderWebhookService(retry_session).process_click_webhook(webhook_data)

        assert result["error"] == 0
        assert replay["error"] == 0
        assert replay["error_note"] == "Already processed"
        assert replay["merchant_prepare_id"] == result["merchant_prepare_id"]
        mock_manager.process_webhook.assert_called_once()

        # Close Session A (simulates production get_db cleanup)
        production_session.close()

        # Verify from NEW Session B
        verify = verify_session_factory()
        try:
            # 1. PaymentWebhook must exist
            webhook_records = verify.query(PaymentWebhook).filter(
                PaymentWebhook.provider == "click"
            ).all()
            assert len(webhook_records) == 1, (
                "PaymentWebhook record NOT found in new PostgreSQL session. "
                "Click webhook data was not committed — production data loss."
            )

            # 2. Payment status must be updated to 'paid'
            committed_payment = verify.query(Payment).filter(
                Payment.id == payment_id
            ).first()
            assert committed_payment is not None, "Payment not found"
            assert committed_payment.status == "paid", (
                f"Payment status should be 'paid' after Click webhook success. "
                f"Got: {committed_payment.status}. Data was not committed to PostgreSQL."
            )

            # 3. PaymentTransaction must exist
            tx_records = verify.query(PaymentTransaction).filter(
                PaymentTransaction.payment_id == payment_id
            ).all()
            assert len(tx_records) == 1, (
                "PaymentTransaction NOT found after Click webhook success. "
                "Business transaction did not commit."
            )

            # 4. provider_data must be updated
            assert committed_payment.provider_data is not None, (
                "provider_data should be set after successful webhook"
            )
            assert "test" in committed_payment.provider_data, (
                f"provider_data should contain mock data. Got: {committed_payment.provider_data}"
            )

            # 5. paid_at must be set
            assert committed_payment.paid_at is not None, (
                "paid_at should be set after payment status='paid'"
            )
        finally:
            verify.close()

    def test_click_error_webhook_survives_rollback(
        self, production_session, verify_session_factory
    ):
        """Click ERROR (terminal→paid): PaymentWebhook survives ValueError rollback.

        Session A: process Click webhook for terminal payment → ValueError
        Session A: close (transaction_ctx rolled back)
        Session B (NEW): PaymentWebhook EXISTS, payment status UNCHANGED,
                         PaymentTransaction ABSENT, provider_data UNCHANGED.

        This is the Finding C fix verified on real PostgreSQL. It proves
        BOTH audit trail durability AND business transaction atomicity.
        """
        from app.services.provider_webhook_service import ProviderWebhookService
        from app.repositories.provider_webhook_repository import ProviderWebhookRepository
        from app.models.payment import Payment
        from app.models.payment_webhook import PaymentTransaction, PaymentWebhook

        # Setup: create payment in terminal state (refunded)
        payment = _setup_payment(production_session, status="refunded")
        payment_id = payment.id
        original_provider_data = payment.provider_data  # should be None for new payment
        webhook_data = _make_click_webhook_data(payment.provider_payment_id)
        production_session.expunge_all()

        mock_manager = _make_mock_manager(webhook_data)

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=mock_manager,
        ):
            repo = ProviderWebhookRepository(production_session)
            service = ProviderWebhookService(production_session, repository=repo)
            result = service.process_click_webhook(webhook_data)

        assert result == {"error": -1, "error_note": "Internal server error"}
        # Close Session A
        production_session.close()

        # Verify from NEW Session B
        verify = verify_session_factory()
        try:
            # 1. PaymentWebhook MUST persist despite ValueError rollback
            webhook_records = verify.query(PaymentWebhook).filter(
                PaymentWebhook.provider == "click"
            ).all()
            assert len(webhook_records) >= 1, (
                "PaymentWebhook record NOT found after ValueError rollback on PostgreSQL. "
                "Finding C fix not working on real DB — audit trail lost."
            )

            # 2. Payment status must NOT change (terminal preserved)
            committed_payment = verify.query(Payment).filter(
                Payment.id == payment_id
            ).first()
            assert committed_payment.status == "refunded", (
                f"Terminal payment status changed to '{committed_payment.status}' on PostgreSQL. "
                f"Should remain 'refunded' — business transaction should have rolled back."
            )

            # 3. PaymentTransaction must NOT exist (business transaction rolled back)
            tx_records = verify.query(PaymentTransaction).filter(
                PaymentTransaction.payment_id == payment_id
            ).all()
            assert len(tx_records) == 0, (
                f"PaymentTransaction found ({len(tx_records)} records) after ValueError rollback. "
                f"Business transaction should have rolled back — PaymentTransaction should NOT exist."
            )

            # 4. provider_data must NOT be changed by the failed business transaction
            assert committed_payment.provider_data == original_provider_data, (
                f"provider_data changed from {original_provider_data!r} to "
                f"{committed_payment.provider_data!r} — business transaction should have "
                f"rolled back all mutations."
            )

            # 5. paid_at must NOT be set (payment is still refunded, not paid)
            assert committed_payment.paid_at is None, (
                "paid_at should not be set for a refunded payment — "
                "business transaction rollback should have reverted it."
            )
        finally:
            verify.close()

    @pytest.mark.parametrize(("order_issued", "amount", "audit_error"), [
        (True, 999, "provider_amount_mismatch"),
        (False, 10000, "provider_order_mismatch"),
    ])
    def test_click_rejected_webhook_survives(
        self, production_session, verify_session_factory, order_issued, amount, audit_error,
    ):
        """The audit survives a rejected amount or an unissued order.

        Session A: process rejected Click webhook
        Session A: close
        Session B (NEW): PaymentWebhook EXISTS, payment status unchanged,
                         PaymentTransaction ABSENT, provider_data unchanged.
        """
        from app.services.provider_webhook_service import ProviderWebhookService
        from app.repositories.provider_webhook_repository import ProviderWebhookRepository
        from app.models.payment import Payment
        from app.models.payment_webhook import PaymentTransaction, PaymentWebhook

        payment = _setup_payment(production_session, status="pending")
        payment_id = payment.id
        original_provider_data = payment.provider_data
        order = payment.provider_payment_id if order_issued else f"clinic_{payment_id}_1700000001"
        production_session.expunge_all()

        webhook_data = _make_click_webhook_data(order, amount)
        mock_manager = _make_mock_manager(webhook_data)

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=mock_manager,
        ):
            repo = ProviderWebhookRepository(production_session)
            service = ProviderWebhookService(production_session, repository=repo)
            result = service.process_click_webhook(webhook_data)

        assert result["error"] == -1
        production_session.close()

        verify = verify_session_factory()
        try:
            # 1. PaymentWebhook must persist
            webhook_records = verify.query(PaymentWebhook).filter(
                PaymentWebhook.provider == "click"
            ).all()
            assert len(webhook_records) >= 1, (
                "PaymentWebhook record NOT found after rejection on PostgreSQL. "
                "Audit trail should persist even for rejected webhooks."
            )
            assert webhook_records[0].error_message == audit_error

            # 2. Payment status must remain 'pending'
            committed_payment = verify.query(Payment).filter(
                Payment.id == payment_id
            ).first()
            assert committed_payment.status == "pending", (
                f"Payment status should remain 'pending'. Got: {committed_payment.status}"
            )

            # 3. PaymentTransaction must NOT exist
            tx_records = verify.query(PaymentTransaction).filter(
                PaymentTransaction.payment_id == payment_id
            ).all()
            assert len(tx_records) == 0, (
                f"PaymentTransaction found ({len(tx_records)} records) after amount mismatch. "
                f"Should NOT exist — business transaction should not have committed."
            )

            # 4. provider_data must be unchanged
            assert committed_payment.provider_data == original_provider_data, (
                f"provider_data changed from {original_provider_data!r} to "
                f"{committed_payment.provider_data!r} — should be unchanged."
            )
        finally:
            verify.close()
