"""
API endpoints для KPI метрик
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.services.advanced_analytics import get_advanced_analytics_service, AdvancedAnalyticsService

router = APIRouter()


@router.get("/kpi-metrics")
async def get_kpi_metrics(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить KPI метрики для аналитики"""
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
    
    # Получаем основные KPI метрики
    kpi_data = {
        "metrics": {
            "revenue": {
                "value": analytics_service.get_revenue_analytics(db, start, end, department).get("total_revenue", 0),
                "trend": analytics_service.get_revenue_trend(db, start, end, department),
                "label": "Общая выручка",
                "description": "Суммарная выручка за период",
                "type": "revenue",
                "format": "revenue",
                "target": 1000000,  # Цель 1 млн рублей
                "comparison": 850000  # Среднее по отрасли
            },
            "patients": {
                "value": analytics_service.get_patient_analytics(db, start, end).get("total_patients", 0),
                "trend": analytics_service.get_patient_trend(db, start, end),
                "label": "Количество пациентов",
                "description": "Уникальные пациенты за период",
                "type": "patients",
                "format": "count",
                "target": 500,
                "comparison": 400
            },
            "appointments": {
                "value": analytics_service.get_appointment_analytics(db, start, end, department).get("total_appointments", 0),
                "trend": analytics_service.get_appointment_trend(db, start, end, department),
                "label": "Записи на прием",
                "description": "Общее количество записей",
                "type": "appointments",
                "format": "count",
                "target": 1000,
                "comparison": 800
            },
            "doctors": {
                "value": analytics_service.get_doctor_performance(db, start, end, department).get("active_doctors", 0),
                "trend": analytics_service.get_doctor_efficiency_trend(db, start, end, department),
                "label": "Активные врачи",
                "description": "Врачи с активными записями",
                "type": "doctors",
                "format": "count",
                "target": 10,
                "comparison": 8
            },
            "efficiency": {
                "value": analytics_service.get_efficiency_metrics(db, start, end, department).get("average_efficiency", 0),
                "trend": analytics_service.get_efficiency_trend(db, start, end, department),
                "label": "Эффективность",
                "description": "Средняя эффективность работы",
                "type": "efficiency",
                "format": "percentage",
                "target": 85,
                "comparison": 75
            },
            "satisfaction": {
                "value": analytics_service.get_satisfaction_metrics(db, start, end, department).get("average_rating", 0),
                "trend": analytics_service.get_satisfaction_trend(db, start, end, department),
                "label": "Удовлетворенность",
                "description": "Средняя оценка пациентов",
                "type": "satisfaction",
                "format": "rating",
                "target": 4.5,
                "comparison": 4.2
            },
            "wait_time": {
                "value": analytics_service.get_wait_time_metrics(db, start, end, department).get("average_wait_time", 0),
                "trend": analytics_service.get_wait_time_trend(db, start, end, department),
                "label": "Время ожидания",
                "description": "Среднее время ожидания (минуты)",
                "type": "wait_time",
                "format": "time",
                "target": 15,
                "comparison": 20
            },
            "no_show_rate": {
                "value": analytics_service.get_no_show_metrics(db, start, end, department).get("no_show_rate", 0),
                "trend": analytics_service.get_no_show_trend(db, start, end, department),
                "label": "Процент неявок",
                "description": "Доля неявок на приемы",
                "type": "no_show_rate",
                "format": "percentage",
                "target": 5,
                "comparison": 8
            }
        },
        "summary": {
            "positive_trends": sum(1 for m in analytics_service.get_all_trends(db, start, end, department) if m > 0),
            "negative_trends": sum(1 for m in analytics_service.get_all_trends(db, start, end, department) if m < 0),
            "achieved_goals": analytics_service.get_achieved_goals_count(db, start, end, department),
            "total_metrics": 8
        },
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "department": department or "all",
            "generated_at": datetime.utcnow().isoformat()
        }
    }

    return kpi_data


@router.get("/kpi-trends")
async def get_kpi_trends(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    metric: Optional[str] = Query(None, description="Конкретная метрика"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить тренды KPI метрик"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    analytics_service = get_advanced_analytics_service()
    
    trends_data = {
        "trends": analytics_service.get_detailed_trends(db, start, end, department, metric),
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "department": department or "all",
            "metric": metric or "all"
        }
    }

    return trends_data


@router.get("/kpi-comparison")
async def get_kpi_comparison(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    comparison_period: str = Query("previous", description="Период сравнения"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Получить сравнение KPI с предыдущими периодами"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    analytics_service = get_advanced_analytics_service()
    
    # Вычисляем период сравнения
    period_duration = end - start
    if comparison_period == "previous":
        compare_start = start - period_duration
        compare_end = start
    elif comparison_period == "year_ago":
        compare_start = start - timedelta(days=365)
        compare_end = end - timedelta(days=365)
    else:
        compare_start = start - period_duration
        compare_end = start

    comparison_data = {
        "current_period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "metrics": analytics_service.get_kpi_metrics(db, start, end, department)
        },
        "comparison_period": {
            "start_date": compare_start.isoformat(),
            "end_date": compare_end.isoformat(),
            "metrics": analytics_service.get_kpi_metrics(db, compare_start, compare_end, department)
        },
        "comparison_type": comparison_period,
        "changes": analytics_service.calculate_kpi_changes(
            db, start, end, compare_start, compare_end, department
        )
    }

    return comparison_data
