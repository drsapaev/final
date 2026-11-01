import asyncio
import logging
from collections.abc import Awaitable, Callable

from fastapi import WebSocket

from app.api.v1.endpoints.ws_token import accept_echoing_subprotocol
from app.services.ws_redis_pubsub import RedisPubSubBridge

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

    def __init__(self, pubsub: RedisPubSubBridge | None = None):
        # Map user_id to list of active WebSockets
        self.active_connections: dict[int, list[WebSocket]] = {}
        # Home loop per accepted connection (keyed by id(websocket); the
        # socket object is referenced by active_connections, so id() is
        # stable for the connection's lifetime).
        self._connection_loops: dict[int, asyncio.AbstractEventLoop] = {}
        # Local connection managers are process-scoped. Redis relays a
        # user-scoped event from outbox workers to the API process holding the
        # authenticated socket.
        self._pubsub = (
            pubsub if pubsub is not None else RedisPubSubBridge("notification_ws")
        )
        self._pubsub_handlers: dict[int, Callable[[dict], Awaitable[None]]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        await accept_echoing_subprotocol(websocket)
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        self._connection_loops[id(websocket)] = asyncio.get_running_loop()
        await self._ensure_user_subscription(user_id)
        logger.info(
            f"User {user_id} connected via WebSocket. Active connections: {len(self.active_connections[user_id])}"
        )

    def disconnect(self, websocket: WebSocket, user_id: int):
        home_loop = self._connection_loops.get(id(websocket))
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                handler = self._pubsub_handlers.pop(user_id, None)
                if handler is not None and home_loop is not None:
                    self._schedule_unsubscribe(home_loop, user_id, handler)
        self._connection_loops.pop(id(websocket), None)
        logger.info(f"User {user_id} disconnected from WebSocket.")

    @staticmethod
    def _user_channel(user_id: int) -> str:
        return f"user:{user_id}"

    async def _ensure_user_subscription(self, user_id: int) -> None:
        handler = self._pubsub_handlers.get(user_id)
        if handler is None:

            async def _receive(payload: dict, _user_id: int = user_id) -> None:
                # Do not republish messages received from Redis.
                await self._send_json_local(payload, _user_id)

            handler = _receive
            self._pubsub_handlers[user_id] = handler

        try:
            await self._pubsub.subscribe(self._user_channel(user_id), handler)
        except Exception as exc:
            logger.warning(
                "Notification WebSocket Redis subscription unavailable: %s",
                type(exc).__name__,
            )

    def _schedule_unsubscribe(
        self,
        loop: asyncio.AbstractEventLoop,
        user_id: int,
        handler: Callable[[dict], Awaitable[None]],
    ) -> None:
        if loop.is_closed():
            return

        async def _unsubscribe() -> None:
            try:
                await self._pubsub.unsubscribe(self._user_channel(user_id), handler)
            except Exception as exc:
                logger.warning(
                    "Notification WebSocket Redis unsubscribe failed: %s",
                    type(exc).__name__,
                )

        def _start() -> None:
            if not loop.is_closed():
                loop.create_task(_unsubscribe())

        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if current_loop is loop:
            _start()
        elif loop.is_running():
            loop.call_soon_threadsafe(_start)

    async def _send_json_local(self, data: dict, user_id: int) -> None:
        # Iterate over a copy in case disconnect modifies the list.
        for connection in self.active_connections.get(user_id, [])[:]:
            try:
                send_coro = connection.send_json(data)
                if self._schedule_if_foreign_loop(connection, send_coro):
                    continue
                await send_coro
            except Exception as exc:
                logger.error(
                    "Error sending notification JSON to user %s: %s",
                    user_id,
                    type(exc).__name__,
                )

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
                    send_coro = connection.send_text(message)
                    if self._schedule_if_foreign_loop(connection, send_coro):
                        continue
                    await send_coro
                except Exception as e:
                    logger.error(f"Error sending message to user {user_id}: {e}")

    async def send_json(self, data: dict, user_id: int):
        await self._send_json_local(data, user_id)
        try:
            await self._pubsub.publish_ephemeral(self._user_channel(user_id), data)
        except Exception as exc:
            # Notification persistence is owned by the caller/outbox. Realtime
            # delivery is best-effort and must never change that result.
            logger.warning(
                "Notification WebSocket Redis publish failed: %s",
                type(exc).__name__,
            )

    async def broadcast(self, message: str):
        for user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    send_coro = connection.send_text(message)
                    if self._schedule_if_foreign_loop(connection, send_coro):
                        continue
                    await send_coro
                except Exception as e:
                    logger.error(f"Error broadcasting: {e}")


notification_ws_manager = NotificationWebSocketManager()


def get_notification_ws_manager() -> NotificationWebSocketManager:
    return notification_ws_manager
