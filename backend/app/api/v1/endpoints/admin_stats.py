from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.services.admin_stats_api_service import AdminStatsApiService

router = APIRouter()


@router.get("/stats", summary="Общая статистика для админ-панели")
def get_admin_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> Dict[str, Any]:
    """Агрегированная статистика для админ-панели."""
    try:
        return AdminStatsApiService(db).get_admin_stats()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {e}") from e


@router.get("/quick-stats", summary="Быстрая статистика для дашборда")
def get_quick_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> Dict[str, Any]:
    try:
        return AdminStatsApiService(db).get_quick_stats()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения быстрой статистики: {e}"
        ) from e


@router.get("/recent-activities", summary="Последние действия для дашборда")
def get_recent_activities(
    limit: int = Query(10, ge=1, le=50, description="Количество записей"),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> Dict[str, Any]:
    """Получение последних действий: записи, платежи, регистрации пользователей."""
    try:
        return AdminStatsApiService(db).get_recent_activities(limit=limit)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения последних действий: {e}"
        ) from e


@router.get("/activity-chart", summary="Данные для графика активности")
def get_activity_chart(
    days: int = Query(7, ge=1, le=30, description="Количество дней для графика"),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> Dict[str, Any]:
    """Получение данных для графика активности за последние N дней."""
    try:
        return AdminStatsApiService(db).get_activity_chart(days=days)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения данных графика: {e}"
        ) from e


@router.get("/analytics/overview", summary="Обзор аналитики для админ-панели")
def get_analytics_overview(
    period: str = Query(
        "week", description="Период: today, week, month, quarter, year"
    ),
    department: Optional[str] = Query(None, description="Отделение (опционально)"),
    doctor_id: Optional[int] = Query(None, description="ID врача (опционально)"),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> Dict[str, Any]:
    """Получение обзора аналитики для админ-панели с фильтрами."""
    try:
        return AdminStatsApiService(db).get_analytics_overview(
            period=period,
            department=department,
            doctor_id=doctor_id,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Ошибка получения аналитики: {e}") from e


@router.get("/analytics/charts", summary="Данные для графиков аналитики")
def get_analytics_charts(
    period: str = Query(
        "week", description="Период: today, week, month, quarter, year"
    ),
    chart_type: str = Query(
        "appointments", description="Тип графика: appointments, revenue"
    ),
    department: Optional[str] = Query(None, description="Отделение (опционально)"),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> Dict[str, Any]:
    """Получение данных для графиков аналитики."""
    try:
        return AdminStatsApiService(db).get_analytics_charts(
            period=period,
            chart_type=chart_type,
            department=department,
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения данных графиков: {e}"
        ) from e
