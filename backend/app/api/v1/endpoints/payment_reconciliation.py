"""
Payment Reconciliation API Endpoints

✅ SECURITY: Endpoints for payment reconciliation and discrepancy detection
"""
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.services.payment_reconciliation import PaymentReconciliationService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/reconcile/{provider}")
async def reconcile_provider(
    provider: str,
    start_date: date = Query(..., description="Start date for reconciliation"),
    end_date: date = Query(..., description="End date for reconciliation"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Cashier")),
) -> Dict:
    """
    Reconcile payments with a specific provider
    
    ✅ SECURITY: Requires Admin or Cashier role
    """
    try:
        service = PaymentReconciliationService(db)
        result = service.reconcile_provider(provider, start_date, end_date)
        return result
    except Exception as e:
        logger.error(f"Error in reconcile_provider: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reconciliation error: {str(e)}",
        )


@router.post("/reconcile/all")
async def reconcile_all_providers(
    start_date: date = Query(..., description="Start date for reconciliation"),
    end_date: date = Query(..., description="End date for reconciliation"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin")),
) -> Dict:
    """
    Reconcile all payment providers
    
    ✅ SECURITY: Requires Admin role
    """
    try:
        service = PaymentReconciliationService(db)
        result = service.reconcile_all_providers(start_date, end_date)
        return result
    except Exception as e:
        logger.error(f"Error in reconcile_all_providers: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reconciliation error: {str(e)}",
        )


@router.get("/reconcile/report")
async def get_reconciliation_report(
    start_date: date = Query(None, description="Start date (defaults to 7 days ago)"),
    end_date: date = Query(None, description="End date (defaults to today)"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Cashier")),
) -> Dict:
    """
    Generate comprehensive reconciliation report
    
    ✅ SECURITY: Requires Admin or Cashier role
    """
    try:
        if not start_date:
            start_date = date.today() - timedelta(days=7)
        if not end_date:
            end_date = date.today()

        service = PaymentReconciliationService(db)
        report = service.generate_reconciliation_report(start_date, end_date)
        
        # Add alerts
        alerts = service.alert_on_discrepancies(report)
        report["alerts"] = alerts
        
        return report
    except Exception as e:
        logger.error(f"Error generating reconciliation report: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation error: {str(e)}",
        )


@router.get("/reconcile/missing/{provider}")
async def get_missing_payments(
    provider: str,
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin", "Cashier")),
) -> Dict:
    """
    Detect missing payments for a provider
    
    ✅ SECURITY: Requires Admin or Cashier role
    """
    try:
        service = PaymentReconciliationService(db)
        missing = service.detect_missing_payments(provider, days)
        return {
            "provider": provider,
            "days": days,
            "missing_count": len(missing),
            "missing_payments": missing,
        }
    except Exception as e:
        logger.error(f"Error detecting missing payments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}",
        )


@router.get("/reconcile/alerts")
async def get_reconciliation_alerts(
    threshold: float = Query(1000.0, description="Minimum difference to alert on"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles("Admin")),
) -> Dict:
    """
    Get reconciliation alerts for all providers
    
    ✅ SECURITY: Requires Admin role
    """
    try:
        from decimal import Decimal
        
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()

        service = PaymentReconciliationService(db)
        reconciliation = service.reconcile_all_providers(start_date, end_date)
        alerts = service.alert_on_discrepancies(reconciliation, Decimal(threshold))

        return {
            "alerts": alerts,
            "alert_count": len(alerts),
            "high_severity_count": len([a for a in alerts if a.get("severity") == "high"]),
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting reconciliation alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error: {str(e)}",
        )


