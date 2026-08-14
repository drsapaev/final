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
