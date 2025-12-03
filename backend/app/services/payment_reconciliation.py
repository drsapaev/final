"""
Payment Reconciliation Service

✅ SECURITY: Automated reconciliation between payment providers and internal records
Detects discrepancies, missing payments, and financial inconsistencies.
"""
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.payment_webhook import PaymentTransaction, PaymentWebhook
from app.services.payment_providers.manager import PaymentProviderManager

logger = logging.getLogger(__name__)


class PaymentReconciliationService:
    """Service for payment reconciliation"""

    def __init__(self, db: Session):
        self.db = db
        self.payment_manager = PaymentProviderManager({})  # Will be initialized with config

    def reconcile_provider(
        self, provider_name: str, start_date: date, end_date: date
    ) -> Dict[str, Any]:
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
            internal_transactions = (
                self.db.query(PaymentTransaction)
                .filter(
                    PaymentTransaction.provider == provider_name,
                    PaymentTransaction.created_at >= datetime.combine(start_date, datetime.min.time()),
                    PaymentTransaction.created_at <= datetime.combine(end_date, datetime.max.time()),
                )
                .all()
            )

            # Get provider statement (if available)
            provider = self.payment_manager.get_provider(provider_name)
            provider_statement = None
            
            if provider and hasattr(provider, 'get_statement'):
                try:
                    provider_statement = provider.get_statement(start_date, end_date)
                except Exception as e:
                    logger.warning(f"Could not get provider statement: {e}")

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
            if provider_statement:
                provider_by_id = {
                    t.get("transaction_id") or t.get("id"): t
                    for t in provider_statement.get("transactions", [])
                }

                # Find matches and discrepancies
                for trans_id, internal_trans in internal_by_id.items():
                    provider_trans = provider_by_id.get(trans_id)
                    
                    if provider_trans:
                        # Compare amounts
                        provider_amount = provider_trans.get("amount", 0)
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
            total_provider = 0
            if provider_statement:
                total_provider = sum(
                    t.get("amount", 0) for t in provider_statement.get("transactions", [])
                )

            return {
                "provider": provider_name,
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "summary": {
                    "total_internal": total_internal,
                    "total_provider": total_provider,
                    "difference": total_provider - total_internal,
                    "matched_count": len(matched),
                    "discrepancy_count": len(discrepancies),
                    "missing_in_provider_count": len(missing_in_provider),
                    "missing_internal_count": len(missing_internal),
                },
                "discrepancies": discrepancies,
                "missing_in_provider": missing_in_provider,
                "missing_internal": missing_internal,
                "reconciled_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error reconciling provider {provider_name}: {e}")
            return {
                "provider": provider_name,
                "error": str(e),
                "reconciled_at": datetime.utcnow().isoformat(),
            }

    def reconcile_all_providers(
        self, start_date: date, end_date: date
    ) -> Dict[str, Any]:
        """
        Reconcile all payment providers
        
        Returns:
            Combined reconciliation report for all providers
        """
        providers = ["click", "payme", "kaspi"]
        results = {}

        for provider in providers:
            results[provider] = self.reconcile_provider(provider, start_date, end_date)

        # Calculate overall summary
        total_discrepancies = sum(
            r.get("summary", {}).get("discrepancy_count", 0) for r in results.values()
        )
        total_difference = sum(
            r.get("summary", {}).get("difference", 0) for r in results.values()
        )

        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "providers": results,
            "overall_summary": {
                "total_discrepancies": total_discrepancies,
                "total_difference": total_difference,
                "has_discrepancies": total_discrepancies > 0 or total_difference != 0,
            },
            "reconciled_at": datetime.utcnow().isoformat(),
        }

    def detect_missing_payments(
        self, provider_name: str, days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Detect payments that should have been received but weren't
        
        Args:
            provider_name: Provider to check
            days: Number of days to look back
        
        Returns:
            List of potentially missing payments
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Find payments that were initiated but never completed
            pending_payments = (
                self.db.query(Payment)
                .filter(
                    Payment.provider == provider_name,
                    Payment.status.in_(["pending", "processing"]),
                    Payment.created_at >= cutoff_date,
                )
                .all()
            )

            missing = []
            for payment in pending_payments:
                # Check if there's a corresponding transaction
                transaction = (
                    self.db.query(PaymentTransaction)
                    .filter(
                        PaymentTransaction.payment_id == payment.id,
                        PaymentTransaction.provider == provider_name,
                        PaymentTransaction.status == "completed",
                    )
                    .first()
                )

                if not transaction:
                    # Payment was initiated but never completed
                    missing.append({
                        "payment_id": payment.id,
                        "amount": payment.amount,
                        "currency": payment.currency,
                        "created_at": payment.created_at.isoformat(),
                        "status": payment.status,
                        "days_pending": (datetime.utcnow() - payment.created_at).days,
                    })

            return missing

        except Exception as e:
            logger.error(f"Error detecting missing payments: {e}")
            return []

    def generate_reconciliation_report(
        self, start_date: date, end_date: date, format: str = "json"
    ) -> Dict[str, Any]:
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

        # Add missing payments detection
        for provider in ["click", "payme", "kaspi"]:
            missing = self.detect_missing_payments(provider, days=(end_date - start_date).days)
            if provider in reconciliation.get("providers", {}):
                reconciliation["providers"][provider]["missing_payments"] = missing

        return reconciliation

    def alert_on_discrepancies(
        self, reconciliation: Dict[str, Any], threshold: Decimal = Decimal("1000")
    ) -> List[Dict[str, Any]]:
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
                    "message": f"Reconciliation error: {provider_data['error']}",
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


