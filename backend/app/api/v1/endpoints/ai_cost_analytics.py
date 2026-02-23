"""
AI Analytics Endpoints - Аналитика и мониторинг AI.

Функции:
- Cost tracking
- Budget alerts
- Performance stats
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.rbac import AIPermission, require_ai_permission
from app.models.user import User
from app.services.ai.cost_tracker import get_cost_tracker

router = APIRouter()


@router.get("/cost-summary")
async def get_cost_summary(
    days_back: int = Query(30, ge=1, le=365, description="Период в днях"),
    current_user: User = Depends(require_ai_permission(AIPermission.VIEW_STATS)),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Сводка расходов на AI.
    
    Requires: VIEW_STATS permission (Admin)
    
    Returns:
    - Общая стоимость за период
    - Breakdown по провайдерам
    - Breakdown по типам задач
    - Daily trend
    - Top users
    - Экономия от кэширования
    """
    tracker = get_cost_tracker(db)
    return tracker.get_period_cost(days_back=days_back)


@router.get("/budget-status")
async def get_budget_status(
    current_user: User = Depends(require_ai_permission(AIPermission.VIEW_STATS)),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Статус бюджета на AI.
    
    Requires: VIEW_STATS permission (Admin)
    
    Returns:
    - Бюджет / потрачено / остаток
    - Процент использования
    - Alert статус
    - Прогноз на месяц
    """
    tracker = get_cost_tracker(db)
    return tracker.check_budget_status(settings.AI_MONTHLY_BUDGET_USD)


@router.get("/provider-stats")
async def get_provider_stats(
    current_user: User = Depends(require_ai_permission(AIPermission.VIEW_STATS)),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    Статистика по AI провайдерам.
    
    Requires: VIEW_STATS permission (Admin)
    
    Returns:
    - Количество запросов
    - Токены
    - Средняя латентность
    - Success rate
    """
    tracker = get_cost_tracker(db)
    return tracker.get_provider_stats()


@router.get("/my-usage")
async def get_my_usage(
    days_back: int = Query(30, ge=1, le=365),
    current_user: User = Depends(require_ai_permission(AIPermission.CHAT)),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Моя статистика использования AI.
    
    Доступно любому пользователю с CHAT permission.
    """
    tracker = get_cost_tracker(db)
    
    stats = tracker.get_period_cost(
        days_back=days_back,
        user_id=current_user.id
    )
    
    # Убираем sensitive данные для non-admin
    return {
        "period_days": stats["period_days"],
        "total_requests": stats["total_requests"],
        "total_tokens": stats["total_tokens"],
        "cached_requests": stats["cached_requests"],
        "by_task": stats["by_task"],
        "by_day": stats["by_day"][-7:],  # Только последние 7 дней
    }


@router.get("/pricing")
async def get_pricing_info(
    current_user: User = Depends(require_ai_permission(AIPermission.VIEW_STATS)),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Информация о ценах провайдеров.
    
    Requires: VIEW_STATS permission
    """
    from app.services.ai.cost_tracker import COST_PER_1K_TOKENS
    
    return {
        "unit": "USD per 1000 tokens",
        "updated_at": "2026-01-01",  # Обновлять при изменении цен
        "providers": COST_PER_1K_TOKENS
    }


@router.get("/alerts")
async def get_active_alerts(
    current_user: User = Depends(require_ai_permission(AIPermission.VIEW_STATS)),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Активные предупреждения по AI.
    """
    tracker = get_cost_tracker(db)
    budget_status = tracker.check_budget_status(settings.AI_MONTHLY_BUDGET_USD)
    
    alerts = []
    
    # Budget alert
    if budget_status["alert"]:
        alerts.append({
            "type": "budget_warning",
            "severity": "warning" if budget_status["used_pct"] < 100 else "critical",
            "message": f"AI budget is {budget_status['used_pct']}% used. "
                       f"Spent: ${budget_status['spent_usd']}, "
                       f"Budget: ${budget_status['budget_usd']}",
            "data": budget_status
        })
    
    # Check provider health
    from app.services.ai import get_ai_gateway
    gateway = get_ai_gateway()
    health = await gateway.health_check()
    
    # Provider alerts
    for provider, status in health.get("providers", {}).items():
        if status.get("circuit_breaker") == "OPEN":
            alerts.append({
                "type": "provider_down",
                "severity": "warning",
                "message": f"AI provider '{provider}' is temporarily unavailable",
                "data": {"provider": provider, "failures": status.get("failures")}
            })
    
    return {
        "has_alerts": len(alerts) > 0,
        "alerts": alerts
    }
