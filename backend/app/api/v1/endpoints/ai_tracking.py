"""
API endpoints для трекинга AI моделей
"""
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.ai_tracking_service import get_ai_tracking_service
from app.schemas.ai_tracking import (
    AIModelStats,
    AIProviderStats,
    AIResponseWithTracking
)

router = APIRouter()


@router.get("/models/stats", response_model=List[AIModelStats])
async def get_ai_model_stats(
    days_back: int = Query(30, ge=1, le=365, description="Количество дней назад"),
    provider_id: Optional[int] = Query(None, description="ID провайдера"),
    specialty: Optional[str] = Query(None, description="Специализация"),
    db: Session = Depends(get_db)
):
    """
    Получить статистику по AI моделям
    
    Показывает:
    - Какие модели использовались
    - Количество запросов
    - Время ответа
    - Успешность
    - Использование токенов
    """
    tracking_service = get_ai_tracking_service(db)
    
    try:
        stats = tracking_service.get_model_stats(
            days_back=days_back,
            provider_id=provider_id,
            specialty=specialty
        )
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {str(e)}")


@router.get("/providers/stats", response_model=List[AIProviderStats])
async def get_ai_provider_stats(
    days_back: int = Query(30, ge=1, le=365, description="Количество дней назад"),
    db: Session = Depends(get_db)
):
    """
    Получить статистику по провайдерам AI
    
    Показывает:
    - Активные провайдеры
    - Общую статистику использования
    - Статистику по каждой модели
    - Производительность
    """
    tracking_service = get_ai_tracking_service(db)
    
    try:
        stats = tracking_service.get_provider_stats(days_back=days_back)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {str(e)}")


@router.get("/models/current")
async def get_current_ai_models(
    db: Session = Depends(get_db)
):
    """
    Получить информацию о текущих AI моделях
    
    Показывает:
    - Активные модели
    - Их возможности
    - Настройки
    - Статус
    """
    from app.crud import ai_config as crud_ai
    
    try:
        providers = crud_ai.get_active_providers(db)
        
        models_info = []
        for provider in providers:
            model_info = {
                "provider_id": provider.id,
                "provider_name": provider.name,
                "display_name": provider.display_name,
                "model_name": provider.model,
                "temperature": provider.temperature,
                "max_tokens": provider.max_tokens,
                "capabilities": provider.capabilities,
                "is_default": provider.is_default,
                "active": provider.active
            }
            models_info.append(model_info)
        
        return {
            "models": models_info,
            "total_models": len(models_info),
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения моделей: {str(e)}")


@router.get("/requests/recent")
async def get_recent_ai_requests(
    limit: int = Query(50, ge=1, le=200, description="Количество записей"),
    db: Session = Depends(get_db)
):
    """
    Получить последние AI запросы с информацией о моделях
    
    Показывает:
    - Последние запросы
    - Какая модель их обработала
    - Время выполнения
    - Результат
    """
    from app.models.ai_config import AIUsageLog, AIProvider
    
    try:
        # Получаем последние записи
        logs = db.query(AIUsageLog, AIProvider).join(
            AIProvider, AIUsageLog.provider_id == AIProvider.id
        ).order_by(AIUsageLog.created_at.desc()).limit(limit).all()
        
        requests = []
        for log, provider in logs:
            request_info = {
                "id": log.id,
                "task_type": log.task_type,
                "specialty": log.specialty,
                "provider_name": provider.name,
                "model_name": provider.model,
                "display_name": provider.display_name,
                "success": log.success,
                "response_time_ms": log.response_time_ms,
                "tokens_used": log.tokens_used,
                "cached_response": log.cached_response,
                "error_message": log.error_message,
                "created_at": log.created_at
            }
            requests.append(request_info)
        
        return {
            "requests": requests,
            "total": len(requests),
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения запросов: {str(e)}")


@router.get("/models/performance")
async def get_ai_models_performance(
    days_back: int = Query(7, ge=1, le=30, description="Количество дней назад"),
    db: Session = Depends(get_db)
):
    """
    Получить производительность AI моделей
    
    Показывает:
    - Среднее время ответа
    - Процент успешности
    - Использование токенов
    - Сравнение моделей
    """
    tracking_service = get_ai_tracking_service(db)
    
    try:
        # Получаем статистику по моделям
        model_stats = tracking_service.get_model_stats(days_back=days_back)
        
        # Вычисляем общую производительность
        total_requests = sum(stat.total_requests for stat in model_stats)
        total_successful = sum(stat.successful_requests for stat in model_stats)
        total_tokens = sum(stat.total_tokens_used for stat in model_stats)
        
        # Средние показатели
        avg_response_time = sum(stat.average_response_time_ms for stat in model_stats) / len(model_stats) if model_stats else 0
        success_rate = (total_successful / total_requests * 100) if total_requests > 0 else 0
        
        # Лучшая модель по времени ответа
        fastest_model = min(model_stats, key=lambda x: x.average_response_time_ms) if model_stats else None
        
        # Лучшая модель по успешности
        most_reliable_model = max(model_stats, key=lambda x: x.successful_requests) if model_stats else None
        
        return {
            "summary": {
                "total_requests": total_requests,
                "total_successful": total_successful,
                "success_rate": round(success_rate, 2),
                "total_tokens_used": total_tokens,
                "average_response_time_ms": round(avg_response_time, 2)
            },
            "best_performance": {
                "fastest_model": {
                    "name": fastest_model.model_name if fastest_model else None,
                    "provider": fastest_model.provider_name if fastest_model else None,
                    "response_time_ms": fastest_model.average_response_time_ms if fastest_model else None
                },
                "most_reliable_model": {
                    "name": most_reliable_model.model_name if most_reliable_model else None,
                    "provider": most_reliable_model.provider_name if most_reliable_model else None,
                    "success_rate": round((most_reliable_model.successful_requests / most_reliable_model.total_requests * 100) if most_reliable_model and most_reliable_model.total_requests > 0 else 0, 2)
                }
            },
            "models": model_stats,
            "period_days": days_back,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения производительности: {str(e)}")


@router.get("/models/usage-trends")
async def get_ai_usage_trends(
    days_back: int = Query(30, ge=7, le=90, description="Количество дней назад"),
    db: Session = Depends(get_db)
):
    """
    Получить тренды использования AI моделей
    
    Показывает:
    - Использование по дням
    - Популярные модели
    - Тренды по специализациям
    """
    from app.models.ai_config import AIUsageLog, AIProvider
    from sqlalchemy import func, desc
    
    try:
        # Получаем данные по дням
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        daily_usage = db.query(
            func.date(AIUsageLog.created_at).label('date'),
            AIProvider.name.label('provider_name'),
            AIProvider.model.label('model_name'),
            func.count(AIUsageLog.id).label('requests_count'),
            func.avg(AIUsageLog.response_time_ms).label('avg_response_time'),
            func.sum(AIUsageLog.tokens_used).label('total_tokens')
        ).join(
            AIProvider, AIUsageLog.provider_id == AIProvider.id
        ).filter(
            AIUsageLog.created_at >= cutoff_date
        ).group_by(
            func.date(AIUsageLog.created_at),
            AIProvider.id,
            AIProvider.name,
            AIProvider.model
        ).order_by(
            func.date(AIUsageLog.created_at).desc()
        ).all()
        
        # Группируем по дням
        trends = {}
        for row in daily_usage:
            date_str = row.date.strftime('%Y-%m-%d')
            if date_str not in trends:
                trends[date_str] = {
                    'date': date_str,
                    'total_requests': 0,
                    'total_tokens': 0,
                    'models': []
                }
            
            trends[date_str]['total_requests'] += row.requests_count
            trends[date_str]['total_tokens'] += row.total_tokens or 0
            trends[date_str]['models'].append({
                'provider': row.provider_name,
                'model': row.model_name,
                'requests': row.requests_count,
                'avg_response_time': round(row.avg_response_time or 0, 2),
                'tokens': row.total_tokens or 0
            })
        
        # Сортируем по дате
        sorted_trends = sorted(trends.values(), key=lambda x: x['date'], reverse=True)
        
        return {
            "trends": sorted_trends,
            "period_days": days_back,
            "total_days": len(sorted_trends),
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения трендов: {str(e)}")
