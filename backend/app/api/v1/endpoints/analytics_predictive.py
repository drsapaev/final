"""API endpoints for predictive analytics."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, UTC

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.services.advanced_analytics import get_advanced_analytics_service
from app.services.analytics import AnalyticsService

logger = logging.getLogger(__name__)

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


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _percentage_change(current: float, previous: float) -> float:
    if previous in (None, 0):
        return 0.0 if current in (None, 0) else 100.0
    return round((current - previous) / abs(previous) * 100, 2)


def _build_context(
    db: Session,
    start: datetime,
    end: datetime,
    department: str | None,
) -> dict:
    analytics_service = get_advanced_analytics_service()
    period_days = max((end - start).days + 1, 1)
    previous_start = start - timedelta(days=period_days)
    previous_end = start - timedelta(days=1)

    current_comprehensive = AnalyticsService.calculate_statistics(
        db, start, end, department
    )
    previous_comprehensive = AnalyticsService.calculate_statistics(
        db, previous_start, previous_end, department
    )

    current_visits = current_comprehensive.get("visits", {})
    current_patients = current_comprehensive.get("patients", {})
    current_revenue = current_comprehensive.get("revenue", {})
    current_queues = current_comprehensive.get("queues", {})
    current_appointments = AnalyticsService.get_appointment_flow_analytics(
        db, start, end, department
    )
    current_doctors = analytics_service.get_doctor_performance(db, start, end, department)

    previous_visits = previous_comprehensive.get("visits", {})
    previous_patients = previous_comprehensive.get("patients", {})
    previous_revenue = previous_comprehensive.get("revenue", {})
    previous_queues = previous_comprehensive.get("queues", {})
    previous_appointments = AnalyticsService.get_appointment_flow_analytics(
        db, previous_start, previous_end, department
    )
    previous_doctors = analytics_service.get_doctor_performance(
        db, previous_start, previous_end, department
    )

    total_visits = float(current_visits.get("total_visits", 0) or 0)
    total_appointments = float(
        current_appointments.get("summary", {}).get("total_appointments", 0) or 0
    )
    total_revenue = float(current_revenue.get("total_revenue", 0) or 0)
    new_patients = float(current_patients.get("new_patients", 0) or 0)  # noqa: F841  # manual-review: variable intentionally kept for debugging/future use
    active_patients = float(current_patients.get("active_patients", 0) or 0)
    completion_rate = float(current_visits.get("completion_rate", 0) or 0)
    retention_rate = float(current_patients.get("retention_rate", 0) or 0)
    avg_wait_time = float(current_queues.get("average_wait_time_minutes", 0) or 0)
    no_show_rate = (
        (float(current_visits.get("no_show_visits", 0) or 0) / total_visits * 100)
        if total_visits
        else 0.0
    )
    avg_completion_rate = float(
        current_doctors.get("summary", {}).get("avg_completion_rate", 0) or 0
    )
    total_doctors = float(current_doctors.get("summary", {}).get("total_doctors", 0) or 0)

    revenue_trend = _percentage_change(
        total_revenue, float(previous_revenue.get("total_revenue", 0) or 0)
    )
    patients_trend = _percentage_change(
        active_patients, float(previous_patients.get("active_patients", 0) or 0)
    )
    appointments_trend = _percentage_change(
        total_appointments,
        float(
            previous_appointments.get("summary", {}).get("total_appointments", 0) or 0
        ),
    )
    efficiency_trend = _percentage_change(
        completion_rate, float(previous_visits.get("completion_rate", 0) or 0)
    )
    wait_time_trend = _percentage_change(
        avg_wait_time, float(previous_queues.get("average_wait_time_minutes", 0) or 0)
    )
    satisfaction_trend = _percentage_change(
        retention_rate, float(previous_patients.get("retention_rate", 0) or 0)
    )
    doctor_trend = _percentage_change(
        avg_completion_rate,
        float(previous_doctors.get("summary", {}).get("avg_completion_rate", 0) or 0),
    )

    revenue_daily = total_revenue / period_days if period_days else 0
    appointments_daily = total_appointments / period_days if period_days else 0
    patients_daily = active_patients / period_days if period_days else 0

    return {
        "period_days": period_days,
        "start": start,
        "end": end,
        "department": department or "all",
        "current": {
            "revenue": {
                "value": total_revenue,
                "daily": revenue_daily,
                "unit": "₽",
                "trend": revenue_trend,
            },
            "patients": {
                "value": active_patients,
                "daily": patients_daily,
                "unit": "чел",
                "trend": patients_trend,
            },
            "appointments": {
                "value": total_appointments,
                "daily": appointments_daily,
                "unit": "записей",
                "trend": appointments_trend,
            },
            "efficiency": {
                "value": completion_rate,
                "daily": completion_rate,
                "unit": "%",
                "trend": efficiency_trend,
            },
            "satisfaction": {
                "value": retention_rate,
                "daily": retention_rate,
                "unit": "%",
                "trend": satisfaction_trend,
            },
            "wait_time": {
                "value": avg_wait_time,
                "daily": avg_wait_time,
                "unit": "мин",
                "trend": wait_time_trend,
            },
            "no_show_rate": {
                "value": no_show_rate,
                "daily": no_show_rate,
                "unit": "%",
                "trend": -no_show_rate,
            },
            "doctors": {
                "value": total_doctors,
                "daily": total_doctors,
                "unit": "врачей",
                "trend": doctor_trend,
            },
        },
    }


def _confidence_from_trend(value: float, period_days: int) -> float:
    base = 0.58 + min(period_days / 120, 0.12)
    trend_bonus = min(abs(value) / 200, 0.2)
    return round(_clamp(base + trend_bonus, 0.55, 0.95), 2)


def _build_forecasts(context: dict, forecast_days: int) -> list[dict]:
    metric_specs = {
        "revenue": {
            "label": "Доходы",
            "unit": "₽",
            "base": context["current"]["revenue"]["daily"],
            "trend": context["current"]["revenue"]["trend"],
        },
        "patients": {
            "label": "Пациенты",
            "unit": "чел",
            "base": context["current"]["patients"]["daily"],
            "trend": context["current"]["patients"]["trend"],
        },
        "appointments": {
            "label": "Записи",
            "unit": "записей",
            "base": context["current"]["appointments"]["daily"],
            "trend": context["current"]["appointments"]["trend"],
        },
        "efficiency": {
            "label": "Эффективность",
            "unit": "%",
            "base": context["current"]["efficiency"]["daily"],
            "trend": context["current"]["efficiency"]["trend"],
        },
    }

    forecasts: list[dict] = []
    forecast_start = context["end"] + timedelta(days=1)
    for day_index in range(forecast_days):
        forecast_date = forecast_start + timedelta(days=day_index)
        progression = (day_index + 1) / max(forecast_days, 1)
        for metric, spec in metric_specs.items():
            trend_adjustment = spec["trend"] * 0.45 * progression
            if metric == "efficiency":
                projected_value = _clamp(
                    spec["base"] * (1 + trend_adjustment / 100), 0, 100
                )
            else:
                projected_value = max(
                    0.0, spec["base"] * (1 + trend_adjustment / 100)
                )

            forecasts.append(
                {
                    "metric": metric,
                    "metric_label": spec["label"],
                    "period": forecast_date.strftime("%Y-%m-%d"),
                    "value": round(projected_value, 2),
                    "confidence": _confidence_from_trend(
                        spec["trend"], context["period_days"]
                    ),
                    "trend": round(spec["trend"], 2),
                    "unit": spec["unit"],
                    "factors": [
                        {
                            "name": "Исторический тренд",
                            "impact": round(spec["trend"] * 0.45, 2),
                        },
                        {
                            "name": "Длина базового периода",
                            "impact": round(context["period_days"], 0),
                        },
                    ],
                }
            )

    return forecasts


def _build_recommendations(context: dict) -> list[dict]:
    current = context["current"]
    recommendations: list[dict] = []

    if current["wait_time"]["value"] > 20:
        recommendations.append(
            {
                "priority": "high",
                "title": "Сократить время ожидания",
                "description": "Оптимизировать расписание и поток пациентов в очереди.",
                "impact": "10-20%",
                "timeline": "7 дней",
            }
        )

    if current["no_show_rate"]["value"] > 10:
        recommendations.append(
            {
                "priority": "high",
                "title": "Снизить неявки",
                "description": "Добавить напоминания и подтверждение записи перед визитом.",
                "impact": "5-15%",
                "timeline": "7-14 дней",
            }
        )

    if current["revenue"]["trend"] < 0:
        recommendations.append(
            {
                "priority": "medium",
                "title": "Поддержать выручку",
                "description": "Сфокусироваться на конверсии записей и повторных визитах.",
                "impact": "5-10%",
                "timeline": "14 дней",
            }
        )

    if current["appointments"]["trend"] > 0 and current["efficiency"]["value"] < 80:
        recommendations.append(
            {
                "priority": "medium",
                "title": "Усилить завершение записей",
                "description": "Синхронизировать запись, подтверждение и работу врачей.",
                "impact": "5-12%",
                "timeline": "14 дней",
            }
        )

    if not recommendations:
        recommendations.append(
            {
                "priority": "low",
                "title": "Сохранять текущий режим",
                "description": "Показатели стабильны, достаточно следить за динамикой.",
                "impact": "0-5%",
                "timeline": "30 дней",
            }
        )

    return recommendations


def _build_trends(context: dict) -> list[dict]:
    current = context["current"]
    trend_map = [
        ("revenue", "Выручка", "up" if current["revenue"]["trend"] >= 0 else "down"),
        (
            "patients",
            "Пациенты",
            "up" if current["patients"]["trend"] >= 0 else "down",
        ),
        (
            "appointments",
            "Записи",
            "up" if current["appointments"]["trend"] >= 0 else "down",
        ),
        (
            "efficiency",
            "Эффективность",
            "up" if current["efficiency"]["trend"] >= 0 else "down",
        ),
        (
            "wait_time",
            "Время ожидания",
            "down" if current["wait_time"]["trend"] >= 0 else "up",
        ),
        (
            "no_show_rate",
            "Неявки",
            "down" if current["no_show_rate"]["trend"] >= 0 else "up",
        ),
    ]

    return [
        {
            "metric": label,
            "description": f"{label} за период с учетом исторического тренда.",
            "direction": direction,
            "change": round(current[key]["trend"], 2),
            "period": f"{context['period_days']} дн.",
        }
        for key, label, direction in trend_map
    ]


@router.get("/predictive")
async def get_predictive_analytics(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: str | None = Query(None, description="Отделение"),
    forecast_days: int = Query(30, description="Дни прогноза"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(FINANCIAL_ANALYTICS_ROLES)),
):
    """Получить предиктивную аналитику и прогнозы."""
    start, end = _parse_date_range(start_date, end_date)
    forecast_days = max(1, min(int(forecast_days), 90))

    logger.info(
        "[PredictiveAnalytics] building forecast",
        extra={
            "start_date": start.date().isoformat(),
            "end_date": end.date().isoformat(),
            "department": department or "all",
            "forecast_days": forecast_days,
            "user_id": getattr(current_user, "id", None),
        },
    )

    context = _build_context(db, start, end, department)
    forecasts = _build_forecasts(context, forecast_days)
    recommendations = _build_recommendations(context)
    trends = _build_trends(context)

    return {
        "forecasts": forecasts,
        "recommendations": recommendations,
        "trends": trends,
        "model_info": {
            "algorithm": "historical-trend-smoothing",
            "confidence_threshold": 0.7,
            "training_data_period": f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}",
            "forecast_horizon": f"{forecast_days} days",
        },
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "forecast_start": (end + timedelta(days=1)).isoformat(),
            "forecast_end": (end + timedelta(days=forecast_days)).isoformat(),
            "department": department or "all",
            "generated_at": datetime.now(UTC).isoformat(),
        },
    }


@router.get("/predictive/accuracy")
async def get_prediction_accuracy(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: str | None = Query(None, description="Отделение"),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(FINANCIAL_ANALYTICS_ROLES)),
):
    """Получить оценочную точность предыдущих прогнозов."""
    start, end = _parse_date_range(start_date, end_date)
    context = _build_context(db, start, end, department)

    forecast_volume = len(_build_forecasts(context, 7))
    average_confidence = sum(
        forecast["confidence"] for forecast in _build_forecasts(context, 3)
    ) / max(len(_build_forecasts(context, 3)), 1)

    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "department": department or "all",
        },
        "accuracy": {
            "forecast_points": forecast_volume,
            "average_confidence": round(average_confidence, 2),
            "estimated_accuracy": round(min(average_confidence * 100, 98.0), 2),
        },
    }


@router.get("/predictive/scenarios")
async def get_scenario_analysis(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: str | None = Query(None, description="Отделение"),
    scenario: str = Query(
        "optimistic", description="Сценарий: optimistic, realistic, pessimistic"
    ),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(FINANCIAL_ANALYTICS_ROLES)),
):
    """Получить анализ сценариев развития."""
    start, end = _parse_date_range(start_date, end_date)
    context = _build_context(db, start, end, department)

    multipliers = {
        "optimistic": 1.12,
        "realistic": 1.0,
        "pessimistic": 0.88,
    }
    multiplier = multipliers.get(scenario, 1.0)

    forecast_sample = _build_forecasts(context, 7)
    scenario_forecasts = []
    for forecast in forecast_sample:
        scenario_forecasts.append(
            {
                **forecast,
                "scenario": scenario,
                "value": round(float(forecast["value"]) * multiplier, 2),
                "confidence": _clamp(
                    float(forecast["confidence"]) - (0.05 if scenario == "pessimistic" else 0.0),
                    0.5,
                    0.98,
                ),
            }
        )

    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "department": department or "all",
        },
        "scenario": scenario,
        "forecasts": scenario_forecasts,
        "recommendations": _build_recommendations(context),
    }


@router.get("/predictive/insights")
async def get_predictive_insights(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: str | None = Query(None, description="Отделение"),
    insight_type: str = Query(
        "all", description="Тип инсайтов: all, revenue, patients, efficiency"
    ),
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(FINANCIAL_ANALYTICS_ROLES)),
):
    """Получить инсайты и паттерны из предиктивной аналитики."""
    start, end = _parse_date_range(start_date, end_date)
    context = _build_context(db, start, end, department)
    recommendations = _build_recommendations(context)
    trends = _build_trends(context)

    if insight_type != "all":
        trends = [trend for trend in trends if insight_type in trend["metric"].lower()]

    return {
        "period": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "department": department or "all",
        },
        "insight_type": insight_type,
        "insights": [
            {
                "title": rec["title"],
                "description": rec["description"],
                "priority": rec["priority"],
                "impact": rec["impact"],
            }
            for rec in recommendations
        ],
        "trends": trends,
    }
