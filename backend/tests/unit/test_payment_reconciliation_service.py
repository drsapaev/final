from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services.payment_reconciliation import PaymentReconciliationService


class _RepositoryStub:
    def __init__(
        self,
        *,
        transactions: list[SimpleNamespace] | None = None,
        pending_payments: list[SimpleNamespace] | None = None,
        completed_payment_ids: set[int] | None = None,
    ):
        self.transactions = transactions or []
        self.pending_payments = pending_payments or []
        self.completed_payment_ids = completed_payment_ids or set()

    def list_transactions_for_provider(self, **_: object):
        return self.transactions

    def list_pending_payments_for_provider(self, **_: object):
        return self.pending_payments

    def get_completed_transaction_for_payment(self, *, payment_id: int, **_: object):
        if payment_id in self.completed_payment_ids:
            return SimpleNamespace(id=99)
        return None


class _ProviderStub:
    def __init__(self, statement: dict):
        self._statement = statement

    def get_statement(self, _: date, __: date):
        return self._statement


class _ManagerStub:
    def __init__(self, provider: _ProviderStub | None):
        self._provider = provider

    def get_provider(self, _: str):
        return self._provider


@pytest.mark.unit
class TestPaymentReconciliationService:
    def test_reconcile_provider_detects_discrepancies(self):
        repository = _RepositoryStub(
            transactions=[
                SimpleNamespace(
                    transaction_id="t-1",
                    amount=100,
                    status="completed",
                ),
                SimpleNamespace(
                    transaction_id="t-2",
                    amount=200,
                    status="completed",
                ),
            ]
        )
        provider = _ProviderStub(
            {
                "transactions": [
                    {"transaction_id": "t-1", "amount": 100, "status": "completed"},
                    {"transaction_id": "t-2", "amount": 250, "status": "failed"},
                    {"transaction_id": "t-3", "amount": 300, "status": "completed"},
                ]
            }
        )
        service = PaymentReconciliationService(
            db=Mock(),
            repository=repository,
            payment_manager=_ManagerStub(provider),
        )

        result = service.reconcile_provider("click", date(2026, 2, 1), date(2026, 2, 2))

        assert result["provider"] == "click"
        assert result["summary"]["matched_count"] == 2
        assert result["summary"]["discrepancy_count"] == 2
        assert result["summary"]["missing_in_provider_count"] == 0
        assert result["summary"]["missing_internal_count"] == 1
        assert result["summary"]["difference"] == 350

    def test_detect_missing_payments_returns_only_unresolved(self):
        now = datetime.utcnow()
        repository = _RepositoryStub(
            pending_payments=[
                SimpleNamespace(
                    id=1,
                    amount=1000,
                    currency="UZS",
                    created_at=now - timedelta(days=3),
                    status="pending",
                ),
                SimpleNamespace(
                    id=2,
                    amount=2000,
                    currency="UZS",
                    created_at=now - timedelta(days=1),
                    status="processing",
                ),
            ],
            completed_payment_ids={2},
        )
        service = PaymentReconciliationService(
            db=Mock(),
            repository=repository,
            payment_manager=_ManagerStub(None),
        )

        missing = service.detect_missing_payments("payme", days=7)

        assert len(missing) == 1
        assert missing[0]["payment_id"] == 1
        assert missing[0]["status"] == "pending"
        assert missing[0]["days_pending"] >= 3
