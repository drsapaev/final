"""
Упрощенный API endpoint для тестирования очереди
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

class QueueJoinRequest(BaseModel):
    token: str
    patient_name: str
    phone: Optional[str] = None
    telegram_id: Optional[str] = None

class QueueJoinResponse(BaseModel):
    success: bool
    message: str
    number: Optional[int] = None

@router.post("/join-simple", response_model=QueueJoinResponse)
def join_queue_simple(request: QueueJoinRequest):
    """
    Упрощенное вступление в очередь (без БД)
    """
    # Простая валидация
    if not request.token:
        return QueueJoinResponse(
            success=False,
            message="Токен обязателен"
        )
    
    if not request.patient_name:
        return QueueJoinResponse(
            success=False,
            message="ФИО обязательно"
        )
    
    # Имитируем успешную запись
    return QueueJoinResponse(
        success=True,
        message=f"Вы записаны в очередь, {request.patient_name}!",
        number=42
    )

@router.get("/test")
def test_queue():
    """Тестовый endpoint"""
    return {
        "status": "ok",
        "message": "Queue API работает!",
        "endpoints": [
            "POST /join-simple - упрощенная запись в очередь",
            "GET /test - этот тест"
        ]
    }
