"""Service layer for payment reconciliation API endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.services.payment_reconciliation import PaymentReconciliationService


@dataclass
class PaymentReconciliationApiDomainError(Exception):
    status_code: int
    detail: str


class PaymentReconciliationApiService:
    """Orchestrates payment reconciliation API flows."""

    def __init__(self, db):  # type: ignore[no-untyped-def]
        self.reconciliation_service = PaymentReconciliationService(db)

    def reconcile_provider(
        self, *, provider: str, start_date: date, end_date: date
    ) -> dict[str, Any]:
        try:
            return self.reconciliation_service.reconcile_provider(
                provider, start_date, end_date
            )
        except Exception as exc:
            raise PaymentReconciliationApiDomainError(
                status_code=500,
                detail=f"Reconciliation error: {exc}",
            ) from exc

    def reconcile_all_providers(
        self, *, start_date: date, end_date: date
    ) -> dict[str, Any]:
        try:
            return self.reconciliation_service.reconcile_all_providers(
                start_date, end_date
            )
        except Exception as exc:
            raise PaymentReconciliationApiDomainError(
                status_code=500,
                detail=f"Reconciliation error: {exc}",
            ) from exc

    def get_reconciliation_report(
        self,
        *,
        start_date: date | None,
        end_date: date | None,
    ) -> dict[str, Any]:
        effective_start = start_date or (date.today() - timedelta(days=7))
        effective_end = end_date or date.today()

        try:
            report = self.reconciliation_service.generate_reconciliation_report(
                effective_start,
                effective_end,
            )
            report["alerts"] = self.reconciliation_service.alert_on_discrepancies(report)
            return report
        except Exception as exc:
            raise PaymentReconciliationApiDomainError(
                status_code=500,
                detail=f"Report generation error: {exc}",
            ) from exc

    def get_missing_payments(
        self, *, provider: str, days: int
    ) -> dict[str, Any]:
        try:
            missing = self.reconciliation_service.detect_missing_payments(
                provider, days
            )
            return {
                "provider": provider,
                "days": days,
                "missing_count": len(missing),
                "missing_payments": missing,
            }
        except Exception as exc:
            raise PaymentReconciliationApiDomainError(
                status_code=500,
                detail=f"Error: {exc}",
            ) from exc

    def get_reconciliation_alerts(self, *, threshold: float) -> dict[str, Any]:
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()

        try:
            reconciliation = self.reconciliation_service.reconcile_all_providers(
                start_date,
                end_date,
            )
            alerts = self.reconciliation_service.alert_on_discrepancies(
                reconciliation,
                Decimal(str(threshold)),
            )
            return {
                "alerts": alerts,
                "alert_count": len(alerts),
                "high_severity_count": len(
                    [a for a in alerts if a.get("severity") == "high"]
                ),
                "generated_at": datetime.utcnow().isoformat(),
            }
        except Exception as exc:
            raise PaymentReconciliationApiDomainError(
                status_code=500,
                detail=f"Error: {exc}",
            ) from exc
