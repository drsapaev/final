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
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# Set test environment BEFORE importing app modules
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-webhook-real-db-32!")
os.environ.setdefault("TESTING", "1")


@pytest.fixture(scope="module")
def db_engine():
    """Create a real PostgreSQL engine for the test module.

    Refuses SQLite — real-DB tests require PostgreSQL transaction semantics.
    """
    db_url = os.environ.get("DATABASE_URL", "")

    if not db_url or "sqlite" in db_url:
        pytest.skip(
            "Finding F real-DB tests require PostgreSQL. "
            "Set DATABASE_URL to a postgresql+psycopg:// URL. "
            f"Got: {db_url or '(empty)'}"
        )

    engine = create_engine(db_url, echo=False, pool_pre_ping=True)

    from app.db.base_class import Base
    from app.models import (  # noqa: F401
        audit, appointment, clinic, emr_v2, lab, online_queue,
        payment, payment_invoice, payment_webhook, patient, user, visit,
    )
    from app.models import (  # noqa: F401
        authentication, billing, department, emr, file_system,
        role_permission, schedule, user_profile,
    )

    Base.metadata.create_all(engine)

    yield engine

    # Clean up test data (don't drop tables — other tests may use them)
    with engine.connect() as conn:
        for table in [
            "payment_transactions", "payment_webhooks", "payments",
            "queue_entries", "visit_services", "visits",
            "daily_queues", "services", "doctors", "patients", "users",
        ]:
            conn.execute(text(f"DELETE FROM {table}"))
        conn.commit()
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


@pytest.fixture
def clean_db(db_engine):
    """Clean all relevant tables before each test."""
    with db_engine.connect() as conn:
        for table in [
            "payment_transactions", "payment_webhooks", "payments",
            "queue_entries", "visit_services", "visits",
            "daily_queues", "services", "doctors", "patients", "users",
        ]:
            conn.execute(text(f"DELETE FROM {table}"))
        conn.commit()


def _setup_payment(session, *, status: str = "pending"):
    """Create a payment with the given status using real DB objects."""
    from app.models.clinic import Doctor
    from app.models.patient import Patient
    from app.models.payment import Payment
    from app.models.service import Service
    from app.models.user import User
    from app.models.visit import Visit, VisitService

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
        sex="M", phone="+998900000000", email=f"p_{unique}@t.local",
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
        status=status, method="click",
        created_at=datetime.now(UTC),
    )
    session.add(payment)
    session.commit()
    session.refresh(payment)
    return payment


def _make_click_webhook_data(payment_id: int) -> dict:
    """Create Click webhook data with correct order_id format."""
    ts = int(datetime.now(UTC).timestamp())
    return {
        "click_trans_id": f"test-{uuid.uuid4().hex[:8]}",
        "merchant_trans_id": f"clinic_{payment_id}_{ts}",
        "amount": 10000,
        "sign_string": "test-sig",
        "_test_ts": ts,
    }


def _make_mock_manager(payment_id: int, status: str = "completed", ts: int = None):
    """Create a mock payment manager that returns success for the given payment.

    The mock replaces get_payment_manager() so that:
    - validate_webhook_signature returns True (bypasses real signature check)
    - process_webhook returns a PaymentResult with the correct payment_id format

    transaction_ctx is NOT mocked — real transaction boundaries are used.
    BillingService is NOT mocked — real state machine validation applies.
    """
    if ts is None:
        ts = int(datetime.now(UTC).timestamp())
    mock_manager = MagicMock()
    mock_provider = MagicMock()
    mock_provider.validate_webhook_signature.return_value = True
    mock_manager.get_provider.return_value = mock_provider

    mock_result = MagicMock()
    mock_result.success = True
    mock_result.status = status
    mock_result.payment_id = f"clinic_{payment_id}_{ts}"
    mock_result.provider_data = {"test": "data", "amount": Decimal("10000")}
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
        self, production_session, verify_session_factory, clean_db
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
        original_provider_data = None  # pending payment has no provider_data yet
        production_session.expunge_all()

        # Process Click webhook
        webhook_data = _make_click_webhook_data(payment_id)
        mock_manager = _make_mock_manager(
            payment_id, "completed", ts=webhook_data.get("_test_ts")
        )

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=mock_manager,
        ):
            repo = ProviderWebhookRepository(production_session)
            service = ProviderWebhookService(production_session, repository=repo)
            result = service.process_click_webhook(webhook_data)

        # Close Session A (simulates production get_db cleanup)
        production_session.close()

        # Verify from NEW Session B
        verify = verify_session_factory()
        try:
            # 1. PaymentWebhook must exist
            webhook_records = verify.query(PaymentWebhook).filter(
                PaymentWebhook.provider == "click"
            ).all()
            assert len(webhook_records) >= 1, (
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
            assert len(tx_records) >= 1, (
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
        self, production_session, verify_session_factory, clean_db
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
        production_session.expunge_all()

        webhook_data = _make_click_webhook_data(payment_id)
        mock_manager = _make_mock_manager(
            payment_id, "completed", ts=webhook_data.get("_test_ts")
        )

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=mock_manager,
        ):
            repo = ProviderWebhookRepository(production_session)
            service = ProviderWebhookService(production_session, repository=repo)
            result = service.process_click_webhook(webhook_data)

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

    def test_click_amount_mismatch_webhook_survives(
        self, production_session, verify_session_factory, clean_db
    ):
        """Click AMOUNT MISMATCH: PaymentWebhook survives rejection.

        Session A: process Click webhook with wrong amount → rejected
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
        production_session.expunge_all()

        webhook_data = _make_click_webhook_data(payment_id)
        webhook_data["amount"] = 999  # wrong amount

        mock_manager = _make_mock_manager(
            payment_id, "completed", ts=webhook_data.get("_test_ts")
        )

        with patch(
            "app.services.provider_webhook_service.get_payment_manager",
            return_value=mock_manager,
        ):
            repo = ProviderWebhookRepository(production_session)
            service = ProviderWebhookService(production_session, repository=repo)
            result = service.process_click_webhook(webhook_data)

        production_session.close()

        verify = verify_session_factory()
        try:
            # 1. PaymentWebhook must persist
            webhook_records = verify.query(PaymentWebhook).filter(
                PaymentWebhook.provider == "click"
            ).all()
            assert len(webhook_records) >= 1, (
                "PaymentWebhook record NOT found after amount mismatch on PostgreSQL. "
                "Audit trail should persist even for rejected webhooks."
            )

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
