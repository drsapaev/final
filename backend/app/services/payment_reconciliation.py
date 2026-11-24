"""
Payment Reconciliation Service

✅ SECURITY: Automated reconciliation between payment providers and internal records
Detects discrepancies, missing payments, and financial inconsistencies.
"""
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.payment_reconciliation_repository import (
    PaymentReconciliationRepository,
)
from app.services.payment_providers.manager import PaymentProviderManager

logger = logging.getLogger(__name__)

SUPPORTED_RECONCILIATION_PROVIDERS = ("click", "payme", "kaspi")
RECONCILIATION_UNAVAILABLE = "Payment reconciliation is temporarily unavailable"


def _as_aware_utc(value: datetime) -> datetime:
    """Return ``value`` as a timezone-aware UTC datetime.

    SQLAlchemy ``DateTime(timezone=True)`` columns return aware datetimes on
    PostgreSQL but naive datetimes on SQLite (used by the test suite). Mixing
    naive and aware datetimes in comparisons or arithmetic raises
    ``TypeError``. Normalize every datetime read from the database to aware
    UTC before comparing with ``datetime.now(UTC)``.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class PaymentReconciliationService:
    """Service for payment reconciliation"""

    def __init__(
        self,
        db: Session,
        repository: PaymentReconciliationRepository | None = None,
        payment_manager: PaymentProviderManager | None = None,
    ):
        self.db = db
        self.repository = repository or PaymentReconciliationRepository(db)
        self.payment_manager = payment_manager or PaymentProviderManager({})

    def reconcile_provider(
        self, provider_name: str, start_date: date, end_date: date
    ) -> dict[str, Any]:
        """
        Reconcile payments with a specific provider

        Args:
            provider_name: Name of the provider (click, payme, kaspi)
            start_date: Start date for reconciliation
            end_date: End date for reconciliation

        Returns:
            Reconciliation report with discrepancies
        """
        try:
            # Get all internal transactions for the period
            internal_transactions = self.repository.list_transactions_for_provider(
                provider_name=provider_name,
                start_at=datetime.combine(start_date, datetime.min.time()),
                end_at=datetime.combine(end_date, datetime.max.time()),
            )

            # Get provider statement (if available)
            provider = self.payment_manager.get_provider(provider_name)
            provider_transactions = None

            get_statement = getattr(provider, "get_statement", None)
            if callable(get_statement):
                try:
                    statement = get_statement(start_date, end_date)
                except Exception as exc:
                    logger.warning("Could not get provider statement (%s)", type(exc).__name__)
                else:
                    if isinstance(statement, dict) and isinstance(statement.get("transactions"), list):
                        provider_transactions = statement["transactions"]

            # Compare internal vs provider records
            discrepancies = []
            matched = []
            missing_in_provider = []
            missing_internal = []

            # Group internal transactions by transaction_id
            internal_by_id = {
                t.transaction_id: t for t in internal_transactions
            }

            # If we have provider statement, compare
            if provider_transactions is not None:
                provider_by_id = {
                    t.get("transaction_id") or t.get("id"): t
                    for t in provider_transactions
                }
                if None in provider_by_id or len(provider_by_id) != len(provider_transactions):
                    raise ValueError("Invalid provider transaction identifiers")

                # Find matches and discrepancies
                for trans_id, internal_trans in internal_by_id.items():
                    provider_trans = provider_by_id.get(trans_id)

                    if provider_trans:
                        # Compare amounts
                        provider_amount = provider_trans["amount"]
                        internal_amount = internal_trans.amount

                        if provider_amount != internal_amount:
                            discrepancies.append({
                                "type": "amount_mismatch",
                                "transaction_id": trans_id,
                                "internal_amount": internal_amount,
                                "provider_amount": provider_amount,
                                "difference": provider_amount - internal_amount,
                            })

                        # Compare statuses
                        provider_status = provider_trans.get("status")
                        internal_status = internal_trans.status

                        if provider_status != internal_status:
                            discrepancies.append({
                                "type": "status_mismatch",
                                "transaction_id": trans_id,
                                "internal_status": internal_status,
                                "provider_status": provider_status,
                            })

                        matched.append(trans_id)
                    else:
                        missing_in_provider.append(trans_id)

                # Find transactions in provider but not in internal
                for trans_id in provider_by_id:
                    if trans_id not in internal_by_id:
                        missing_internal.append(trans_id)

            # Calculate totals
            total_internal = sum(t.amount for t in internal_transactions)
            total_provider = (
                sum(t["amount"] for t in provider_transactions)
                if provider_transactions is not None
                else None
            )
            statement_available = provider_transactions is not None

            return {
                "provider": provider_name,
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "statement_available": statement_available,
                "summary": {
                    "total_internal": total_internal,
                    "total_provider": total_provider,
                    "difference": total_provider - total_internal if total_provider is not None else None,
                    "matched_count": len(matched) if statement_available else None,
                    "discrepancy_count": len(discrepancies) if statement_available else None,
                    "missing_in_provider_count": len(missing_in_provider) if statement_available else None,
                    "missing_internal_count": len(missing_internal) if statement_available else None,
                },
                "discrepancies": discrepancies,
                "missing_in_provider": missing_in_provider,
                "missing_internal": missing_internal,
                "reconciled_at": datetime.now(UTC).isoformat(),
            }

        except Exception as exc:
            logger.error("Payment reconciliation failed (%s)", type(exc).__name__)
            return {
                "provider": provider_name,
                "statement_available": False,
                "error": RECONCILIATION_UNAVAILABLE,
                "reconciled_at": datetime.now(UTC).isoformat(),
            }

    def reconcile_all_providers(
        self, start_date: date, end_date: date
    ) -> dict[str, Any]:
        """
        Reconcile all payment providers

        Returns:
            Combined reconciliation report for all providers
        """
        results = {}

        for provider in SUPPORTED_RECONCILIATION_PROVIDERS:
            results[provider] = self.reconcile_provider(provider, start_date, end_date)

        compared = [report["summary"] for report in results.values() if report.get("statement_available")]
        comparison_complete = len(compared) == len(results)
        has_discrepancies = any(
            summary["discrepancy_count"]
            or summary["difference"]
            or summary["missing_in_provider_count"]
            or summary["missing_internal_count"]
            for summary in compared
        )

        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "providers": results,
            "overall_summary": {
                "comparison_complete": comparison_complete,
                "total_discrepancies": (
                    sum(summary["discrepancy_count"] for summary in compared)
                    if comparison_complete else None
                ),
                "total_difference": (
                    sum(summary["difference"] for summary in compared)
                    if comparison_complete else None
                ),
                "has_discrepancies": has_discrepancies if comparison_complete or has_discrepancies else None,
            },
            "reconciled_at": datetime.now(UTC).isoformat(),
        }

    def detect_missing_payments(
        self, provider_name: str, days: int = 7
    ) -> list[dict[str, Any]]:
        """
        Detect payments that should have been received but weren't

        Args:
            provider_name: Provider to check
            days: Number of days to look back

        Returns:
            List of potentially missing payments
        """
        cutoff_date = datetime.now(UTC) - timedelta(days=days)
        return self._find_missing_payments(provider_name, cutoff_date=cutoff_date)

    def _find_missing_payments(
        self, provider_name: str, *, cutoff_date: datetime, end_at: datetime | None = None,
    ) -> list[dict[str, Any]]:
        pending_payments = self.repository.list_pending_payments_for_provider(
            provider_name=provider_name,
            cutoff_date=cutoff_date,
            end_at=end_at,
        )

        now = datetime.now(UTC)
        missing = []
        for payment in pending_payments:
            transaction = self.repository.get_completed_transaction_for_payment(
                payment_id=payment.id,
                provider_name=provider_name,
            )
            if not transaction:
                missing.append({
                    "payment_id": payment.id,
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "created_at": payment.created_at.isoformat(),
                    "status": payment.status,
                    "days_pending": (now - _as_aware_utc(payment.created_at)).days,
                })
        return missing

    def generate_reconciliation_report(
        self, start_date: date, end_date: date, format: str = "json"
    ) -> dict[str, Any]:
        """
        Generate a comprehensive reconciliation report

        Args:
            start_date: Start date
            end_date: End date
            format: Report format (json, csv)

        Returns:
            Reconciliation report
        """
        reconciliation = self.reconcile_all_providers(start_date, end_date)

        # Apply the report's UTC date boundaries to the missing-payment section.
        start_at = datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
        end_at = datetime.combine(end_date, datetime.max.time(), tzinfo=UTC)
        for provider in SUPPORTED_RECONCILIATION_PROVIDERS:
            missing = self._find_missing_payments(provider, cutoff_date=start_at, end_at=end_at)
            if provider in reconciliation.get("providers", {}):
                reconciliation["providers"][provider]["missing_payments"] = missing

        return reconciliation

    def alert_on_discrepancies(
        self, reconciliation: dict[str, Any], threshold: Decimal = Decimal("1000")
    ) -> list[dict[str, Any]]:
        """
        Generate alerts for significant discrepancies

        Args:
            reconciliation: Reconciliation report
            threshold: Minimum difference to alert on (in currency units)

        Returns:
            List of alerts
        """
        alerts = []

        for provider_name, provider_data in reconciliation.get("providers", {}).items():
            if "error" in provider_data:
                alerts.append({
                    "severity": "error",
                    "provider": provider_name,
                    "message": RECONCILIATION_UNAVAILABLE,
                })
                continue
            if provider_data.get("statement_available") is False:
                alerts.append({
                    "severity": "warning",
                    "provider": provider_name,
                    "message": "Provider statement unavailable",
                })
                continue

            summary = provider_data.get("summary", {})

            # Alert on amount discrepancies
            difference = abs(summary.get("difference", 0))
            if difference > threshold:
                alerts.append({
                    "severity": "high",
                    "provider": provider_name,
                    "message": f"Significant amount discrepancy: {difference} {provider_data.get('currency', 'UZS')}",
                    "difference": difference,
                })

            # Alert on missing transactions
            if summary.get("missing_in_provider_count", 0) > 0:
                alerts.append({
                    "severity": "medium",
                    "provider": provider_name,
                    "message": f"{summary['missing_in_provider_count']} transactions missing in provider",
                })

            if summary.get("missing_internal_count", 0) > 0:
                alerts.append({
                    "severity": "high",
                    "provider": provider_name,
                    "message": f"{summary['missing_internal_count']} transactions in provider but not in internal records",
                })

            # Alert on status mismatches
            status_mismatches = [
                d for d in provider_data.get("discrepancies", [])
                if d.get("type") == "status_mismatch"
            ]
            if status_mismatches:
                alerts.append({
                    "severity": "medium",
                    "provider": provider_name,
                    "message": f"{len(status_mismatches)} transactions with status mismatches",
                })

        return alerts


