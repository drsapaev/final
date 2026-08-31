import asyncio
import logging

from fastapi import WebSocket

from app.api.v1.endpoints.ws_token import accept_echoing_subprotocol

logger = logging.getLogger(__name__)


class NotificationWebSocketManager:
    """
    Manager for handling user-specific WebSocket connections.
    Allows sending notifications directly to connected users.

    Cross-loop safety (codex follow-up on #2874): a WebSocket is bound to the
    event loop that accepted it (Uvicorn's application loop). Background
    schedulers now run their jobs on worker-thread loops, so a delivery
    attempted from a foreign loop is marshalled back to the connection's home
    loop instead of raising "attached to a different loop" and dropping the
    notification.
    """

    def __init__(self):
        # Map user_id to list of active WebSockets
        self.active_connections: dict[int, list[WebSocket]] = {}
        # Home loop per accepted connection (keyed by id(websocket); the
        # socket object is referenced by active_connections, so id() is
        # stable for the connection's lifetime).
        self._connection_loops: dict[int, asyncio.AbstractEventLoop] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await accept_echoing_subprotocol(websocket)
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        self._connection_loops[id(websocket)] = asyncio.get_running_loop()
        logger.info(
            f"User {user_id} connected via WebSocket. Active connections: {len(self.active_connections[user_id])}"
        )

    def disconnect(self, websocket: WebSocket, user_id: int):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        self._connection_loops.pop(id(websocket), None)
        logger.info(f"User {user_id} disconnected from WebSocket.")

    def _schedule_if_foreign_loop(self, connection: WebSocket, coro) -> bool:
        """Run ``coro`` on the connection's home loop when the caller is on a
        different loop (worker thread). Fire-and-forget: delivery errors are
        logged. Returns True when the send was marshalled away."""
        home_loop = self._connection_loops.get(id(connection))
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        if home_loop is None or current_loop is home_loop:
            return False

        fut = asyncio.run_coroutine_threadsafe(coro, home_loop)

        def _log_error(done) -> None:
            exc = done.exception()
            if exc is not None:
                logger.error(f"Cross-loop WebSocket delivery failed: {exc}")

        fut.add_done_callback(_log_error)
        return True

    async def send_personal_message(self, message: str, user_id: int):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    if self._schedule_if_foreign_loop(
                        connection, connection.send_text(message)
                    ):
                        continue
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Error sending message to user {user_id}: {e}")

    async def send_json(self, data: dict, user_id: int):
        if user_id in self.active_connections:
            # Iterate over a copy in case disconnect modifies the list
            for connection in self.active_connections[user_id][:]:
                try:
                    if self._schedule_if_foreign_loop(
                        connection, connection.send_json(data)
                    ):
                        continue
                    await connection.send_json(data)
                except Exception as e:
                    logger.error(f"Error sending JSON to user {user_id}: {e}")
                    # Optionally handle disconnect here if needed,
                    # but usually WebSocketDisconnect handles cleanup in the endpoint loop

    async def broadcast(self, message: str):
        for user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    if self._schedule_if_foreign_loop(
                        connection, connection.send_text(message)
                    ):
                        continue
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Error broadcasting: {e}")


notification_ws_manager = NotificationWebSocketManager()


def get_notification_ws_manager() -> NotificationWebSocketManager:
    return notification_ws_manager
