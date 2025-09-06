"""
WebSocket endpoints для табло очереди
Основа: passport.md стр. 2571-3324
"""
import json
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles, get_current_user
from app.models.user import User
from app.services.display_websocket import get_display_manager, DisplayWebSocketManager
from app.models.online_queue import QueueEntry
from app.crud import display_config as crud_display

router = APIRouter()

# ===================== WEBSOCKET ПОДКЛЮЧЕНИЯ =====================

@router.websocket("/ws/board/{board_id}")
async def websocket_display_board(
    websocket: WebSocket,
    board_id: str,
    token: Optional[str] = None
):
    """
    WebSocket подключение для табло очереди
    """
    manager = get_display_manager()
    
    try:
        # TODO: Добавить аутентификацию по токену если нужно
        
        await manager.connect(websocket, board_id)
        
        try:
            while True:
                # Ожидаем сообщения от клиента (ping/pong, команды управления)
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Обрабатываем команды от табло
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    }))
                elif message.get("type") == "request_update":
                    # Запрос обновления состояния
                    await manager._send_current_state(websocket, board_id)
                
        except WebSocketDisconnect:
            pass
            
    except Exception as e:
        print(f"Ошибка WebSocket: {e}")
    finally:
        await manager.disconnect(websocket, board_id)


# ===================== УПРАВЛЕНИЕ ТАБЛО =====================

@router.post("/call-patient")
async def call_patient_to_board(
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar"))
):
    """
    Вызов пациента с трансляцией на табло
    """
    try:
        entry_id = request.get("entry_id")
        board_ids = request.get("board_ids", [])  # Конкретные табло или все
        
        if not entry_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не указан ID записи в очереди"
            )

        # Получаем запись в очереди
        queue_entry = db.query(QueueEntry).filter(QueueEntry.id == entry_id).first()
        
        if not queue_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись в очереди не найдена"
            )

        # Обновляем статус
        queue_entry.status = "called"
        queue_entry.called_at = datetime.utcnow()
        db.commit()

        # Получаем данные врача
        doctor = queue_entry.queue.specialist
        doctor_name = doctor.user.full_name if doctor and doctor.user else "Врач"
        cabinet = doctor.cabinet if doctor else None

        # Транслируем на табло
        manager = get_display_manager()
        await manager.broadcast_patient_call(
            queue_entry=queue_entry,
            doctor_name=doctor_name,
            cabinet=cabinet,
            board_ids=board_ids if board_ids else None
        )

        return {
            "success": True,
            "message": f"Пациент #{queue_entry.number} вызван на табло",
            "call_data": {
                "number": queue_entry.number,
                "patient_name": queue_entry.patient_name,
                "doctor": doctor_name,
                "cabinet": cabinet,
                "called_at": queue_entry.called_at.isoformat()
            },
            "boards_notified": len(board_ids) if board_ids else len(manager.connections)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка вызова пациента на табло: {str(e)}"
        )


@router.post("/announcement")
async def send_announcement_to_board(
    request: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Отправка объявления на табло
    """
    try:
        text = request.get("text")
        announcement_type = request.get("type", "info")  # info, warning, emergency
        duration = request.get("duration", 60)
        board_ids = request.get("board_ids", [])
        
        if not text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Текст объявления не указан"
            )

        # Транслируем объявление
        manager = get_display_manager()
        await manager.broadcast_announcement(
            announcement_text=text,
            announcement_type=announcement_type,
            duration=duration,
            board_ids=board_ids if board_ids else None
        )

        return {
            "success": True,
            "message": "Объявление отправлено на табло",
            "announcement": {
                "text": text,
                "type": announcement_type,
                "duration": duration
            },
            "boards_notified": len(board_ids) if board_ids else len(manager.connections)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки объявления: {str(e)}"
        )


@router.get("/boards/status")
def get_boards_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Получить статус всех табло
    """
    try:
        manager = get_display_manager()
        boards_status = manager.get_all_boards_status()
        
        # Получаем конфигурации табло из БД
        boards_config = crud_display.get_display_boards(db, active_only=True)
        
        # Объединяем данные
        result = []
        for board in boards_config:
            ws_status = boards_status.get(board.name, {
                "connections": 0,
                "last_update": None,
                "active": False
            })
            
            result.append({
                "id": board.id,
                "name": board.name,
                "display_name": board.display_name,
                "location": board.location,
                "theme": board.theme,
                "websocket_connections": ws_status["connections"],
                "last_update": ws_status["last_update"],
                "online": ws_status["active"],
                "config": {
                    "show_patient_names": board.show_patient_names,
                    "queue_display_count": board.queue_display_count,
                    "sound_enabled": board.sound_enabled,
                    "voice_announcements": board.voice_announcements
                }
            })

        return {
            "boards": result,
            "total_boards": len(result),
            "total_connections": sum(board["websocket_connections"] for board in result)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статуса табло: {str(e)}"
        )


# ===================== БЫСТРЫЕ ДЕЙСТВИЯ =====================

@router.post("/quick/call-next")
async def quick_call_next_patient(
    specialty: str,
    board_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar"))
):
    """
    Быстрый вызов следующего пациента
    """
    try:
        from datetime import date
        from app.models.clinic import Doctor
        
        # Находим врача по специальности
        doctor = db.query(Doctor).filter(
            Doctor.specialty == specialty,
            Doctor.active == True
        ).first()
        
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Врач специальности {specialty} не найден"
            )

        # Находим дневную очередь
        from app.models.online_queue import DailyQueue
        today = date.today()
        daily_queue = db.query(DailyQueue).filter(
            DailyQueue.day == today,
            DailyQueue.specialist_id == doctor.id
        ).first()
        
        if not daily_queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Очередь на сегодня не найдена"
            )

        # Находим следующего пациента в статусе "waiting"
        next_entry = db.query(QueueEntry).filter(
            QueueEntry.queue_id == daily_queue.id,
            QueueEntry.status == "waiting"
        ).order_by(QueueEntry.number).first()
        
        if not next_entry:
            return {
                "success": False,
                "message": "Нет пациентов в очереди",
                "queue_empty": True
            }

        # Вызываем пациента
        call_request = {
            "entry_id": next_entry.id,
            "board_ids": [board_id] if board_id else []
        }
        
        return await call_patient_to_board(call_request, db, current_user)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка быстрого вызова: {str(e)}"
        )

