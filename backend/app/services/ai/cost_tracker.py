"""
AI Cost Tracking Service - Мониторинг расходов на AI API.

Функции:
- Расчет стоимости по провайдерам
- Budget alerts
- Аналитика использования
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.ai_config import AIUsageLog

logger = logging.getLogger(__name__)


# Стоимость за 1000 токенов (USD)
# Обновлять при изменении цен провайдерами
COST_PER_1K_TOKENS = {
    "openai": {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "default": {"input": 0.01, "output": 0.03},
    },
    "gemini": {
        "gemini-1.5-flash": {"input": 0.00035, "output": 0.0014},
        "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
        "gemini-pro": {"input": 0.0005, "output": 0.0015},
        "default": {"input": 0.0005, "output": 0.0015},
    },
    "deepseek": {
        "deepseek-chat": {"input": 0.0014, "output": 0.0028},
        "deepseek-coder": {"input": 0.0014, "output": 0.0028},
        "default": {"input": 0.0014, "output": 0.0028},
    },
    "mock": {
        "default": {"input": 0.0, "output": 0.0},
    },
}


class AICostTracker:
    """
    Трекер расходов на AI API.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_token_cost(
        self, 
        provider: str, 
        model: Optional[str], 
        tokens: int,
        is_input: bool = True
    ) -> float:
        """
        Рассчитать стоимость токенов.
        
        Args:
            provider: Имя провайдера
            model: Модель (или None для default)
            tokens: Количество токенов
            is_input: Input или output токены
            
        Returns:
            Стоимость в USD
        """
        provider_costs = COST_PER_1K_TOKENS.get(provider, COST_PER_1K_TOKENS["openai"])
        model_costs = provider_costs.get(model or "default", provider_costs["default"])
        
        rate = model_costs["input" if is_input else "output"]
        cost = (tokens / 1000) * rate
        
        return round(cost, 6)
    
    def calculate_request_cost(
        self,
        provider: str,
        model: Optional[str],
        tokens_used: int
    ) -> float:
        """
        Рассчитать стоимость запроса.
        
        Упрощение: считаем все токены как input (типичное соотношение 70/30 input/output)
        """
        if not tokens_used:
            return 0.0
        
        # Приблизительно: 70% input, 30% output
        input_tokens = int(tokens_used * 0.7)
        output_tokens = tokens_used - input_tokens
        
        input_cost = self.get_token_cost(provider, model, input_tokens, is_input=True)
        output_cost = self.get_token_cost(provider, model, output_tokens, is_input=False)
        
        return round(input_cost + output_cost, 6)
    
    def get_period_cost(
        self,
        days_back: int = 30,
        user_id: Optional[int] = None,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Получить расходы за период.
        
        Returns:
            {
                "total_cost_usd": 125.50,
                "total_tokens": 1250000,
                "total_requests": 5000,
                "by_provider": {"openai": 80.0, "gemini": 30.0, ...},
                "by_day": [{"date": "2024-01-15", "cost": 5.2}, ...],
                "cached_savings_usd": 15.0
            }
        """
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        
        query = self.db.query(AIUsageLog).filter(
            AIUsageLog.created_at >= cutoff,
            AIUsageLog.success == True
        )
        
        if user_id:
            query = query.filter(AIUsageLog.user_id == user_id)
        
        if provider:
            query = query.filter(AIUsageLog.provider_name == provider)
        
        logs = query.all()
        
        # Агрегация
        total_cost = 0.0
        total_tokens = 0
        total_requests = len(logs)
        cached_count = 0
        cached_tokens = 0
        
        by_provider: Dict[str, float] = {}
        by_day: Dict[str, float] = {}
        by_task: Dict[str, float] = {}
        by_user: Dict[int, float] = {}
        
        for log in logs:
            tokens = log.tokens_used or 0
            total_tokens += tokens
            
            # Для кэшированных ответов - это экономия
            if log.cached_response:
                cached_count += 1
                cached_tokens += tokens
                continue
            
            # Рассчитываем стоимость
            # Нужно получить model из провайдера (в текущей схеме нет поля model в AIUsageLog)
            cost = self.calculate_request_cost(
                provider=log.provider_name or "unknown",
                model=None,  # TODO: добавить поле model в AIUsageLog
                tokens_used=tokens
            )
            
            total_cost += cost
            
            # По провайдерам
            prov = log.provider_name or "unknown"
            by_provider[prov] = by_provider.get(prov, 0) + cost
            
            # По дням
            day = log.created_at.strftime("%Y-%m-%d")
            by_day[day] = by_day.get(day, 0) + cost
            
            # По типам задач
            task = log.task_type or "unknown"
            by_task[task] = by_task.get(task, 0) + cost
            
            # По пользователям
            if log.user_id:
                by_user[log.user_id] = by_user.get(log.user_id, 0) + cost
        
        # Расчет экономии от кэширования
        cached_savings = self.calculate_request_cost(
            provider="openai",  # Средняя стоимость
            model="gpt-4o-mini",
            tokens_used=cached_tokens
        )
        
        # Сортировка by_day
        sorted_days = [
            {"date": d, "cost": round(c, 4)}
            for d, c in sorted(by_day.items())
        ]
        
        # Top users
        top_users = sorted(
            [{"user_id": u, "cost": round(c, 4)} for u, c in by_user.items()],
            key=lambda x: x["cost"],
            reverse=True
        )[:10]
        
        return {
            "period_days": days_back,
            "total_cost_usd": round(total_cost, 4),
            "total_tokens": total_tokens,
            "total_requests": total_requests,
            "cached_requests": cached_count,
            "cached_savings_usd": round(cached_savings, 4),
            "by_provider": {k: round(v, 4) for k, v in by_provider.items()},
            "by_task": {k: round(v, 4) for k, v in by_task.items()},
            "by_day": sorted_days,
            "top_users": top_users,
        }
    
    def check_budget_status(self, monthly_budget: float) -> Dict[str, Any]:
        """
        Проверка статуса бюджета.
        
        Returns:
            {
                "budget_usd": 500.0,
                "spent_usd": 125.5,
                "remaining_usd": 374.5,
                "used_pct": 25.1,
                "alert": False,
                "projected_monthly_usd": 175.0,
                "days_remaining": 15
            }
        """
        from app.core.config import settings
        
        # Получаем текущий месяц
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        days_in_month = 30  # Упрощение
        days_elapsed = (now - month_start).days + 1
        days_remaining = max(1, days_in_month - days_elapsed)
        
        # Расходы за текущий месяц
        month_stats = self.get_period_cost(days_back=days_elapsed)
        spent = month_stats["total_cost_usd"]
        
        # Проекция на месяц
        daily_avg = spent / days_elapsed if days_elapsed > 0 else 0
        projected = daily_avg * days_in_month
        
        # Статус
        used_pct = (spent / monthly_budget * 100) if monthly_budget > 0 else 0
        alert = used_pct >= settings.AI_BUDGET_ALERT_THRESHOLD_PCT
        
        return {
            "budget_usd": monthly_budget,
            "spent_usd": round(spent, 2),
            "remaining_usd": round(max(0, monthly_budget - spent), 2),
            "used_pct": round(used_pct, 1),
            "alert": alert,
            "alert_threshold_pct": settings.AI_BUDGET_ALERT_THRESHOLD_PCT,
            "projected_monthly_usd": round(projected, 2),
            "days_elapsed": days_elapsed,
            "days_remaining": days_remaining,
        }
    
    def get_provider_stats(self) -> List[Dict[str, Any]]:
        """
        Статистика по провайдерам.
        """
        stats = self.db.query(
            AIUsageLog.provider_name,
            func.count(AIUsageLog.id).label("request_count"),
            func.sum(AIUsageLog.tokens_used).label("total_tokens"),
            func.avg(AIUsageLog.response_time_ms).label("avg_latency_ms"),
            func.sum(func.cast(AIUsageLog.success, type_=None)).label("success_count"),
        ).group_by(
            AIUsageLog.provider_name
        ).all()
        
        result = []
        for stat in stats:
            success_rate = (
                (stat.success_count / stat.request_count * 100)
                if stat.request_count > 0 else 0
            )
            
            result.append({
                "provider": stat.provider_name,
                "requests": stat.request_count,
                "tokens": stat.total_tokens or 0,
                "avg_latency_ms": round(stat.avg_latency_ms or 0, 1),
                "success_rate_pct": round(success_rate, 1),
            })
        
        return result


def get_cost_tracker(db: Session) -> AICostTracker:
    """Factory function for DI"""
    return AICostTracker(db)
