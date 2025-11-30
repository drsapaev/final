"""
API endpoints для предиктивной аналитики
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.services.advanced_analytics import (
    AdvancedAnalyticsService,
    get_advanced_analytics_service,
)

router = APIRouter()


@router.get("/predictive")
async def get_predictive_analytics(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    forecast_days: int = Query(30, description="Дни прогноза"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Получить предиктивную аналитику и прогнозы"""
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

    # Получаем исторические данные для прогнозирования
    historical_data = analytics_service.get_historical_data(db, start, end, department)

    # Генерируем прогнозы
    forecasts = []
    for i in range(1, forecast_days + 1):
        forecast_date = end + timedelta(days=i)

        # Прогноз выручки
        revenue_forecast = analytics_service.predict_revenue(
            historical_data, forecast_date, department
        )

        # Прогноз количества пациентов
        patients_forecast = analytics_service.predict_patients(
            historical_data, forecast_date, department
        )

        # Прогноз записей
        appointments_forecast = analytics_service.predict_appointments(
            historical_data, forecast_date, department
        )

        # Прогноз эффективности
        efficiency_forecast = analytics_service.predict_efficiency(
            historical_data, forecast_date, department
        )

        forecasts.append(
            {
                "period": forecast_date.strftime("%Y-%m-%d"),
                "date": forecast_date.isoformat(),
                "revenue": {
                    "value": revenue_forecast["value"],
                    "confidence": revenue_forecast["confidence"],
                    "trend": revenue_forecast["trend"],
                    "unit": "₽",
                    "factors": revenue_forecast.get("factors", []),
                },
                "patients": {
                    "value": patients_forecast["value"],
                    "confidence": patients_forecast["confidence"],
                    "trend": patients_forecast["trend"],
                    "unit": "чел",
                    "factors": patients_forecast.get("factors", []),
                },
                "appointments": {
                    "value": appointments_forecast["value"],
                    "confidence": appointments_forecast["confidence"],
                    "trend": appointments_forecast["trend"],
                    "unit": "записей",
                    "factors": appointments_forecast.get("factors", []),
                },
                "efficiency": {
                    "value": efficiency_forecast["value"],
                    "confidence": efficiency_forecast["confidence"],
                    "trend": efficiency_forecast["trend"],
                    "unit": "%",
                    "factors": efficiency_forecast.get("factors", []),
                },
            }
        )

    # Генерируем рекомендации
    recommendations = analytics_service.generate_recommendations(
        historical_data, forecasts, department
    )

    # Анализ трендов
    trends = analytics_service.analyze_trends(historical_data, department)

    predictive_data = {
        "forecasts": forecasts,
        "recommendations": recommendations,
        "trends": trends,
        "model_info": {
            "algorithm": "ARIMA + Seasonal Decomposition",
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
            "generated_at": datetime.utcnow().isoformat(),
        },
    }

    return predictive_data


@router.get("/predictive/accuracy")
async def get_prediction_accuracy(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Получить точность предыдущих прогнозов"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    analytics_service = get_advanced_analytics_service()

    accuracy_data = analytics_service.calculate_prediction_accuracy(
        db, start, end, department
    )

    return accuracy_data


@router.get("/predictive/scenarios")
async def get_scenario_analysis(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    scenario: str = Query(
        "optimistic", description="Сценарий: optimistic, realistic, pessimistic"
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Получить анализ сценариев развития"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    analytics_service = get_advanced_analytics_service()

    scenario_data = analytics_service.generate_scenario_analysis(
        db, start, end, department, scenario
    )

    return scenario_data


@router.get("/predictive/insights")
async def get_predictive_insights(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Отделение"),
    insight_type: str = Query(
        "all", description="Тип инсайтов: all, revenue, patients, efficiency"
    ),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Получить инсайты и паттерны из предиктивной аналитики"""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты")

    analytics_service = get_advanced_analytics_service()

    insights_data = analytics_service.extract_predictive_insights(
        db, start, end, department, insight_type
    )

    return insights_data
