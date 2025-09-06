"""
WebSocket сервис для табло очереди
Основа: passport.md стр. 2571-3324, detail.md стр. 1567-1789
"""
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Set, Optional, List
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.models.display_config import DisplayBoard
from app.models.online_queue import QueueEntry, DailyQueue
from app.crud import display_config as crud_display
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

class DisplayWebSocketManager:
    """Менеджер WebSocket соединений для табло"""
    
    def __init__(self):
        # Активные соединения по board_id
        self.connections: Dict[str, Set[WebSocket]] = {}
        # Последнее состояние каждого табло
        self.board_states: Dict[str, Dict[str, Any]] = {}
        
    async def connect(self, websocket: WebSocket, board_id: str) -> None:
        """Подключение нового WebSocket"""
        try:
            await websocket.accept()
            
            if board_id not in self.connections:
                self.connections[board_id] = set()
            
            self.connections[board_id].add(websocket)
            
            logger.info(f"WebSocket подключен к табло {board_id}. Всего соединений: {len(self.connections[board_id])}")
            
            # Отправляем текущее состояние табло
            await self._send_current_state(websocket, board_id)
            
        except Exception as e:
            logger.error(f"Ошибка подключения WebSocket: {e}")

    async def disconnect(self, websocket: WebSocket, board_id: str) -> None:
        """Отключение WebSocket"""
        try:
            if board_id in self.connections:
                self.connections[board_id].discard(websocket)
                
                if len(self.connections[board_id]) == 0:
                    del self.connections[board_id]
                
            logger.info(f"WebSocket отключен от табло {board_id}")
            
        except Exception as e:
            logger.error(f"Ошибка отключения WebSocket: {e}")

    async def broadcast_to_board(self, board_id: str, message: Dict[str, Any]) -> None:
        """Отправка сообщения всем подключенным к табло"""
        try:
            if board_id not in self.connections:
                return

            # Обновляем состояние табло
            self.board_states[board_id] = {
                **self.board_states.get(board_id, {}),
                **message,
                "last_update": datetime.utcnow().isoformat()
            }

            # Отправляем всем подключенным
            disconnected = set()
            for websocket in self.connections[board_id].copy():
                try:
                    await websocket.send_text(json.dumps(message, ensure_ascii=False))
                except WebSocketDisconnect:
                    disconnected.add(websocket)
                except Exception as e:
                    logger.error(f"Ошибка отправки WebSocket сообщения: {e}")
                    disconnected.add(websocket)

            # Удаляем отключенные соединения
            for ws in disconnected:
                self.connections[board_id].discard(ws)

            if disconnected:
                logger.info(f"Удалено {len(disconnected)} отключенных соединений")

        except Exception as e:
            logger.error(f"Ошибка broadcast сообщения: {e}")

    async def broadcast_patient_call(
        self, 
        queue_entry: QueueEntry,
        doctor_name: str,
        cabinet: str = None,
        board_ids: List[str] = None
    ) -> None:
        """Трансляция вызова пациента на табло"""
        try:
            call_message = {
                "type": "patient_call",
                "data": {
                    "queue_number": queue_entry.number,
                    "patient_name": self._format_patient_name(queue_entry.patient_name),
                    "doctor_name": doctor_name,
                    "cabinet": cabinet or "Каб. не указан",
                    "specialty": queue_entry.queue.specialist.specialty if queue_entry.queue.specialist else "Врач",
                    "called_at": queue_entry.called_at.isoformat() if queue_entry.called_at else datetime.utcnow().isoformat(),
                    "urgency": "normal"  # normal, urgent, emergency
                },
                "display_duration": 30,  # Секунды показа
                "sound_enabled": True,
                "voice_text": f"Пациент номер {queue_entry.number}, пройдите в {cabinet or 'кабинет врача'}"
            }

            # Если не указаны конкретные табло, отправляем на все активные
            if not board_ids:
                board_ids = list(self.connections.keys())

            # Отправляем на указанные табло
            for board_id in board_ids:
                await self.broadcast_to_board(board_id, call_message)
                
            logger.info(f"Вызов пациента #{queue_entry.number} отправлен на {len(board_ids)} табло")

        except Exception as e:
            logger.error(f"Ошибка трансляции вызова пациента: {e}")

    async def broadcast_queue_update(
        self,
        daily_queue: DailyQueue,
        board_ids: List[str] = None
    ) -> None:
        """Трансляция обновления очереди"""
        try:
            db = SessionLocal()
            
            # Получаем текущую очередь
            queue_entries = db.query(QueueEntry).filter(
                QueueEntry.queue_id == daily_queue.id
            ).order_by(QueueEntry.number).all()

            # Формируем данные очереди
            queue_data = []
            for entry in queue_entries:
                queue_data.append({
                    "number": entry.number,
                    "patient_name": self._format_patient_name(entry.patient_name),
                    "status": entry.status,
                    "source": entry.source,
                    "created_at": entry.created_at.isoformat(),
                    "called_at": entry.called_at.isoformat() if entry.called_at else None
                })

            update_message = {
                "type": "queue_update",
                "data": {
                    "doctor_name": daily_queue.specialist.user.full_name if daily_queue.specialist and daily_queue.specialist.user else "Врач",
                    "specialty": daily_queue.specialist.specialty if daily_queue.specialist else "Специалист",
                    "cabinet": daily_queue.specialist.cabinet if daily_queue.specialist else None,
                    "queue_date": daily_queue.day.isoformat(),
                    "opened_at": daily_queue.opened_at.isoformat() if daily_queue.opened_at else None,
                    "queue_entries": queue_data,
                    "stats": {
                        "total": len(queue_entries),
                        "waiting": len([e for e in queue_entries if e.status == "waiting"]),
                        "called": len([e for e in queue_entries if e.status == "called"]),
                        "served": len([e for e in queue_entries if e.status == "served"])
                    }
                }
            }

            # Отправляем на табло
            if not board_ids:
                board_ids = list(self.connections.keys())

            for board_id in board_ids:
                await self.broadcast_to_board(board_id, update_message)

            db.close()
            
        except Exception as e:
            logger.error(f"Ошибка трансляции обновления очереди: {e}")

    async def broadcast_announcement(
        self,
        announcement_text: str,
        announcement_type: str = "info",
        duration: int = 60,
        board_ids: List[str] = None
    ) -> None:
        """Трансляция объявления"""
        try:
            announcement_message = {
                "type": "announcement",
                "data": {
                    "text": announcement_text,
                    "announcement_type": announcement_type,  # info, warning, emergency
                    "created_at": datetime.utcnow().isoformat()
                },
                "display_duration": duration,
                "sound_enabled": announcement_type in ["warning", "emergency"],
                "voice_text": announcement_text if announcement_type == "emergency" else None
            }

            if not board_ids:
                board_ids = list(self.connections.keys())

            for board_id in board_ids:
                await self.broadcast_to_board(board_id, announcement_message)
                
            logger.info(f"Объявление отправлено на {len(board_ids)} табло")

        except Exception as e:
            logger.error(f"Ошибка трансляции объявления: {e}")

    async def _send_current_state(self, websocket: WebSocket, board_id: str) -> None:
        """Отправка текущего состояния табло новому подключению"""
        try:
            if board_id in self.board_states:
                current_state = {
                    "type": "initial_state",
                    "data": self.board_states[board_id]
                }
                await websocket.send_text(json.dumps(current_state, ensure_ascii=False))
            else:
                # Отправляем пустое состояние
                empty_state = {
                    "type": "initial_state",
                    "data": {
                        "queue_entries": [],
                        "current_call": None,
                        "announcements": [],
                        "last_update": datetime.utcnow().isoformat()
                    }
                }
                await websocket.send_text(json.dumps(empty_state, ensure_ascii=False))
                
        except Exception as e:
            logger.error(f"Ошибка отправки текущего состояния: {e}")

    def _format_patient_name(self, full_name: str, format_type: str = "initials") -> str:
        """Форматирование имени пациента для табло"""
        if not full_name:
            return "Пациент"
        
        try:
            if format_type == "full":
                return full_name
            elif format_type == "initials":
                parts = full_name.split()
                if len(parts) >= 2:
                    return f"{parts[0]} {parts[1][0]}."
                return full_name
            elif format_type == "none":
                return "Пациент"
            else:
                return full_name
                
        except Exception:
            return "Пациент"

    def get_board_connections_count(self, board_id: str) -> int:
        """Получить количество подключений к табло"""
        return len(self.connections.get(board_id, set()))

    def get_all_boards_status(self) -> Dict[str, Dict[str, Any]]:
        """Получить статус всех табло"""
        status = {}
        for board_id, connections in self.connections.items():
            status[board_id] = {
                "connections": len(connections),
                "last_update": self.board_states.get(board_id, {}).get("last_update"),
                "active": len(connections) > 0
            }
        return status

# Глобальный менеджер WebSocket
display_manager = DisplayWebSocketManager()

def get_display_manager() -> DisplayWebSocketManager:
    """Получить экземпляр менеджера табло"""
    return display_manager

