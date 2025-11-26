"""
Legacy API endpoints для совместимости с документацией
Алиасы для /api/online-queue/* путей
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, date

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.qr_queue_service import QRQueueService

router = APIRouter()

@router.post("/qrcode")
async def generate_qr_code_legacy(
    day: str = Query(..., description="Дата в формате YYYY-MM-DD"),
    specialist_id: int = Query(..., description="ID специалиста"),
    department: Optional[str] = Query("general", description="Отделение"),
    expires_hours: int = Query(24, description="Срок действия в часах"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Legacy endpoint для генерации QR кода
    Совместимость с документацией: POST /api/online-queue/qrcode?day=YYYY-MM-DD&specialist_id=...
    """
    
    # Валидация даты
    try:
        target_date = datetime.strptime(day, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты. Используйте YYYY-MM-DD")
    
    # Проверяем права доступа
    if not current_user.role in ["admin", "registrar"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав для генерации QR токенов")
    
    try:
        service = QRQueueService(db)
        
        # Генерируем QR токен
        result = service.generate_qr_token(
            specialist_id=specialist_id,
            department=department,
            expires_hours=expires_hours,
            generated_by_user_id=current_user.id
        )
        
        # Возвращаем в формате, совместимом с документацией
        return {
            "token": result["token"],
            "day": day,
            "specialist_id": specialist_id,
            "department": result["department"],
            "specialist_name": result["specialist_name"],
            "expires_at": result["expires_at"],
            "qr_url": result["qr_url"],
            "qr_code_base64": result["qr_code_base64"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status")
async def get_queue_status_legacy(
    day: str = Query(..., description="Дата в формате YYYY-MM-DD"),
    specialist_id: int = Query(..., description="ID специалиста"),
    db: Session = Depends(get_db)
):
    """
    Legacy endpoint для получения статуса очереди
    """
    
    # Валидация даты
    try:
        target_date = datetime.strptime(day, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты. Используйте YYYY-MM-DD")
    
    try:
        service = QRQueueService(db)
        
        # Получаем статус очереди
        status = service.get_queue_status(specialist_id, target_date)
        
        return {
            "day": day,
            "specialist_id": specialist_id,
            "active": status["active"],
            "queue_length": status["queue_length"],
            "current_number": status["current_number"],
            "entries": status["entries"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/join")
async def join_queue_legacy(
    token: str,
    phone: Optional[str] = None,
    telegram_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Legacy endpoint для присоединения к очереди
    Совместимость с документацией: PWA/Telegram отправляет { token, phone?, telegram_id? }
    """
    
    try:
        service = QRQueueService(db)
        
        # Начинаем сессию присоединения
        session_data = service.start_join_session(token)
        
        # Если есть данные пациента, сразу завершаем присоединение
        if phone or telegram_id:
            patient_name = f"Пациент {phone or telegram_id}"
            
            result = service.complete_join_session(
                session_token=session_data["session_token"],
                patient_name=patient_name,
                phone=phone,
                telegram_id=telegram_id
            )
            
            return {
                "number": result["queue_number"],
                "duplicate": result.get("duplicate", False),
                "message": "Вы записаны в очередь"
            }
        else:
            # Возвращаем токен сессии для дальнейшего заполнения
            return {
                "session_token": session_data["session_token"],
                "expires_at": session_data["expires_at"],
                "message": "Заполните данные для записи"
            }
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
