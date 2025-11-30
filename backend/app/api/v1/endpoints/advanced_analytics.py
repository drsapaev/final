"""
API endpoints для расширенной аналитики
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.services.analytics import AnalyticsService
from app.services.advanced_analytics import get_advanced_analytics_service

router = APIRouter()


@router.get("/kpi")
async def get_kpi_metrics(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить ключевые показатели эффективности (KPI)"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    if start > end:
        raise HTTPException(
            status_code=400, detail="Начальная дата должна быть раньше конечной"
        )

    # Используем SSOT для KPI метрик
    # get_kpi_metrics() заменён на calculate_statistics() (SSOT)
    return AnalyticsService.calculate_statistics(db, start, end, department)


@router.get("/doctors/performance")
async def get_doctor_performance(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить показатели эффективности врачей"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    if start > end:
        raise HTTPException(
            status_code=400, detail="Начальная дата должна быть раньше конечной"
        )

    analytics_service = get_advanced_analytics_service()
    return analytics_service.get_doctor_performance(db, start, end, department)


@router.get("/patients/advanced")
async def get_advanced_patient_analytics(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить расширенную аналитику пациентов"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    if start > end:
        raise HTTPException(
            status_code=400, detail="Начальная дата должна быть раньше конечной"
        )

    analytics_service = get_advanced_analytics_service()
    return analytics_service.get_patient_analytics(db, start, end)


@router.get("/revenue/advanced")
async def get_advanced_revenue_analytics(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить расширенную аналитику доходов"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    if start > end:
        raise HTTPException(
            status_code=400, detail="Начальная дата должна быть раньше конечной"
        )

    # Используем SSOT для доходов
    return AnalyticsService.calculate_revenue(db, start, end, department)


@router.get("/predictive")
async def get_predictive_analytics(
    days_ahead: int = Query(30, ge=1, le=365, description="Количество дней для прогноза"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить предиктивную аналитику и прогнозы"""
    analytics_service = get_advanced_analytics_service()
    return analytics_service.get_predictive_analytics(db, days_ahead)


@router.get("/comprehensive/advanced")
async def get_advanced_comprehensive_report(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    include_predictive: bool = Query(True, description="Включить предиктивную аналитику"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить расширенный комплексный отчет"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    if start > end:
        raise HTTPException(
            status_code=400, detail="Начальная дата должна быть раньше конечной"
        )

    # Используем SSOT для комплексного отчёта
    report = AnalyticsService.calculate_statistics(db, start, end, department)
    
    # Добавляем расширенные метрики из advanced_analytics (если нужно)
    if include_predictive:
        from app.services.advanced_analytics import get_advanced_analytics_service
        analytics_service = get_advanced_analytics_service()
        report["predictive_analytics"] = analytics_service.get_predictive_analytics(db, 30)
    
    return report


@router.get("/health")
async def analytics_health_check():
    """Проверка здоровья сервиса аналитики"""
    return {
        "status": "ok",
        "advanced_analytics": "active",
        "features": [
            "kpi_metrics",
            "doctor_performance",
            "patient_analytics",
            "revenue_analytics",
            "predictive_analytics",
            "comprehensive_reports"
        ],
        "supported_periods": {
            "min_days": 1,
            "max_days": 365
        }
    }
