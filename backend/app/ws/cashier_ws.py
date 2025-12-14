"""
WebSocket endpoint для кассира
Обеспечивает real-time обновления при изменении платежей/визитов
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Set, Dict, Any
import json
import logging

from app.api import deps

logger = logging.getLogger(__name__)

router = APIRouter()


class CashierWSManager:
    """Менеджер WebSocket соединений для кассиров"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.connections: Set[WebSocket] = set()
        return cls._instance
    
    async def connect(self, websocket: WebSocket) -> None:
        """Подключение нового WebSocket"""
        await websocket.accept()
        self.connections.add(websocket)
        logger.info(f"Cashier WebSocket connected. Total connections: {len(self.connections)}")
    
    def disconnect(self, websocket: WebSocket) -> None:
        """Отключение WebSocket"""
        self.connections.discard(websocket)
        logger.info(f"Cashier WebSocket disconnected. Total connections: {len(self.connections)}")
    
    async def broadcast(self, message: Dict[str, Any]) -> None:
        """Рассылка сообщения всем подключенным кассирам"""
        disconnected = set()
        
        for connection in self.connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.add(connection)
        
        # Удаляем отключенные соединения
        for ws in disconnected:
            self.connections.discard(ws)
        
        if disconnected:
            logger.info(f"Removed {len(disconnected)} disconnected WebSockets")


# Глобальный экземпляр менеджера
cashier_ws_manager = CashierWSManager()


def get_cashier_ws_manager() -> CashierWSManager:
    """Получить экземпляр менеджера WebSocket"""
    return cashier_ws_manager


@router.websocket("/ws/cashier")
async def cashier_websocket(
    websocket: WebSocket,
):
    """
    WebSocket endpoint для кассиров.
    Получает real-time уведомления о:
    - Новых визитах
    - Новых платежах
    - Изменениях статусов
    """
    await cashier_ws_manager.connect(websocket)
    
    try:
        # Отправляем приветственное сообщение
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to cashier WebSocket"
        })
        
        # Ждем сообщений от клиента (для heartbeat/ping-pong)
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Обрабатываем ping
                if message.get("type") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": message.get("timestamp")
                    })
                    
            except json.JSONDecodeError:
                logger.warning("Received invalid JSON from WebSocket")
                
    except WebSocketDisconnect:
        cashier_ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        cashier_ws_manager.disconnect(websocket)


async def broadcast_cashier_update(event_type: str, data: Dict[str, Any]) -> None:
    """
    Вспомогательная функция для рассылки обновлений кассирам.
    Используется из других модулей.
    
    event_type: "payment_created", "payment_refunded", "visit_created", "visit_updated"
    """
    message = {
        "type": event_type,
        "data": data
    }
    await cashier_ws_manager.broadcast(message)
