from __future__ import annotations

from datetime import date
from unittest.mock import Mock, patch

import pytest

from app.services.payment_reconciliation_api_service import (
    PaymentReconciliationApiDomainError,
    PaymentReconciliationApiService,
)


@pytest.mark.unit
class TestPaymentReconciliationApiService:
    def test_get_reconciliation_report_applies_default_dates_and_alerts(self):
        reconciliation_service = Mock()
        reconciliation_service.generate_reconciliation_report.return_value = {
            "providers": {}
        }
        reconciliation_service.alert_on_discrepancies.return_value = [
            {"severity": "high"}
        ]

        with patch(
            "app.services.payment_reconciliation_api_service.PaymentReconciliationService",
            return_value=reconciliation_service,
        ):
            service = PaymentReconciliationApiService(db=Mock())
            result = service.get_reconciliation_report(start_date=None, end_date=None)

        assert result["alerts"] == [{"severity": "high"}]
        call_args = reconciliation_service.generate_reconciliation_report.call_args[0]
        assert isinstance(call_args[0], date)
        assert isinstance(call_args[1], date)
        assert call_args[1] >= call_args[0]

    def test_get_missing_payments_wraps_payload(self):
        reconciliation_service = Mock()
        reconciliation_service.detect_missing_payments.return_value = [{"payment_id": 7}]

        with patch(
            "app.services.payment_reconciliation_api_service.PaymentReconciliationService",
            return_value=reconciliation_service,
        ):
            service = PaymentReconciliationApiService(db=Mock())
            result = service.get_missing_payments(provider="click", days=5)

        assert result["provider"] == "click"
        assert result["days"] == 5
        assert result["missing_count"] == 1
        assert result["missing_payments"][0]["payment_id"] == 7

    def test_reconcile_provider_raises_domain_error_on_failure(self):
        reconciliation_service = Mock()
        reconciliation_service.reconcile_provider.side_effect = RuntimeError("boom")

        with patch(
            "app.services.payment_reconciliation_api_service.PaymentReconciliationService",
            return_value=reconciliation_service,
        ):
            service = PaymentReconciliationApiService(db=Mock())
            with pytest.raises(PaymentReconciliationApiDomainError) as exc_info:
                service.reconcile_provider(
                    provider="payme",
                    start_date=date(2026, 2, 1),
                    end_date=date(2026, 2, 2),
                )

        assert exc_info.value.status_code == 500
        assert "Reconciliation error" in exc_info.value.detail
