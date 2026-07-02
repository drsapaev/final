from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.services.analytics_simple_api_service import (
    AnalyticsSimpleApiService,
    AnalyticsSimpleDomainError,
)

router = APIRouter()


@router.get("/quick-stats")
async def get_quick_stats(
    current_user=Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db),
):
    """Получение быстрой статистики"""
    service = AnalyticsSimpleApiService(db)
    try:
        return service.get_quick_stats()
    except AnalyticsSimpleDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/dashboard")
async def get_dashboard_data(
    current_user=Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db),
):
    """Получение данных для дашборда"""
    service = AnalyticsSimpleApiService(db)
    try:
        return service.get_dashboard_data()
    except AnalyticsSimpleDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/trends")
async def get_trends_analytics(
    days: int = Query(30, ge=1, le=365, description="Количество дней для анализа"),
    current_user=Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db),
):
    """Получение трендов за последние N дней"""
    service = AnalyticsSimpleApiService(db)
    try:
        return service.get_trends_analytics(days=days)
    except AnalyticsSimpleDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
