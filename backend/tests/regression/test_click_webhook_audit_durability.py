"""Regression tests for P2-3 Finding C: Click webhook audit trail durability.

Finding C: When a webhook arrives for an already-terminal payment,
BillingService raises ValueError → transaction_ctx rolls back →
PaymentWebhook record is lost → no audit trail of the rejected webhook.

Fix (PR #2730): persist PaymentWebhook record in a SEPARATE transaction
BEFORE entering transaction_ctx. This ensures the webhook receipt
survives even if the business transaction rolls back.

ANALYSIS CORRECTION:
  Initial read-only audit incorrectly concluded that Click lacked
  transaction_ctx entirely. Code review identified that transaction_ctx
  IS present (line 191); the actual issue is that PaymentWebhook is
  created INSIDE the same transaction and is rolled back when downstream
  payment processing raises ValueError.

Tests use PRODUCTION-LIKE session management (not savepoints) and verify
data from a NEW session after the original session closes.

Run:
    pytest backend/tests/regression/test_click_webhook_audit_durability.py -v
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_click_audit.db")
os.environ.setdefault("ENV", "dev")
os.environ.setdefault("SECRET_KEY", "test-secret-key-click-audit-32-chars!")
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
from app.models.patient import Patient  # noqa: E402
from app.models.payment import Payment  # noqa: E402
from app.models.payment_webhook import PaymentWebhook  # noqa: E402
from app.models.service import Service  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.visit import Visit  # noqa: E402


@pytest.fixture(scope="module")
def db_engine(tmp_path_factory):
    """Real engine — NO savepoint tricks. Commits are real."""
    db_path = tmp_path_factory.mktemp("click_audit") / "payments.db"
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


@pytest.fixture
def production_session(db_engine):
    """Production-like session: autocommit=False, NO savepoint."""
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def verify_session(db_engine):
    """Separate session to verify data was actually committed."""
    Session = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def clean_db(db_engine):
    with db_engine.connect() as conn:
        for table in [
            "payment_transactions", "payment_webhooks", "payments",
            "queue_entries", "visit_services", "visits",
            "daily_queues", "services", "doctors", "patients", "users",
        ]:
            conn.execute(__import__("sqlalchemy").text(f"DELETE FROM {table}"))
        conn.commit()


def _setup_payment(session, *, status: str = "pending"):
    """Create a payment with the given status."""
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
    """Build a synthetic callback in the provider's minor units."""
    return {
        "click_trans_id": f"test-{uuid.uuid4().hex[:8]}",
        "merchant_trans_id": issued_order,
        "amount": amount * 100,
        "sign_string": "test-sig",
    }


@pytest.mark.unit
class TestClickWebhookAuditDurability:
    """New legacy observations remain auditable without mutating payment state."""

    @pytest.mark.parametrize(("payment_status", "amount"), [
        ("pending", 10000),
        ("refunded", 10000),
        ("pending", 999),
    ])
    def test_click_hold_persists_the_receipt_across_sessions(
        self, production_session, verify_session, clean_db, payment_status, amount,
    ):
        from app.services.provider_webhook_service import ProviderWebhookService

        payment = _setup_payment(production_session, status=payment_status)
        payment_id = payment.id
        callback = _make_click_webhook_data(payment.provider_payment_id, amount=amount)
        production_session.expunge_all()
        manager = MagicMock()
        manager.get_provider.return_value.validate_webhook_signature.return_value = True

        with patch("app.services.provider_webhook_service.get_payment_manager", return_value=manager):
            result = ProviderWebhookService(production_session).process_click_webhook(callback)

        assert result == {"error": -1, "error_note": "Payment reconciliation required"}
        production_session.close()
        receipt = verify_session.query(PaymentWebhook).filter_by(
            provider="click", transaction_id=callback["merchant_trans_id"],
        ).one()
        assert receipt.status == "failed" and receipt.error_message == "provider_reconciliation_required"
        assert receipt.visit_id is None and receipt.processed_at is not None
        assert receipt.raw_data == callback
        assert verify_session.get(Payment, payment_id).status == payment_status
        manager.process_webhook.assert_not_called()
