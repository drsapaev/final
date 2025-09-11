from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api.deps import get_db, require_roles

router = APIRouter()

@router.get("/history/stats")
async def get_notification_stats_simple(
    days: int = Query(7, ge=1, le=365),
    current_user=Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Упрощенная статистика уведомлений"""
    try:
        # Простая статистика без сложных запросов
        return {
            "total_notifications": 0,
            "sent_today": 0,
            "failed_today": 0,
            "success_rate": 100.0,
            "recent_activity": [],
            "period_days": days
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {str(e)}")

@router.get("/history")
async def get_notification_history_simple(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user=Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Упрощенная история уведомлений"""
    try:
        # Простая история без сложных запросов
        return {
            "notifications": [],
            "total": 0,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения истории: {str(e)}")

@router.get("/templates")
async def get_notification_templates_simple(
    current_user=Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Упрощенные шаблоны уведомлений"""
    try:
        # Простые шаблоны без сложных запросов
        return {
            "templates": [
                {
                    "id": 1,
                    "name": "Напоминание о записи",
                    "subject": "Напоминание о записи к врачу",
                    "content": "У вас запись к врачу завтра в {time}",
                    "type": "appointment_reminder"
                },
                {
                    "id": 2,
                    "name": "Подтверждение записи",
                    "subject": "Запись подтверждена",
                    "content": "Ваша запись к врачу {doctor} подтверждена",
                    "type": "appointment_confirmation"
                }
            ],
            "total": 2
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения шаблонов: {str(e)}")
