"""
WebSocket для системы сообщений в реальном времени
"""

from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
import json
import logging

from app.api.deps import get_db
from jose import jwt, JWTError
from app.core.config import get_settings
from app.models.user import User

settings = get_settings()
logger = logging.getLogger(__name__)


class ChatConnectionManager:
    """Менеджер WebSocket соединений для чата"""
    
    def __init__(self):
        # user_id -> WebSocket
        self.active_connections: Dict[int, WebSocket] = {}
    
    async def connect(self, user_id: int, websocket: WebSocket) -> bool:
        """Подключить пользователя"""
        try:
            # Закрыть старое соединение если есть
            if user_id in self.active_connections:
                try:
                    await self.active_connections[user_id].close()
                except Exception:
                    pass
            
            await websocket.accept()
            self.active_connections[user_id] = websocket
            logger.info(f"Chat WebSocket connected: user_id={user_id}")
            return True
        except Exception as e:
            logger.error(f"Chat WebSocket connect error: {e}")
            return False
    
    def disconnect(self, user_id: int):
        """Отключить пользователя"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"Chat WebSocket disconnected: user_id={user_id}")
    
    async def send_to_user(self, user_id: int, data: dict) -> bool:
        """Отправить сообщение конкретному пользователю"""
        if user_id in self.active_connections:
            try:
                # Используем jsonable_encoder для сериализации datetime и других типов
                await self.active_connections[user_id].send_json(jsonable_encoder(data))
                return True
            except Exception as e:
                logger.error(f"Chat WebSocket send error: {e}")
                self.disconnect(user_id)
        return False
    
    def is_online(self, user_id: int) -> bool:
        """Проверить, онлайн ли пользователь"""
        return user_id in self.active_connections
    
    def get_online_users(self) -> list:
        """Получить список онлайн пользователей"""
        return list(self.active_connections.keys())
    
    async def broadcast_typing(self, sender_id: int, recipient_id: int, is_typing: bool):
        """Отправить статус набора текста"""
        await self.send_to_user(recipient_id, {
            "type": "typing",
            "sender_id": sender_id,
            "is_typing": is_typing
        })
    
    async def notify_new_message(self, recipient_id: int, message_data: dict):
        """Уведомить о новом сообщении"""
        is_online = recipient_id in self.active_connections
        logger.info(f"WS: Notifying user {recipient_id} about new message. Online: {is_online}")
        if is_online:
            await self.send_to_user(recipient_id, {
                "type": "new_message",
                "message": message_data
            })
        else:
            logger.info(f"WS: User {recipient_id} is offline, skipping notification")
    
    async def notify_message_read(self, sender_id: int, message_id: int):
        """Уведомить о прочтении сообщения"""
        await self.send_to_user(sender_id, {
            "type": "message_read",
            "message_id": message_id
        })


# Глобальный менеджер соединений
chat_manager = ChatConnectionManager()


async def authenticate_websocket(
    websocket: WebSocket,
    token: str,
    db: Session
) -> Optional[User]:
    """Аутентификация WebSocket соединения через токен"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[getattr(settings, "ALGORITHM", "HS256")]
        )
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        # Поддержка и строкового и числового ID
        if isinstance(user_id, str) and user_id.isdigit():
            user_id = int(user_id)
        elif isinstance(user_id, str):
            # Если это username, ищем по username
            user = db.query(User).filter(User.username == user_id).first()
            return user
        
        user = db.query(User).filter(User.id == int(user_id)).first()
        return user
    except JWTError as e:
        logger.error(f"Chat WebSocket JWT error: {e}")
        return None
    except Exception as e:
        logger.error(f"Chat WebSocket auth error: {e}")
        return None


from app.db.session import SessionLocal

async def chat_websocket_handler(
    websocket: WebSocket,
    token: str = Query(...)
):
    """
    WebSocket endpoint для чата.
    
    Подключение: ws://localhost:8000/ws/chat?token=<JWT_TOKEN>
    """
    
    logger.info(f"🔌 Chat WebSocket connection attempt. Token provided: {bool(token)}")
    
    # Аутентификация
    db = SessionLocal()
    try:
        user = await authenticate_websocket(websocket, token, db)
        if user:
            logger.info(f"✅ Chat WebSocket authenticated: user_id={user.id}, username={user.username}")
        else:
            logger.warning(f"❌ Chat WebSocket authentication failed")
    finally:
        db.close()

    if not user:
        try:
            await websocket.accept()
        except Exception as e:
            logger.error(f"Failed to accept websocket: {e}")
        await websocket.close(code=4001, reason="Unauthorized")
        return
    
    # Подключение
    connected = await chat_manager.connect(user.id, websocket)
    if not connected:
        return
    
    try:
        while True:
            # Получаем сообщение от клиента
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                msg_type = message.get("type")
                
                if msg_type == "typing":
                    recipient_id = message.get("recipient_id")
                    is_typing = message.get("is_typing", False)
                    if recipient_id:
                        await chat_manager.broadcast_typing(
                            sender_id=user.id,
                            recipient_id=recipient_id,
                            is_typing=is_typing
                        )
                
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                
                elif msg_type == "get_online_status":
                    user_ids = message.get("user_ids", [])
                    online_status = {
                        uid: chat_manager.is_online(uid) 
                        for uid in user_ids
                    }
                    await websocket.send_json({
                        "type": "online_status",
                        "users": online_status
                    })
                
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}"
                    })
                    
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON"
                })
                
    except WebSocketDisconnect:
        chat_manager.disconnect(user.id)
    except Exception as e:
        logger.error(f"Chat WebSocket error: {e}")
        chat_manager.disconnect(user.id)

