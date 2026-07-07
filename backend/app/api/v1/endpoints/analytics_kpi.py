"""API endpoints for KPI analytics."""

from __future__ import annotations

from datetime import datetime, timedelta, UTC

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.services.advanced_analytics import get_advanced_analytics_service
from app.services.analytics import AnalyticsService

router = APIRouter()

FINANCIAL_ANALYTICS_ROLES = ["admin", "manager"]


def _parse_date_range(start_date: str, end_date: str) -> tuple[datetime, datetime]:
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Неверный формат даты") from exc

    if start > end:
        raise HTTPException(
            status_code=400, detail="Начальная дата должна быть раньше конечной"
        )

    return start, end


def _percentage_change(current: float, previous: float) -> float:
    if previous in (None, 0):
        return 0.0 if current in (None, 0) else 100.0
    return round((current - previous) / abs(previous) * 100, 2)


def _build_kpi_snapshot(
    db: Session, start: datetime, end: datetime, department: str | None
) -> dict:
    analytics_service = get_advanced_analytics_service()
    comprehensive = AnalyticsService.calculate_statistics(db, start, end, department)
    visits = comprehensive.get("visits", {})
    patients = comprehensive.get("patients", {})
    revenue = comprehensive.get("revenue", {})
    queues = comprehensive.get("queues", {})
    appointment_flow = AnalyticsService.get_appointment_flow_analytics(
        db, start, end, department
    )
    doctor_perf = analytics_service.get_doctor_performance(db, start, end, department)

    total_visits = visits.get("total_visits", 0)
    completion_rate = visits.get("completion_rate", 0)
    no_show_visits = visits.get("no_show_visits", 0)
    total_appointments = appointment_flow.get("summary", {}).get(
        "total_appointments", 0
    )
    total_doctors = doctor_perf.get("summary", {}).get("total_doctors", 0)
    new_patients = patients.get("new_patients", 0)
    active_patients = patients.get("active_patients", 0)
    retention_rate = patients.get("retention_rate", 0)
    avg_wait_time = queues.get("average_wait_time_minutes", 0)
    avg_revenue_per_visit = revenue.get("average_check", 0)
    total_revenue = revenue.get("total_revenue", 0)

    return {
        "revenue": {
            "value": total_revenue,
            "label": "Общая выручка",
            "description": "Суммарная выручка за период",
            "type": "revenue",
            "format": "revenue",
        },
        "patients": {
            "value": new_patients,
            "label": "Количество пациентов",
            "description": "Уникальные пациенты за период",
            "type": "patients",
            "format": "count",
        },
        "appointments": {
            "value": total_appointments,
            "label": "Записи на прием",
            "description": "Общее количество записей",
            "type": "appointments",
            "format": "count",
        },
        "doctors": {
            "value": total_doctors,
            "label": "Активные врачи",
            "description": "Врачи с активными записями",
            "type": "doctors",
            "format": "count",
        },
        "efficiency": {
            "value": round(completion_rate, 2),
            "label": "Эффективность",
            "description": "Процент завершенных визитов",
            "type": "efficiency",
            "format": "percentage",
        },
        "satisfaction": {
            "value": round(retention_rate, 2),
            "label": "Удовлетворенность",
            "description": "Доля возвращающихся пациентов",
            "type": "satisfaction",
            "format": "percentage",
        },
        "wait_time": {
            "value": round(avg_wait_time, 2),
            "label": "Время ожидания",
            "description": "Среднее время ожидания (минуты)",
            "type": "wait_time",
            "format": "time",
        },
        "no_show_rate": {
            "value": round((no_show_visits / total_visits * 100) if total_visits else 0, 2),
            "label": "Процент неявок",
            "description": "Доля неявок на приемы",
            "type": "no_show_rate",
            "format": "percentage",
        },
        "_meta": {
            "total_revenue": total_revenue,
            "avg_revenue_per_visit": avg_revenue_per_visit,
            "active_patients": active_patients,
        },
    }


def _build_kpi_trend_rows(
    current: dict, previous: dict, metric: str | None = None
) -> list[dict]:
    keys = [
        "revenue",
        "patients",
        "appointments",
        "doctors",
        "efficiency",
        "satisfaction",
        "wait_time",
        "no_show_rate",
    ]
    if metric and metric in keys:
        keys = [metric]

    rows: list[dict] = []
    for key in keys:
        current_value = float(current.get(key, {}).get("value", 0) or 0)
        previous_value = float(previous.get(key, {}).get("value", 0) or 0)
        change = _percentage_change(current_value, previous_value)
        rows.append(
            {
                "metric": key,
                "description": current.get(key, {}).get("description", ""),
                "direction": "up" if change >= 0 else "down",
                "change": change,
                "period": "previous_period",
                "current": current_value,
                "previous": previous_value,
            }
        )
    return rows


@router.get("/kpi-metrics")
async def get_kpi_metrics(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: str | None = Query(None, description="Отделение"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(FINANCIAL_ANALYTICS_ROLES)),
):
    """Получить KPI метрики для аналитики."""
    start, end = _parse_date_range(start_date, end_date)
    period = end - start
    compare_start = start - period
    compare_end = start

    current = _build_kpi_snapshot(db, start, end, department)
    previous = _build_kpi_snapshot(db, compare_start, compare_end, department)

    metrics = {}
    for key in [
        "revenue",
        "patients",
        "appointments",
        "doctors",
        "efficiency",
        "satisfaction",
        "wait_time",
        "no_show_rate",
    ]:
        current_value = float(current[key]["value"] or 0)
        previous_value = float(previous[key]["value"] or 0)
        metrics[key] = {
            **current[key],
            "trend": _percentage_change(current_value, previous_value),
            "target": {
                "revenue": 1_000_000,
                "patients": 500,
                "appointments": 1_000,
                "doctors": 10,
                "efficiency": 85,
                "satisfaction": 70,
                "wait_time": 15,
                "no_show_rate": 5,
            }[key],
            "comparison": previous_value,
        }

    trend_values = [v["trend"] for v in metrics.values()]
    achieved_goals = 0
    for key, metric_data in metrics.items():
        current_value = float(metric_data["value"] or 0)
        target = float(metric_data["target"] or 0)
        if key == "wait_time" or key == "no_show_rate":
            if current_value <= target:
                achieved_goals += 1
        elif current_value >= target:
            achieved_goals += 1

    return {
        "metrics": metrics,
        "summary": {
            "positive_trends": sum(1 for value in trend_values if value > 0),
            "negative_trends": sum(1 for value in trend_values if value < 0),
            "achieved_goals": achieved_goals,
            "total_metrics": len(metrics),
        },
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "department": department or "all",
            "generated_at": datetime.now(UTC).isoformat(),
        },
    }


@router.get("/kpi-trends")
async def get_kpi_trends(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: str | None = Query(None, description="Отделение"),
    metric: str | None = Query(None, description="Конкретная метрика"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(FINANCIAL_ANALYTICS_ROLES)),
):
    """Получить тренды KPI метрик."""
    start, end = _parse_date_range(start_date, end_date)
    period = end - start
    compare_start = start - period
    compare_end = start

    current = _build_kpi_snapshot(db, start, end, department)
    previous = _build_kpi_snapshot(db, compare_start, compare_end, department)

    return {
        "trends": _build_kpi_trend_rows(current, previous, metric),
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "department": department or "all",
            "metric": metric or "all",
        },
    }


@router.get("/kpi-comparison")
async def get_kpi_comparison(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: str | None = Query(None, description="Отделение"),
    comparison_period: str = Query("previous", description="Период сравнения"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(FINANCIAL_ANALYTICS_ROLES)),
):
    """Получить сравнение KPI с предыдущими периодами."""
    start, end = _parse_date_range(start_date, end_date)

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

    current = _build_kpi_snapshot(db, start, end, department)
    previous = _build_kpi_snapshot(db, compare_start, compare_end, department)

    changes = {}
    for key in [
        "revenue",
        "patients",
        "appointments",
        "doctors",
        "efficiency",
        "satisfaction",
        "wait_time",
        "no_show_rate",
    ]:
        current_value = float(current[key]["value"] or 0)
        previous_value = float(previous[key]["value"] or 0)
        changes[key] = {
            "current": current_value,
            "previous": previous_value,
            "change": _percentage_change(current_value, previous_value),
            "better_is_higher": key not in {"wait_time", "no_show_rate"},
        }

    return {
        "current_period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "metrics": AnalyticsService.calculate_statistics(db, start, end, department),
        },
        "comparison_period": {
            "start_date": compare_start.isoformat(),
            "end_date": compare_end.isoformat(),
            "metrics": AnalyticsService.calculate_statistics(
                db, compare_start, compare_end, department
            ),
        },
        "comparison_type": comparison_period,
        "changes": changes,
    }
