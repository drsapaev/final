"""
API endpoints для расширенной аналитики AI использования
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.deps import get_db, require_roles, get_current_user
from app.models.user import User
from app.services.ai_analytics_service import get_ai_analytics_service

logger = logging.getLogger(__name__)

router = APIRouter()

# ===================== PYDANTIC СХЕМЫ =====================

class AIUsageTrackingRequest(BaseModel):
    """Схема для отслеживания использования AI"""
    ai_function: str = Field(..., description="Название AI функции")
    input_data: dict = Field(..., description="Входные данные")
    output_data: dict = Field(..., description="Выходные данные")
    execution_time: float = Field(..., description="Время выполнения в секундах")
    success: bool = Field(True, description="Успешность выполнения")
    error_message: Optional[str] = Field(None, description="Сообщение об ошибке")

class AIUsageAnalyticsResponse(BaseModel):
    """Схема ответа с аналитикой использования AI"""
    period: dict
    usage_statistics: dict
    function_breakdown: dict
    user_breakdown: dict
    performance_metrics: dict
    cost_analysis: dict
    trends: dict
    recommendations: List[str]

class AILearningInsightsResponse(BaseModel):
    """Схема ответа с инсайтами для обучения AI"""
    period: dict
    medical_patterns: dict
    diagnostic_accuracy: dict
    treatment_effectiveness: dict
    patient_outcomes: dict
    seasonal_trends: dict
    learning_recommendations: List[str]

class AIOptimizationResponse(BaseModel):
    """Схема ответа с результатами оптимизации AI"""
    timestamp: str
    models_analyzed: List[dict]
    optimizations_applied: List[dict]
    performance_improvements: dict
    recommendations: List[str]

class TrainingDatasetRequest(BaseModel):
    """Схема запроса на генерацию обучающего датасета"""
    data_type: str = Field(..., description="Тип данных: diagnostic_patterns, treatment_outcomes, patient_symptoms, scheduling_patterns")
    start_date: str = Field(..., description="Начальная дата (YYYY-MM-DD)")
    end_date: str = Field(..., description="Конечная дата (YYYY-MM-DD)")
    anonymize: bool = Field(True, description="Анонимизировать данные")

class TrainingDatasetResponse(BaseModel):
    """Схема ответа с информацией о датасете"""
    data_type: str
    period: dict
    anonymized: bool
    generated_at: str
    records_count: int
    features: List[str]
    quality_score: float
    privacy_compliance: dict
    dataset_path: str

# ===================== ENDPOINTS =====================

@router.post("/track-usage")
async def track_ai_usage(
    request: AIUsageTrackingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Отслеживает использование AI функций"""
    try:
        service = get_ai_analytics_service(db)
        
        result = service.track_ai_usage(
            user_id=current_user.id,
            ai_function=request.ai_function,
            input_data=request.input_data,
            output_data=request.output_data,
            execution_time=request.execution_time,
            success=request.success,
            error_message=request.error_message
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Ошибка отслеживания AI использования: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отслеживания: {str(e)}"
        )

@router.get("/usage-analytics", response_model=AIUsageAnalyticsResponse)
async def get_ai_usage_analytics(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    user_id: Optional[int] = Query(None, description="Фильтр по пользователю"),
    ai_function: Optional[str] = Query(None, description="Фильтр по AI функции"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Doctor"]))
):
    """Получить аналитику использования AI за период"""
    try:
        # Валидация дат
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат даты. Используйте YYYY-MM-DD"
            )
        
        if start > end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Начальная дата должна быть раньше конечной"
            )
        
        # Ограничиваем период анализа (максимум 180 дней)
        if (end - start).days > 180:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Период анализа не может превышать 180 дней"
            )
        
        service = get_ai_analytics_service(db)
        analytics = service.get_ai_usage_analytics(start, end, user_id, ai_function)
        
        return AIUsageAnalyticsResponse(**analytics)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения аналитики AI использования: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения аналитики: {str(e)}"
        )

@router.get("/learning-insights", response_model=AILearningInsightsResponse)
async def get_ai_learning_insights(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin"]))
):
    """Получить инсайты для обучения AI на основе данных клиники"""
    try:
        # Валидация дат
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат даты. Используйте YYYY-MM-DD"
            )
        
        if start > end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Начальная дата должна быть раньше конечной"
            )
        
        service = get_ai_analytics_service(db)
        insights = service.get_ai_learning_insights(start, end)
        
        return AILearningInsightsResponse(**insights)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения инсайтов для обучения AI: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения инсайтов: {str(e)}"
        )

@router.post("/optimize-models", response_model=AIOptimizationResponse)
async def optimize_ai_models(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin"]))
):
    """Запустить оптимизацию AI моделей на основе накопленных данных"""
    try:
        service = get_ai_analytics_service(db)
        
        # Запускаем оптимизацию в фоновом режиме для длительных операций
        def run_optimization():
            try:
                result = service.optimize_ai_models()
                logger.info(f"AI оптимизация завершена: {result}")
            except Exception as e:
                logger.error(f"Ошибка в фоновой оптимизации AI: {e}")
        
        background_tasks.add_task(run_optimization)
        
        # Возвращаем немедленный ответ
        optimization_result = service.optimize_ai_models()
        
        return AIOptimizationResponse(**optimization_result)
        
    except Exception as e:
        logger.error(f"Ошибка оптимизации AI моделей: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка оптимизации: {str(e)}"
        )

@router.post("/generate-training-dataset", response_model=TrainingDatasetResponse)
async def generate_training_dataset(
    request: TrainingDatasetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin"]))
):
    """Генерирует обучающий датасет из данных клиники"""
    try:
        # Валидация дат
        try:
            start = datetime.strptime(request.start_date, "%Y-%m-%d").date()
            end = datetime.strptime(request.end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат даты. Используйте YYYY-MM-DD"
            )
        
        if start > end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Начальная дата должна быть раньше конечной"
            )
        
        # Валидация типа данных
        valid_types = ["diagnostic_patterns", "treatment_outcomes", "patient_symptoms", "scheduling_patterns"]
        if request.data_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Неподдерживаемый тип данных. Доступные типы: {', '.join(valid_types)}"
            )
        
        service = get_ai_analytics_service(db)
        
        # Генерируем датасет
        dataset_info = service.generate_ai_training_dataset(
            data_type=request.data_type,
            start_date=start,
            end_date=end,
            anonymize=request.anonymize
        )
        
        if "error" in dataset_info:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=dataset_info["error"]
            )
        
        return TrainingDatasetResponse(**dataset_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка генерации обучающего датасета: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка генерации датасета: {str(e)}"
        )

@router.get("/usage-summary")
async def get_ai_usage_summary(
    days: int = Query(30, ge=1, le=365, description="Количество дней для анализа"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Doctor"]))
):
    """Получить краткую сводку использования AI за последние дни"""
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        service = get_ai_analytics_service(db)
        analytics = service.get_ai_usage_analytics(start_date, end_date)
        
        # Формируем краткую сводку
        usage_stats = analytics.get("usage_statistics", {})
        cost_analysis = analytics.get("cost_analysis", {})
        performance = analytics.get("performance_metrics", {})
        
        summary = {
            "period_days": days,
            "total_requests": usage_stats.get("total_requests", 0),
            "success_rate": usage_stats.get("success_rate", 0),
            "average_response_time": usage_stats.get("average_execution_time", 0),
            "total_cost_usd": cost_analysis.get("total_cost_usd", 0),
            "daily_average_cost": cost_analysis.get("average_daily_cost", 0),
            "most_used_function": _get_most_used_function(analytics.get("function_breakdown", {})),
            "peak_usage_hour": performance.get("peak_hour"),
            "error_rate": performance.get("error_rate", 0),
            "cost_trend": cost_analysis.get("cost_trend", "stable"),
            "recommendations": analytics.get("recommendations", [])[:3],  # Топ-3 рекомендации
            "last_updated": datetime.now().isoformat()
        }
        
        return summary
        
    except Exception as e:
        logger.error(f"Ошибка получения сводки AI использования: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения сводки: {str(e)}"
        )

@router.get("/function-performance/{function_name}")
async def get_function_performance(
    function_name: str,
    days: int = Query(7, ge=1, le=90, description="Количество дней для анализа"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Doctor"]))
):
    """Получить детальную информацию о производительности конкретной AI функции"""
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        service = get_ai_analytics_service(db)
        analytics = service.get_ai_usage_analytics(start_date, end_date, ai_function=function_name)
        
        function_stats = analytics.get("function_breakdown", {}).get(function_name, {})
        
        if not function_stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Данные для функции '{function_name}' не найдены"
            )
        
        performance_details = {
            "function_name": function_name,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days
            },
            "statistics": function_stats,
            "performance_rating": _calculate_performance_rating(function_stats),
            "optimization_suggestions": _get_optimization_suggestions(function_name, function_stats),
            "usage_trend": analytics.get("trends", {}).get("trend", "stable"),
            "cost_efficiency": _calculate_cost_efficiency(function_stats),
            "user_satisfaction": _estimate_user_satisfaction(function_stats)
        }
        
        return performance_details
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения производительности функции {function_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения данных: {str(e)}"
        )

@router.get("/cost-analysis")
async def get_ai_cost_analysis(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)"),
    group_by: str = Query("day", description="Группировка: day, week, month"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin"]))
):
    """Получить детальный анализ затрат на AI"""
    try:
        # Валидация дат
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат даты. Используйте YYYY-MM-DD"
            )
        
        service = get_ai_analytics_service(db)
        analytics = service.get_ai_usage_analytics(start, end)
        
        cost_analysis = analytics.get("cost_analysis", {})
        function_breakdown = analytics.get("function_breakdown", {})
        
        # Рассчитываем затраты по функциям
        function_costs = {}
        for function, stats in function_breakdown.items():
            function_costs[function] = {
                "total_cost": stats.get("total_cost", 0),
                "average_cost_per_request": stats.get("average_cost", 0),
                "requests": stats.get("requests", 0),
                "cost_percentage": (stats.get("total_cost", 0) / cost_analysis.get("total_cost_usd", 1)) * 100
            }
        
        # Прогнозируем затраты
        daily_cost = cost_analysis.get("average_daily_cost", 0)
        monthly_forecast = daily_cost * 30
        yearly_forecast = daily_cost * 365
        
        detailed_analysis = {
            "period": {
                "start_date": start_date,
                "end_date": end_date,
                "group_by": group_by
            },
            "summary": cost_analysis,
            "function_costs": function_costs,
            "forecasts": {
                "monthly_usd": monthly_forecast,
                "yearly_usd": yearly_forecast,
                "confidence": "medium"  # Зависит от объема данных
            },
            "cost_optimization": {
                "potential_savings": _calculate_potential_savings(function_costs),
                "recommendations": _generate_cost_recommendations(function_costs)
            },
            "budget_alerts": _check_budget_alerts(cost_analysis, monthly_forecast)
        }
        
        return detailed_analysis
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка анализа затрат на AI: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка анализа затрат: {str(e)}"
        )

@router.get("/model-comparison")
async def compare_ai_models(
    function: str = Query(..., description="AI функция для сравнения"),
    days: int = Query(30, ge=7, le=180, description="Период для сравнения"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin"]))
):
    """Сравнить производительность разных AI моделей"""
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        service = get_ai_analytics_service(db)
        
        # Получаем данные для сравнения (в реальности здесь будет сравнение разных моделей)
        comparison_data = {
            "function": function,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "models": {
                "gpt-4": {
                    "accuracy": 92.5,
                    "speed": 2.3,
                    "cost_per_request": 0.002,
                    "user_satisfaction": 4.6,
                    "reliability": 98.2
                },
                "gpt-3.5": {
                    "accuracy": 87.1,
                    "speed": 1.1,
                    "cost_per_request": 0.0005,
                    "user_satisfaction": 4.2,
                    "reliability": 96.8
                },
                "claude": {
                    "accuracy": 89.8,
                    "speed": 1.8,
                    "cost_per_request": 0.0015,
                    "user_satisfaction": 4.4,
                    "reliability": 97.5
                }
            },
            "recommendations": {
                "best_for_accuracy": "gpt-4",
                "best_for_speed": "gpt-3.5",
                "best_for_cost": "gpt-3.5",
                "best_overall": "gpt-4"
            },
            "optimization_suggestions": [
                "Использовать gpt-3.5 для простых запросов",
                "Переключаться на gpt-4 для сложных диагнозов",
                "Внедрить гибридный подход для оптимизации затрат"
            ]
        }
        
        return comparison_data
        
    except Exception as e:
        logger.error(f"Ошибка сравнения AI моделей: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка сравнения моделей: {str(e)}"
        )

# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================

def _get_most_used_function(function_breakdown: dict) -> Optional[str]:
    """Находит наиболее используемую AI функцию"""
    if not function_breakdown:
        return None
    
    return max(function_breakdown.items(), key=lambda x: x[1].get("requests", 0))[0]

def _calculate_performance_rating(function_stats: dict) -> str:
    """Рассчитывает рейтинг производительности функции"""
    success_rate = function_stats.get("success_rate", 0)
    avg_time = function_stats.get("average_time", 0)
    
    if success_rate >= 95 and avg_time <= 2:
        return "Отлично"
    elif success_rate >= 90 and avg_time <= 3:
        return "Хорошо"
    elif success_rate >= 85 and avg_time <= 5:
        return "Удовлетворительно"
    else:
        return "Требует улучшения"

def _get_optimization_suggestions(function_name: str, stats: dict) -> List[str]:
    """Генерирует предложения по оптимизации функции"""
    suggestions = []
    
    if stats.get("average_time", 0) > 3:
        suggestions.append("Оптимизировать промпты для сокращения времени ответа")
    
    if stats.get("success_rate", 100) < 95:
        suggestions.append("Улучшить обработку входных данных")
    
    if stats.get("average_cost", 0) > 0.005:
        suggestions.append("Рассмотреть использование более экономичной модели")
    
    return suggestions if suggestions else ["Функция работает оптимально"]

def _calculate_cost_efficiency(function_stats: dict) -> float:
    """Рассчитывает эффективность затрат"""
    success_rate = function_stats.get("success_rate", 0) / 100
    avg_cost = function_stats.get("average_cost", 0)
    
    if avg_cost == 0:
        return 100.0
    
    # Эффективность = успешность / стоимость * 100
    efficiency = (success_rate / avg_cost) * 100
    return min(100.0, efficiency)

def _estimate_user_satisfaction(function_stats: dict) -> float:
    """Оценивает удовлетворенность пользователей"""
    success_rate = function_stats.get("success_rate", 0)
    avg_time = function_stats.get("average_time", 0)
    
    # Простая формула на основе успешности и скорости
    time_factor = max(0, 5 - avg_time) / 5  # Чем быстрее, тем лучше
    success_factor = success_rate / 100
    
    satisfaction = (success_factor * 0.7 + time_factor * 0.3) * 5  # Шкала 0-5
    return round(satisfaction, 1)

def _calculate_potential_savings(function_costs: dict) -> dict:
    """Рассчитывает потенциальную экономию"""
    total_cost = sum(func["total_cost"] for func in function_costs.values())
    
    # Предполагаем 15% экономию при оптимизации
    potential_savings = total_cost * 0.15
    
    return {
        "amount_usd": potential_savings,
        "percentage": 15.0,
        "methods": [
            "Оптимизация промптов",
            "Кэширование результатов",
            "Использование более экономичных моделей"
        ]
    }

def _generate_cost_recommendations(function_costs: dict) -> List[str]:
    """Генерирует рекомендации по оптимизации затрат"""
    recommendations = []
    
    # Находим самую дорогую функцию
    if function_costs:
        most_expensive = max(function_costs.items(), key=lambda x: x[1]["total_cost"])
        recommendations.append(f"Оптимизировать функцию '{most_expensive[0]}' - наибольшие затраты")
    
    recommendations.extend([
        "Внедрить кэширование для часто запрашиваемых результатов",
        "Использовать пакетную обработку для снижения затрат",
        "Настроить автоматическое переключение между моделями"
    ])
    
    return recommendations

def _check_budget_alerts(cost_analysis: dict, monthly_forecast: float) -> List[dict]:
    """Проверяет превышение бюджета"""
    alerts = []
    
    # Примерные лимиты (в реальности будут настраиваться)
    daily_limit = 10.0  # $10 в день
    monthly_limit = 200.0  # $200 в месяц
    
    daily_cost = cost_analysis.get("average_daily_cost", 0)
    
    if daily_cost > daily_limit:
        alerts.append({
            "type": "daily_limit_exceeded",
            "message": f"Превышен дневной лимит: ${daily_cost:.2f} > ${daily_limit}",
            "severity": "high"
        })
    
    if monthly_forecast > monthly_limit:
        alerts.append({
            "type": "monthly_forecast_high",
            "message": f"Прогноз месячных затрат превышает лимит: ${monthly_forecast:.2f} > ${monthly_limit}",
            "severity": "medium"
        })
    
    return alerts

