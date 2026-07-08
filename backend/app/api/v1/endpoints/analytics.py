import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.services.analytics import AnalyticsService
from app.services.analytics_simple_api_service import (
    AnalyticsSimpleApiService,
    AnalyticsSimpleDomainError,
)

router = APIRouter()
logger = logging.getLogger(__name__)

ANALYTICS_PUBLIC_ERROR = "Internal server error"
CLINICAL_ANALYTICS_ROLES = ["admin", "doctor", "nurse"]
FINANCIAL_ANALYTICS_ROLES = ["admin", "manager"]


def _build_payment_provider_payload(
    db: Session, start: datetime, end: datetime, department: str | None
) -> dict:
    revenue_breakdown = AnalyticsService.get_revenue_breakdown_analytics(
        db, start, end, department
    )

    providers = {}
    for provider_code, stats in revenue_breakdown.get("provider_breakdown", {}).items():
        providers[provider_code] = {
            "name": provider_code,
            "count": stats.get("count", 0),
            "total_amount": stats.get("total_amount", 0),
            "average_amount": stats.get("average_amount", 0),
            "success_rate": 100.0 if stats.get("count", 0) > 0 else 0.0,
        }

    return {
        "providers": providers,
        "summary": {
            "active_providers": sum(1 for stats in providers.values() if stats["count"]),
            "total_transactions": revenue_breakdown.get("total_transactions", 0),
            "total_revenue": revenue_breakdown.get("total_revenue", 0),
            "total_commission": 0,
        },
        "period": revenue_breakdown.get("period", {}),
    }


@router.get("/quick-stats", response_model=dict[str, Any])
async def get_quick_stats(
    current_user=Depends(require_roles(CLINICAL_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
):
    """Получение быстрой статистики"""
    service = AnalyticsSimpleApiService(db)
    try:
        return service.get_quick_stats()
    except AnalyticsSimpleDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/dashboard", response_model=dict[str, Any])
async def get_dashboard_data(
    current_user=Depends(require_roles(CLINICAL_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
):
    """Получение данных для дашборда"""
    service = AnalyticsSimpleApiService(db)
    try:
        return service.get_dashboard_data()
    except AnalyticsSimpleDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/trends", response_model=dict[str, Any])
async def get_trends_analytics(
    days: int = Query(30, ge=1, le=365, description="Количество дней для анализа"),
    current_user=Depends(require_roles(CLINICAL_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
):
    """Получение трендов за последние N дней через SSOT"""
    try:
        _end_date = datetime.now()
        _start_date = _end_date - timedelta(days=days)

        # Используем SSOT для получения трендов
        return AnalyticsService.get_trends(db, days)
    except Exception as e:
        logger.warning(
            "Analytics trends endpoint failed error_type=%s",
            type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail=ANALYTICS_PUBLIC_ERROR,
        ) from e


@router.get("/appointment-flow", response_model=dict[str, Any])
async def get_appointment_flow_analytics(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: str | None = Query(None, description="Отделение"),
    current_user=Depends(require_roles(CLINICAL_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
):
    """Legacy-compatible analytics route for appointment flow."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    if start > end:
        raise HTTPException(
            status_code=400, detail="Начальная дата должна быть раньше конечной"
        )

    return AnalyticsService.get_appointment_flow_analytics(db, start, end, department)


@router.get("/revenue-breakdown", response_model=dict[str, Any])
async def get_revenue_breakdown_analytics(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: str | None = Query(None, description="Отделение"),
    current_user=Depends(require_roles(FINANCIAL_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
):
    """Legacy-compatible analytics route for revenue breakdown."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    if start > end:
        raise HTTPException(
            status_code=400, detail="Начальная дата должна быть раньше конечной"
        )

    return AnalyticsService.get_revenue_breakdown_analytics(db, start, end, department)


@router.get("/payment-providers", response_model=dict[str, Any])
async def get_payment_provider_analytics(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: str | None = Query(None, description="Отделение"),
    current_user=Depends(require_roles(FINANCIAL_ANALYTICS_ROLES)),
    db: Session = Depends(get_db),
):
    """Legacy-compatible analytics route for provider summary."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    if start > end:
        raise HTTPException(
            status_code=400, detail="Начальная дата должна быть раньше конечной"
        )

    return _build_payment_provider_payload(db, start, end, department)
