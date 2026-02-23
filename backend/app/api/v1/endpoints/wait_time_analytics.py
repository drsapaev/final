"""
API endpoints для аналитики времени ожидания
"""

import logging
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.models.user import User
from app.services.wait_time_analytics_service import get_wait_time_analytics_service

logger = logging.getLogger(__name__)

router = APIRouter()

# ===================== PYDANTIC СХЕМЫ =====================


class WaitTimeStatsResponse(BaseModel):
    """Схема ответа со статистикой времени ожидания"""

    count: int
    average_minutes: float
    median_minutes: float
    min_minutes: float
    max_minutes: float
    std_deviation: float
    percentile_75: float
    percentile_90: float
    percentile_95: float


class WaitTimeAnalyticsResponse(BaseModel):
    """Схема ответа с полной аналитикой времени ожидания"""

    period: dict
    overall_stats: WaitTimeStatsResponse
    department_breakdown: dict
    doctor_breakdown: dict
    hourly_breakdown: dict
    daily_breakdown: dict
    trends: dict
    recommendations: List[str]


class RealTimeWaitEstimateResponse(BaseModel):
    """Схема ответа с оценками времени ожидания в реальном времени"""

    timestamp: str
    queues: dict
    summary: dict


class ServiceWaitAnalyticsResponse(BaseModel):
    """Схема ответа с аналитикой времени ожидания по услугам"""

    period: dict
    service_analytics: dict
    summary: dict


# ===================== ENDPOINTS =====================


@router.get("/wait-time-analytics", response_model=WaitTimeAnalyticsResponse)
async def get_wait_time_analytics(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Фильтр по отделению"),
    doctor_id: Optional[int] = Query(None, description="Фильтр по врачу"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar", "Doctor"])),
):
    """Получить полную аналитику времени ожидания за период"""
    try:
        # Валидация дат
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат даты. Используйте YYYY-MM-DD",
            )

        if start > end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Начальная дата должна быть раньше конечной",
            )

        # Ограничиваем период анализа (максимум 90 дней)
        if (end - start).days > 90:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Период анализа не может превышать 90 дней",
            )

        service = get_wait_time_analytics_service(db)
        analytics = service.calculate_accurate_wait_times(
            start, end, department, doctor_id
        )

        return WaitTimeAnalyticsResponse(**analytics)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения аналитики времени ожидания: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения аналитики: {str(e)}",
        )


@router.get("/real-time-wait-estimates", response_model=RealTimeWaitEstimateResponse)
async def get_real_time_wait_estimates(
    department: Optional[str] = Query(None, description="Фильтр по отделению"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar", "Doctor"])),
):
    """Получить текущие оценки времени ожидания в реальном времени"""
    try:
        service = get_wait_time_analytics_service(db)
        estimates = service.get_real_time_wait_estimates(department)

        return RealTimeWaitEstimateResponse(**estimates)

    except Exception as e:
        logger.error(
            f"Ошибка получения оценок времени ожидания в реальном времени: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения оценок: {str(e)}",
        )


@router.get("/service-wait-analytics", response_model=ServiceWaitAnalyticsResponse)
async def get_service_wait_analytics(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    service_codes: Optional[str] = Query(None, description="Коды услуг через запятую"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar", "Doctor"])),
):
    """Получить аналитику времени ожидания по типам услуг"""
    try:
        # Валидация дат
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат даты. Используйте YYYY-MM-DD",
            )

        if start > end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Начальная дата должна быть раньше конечной",
            )

        # Парсим коды услуг
        service_codes_list = None
        if service_codes:
            service_codes_list = [code.strip() for code in service_codes.split(",")]

        service = get_wait_time_analytics_service(db)
        analytics = service.get_wait_time_analytics_by_service(
            start, end, service_codes_list
        )

        return ServiceWaitAnalyticsResponse(**analytics)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения аналитики времени ожидания по услугам: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения аналитики: {str(e)}",
        )


@router.get("/wait-time-summary")
async def get_wait_time_summary(
    days: int = Query(7, ge=1, le=30, description="Количество дней для анализа"),
    department: Optional[str] = Query(None, description="Фильтр по отделению"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar", "Doctor"])),
):
    """Получить краткую сводку времени ожидания за последние дни"""
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        service = get_wait_time_analytics_service(db)
        analytics = service.calculate_accurate_wait_times(
            start_date, end_date, department
        )

        # Формируем краткую сводку
        overall_stats = analytics.get("overall_stats", {})
        trends = analytics.get("trends", {})
        recommendations = analytics.get("recommendations", [])

        summary = {
            "period_days": days,
            "department": department or "Все отделения",
            "total_analyzed_entries": overall_stats.get("count", 0),
            "average_wait_time_minutes": overall_stats.get("average_minutes", 0),
            "median_wait_time_minutes": overall_stats.get("median_minutes", 0),
            "trend": trends.get("trend", "stable"),
            "trend_change_percent": trends.get("change_percent", 0),
            "top_recommendations": recommendations[:3],  # Топ-3 рекомендации
            "performance_rating": _calculate_performance_rating(
                overall_stats.get("average_minutes", 0)
            ),
            "last_updated": datetime.now().isoformat(),
        }

        return summary

    except Exception as e:
        logger.error(f"Ошибка получения сводки времени ожидания: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения сводки: {str(e)}",
        )


@router.get("/wait-time-comparison")
async def get_wait_time_comparison(
    current_start: str = Query(..., description="Начало текущего периода (YYYY-MM-DD)"),
    current_end: str = Query(..., description="Конец текущего периода (YYYY-MM-DD)"),
    compare_with_previous: bool = Query(
        True, description="Сравнить с предыдущим периодом"
    ),
    department: Optional[str] = Query(None, description="Фильтр по отделению"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar", "Doctor"])),
):
    """Сравнить время ожидания между периодами"""
    try:
        # Валидация дат
        try:
            current_start_date = datetime.strptime(current_start, "%Y-%m-%d").date()
            current_end_date = datetime.strptime(current_end, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат даты. Используйте YYYY-MM-DD",
            )

        if current_start_date > current_end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Начальная дата должна быть раньше конечной",
            )

        service = get_wait_time_analytics_service(db)

        # Получаем аналитику для текущего периода
        current_analytics = service.calculate_accurate_wait_times(
            current_start_date, current_end_date, department
        )

        comparison_result = {
            "current_period": {
                "start_date": current_start,
                "end_date": current_end,
                "analytics": current_analytics,
            }
        }

        # Если нужно сравнить с предыдущим периодом
        if compare_with_previous:
            period_length = (current_end_date - current_start_date).days
            previous_end_date = current_start_date - timedelta(days=1)
            previous_start_date = previous_end_date - timedelta(days=period_length)

            previous_analytics = service.calculate_accurate_wait_times(
                previous_start_date, previous_end_date, department
            )

            comparison_result["previous_period"] = {
                "start_date": previous_start_date.isoformat(),
                "end_date": previous_end_date.isoformat(),
                "analytics": previous_analytics,
            }

            # Рассчитываем изменения
            current_avg = current_analytics.get("overall_stats", {}).get(
                "average_minutes", 0
            )
            previous_avg = previous_analytics.get("overall_stats", {}).get(
                "average_minutes", 0
            )

            if previous_avg > 0:
                change_percent = ((current_avg - previous_avg) / previous_avg) * 100
            else:
                change_percent = 0

            comparison_result["comparison"] = {
                "average_wait_change_minutes": round(current_avg - previous_avg, 2),
                "average_wait_change_percent": round(change_percent, 2),
                "improvement": change_percent < 0,
                "significant_change": abs(change_percent) > 10,
            }

        return comparison_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка сравнения времени ожидания: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка сравнения: {str(e)}",
        )


@router.get("/wait-time-heatmap")
async def get_wait_time_heatmap(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    department: Optional[str] = Query(None, description="Фильтр по отделению"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar", "Doctor"])),
):
    """Получить тепловую карту времени ожидания по дням недели и часам"""
    try:
        # Валидация дат
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат даты. Используйте YYYY-MM-DD",
            )

        service = get_wait_time_analytics_service(db)
        analytics = service.calculate_accurate_wait_times(start, end, department)

        # Извлекаем почасовую разбивку
        hourly_breakdown = analytics.get("hourly_breakdown", {})

        # Формируем тепловую карту
        heatmap_data = []
        for hour in range(8, 19):  # Рабочие часы с 8 до 18
            hour_key = f"{hour:02d}:00"
            hour_stats = hourly_breakdown.get(hour_key, {})

            heatmap_data.append(
                {
                    "hour": hour,
                    "hour_label": hour_key,
                    "average_wait_minutes": hour_stats.get("average_minutes", 0),
                    "patient_count": hour_stats.get("count", 0),
                    "intensity": _calculate_intensity(
                        hour_stats.get("average_minutes", 0)
                    ),
                }
            )

        return {
            "period": {
                "start_date": start_date,
                "end_date": end_date,
                "department": department or "Все отделения",
            },
            "heatmap_data": heatmap_data,
            "summary": {
                "peak_hour": (
                    max(heatmap_data, key=lambda x: x["average_wait_minutes"])["hour"]
                    if heatmap_data
                    else None
                ),
                "best_hour": (
                    min(
                        heatmap_data,
                        key=lambda x: x["average_wait_minutes"] or float('inf'),
                    )["hour"]
                    if heatmap_data
                    else None
                ),
                "busiest_hour": (
                    max(heatmap_data, key=lambda x: x["patient_count"])["hour"]
                    if heatmap_data
                    else None
                ),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения тепловой карты времени ожидания: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения тепловой карты: {str(e)}",
        )


# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================


def _calculate_performance_rating(average_wait_minutes: float) -> str:
    """Рассчитывает рейтинг производительности на основе среднего времени ожидания"""
    if average_wait_minutes <= 10:
        return "Отлично"
    elif average_wait_minutes <= 20:
        return "Хорошо"
    elif average_wait_minutes <= 30:
        return "Удовлетворительно"
    elif average_wait_minutes <= 45:
        return "Требует улучшения"
    else:
        return "Критично"


def _calculate_intensity(average_wait_minutes: float) -> float:
    """Рассчитывает интенсивность для тепловой карты (0-1)"""
    # Нормализуем время ожидания к диапазону 0-1
    # 0 минут = 0, 60+ минут = 1
    return min(1.0, average_wait_minutes / 60.0)
