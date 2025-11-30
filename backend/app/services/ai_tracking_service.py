"""
Сервис для трекинга AI моделей в авто режиме
"""

import hashlib
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.crud import ai_config as crud_ai
from app.models.ai_config import AIProvider, AIUsageLog
from app.schemas.ai_tracking import (
    AIModelInfo,
    AIModelStats,
    AIProviderStats,
    AIRequestTracking,
    AIResponseWithTracking,
)


class AITrackingService:
    """Сервис для трекинга AI моделей"""

    def __init__(self, db: Session):
        self.db = db

    def create_request_tracking(
        self,
        provider_id: int,
        task_type: str,
        specialty: Optional[str] = None,
        user_id: Optional[int] = None,
        request_data: Optional[Dict[str, Any]] = None,
    ) -> AIRequestTracking:
        """Создать трекинг для AI запроса"""

        # Получаем информацию о провайдере
        provider = (
            self.db.query(AIProvider).filter(AIProvider.id == provider_id).first()
        )
        if not provider:
            raise ValueError(f"AI провайдер с ID {provider_id} не найден")

        # Создаем уникальный ID запроса
        request_id = str(uuid.uuid4())

        # Создаем хеш запроса для кэширования
        request_hash = None
        if request_data:
            request_str = f"{task_type}:{specialty}:{str(request_data)}"
            request_hash = hashlib.sha256(request_str.encode()).hexdigest()

        # Создаем информацию о модели
        model_info = AIModelInfo(
            provider_id=provider.id,
            provider_name=provider.name,
            model_name=provider.model or "unknown",
            model_version=getattr(provider, 'version', None),
            temperature=provider.temperature,
            max_tokens=provider.max_tokens,
            capabilities=provider.capabilities,
        )

        # Создаем трекинг
        tracking = AIRequestTracking(
            request_id=request_id,
            task_type=task_type,
            specialty=specialty,
            user_id=user_id,
            model_info=model_info,
            response_time_ms=0,  # Будет обновлено при завершении
            tokens_used=0,  # Будет обновлено при завершении
            success=False,  # Будет обновлено при завершении
            request_hash=request_hash,
        )

        return tracking

    def complete_request_tracking(
        self,
        tracking: AIRequestTracking,
        response_data: Dict[str, Any],
        tokens_used: int,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> AIResponseWithTracking:
        """Завершить трекинг AI запроса"""

        # Обновляем время завершения
        tracking.completed_at = datetime.utcnow()

        # Вычисляем время ответа
        if tracking.created_at:
            response_time = (
                tracking.completed_at - tracking.created_at
            ).total_seconds() * 1000
            tracking.response_time_ms = int(response_time)

        # Обновляем метрики
        tracking.tokens_used = tokens_used
        tracking.success = success
        tracking.error_message = error_message

        # Сохраняем в базу данных
        self._save_usage_log(tracking)

        # Создаем ответ с трекингом
        response = AIResponseWithTracking(data=response_data, tracking=tracking)

        return response

    def _save_usage_log(self, tracking: AIRequestTracking):
        """Сохранить лог использования в базу данных"""
        try:
            log = AIUsageLog(
                user_id=tracking.user_id,
                provider_id=tracking.model_info.provider_id,
                task_type=tracking.task_type,
                specialty=tracking.specialty,
                tokens_used=tracking.tokens_used,
                response_time_ms=tracking.response_time_ms,
                success=tracking.success,
                error_message=tracking.error_message,
                request_hash=tracking.request_hash,
                cached_response=tracking.cached_response,
            )

            self.db.add(log)
            self.db.commit()

        except Exception as e:
            print(f"Ошибка сохранения лога AI: {e}")
            self.db.rollback()

    def get_model_stats(
        self,
        days_back: int = 30,
        provider_id: Optional[int] = None,
        specialty: Optional[str] = None,
    ) -> List[AIModelStats]:
        """Получить статистику по AI моделям"""

        # Базовый запрос
        query = self.db.query(
            AIProvider.name.label('provider_name'),
            AIProvider.model.label('model_name'),
            func.count(AIUsageLog.id).label('total_requests'),
            func.sum(func.case([(AIUsageLog.success == True, 1)], else_=0)).label(
                'successful_requests'
            ),
            func.sum(func.case([(AIUsageLog.success == False, 1)], else_=0)).label(
                'failed_requests'
            ),
            func.avg(AIUsageLog.response_time_ms).label('average_response_time_ms'),
            func.sum(AIUsageLog.tokens_used).label('total_tokens_used'),
            func.avg(
                func.case([(AIUsageLog.cached_response == True, 1)], else_=0)
            ).label('cache_hit_rate'),
            func.max(AIUsageLog.created_at).label('last_used'),
        ).join(AIProvider, AIUsageLog.provider_id == AIProvider.id)

        # Фильтры
        if days_back:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            query = query.filter(AIUsageLog.created_at >= cutoff_date)

        if provider_id:
            query = query.filter(AIProvider.id == provider_id)

        if specialty:
            query = query.filter(AIUsageLog.specialty == specialty)

        # Группировка и сортировка
        query = query.group_by(
            AIProvider.id, AIProvider.name, AIProvider.model
        ).order_by(desc('total_requests'))

        # Выполняем запрос
        results = query.all()

        # Преобразуем в схемы
        stats = []
        for result in results:
            stat = AIModelStats(
                provider_name=result.provider_name,
                model_name=result.model_name or "unknown",
                total_requests=result.total_requests or 0,
                successful_requests=result.successful_requests or 0,
                failed_requests=result.failed_requests or 0,
                average_response_time_ms=float(result.average_response_time_ms or 0),
                total_tokens_used=result.total_tokens_used or 0,
                cache_hit_rate=float(result.cache_hit_rate or 0),
                last_used=result.last_used,
            )
            stats.append(stat)

        return stats

    def get_provider_stats(self, days_back: int = 30) -> List[AIProviderStats]:
        """Получить статистику по провайдерам AI"""

        # Получаем всех провайдеров
        providers = self.db.query(AIProvider).all()

        stats = []
        for provider in providers:
            # Получаем статистику моделей для провайдера
            model_stats = self.get_model_stats(
                days_back=days_back, provider_id=provider.id
            )

            # Вычисляем общую статистику провайдера
            total_requests = sum(stat.total_requests for stat in model_stats)
            successful_requests = sum(stat.successful_requests for stat in model_stats)
            avg_response_time = (
                sum(stat.average_response_time_ms for stat in model_stats)
                / len(model_stats)
                if model_stats
                else 0
            )

            success_rate = (
                (successful_requests / total_requests * 100)
                if total_requests > 0
                else 0
            )

            provider_stat = AIProviderStats(
                provider_id=provider.id,
                provider_name=provider.name,
                display_name=provider.display_name,
                is_active=provider.active,
                is_default=provider.is_default,
                models=model_stats,
                total_requests=total_requests,
                success_rate=success_rate,
                average_response_time_ms=avg_response_time,
            )

            stats.append(provider_stat)

        return stats

    def get_request_tracking(self, request_id: str) -> Optional[AIRequestTracking]:
        """Получить трекинг запроса по ID"""
        # Здесь можно реализовать кэширование или поиск в БД
        # Пока возвращаем None, так как трекинг хранится в памяти
        return None


# Глобальные функции для использования в API
def get_ai_tracking_service(db: Session) -> AITrackingService:
    """Получить экземпляр сервиса трекинга AI"""
    return AITrackingService(db)
