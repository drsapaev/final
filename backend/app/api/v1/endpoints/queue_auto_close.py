"""
API endpoints для автозакрытия очередей
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.services.queue_auto_close import QueueAutoCloseService

router = APIRouter()


@router.post("/check-and-close")
async def check_and_close_expired_queues(
    current_user: User = Depends(require_roles(["admin", "registrar"])),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Проверяет и закрывает очереди с истекшим временем записи
    """
    try:
        service = QueueAutoCloseService(db)
        result = service.check_and_close_expired_queues()

        return {
            "success": True,
            "message": f"Проверка завершена. Закрыто очередей: {result['closed_count']}",
            "data": result,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка при проверке очередей: {str(e)}"
        )


@router.get("/pending-close")
async def get_queues_pending_close(
    current_user: User = Depends(require_roles(["admin", "registrar"])),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    Возвращает список очередей, которые скоро будут закрыты
    """
    try:
        service = QueueAutoCloseService(db)
        pending_queues = service.get_queues_pending_close()

        return pending_queues

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка при получении очередей: {str(e)}"
        )


@router.post("/force-close/{queue_id}")
async def force_close_queue(
    queue_id: int,
    current_user: User = Depends(require_roles(["admin", "registrar"])),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Принудительно закрывает очередь
    """
    try:
        service = QueueAutoCloseService(db)
        result = service.force_close_queue(queue_id, current_user.id)

        return {"success": True, "message": "Очередь успешно закрыта", "data": result}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка при закрытии очереди: {str(e)}"
        )


@router.get("/auto-close-status")
async def get_auto_close_status(
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Возвращает статус системы автозакрытия
    """
    try:
        service = QueueAutoCloseService(db)
        pending_queues = service.get_queues_pending_close()

        return {
            "auto_close_enabled": True,
            "pending_queues_count": len(pending_queues),
            "pending_queues": pending_queues,
            "last_check": "Проверка выполняется по запросу",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка при получении статуса: {str(e)}"
        )
