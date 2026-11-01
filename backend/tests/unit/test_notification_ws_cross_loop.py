"""Cross-loop WebSocket delivery for NotificationWebSocketManager.

Codex follow-up on #2874: background schedulers (lab notifications) run on
worker-thread loops. A WebSocket lives on Uvicorn's application loop, so a
direct ``await connection.send_json(...)`` from a foreign loop fails with
"attached to a different loop" and the notification is dropped. The manager
must marshal such sends back onto the connection's home loop.

Run:
    pytest backend/tests/unit/test_notification_ws_cross_loop.py -v
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
from collections import defaultdict
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest

from app.services.notification_websocket import NotificationWebSocketManager
from app.services.ws_redis_pubsub import RedisPubSubBridge


def _staging_compose_service_environment(service_name: str) -> dict[str, str]:
    compose_path = Path(__file__).resolve().parents[3] / "ops" / "compose.staging.yml"
    compose_text = compose_path.read_text(encoding="utf-8")
    service_match = re.search(
        rf"(?ms)^  {re.escape(service_name)}:\n(.*?)(?=^  [A-Za-z][A-Za-z0-9_-]*:\n|\Z)",
        compose_text,
    )
    assert service_match is not None, f"staging Compose service missing: {service_name}"

    environment_match = re.search(
        r"(?m)^    environment:\s*\n((?:^      .*\n?)*)",
        service_match.group(1),
    )
    assert environment_match is not None, f"staging environment missing: {service_name}"

    environment: dict[str, str] = {}
    for line in environment_match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, value = stripped.partition(":")
        if separator:
            environment[key] = value.strip()
    return environment


@pytest.mark.parametrize("service_name", ("backend", "worker"))
def test_staging_compose_enables_notification_relay_for_each_process(
    service_name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    environment = _staging_compose_service_environment(service_name)
    configured_url = environment.get("WS_REDIS_URL", "")
    expected_url = "redis://redis:6379/0"
    if configured_url != f"${{WS_REDIS_URL:-{expected_url}}}":
        raise AssertionError(
            f"{service_name} must provide the shared staging WS_REDIS_URL default"
        )

    # Compose resolves this fallback before starting each process. Constructing
    # the bridge with that value verifies the service can enable its relay.
    monkeypatch.setenv("WS_REDIS_URL", expected_url)
    bridge = RedisPubSubBridge("notification_ws")

    assert bridge.enabled
    assert bridge.redis_url == expected_url


class _FakeWebSocket:
    def __init__(self, name: str) -> None:
        self.name = name
        self.headers = {}
        self.accepted = False
        self.sent: list[dict] = []
        self.seen_loops: list[int] = []

    async def accept(self, *, subprotocol: str | None = None) -> None:
        self.accepted = True

    async def send_json(self, data: dict) -> None:
        self.seen_loops.append(id(asyncio.get_running_loop()))
        self.sent.append(data)


class _NoopPubSub:
    async def subscribe(self, channel: str, handler) -> None:
        return None

    async def unsubscribe(self, channel: str, handler) -> None:
        return None

    async def publish_ephemeral(self, channel: str, payload: dict) -> bool:
        return False


class _InMemoryRedisHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: dict[
            str,
            list[
                tuple[
                    str,
                    asyncio.AbstractEventLoop,
                    Callable[[dict], Awaitable[None]],
                ]
            ],
        ] = defaultdict(list)

    async def subscribe(self, instance_id: str, channel: str, handler) -> None:
        subscriber = (instance_id, asyncio.get_running_loop(), handler)
        with self._lock:
            subscribers = self._subscribers[channel]
            if not any(
                row[0] == instance_id and row[2] is handler for row in subscribers
            ):
                subscribers.append(subscriber)

    async def unsubscribe(self, instance_id: str, channel: str, handler) -> None:
        with self._lock:
            self._subscribers[channel] = [
                row
                for row in self._subscribers[channel]
                if not (row[0] == instance_id and row[2] is handler)
            ]

    async def publish(self, instance_id: str, channel: str, payload: dict) -> bool:
        with self._lock:
            subscribers = list(self._subscribers[channel])

        current_loop = asyncio.get_running_loop()
        for source, loop, handler in subscribers:
            if source == instance_id:
                continue
            if loop is current_loop:
                await handler(payload)
            else:
                future = asyncio.run_coroutine_threadsafe(handler(payload), loop)
                await asyncio.wrap_future(future)
        return True


class _InMemoryRedisBridge:
    def __init__(self, hub: _InMemoryRedisHub, instance_id: str) -> None:
        self.hub = hub
        self.instance_id = instance_id

    async def subscribe(self, channel: str, handler) -> None:
        await self.hub.subscribe(self.instance_id, channel, handler)

    async def unsubscribe(self, channel: str, handler) -> None:
        await self.hub.unsubscribe(self.instance_id, channel, handler)

    async def publish_ephemeral(self, channel: str, payload: dict) -> bool:
        return await self.hub.publish(self.instance_id, channel, payload)


class _FakeRedisPublisher:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []
        self.closed = False

    async def publish(self, channel: str, message: str) -> None:
        self.messages.append((channel, message))

    async def aclose(self) -> None:
        self.closed = True


async def _wait_until(predicate, timeout: float = 5.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            pytest.fail("condition not reached in time")
        await asyncio.sleep(0.02)


@pytest.mark.asyncio
async def test_send_json_from_foreign_loop_is_marshalled_to_home_loop() -> None:
    manager = NotificationWebSocketManager(pubsub=_NoopPubSub())
    ws = _FakeWebSocket("w1")
    home_loop = asyncio.get_running_loop()

    # Register exactly as connect() would, without a real handshake.
    manager.active_connections[7] = [ws]
    manager._connection_loops[id(ws)] = home_loop

    foreign_loop_id: list[int] = []

    def foreign_thread() -> None:
        async def go() -> None:
            foreign_loop_id.append(id(asyncio.get_running_loop()))
            await manager.send_json({"alert": "lab-ready"}, 7)

        asyncio.run(go())

    worker = threading.Thread(target=foreign_thread, daemon=True)
    worker.start()
    worker.join(timeout=5)
    assert not worker.is_alive()

    # The payload must arrive asynchronously on the HOME loop.
    await _wait_until(lambda: bool(ws.sent))
    assert ws.sent == [{"alert": "lab-ready"}]
    assert ws.seen_loops == [id(home_loop)], "delivery ran on the wrong loop"
    assert foreign_loop_id[0] != id(home_loop), "precondition: foreign loop"


@pytest.mark.asyncio
async def test_send_json_on_home_loop_still_works_directly() -> None:
    manager = NotificationWebSocketManager(pubsub=_NoopPubSub())
    ws = _FakeWebSocket("w2")
    manager.active_connections[8] = [ws]
    manager._connection_loops[id(ws)] = asyncio.get_running_loop()

    await manager.send_json({"alert": "direct"}, 8)

    assert ws.sent == [{"alert": "direct"}]
    assert ws.seen_loops == [id(asyncio.get_running_loop())]


@pytest.mark.asyncio
async def test_disconnect_cleans_up_home_loop_mapping() -> None:
    manager = NotificationWebSocketManager(pubsub=_NoopPubSub())
    ws = _FakeWebSocket("w3")
    manager.active_connections[9] = [ws]
    manager._connection_loops[id(ws)] = asyncio.get_running_loop()

    manager.disconnect(ws, 9)

    assert ws not in manager.active_connections.get(9, [])
    assert id(ws) not in manager._connection_loops


@pytest.mark.asyncio
async def test_outbox_worker_event_reaches_socket_in_separate_api_process() -> None:
    hub = _InMemoryRedisHub()
    api_manager = NotificationWebSocketManager(
        pubsub=_InMemoryRedisBridge(hub, "api-process")
    )
    worker_manager = NotificationWebSocketManager(
        pubsub=_InMemoryRedisBridge(hub, "worker-process")
    )
    ws = _FakeWebSocket("registrar")
    await api_manager.connect(ws, 41)
    assert ws.accepted

    payload = {
        "type": "notification",
        "event_type": "public_booking_request_created",
        "delivery_id": "delivery-1",
    }
    errors: list[BaseException] = []

    def outbox_worker() -> None:
        try:
            asyncio.run(worker_manager.send_json(payload, 41))
        except BaseException as exc:  # surface worker-thread failures in pytest
            errors.append(exc)

    worker = threading.Thread(target=outbox_worker, daemon=True)
    worker.start()
    await asyncio.to_thread(worker.join, 5)
    assert not worker.is_alive()
    assert errors == []
    assert ws.sent == [payload]
    assert ws.seen_loops == [id(asyncio.get_running_loop())]

    api_manager.disconnect(ws, 41)
    await _wait_until(lambda: not hub._subscribers["user:41"])


@pytest.mark.asyncio
async def test_ephemeral_redis_publish_closes_client_without_starting_listener() -> (
    None
):
    publisher = _FakeRedisPublisher()

    class _FakeRedisModule:
        @staticmethod
        def from_url(url: str, **kwargs):
            assert url == "redis://test"
            assert kwargs == {
                "socket_connect_timeout": 1.0,
                "socket_timeout": 1.0,
            }
            return publisher

    bridge = RedisPubSubBridge(
        channel_prefix="notification_ws",
        redis_url="redis://test",
        instance_id="worker-process",
    )
    bridge._redis_mod = _FakeRedisModule

    assert await bridge.publish_ephemeral(
        "user:41", {"type": "notification", "delivery_id": "delivery-2"}
    )

    assert publisher.closed
    assert bridge._pubsub is None
    assert bridge._listener_task is None
    assert len(publisher.messages) == 1
    channel, raw_envelope = publisher.messages[0]
    assert channel == "notification_ws:user:41"
    assert json.loads(raw_envelope) == {
        "source": "worker-process",
        "payload": {"type": "notification", "delivery_id": "delivery-2"},
    }


@pytest.mark.asyncio
async def test_ephemeral_redis_publish_failure_is_best_effort() -> None:
    manager = NotificationWebSocketManager(pubsub=_NoopPubSub())
    ws = _FakeWebSocket("local")
    manager.active_connections[12] = [ws]
    manager._connection_loops[id(ws)] = asyncio.get_running_loop()

    class _FailingPubSub(_NoopPubSub):
        async def publish_ephemeral(self, channel: str, payload: dict) -> bool:
            raise RuntimeError("redis unavailable")

    manager._pubsub = _FailingPubSub()

    await manager.send_json({"type": "notification"}, 12)

    assert ws.sent == [{"type": "notification"}]


@pytest.mark.asyncio
async def test_redis_listener_starts_after_first_subscription() -> None:
    class _FakePubSub:
        def __init__(self) -> None:
            self.subscribed = False
            self.channels: list[str] = []

        async def subscribe(self, channel: str) -> None:
            self.channels.append(channel)
            self.subscribed = True

        async def unsubscribe(self, channel: str) -> None:
            self.channels.remove(channel)
            self.subscribed = bool(self.channels)

        async def listen(self):
            if not self.subscribed:
                return
            while self.subscribed:
                await asyncio.sleep(0.01)
                yield {"type": "subscribe"}

    class _FakeRedisClient:
        def __init__(self) -> None:
            self.pubsub_client = _FakePubSub()

        def pubsub(self):
            return self.pubsub_client

        async def publish(self, channel: str, payload: str) -> None:
            return None

        async def aclose(self) -> None:
            return None

    client = _FakeRedisClient()

    class _FakeRedisModule:
        @staticmethod
        def from_url(url: str):
            assert url == "redis://test"
            return client

    bridge = RedisPubSubBridge("notification_ws", redis_url="redis://test")
    bridge._redis_mod = _FakeRedisModule

    async def handler(payload: dict) -> None:
        return None

    assert await bridge._ensure_ready()
    assert bridge._listener_task is None

    await bridge.subscribe("user:41", handler)
    await asyncio.sleep(0)

    assert bridge._listener_task is not None
    assert not bridge._listener_task.done()
    assert client.pubsub_client.channels == ["notification_ws:user:41"]

    await bridge.unsubscribe("user:41", handler)
    await bridge._listener_task
    assert bridge._listener_task.done()
    await bridge._redis_client.aclose()
