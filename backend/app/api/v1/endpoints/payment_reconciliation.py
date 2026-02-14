"""
Payment Reconciliation API Endpoints

✅ SECURITY: Endpoints for payment reconciliation and discrepancy detection
"""
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.services.payment_reconciliation_api_service import (
    PaymentReconciliationApiDomainError,
    PaymentReconciliationApiService,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/reconcile/{provider}")
async def reconcile_provider(
    provider: str,
    start_date: date = Query(..., description="Start date for reconciliation"),
    end_date: date = Query(..., description="End date for reconciliation"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Cashier")),
) -> dict:
    """
    Reconcile payments with a specific provider

    ✅ SECURITY: Requires Admin or Cashier role
    """
    service = PaymentReconciliationApiService(db)
    try:
        return service.reconcile_provider(
            provider=provider,
            start_date=start_date,
            end_date=end_date,
        )
    except PaymentReconciliationApiDomainError as exc:
        logger.error("Error in reconcile_provider: %s", exc.detail)
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/reconcile/all")
async def reconcile_all_providers(
    start_date: date = Query(..., description="Start date for reconciliation"),
    end_date: date = Query(..., description="End date for reconciliation"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin")),
) -> dict:
    """
    Reconcile all payment providers

    ✅ SECURITY: Requires Admin role
    """
    service = PaymentReconciliationApiService(db)
    try:
        return service.reconcile_all_providers(
            start_date=start_date,
            end_date=end_date,
        )
    except PaymentReconciliationApiDomainError as exc:
        logger.error("Error in reconcile_all_providers: %s", exc.detail)
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/reconcile/report")
async def get_reconciliation_report(
    start_date: date = Query(None, description="Start date (defaults to 7 days ago)"),
    end_date: date = Query(None, description="End date (defaults to today)"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Cashier")),
) -> dict:
    """
    Generate comprehensive reconciliation report

    ✅ SECURITY: Requires Admin or Cashier role
    """
    service = PaymentReconciliationApiService(db)
    try:
        return service.get_reconciliation_report(
            start_date=start_date,
            end_date=end_date,
        )
    except PaymentReconciliationApiDomainError as exc:
        logger.error("Error generating reconciliation report: %s", exc.detail)
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/reconcile/missing/{provider}")
async def get_missing_payments(
    provider: str,
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Cashier")),
) -> dict:
    """
    Detect missing payments for a provider

    ✅ SECURITY: Requires Admin or Cashier role
    """
    service = PaymentReconciliationApiService(db)
    try:
        return service.get_missing_payments(provider=provider, days=days)
    except PaymentReconciliationApiDomainError as exc:
        logger.error("Error detecting missing payments: %s", exc.detail)
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/reconcile/alerts")
async def get_reconciliation_alerts(
    threshold: float = Query(1000.0, description="Minimum difference to alert on"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin")),
) -> dict:
    """
    Get reconciliation alerts for all providers

    ✅ SECURITY: Requires Admin role
    """
    service = PaymentReconciliationApiService(db)
    try:
        return service.get_reconciliation_alerts(threshold=threshold)
    except PaymentReconciliationApiDomainError as exc:
        logger.error("Error getting reconciliation alerts: %s", exc.detail)
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


