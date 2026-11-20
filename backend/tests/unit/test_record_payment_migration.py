"""CL-1a regression tests: POST /billing/payments (record_payment migration).

Verifies that record_payment() correctly delegates to
PaymentInvariantService.create_payment_for_visit(commit=False) while
preserving Invoice update semantics.

Covers the acceptance criteria:
  - Payment is created (status='paid', paid_at set)
  - Invoice paid_amount is updated
  - Invoice balance is updated
  - Invoice status transitions (DRAFT→PARTIALLY_PAID→PAID)
  - Invoice paid_date is set when fully paid
  - Non-existent invoice → error
  - Invoice without visit_id → error
  - receipt_no and provider_payment_id are set (fields not in create_payment_for_visit)
  - Existing billing tests remain green

Note: concurrent PostgreSQL test is in test_record_payment_concurrency.py
(separate file, requires real PostgreSQL like Gate D / Finding F).
"""
from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

# Add backend to path
sys.path.insert(0, "backend")


# ============================================================
# Unit tests for record_payment() — uses mocked DB
# ============================================================

class TestRecordPaymentMigration:
    """Verify record_payment() delegates to PaymentInvariantService and preserves Invoice semantics."""

    def _make_service(self, db_session):
        """Create a BillingService with mocked PaymentInvariantService."""
        from app.services.billing_service import BillingService
        from app.services.billing_service_pkg._base import BillingSettings
        from unittest.mock import MagicMock, patch

        service = BillingService(db_session)

        # Mock get_billing_settings to return a simple settings object
        service.get_billing_settings = MagicMock(return_value=type(
            "Settings", (), {"currency_code": "UZS"}
        )())

        # Mock _generate_payment_number
        service._generate_payment_number = MagicMock(return_value="RCPT-TEST-001")

        # Mock _get_local_timestamp_naive
        service._get_local_timestamp_naive = MagicMock(return_value=datetime.now(UTC))

        # Mock db.commit and db.refresh — unit tests don't have real DB state
        # for the mock payment returned by create_payment_for_visit
        service.db.commit = MagicMock()
        service.db.refresh = MagicMock()

        return service

    def _make_invoice(self, db_session, visit_id=None, total_amount=10000, paid_amount=0):
        """Create a test Invoice."""
        from app.models.billing import Invoice, InvoiceStatus
        from app.models.visit import Visit

        if visit_id is not None:
            db_session.add(Visit(
                id=visit_id, patient_id=1, status="open", discount_mode="none", confirmation_context_epoch=1,
            ))
            db_session.flush()
        invoice = Invoice(
            invoice_number=f"TEST-{uuid4().hex[:12]}",
            patient_id=1,
            visit_id=visit_id,
            subtotal=total_amount,
            total_amount=total_amount,
            paid_amount=paid_amount,
            balance=total_amount - paid_amount,
            status=InvoiceStatus.DRAFT,
        )
        db_session.add(invoice)
        db_session.flush()
        return invoice

    def test_record_payment_creates_payment_and_updates_invoice(self, db_session):
        """Payment is created and Invoice paid_amount/balance/status are updated."""
        from unittest.mock import MagicMock, patch
        from app.models.billing import InvoiceStatus
        from app.models.payment import Payment

        service = self._make_service(db_session)
        invoice = self._make_invoice(db_session, visit_id=1, total_amount=10000)

        # Mock PaymentInvariantService.create_payment_for_visit
        mock_payment = Payment(
            id=1, visit_id=1, amount=10000, currency="UZS",
            method="cash", status="paid", paid_at=datetime.now(UTC),
        )

        with patch(
            "app.services.payment_invariant_service.PaymentInvariantService.create_payment_for_visit",
            return_value=mock_payment,
        ):
            result = service.record_payment(
                invoice_id=invoice.id,
                amount=10000,
                payment_method="cash",
                current_user=type("U", (), {"id": 1})(),
            )

        # Payment created
        assert result is mock_payment
        # receipt_no and provider_payment_id set (fields not in create_payment_for_visit)
        assert result.receipt_no == "RCPT-TEST-001"
        assert result.provider_payment_id is None

        # Invoice updated
        assert invoice.paid_amount == 10000
        assert invoice.balance == 0
        assert invoice.status == InvoiceStatus.PAID
        assert invoice.paid_date is not None

    def test_record_payment_partial_payment(self, db_session):
        """Partial payment: Invoice status = PARTIALLY_PAID, balance > 0."""
        from unittest.mock import patch
        from app.models.billing import InvoiceStatus
        from app.models.payment import Payment

        service = self._make_service(db_session)
        invoice = self._make_invoice(db_session, visit_id=1, total_amount=10000)

        mock_payment = Payment(
            id=1, visit_id=1, amount=5000, currency="UZS",
            method="cash", status="paid", paid_at=datetime.now(UTC),
        )

        with patch(
            "app.services.payment_invariant_service.PaymentInvariantService.create_payment_for_visit",
            return_value=mock_payment,
        ):
            service.record_payment(
                invoice_id=invoice.id,
                amount=5000,
                payment_method="cash",
                current_user=type("U", (), {"id": 1})(),
            )

        assert invoice.paid_amount == 5000
        assert invoice.balance == 5000
        assert invoice.status == InvoiceStatus.PARTIALLY_PAID

    def test_record_payment_nonexistent_invoice_raises(self, db_session):
        """Non-existent invoice → ValueError."""
        service = self._make_service(db_session)

        with pytest.raises(ValueError, match="Счет не найден"):
            service.record_payment(
                invoice_id=99999,
                amount=10000,
                payment_method="cash",
                current_user=type("U", (), {"id": 1})(),
            )

    def test_record_payment_invoice_without_visit_raises(self, db_session):
        """Invoice without visit_id → ValueError."""
        service = self._make_service(db_session)
        invoice = self._make_invoice(db_session, visit_id=None, total_amount=10000)

        with pytest.raises(ValueError, match="нет связанного визита"):
            service.record_payment(
                invoice_id=invoice.id,
                amount=10000,
                payment_method="cash",
                current_user=type("U", (), {"id": 1})(),
            )

    def test_record_payment_passes_current_user_to_invariant_service(self, db_session):
        """Verify current_user is passed to PaymentInvariantService."""
        from unittest.mock import MagicMock, patch
        from app.models.payment import Payment

        service = self._make_service(db_session)
        invoice = self._make_invoice(db_session, visit_id=1, total_amount=10000)

        mock_payment = Payment(
            id=1, visit_id=1, amount=10000, currency="UZS",
            method="cash", status="paid", paid_at=datetime.now(UTC),
        )

        test_user = type("U", (), {"id": 42})()

        with patch(
            "app.services.payment_invariant_service.PaymentInvariantService.create_payment_for_visit",
            return_value=mock_payment,
        ) as mock_create:
            service.record_payment(
                invoice_id=invoice.id,
                amount=10000,
                payment_method="cash",
                current_user=test_user,
            )

        # Verify create_payment_for_visit was called with current_user
        assert mock_create.called
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["current_user"] is test_user
        assert call_kwargs["commit"] is False  # critical: commit=False for Invoice update

    def test_record_payment_backward_compat_created_by(self, db_session):
        """Backward compatibility: created_by (int) is wrapped into a UserRef object."""
        from unittest.mock import patch
        from app.models.payment import Payment

        service = self._make_service(db_session)
        invoice = self._make_invoice(db_session, visit_id=1, total_amount=10000)

        mock_payment = Payment(
            id=1, visit_id=1, amount=10000, currency="UZS",
            method="cash", status="paid", paid_at=datetime.now(UTC),
        )

        with patch(
            "app.services.payment_invariant_service.PaymentInvariantService.create_payment_for_visit",
            return_value=mock_payment,
        ) as mock_create:
            service.record_payment(
                invoice_id=invoice.id,
                amount=10000,
                payment_method="cash",
                created_by=99,  # backward compat: int instead of User object
            )

        # Verify current_user was wrapped with .id = 99
        call_kwargs = mock_create.call_args.kwargs
        assert hasattr(call_kwargs["current_user"], "id")
        assert call_kwargs["current_user"].id == 99

    def test_record_payment_sets_receipt_no_and_provider_payment_id(self, db_session):
        """receipt_no and provider_payment_id are set after create_payment_for_visit."""
        from unittest.mock import patch
        from app.models.payment import Payment

        service = self._make_service(db_session)
        invoice = self._make_invoice(db_session, visit_id=1, total_amount=10000)

        mock_payment = Payment(
            id=1, visit_id=1, amount=10000, currency="UZS",
            method="cash", status="paid", paid_at=datetime.now(UTC),
            receipt_no=None, provider_payment_id=None,
        )

        with patch(
            "app.services.payment_invariant_service.PaymentInvariantService.create_payment_for_visit",
            return_value=mock_payment,
        ):
            service.record_payment(
                invoice_id=invoice.id,
                amount=10000,
                payment_method="cash",
                reference_number="REF-12345",
                current_user=type("U", (), {"id": 1})(),
            )

        assert mock_payment.receipt_no == "RCPT-TEST-001"
        assert mock_payment.provider_payment_id == "REF-12345"

    def test_record_payment_amount_passed_as_decimal(self, db_session):
        """Verify amount is converted to Decimal before passing to create_payment_for_visit."""
        from unittest.mock import patch
        from app.models.payment import Payment

        service = self._make_service(db_session)
        invoice = self._make_invoice(db_session, visit_id=1, total_amount=10000)

        mock_payment = Payment(
            id=1, visit_id=1, amount=10000, currency="UZS",
            method="cash", status="paid", paid_at=datetime.now(UTC),
        )

        with patch(
            "app.services.payment_invariant_service.PaymentInvariantService.create_payment_for_visit",
            return_value=mock_payment,
        ) as mock_create:
            service.record_payment(
                invoice_id=invoice.id,
                amount=10000,  # int
                payment_method="cash",
                current_user=type("U", (), {"id": 1})(),
            )

        call_kwargs = mock_create.call_args.kwargs
        assert isinstance(call_kwargs["amount"], Decimal)
        assert call_kwargs["amount"] == Decimal("10000")


@pytest.fixture
def billing_payment_invoice(db_session, test_visit, test_service):
    from app.models.billing import BillingSettings, Invoice
    from app.models.visit import VisitService

    visit_id = test_visit.id
    invoice = Invoice(
        invoice_number=f"SYNTHETIC-{uuid4().hex[:12]}", patient_id=test_visit.patient_id,
        visit_id=visit_id, subtotal=100, total_amount=100, paid_amount=0, balance=100,
    )
    db_session.add_all([
        invoice,
        BillingSettings(currency_code="UZS"),
        VisitService(
            visit_id=visit_id, service_id=test_service.id, name="Synthetic billing line",
            qty=1, price=Decimal("100.00"), currency="UZS",
        ),
    ])
    db_session.commit()
    return invoice


@pytest.mark.parametrize("reject_response", [False, True])
def test_billing_route_validates_the_receipt_before_commit(
    client, db_session, admin_auth_headers, billing_payment_invoice, monkeypatch, reject_response,
):
    from app.api.v1.endpoints import billing
    from app.models.billing import Invoice, InvoiceStatus
    from app.models.payment import Payment, PaymentClientRequest

    invoice = billing_payment_invoice
    invoice_id, patient_id = invoice.id, invoice.patient_id
    visit_id = invoice.visit_id
    key = str(uuid4())
    if reject_response:
        response_model = billing.PaymentResponse

        def reject_invalid_receipt(**payload):
            payload.pop("payment_number")
            return response_model(**payload)

        monkeypatch.setattr(billing, "PaymentResponse", reject_invalid_receipt)

    response = client.post(
        "/api/v1/billing/payments", headers=admin_auth_headers,
        json={"invoice_id": invoice_id, "amount": 100, "payment_method": "cash",
              "client_request_id": key,
              "reference_number": "SYNTHETIC-REF", "description": "Synthetic payment"},
    )
    db_session.expire_all()
    receipts = db_session.query(Payment).filter_by(visit_id=visit_id).all()
    requests = db_session.query(PaymentClientRequest).filter_by(client_request_id=key).all()
    stored_invoice = db_session.get(Invoice, invoice_id)
    if reject_response:
        assert response.status_code == 500, response.text
        assert receipts == []
        assert requests == []
        assert stored_invoice.paid_amount == 0 and stored_invoice.balance == 100
        assert stored_invoice.status == InvoiceStatus.DRAFT
        return

    assert response.status_code == 200, response.text
    receipt, = receipts
    request, = requests
    payload = response.json()
    assert payload["id"] == receipt.id
    assert payload["payment_number"] == receipt.receipt_no
    assert payload["invoice_id"] == invoice_id and payload["patient_id"] == patient_id
    assert payload["amount"] == 100 and payload["payment_method"] == "cash"
    assert payload["reference_number"] == "SYNTHETIC-REF" and payload["is_confirmed"] is True
    assert receipt.client_request_id == key and request.endpoint == "billing"
    assert request.response_payload == {**payload, "recorded_by": request.created_by}
    assert stored_invoice.paid_amount == 100 and stored_invoice.balance == 0
    assert stored_invoice.status == InvoiceStatus.PAID


@pytest.mark.parametrize(
    ("amount_token", "invoice_total", "invoice_status", "expected_status"),
    [
        ("10.0000000000000001", 100, "draft", 422),
        ("true", 100, "draft", 422),
        ("90.01", 90, "draft", 400),
        ("100.01", 200, "draft", 400),
        ("10", 100, "cancelled", 409),
        ("10", 100.125, "draft", 409),
    ],
    ids=["sub-cent", "boolean", "invoice-balance", "visit-balance", "closed-invoice", "legacy-fraction"],
)
def test_billing_route_rejects_invalid_settlement_without_mutations(
    client, db_session, admin_auth_headers, billing_payment_invoice,
    amount_token, invoice_total, invoice_status, expected_status,
):
    from app.models.billing import Invoice, InvoiceStatus
    from app.models.payment import Payment

    invoice = billing_payment_invoice
    invoice.total_amount = invoice.balance = invoice_total
    invoice.status = InvoiceStatus(invoice_status)
    db_session.commit()
    invoice_id, visit_id = invoice.id, invoice.visit_id
    key = str(uuid4())
    response = client.post(
        "/api/v1/billing/payments",
        headers={**admin_auth_headers, "content-type": "application/json"},
        content=(
            f'{{"invoice_id":{invoice_id},"amount":{amount_token},"payment_method":"cash",'
            f'"client_request_id":"{key}"}}'
        ),
    )

    assert response.status_code == expected_status, response.text
    db_session.expire_all()
    assert db_session.query(Payment).filter_by(visit_id=visit_id).count() == 0
    stored = db_session.get(Invoice, invoice_id)
    assert stored.paid_amount == 0 and stored.balance == invoice_total
    assert stored.status == InvoiceStatus(invoice_status)


def test_billing_route_accepts_exact_cents_with_legacy_float_noise(
    client, db_session, admin_auth_headers, billing_payment_invoice,
):
    from app.models.billing import Invoice, InvoiceStatus
    from app.models.payment import Payment

    invoice = billing_payment_invoice
    invoice.total_amount = invoice.balance = 0.1 + 0.2
    db_session.commit()
    invoice_id, visit_id = invoice.id, invoice.visit_id
    response = client.post(
        "/api/v1/billing/payments", headers=admin_auth_headers,
        json={
            "invoice_id": invoice_id, "amount": "0.30", "payment_method": "cash",
            "client_request_id": str(uuid4()),
        },
    )

    assert response.status_code == 200, response.text
    db_session.expire_all()
    receipt = db_session.query(Payment).filter_by(visit_id=visit_id).one()
    assert receipt.amount == Decimal("0.30")
    stored = db_session.get(Invoice, invoice_id)
    assert stored.paid_amount == 0.30 and stored.balance == 0
    assert stored.status == InvoiceStatus.PAID


def test_billing_receipt_replays_to_its_owner_and_exact_intent(
    client, db_session, admin_user, admin_auth_headers, billing_payment_invoice, caplog,
):
    import logging

    from app.models.payment import Payment, PaymentClientRequest
    from app.models.user import User
    from tests.conftest import mint_access_token

    other = User(username=f"synthetic-{uuid4().hex[:12]}", hashed_password="!", role="Cashier", is_active=True)
    db_session.add(other)
    db_session.commit()
    other_headers = {"Authorization": f"Bearer {mint_access_token(other)}"}
    invoice_id = billing_payment_invoice.id
    visit_id = billing_payment_invoice.visit_id
    route = "/api/v1/billing/payments"
    request = {"invoice_id": invoice_id, "amount": "100.00", "payment_method": "cash"}
    assert client.post(route, headers=admin_auth_headers, json=request).status_code == 422
    key = str(uuid4())
    request["client_request_id"] = key
    caplog.set_level(logging.INFO, logger="app.services.payment_client_requests")
    first = client.post(route, headers=admin_auth_headers, json=request)
    assert first.status_code == 200, first.text

    replay = client.post(route, headers=admin_auth_headers, json={**request, "amount": 100})
    assert replay.status_code == 200 and replay.json() == first.json()
    for change in ({"amount": "50.00"}, {"payment_method": "card"}, {"invoice_id": invoice_id + 1}):
        conflict = client.post(route, headers=admin_auth_headers, json={**request, **change})
        assert conflict.status_code == 409, conflict.text
        assert conflict.json()["detail"]["reason"] == "client_request_id_intent_mismatch"
    denied = client.post(route, headers=other_headers, json=request)
    assert denied.status_code == 409, denied.text
    assert denied.json()["detail"]["reason"] == "client_request_id_owner_mismatch"
    assert client.post(route, json=request).status_code in {401, 403}
    assert db_session.query(Payment).filter_by(visit_id=visit_id).count() == 1
    anchor = db_session.query(PaymentClientRequest).filter_by(client_request_id=key).one()
    assert anchor.created_by == admin_user.id
    assert anchor.response_payload["id"] == first.json()["id"]
    assert "recorded_by" not in first.json()
    recorded = [record for record in caplog.records if record.name == "app.services.payment_client_requests"]
    messages = [record.getMessage() for record in recorded]
    assert messages.count("payment.client_request_committed") == 1
    assert {"payment.client_request_replayed", "payment.client_request_owner_mismatch",
            "payment.client_request_intent_mismatch"} <= set(messages)
    assert all(not record.args for record in recorded)


def test_sqlite_billing_receipt_guard_preserves_committed_audit():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine
    from sqlalchemy.exc import DBAPIError

    from app.models.payment import PaymentClientRequest
    from tests.integration.test_encounter_migration_pg import _migration

    engine = create_engine("sqlite://")
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
            conn.exec_driver_sql("INSERT INTO users (id) VALUES (1)")
            table = PaymentClientRequest.__table__
            table.create(conn)
            migration = _migration("0138_billing_payment_receipts.py")
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            migration.downgrade()
            migration.upgrade()

            receipt = {
                "client_request_id": str(uuid4()),
                "endpoint": "billing",
                "response_payload": {"id": 1, "recorded_by": 1},
                "request_fingerprint": "f" * 64,
                "created_by": 1,
            }
            with pytest.raises(DBAPIError, match="invalid billing payment receipt"), conn.begin_nested():
                conn.execute(table.insert().values({**receipt, "response_payload": {"id": 1}}))
            conn.execute(table.insert().values(receipt))
            with pytest.raises(DBAPIError, match="immutable billing payment receipt"), conn.begin_nested():
                conn.execute(table.update().values(request_fingerprint=None))
            with pytest.raises(DBAPIError), conn.begin_nested():
                migration.downgrade()
            assert conn.execute(table.select()).one().response_payload["recorded_by"] == 1
    finally:
        engine.dispose()
