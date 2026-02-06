
import logging
from typing import Dict, List, Optional
from fastapi import WebSocket, WebSocketDisconnect
import json

logger = logging.getLogger(__name__)

class NotificationWebSocketManager:
    """
    Manager for handling user-specific WebSocket connections.
    Allows sending notifications directly to connected users.
    """
    def __init__(self):
        # Map user_id to list of active WebSockets
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info(f"User {user_id} connected via WebSocket. Active connections: {len(self.active_connections[user_id])}")

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"User {user_id} disconnected from WebSocket.")

    async def send_personal_message(self, message: str, user_id: int):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Error sending message to user {user_id}: {e}")

    async def send_json(self, data: dict, user_id: int):
        if user_id in self.active_connections:
            # Iterate over a copy in case disconnect modifies the list
            for connection in self.active_connections[user_id][:]:
                try:
                    await connection.send_json(data)
                except Exception as e:
                    logger.error(f"Error sending JSON to user {user_id}: {e}")
                    # Optionally handle disconnect here if needed, 
                    # but usually WebSocketDisconnect handles cleanup in the endpoint loop

    async def broadcast(self, message: str):
        for user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Error broadcasting: {e}")

notification_ws_manager = NotificationWebSocketManager()

def get_notification_ws_manager() -> NotificationWebSocketManager:
    return notification_ws_manager
