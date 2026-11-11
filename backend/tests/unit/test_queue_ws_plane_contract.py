"""Contract regression coverage for the standalone queue WebSocket plane.

Audit PR #3961, round 35 (docs/audits/2026-11-09-queue-position-notifications-
source-review.md) — six source-observed defects on ``/ws/queue`` +
``WSManager``, one contract file:

- **QUEUEWSDISPATCH-BE-001 (P1/P2)** — ``broadcast_queue_update`` handed the
  result of a SYNCHRONOUS ``WSManager.broadcast`` (always ``None``) to
  ``asyncio.create_task`` — a guaranteed ``TypeError: a coroutine was
  expected`` on every queue mutation (join/call-next/no-show/restore …),
  surfacing as false broadcast errors in endpoint logs while the inner
  broadcast actually ran. The helper must schedule through the manager's own
  single dispatch layer and never wrap a sync result in ``create_task``.
- **QUEUEWSHANDSHAKE-BE-001 (P1/P2)** — the browser hook
  (``useQueueWebSocket.ts``) offers ``Sec-WebSocket-Protocol: bearer.<jwt>``;
  a bare ``accept()`` makes browsers abort the handshake. The success path
  must reuse the canonical ``accept_echoing_subprotocol``.
- **QUEUEWSAUTH-BE-001 (P1, conditional)** — ``TESTING=1`` bypassed JWT
  validation even when ``ENV=production``; the misconfigured combination
  turned the mounted stream anonymous. The bypass must be refused in
  production and kept for dev/test harnesses.
- **QUEUEWSAUTH-BE-002 (P1, conditional)** — revocation ran only for numeric
  ``sub`` subjects; a revoked (or bulk-invalidated) username-sub JWT kept
  passing. The validated subject must be resolved to a stable user BEFORE
  the blacklist (exact-jti + all-user sentinel) is applied.
- **QUEUEWSSCOPE-BE-001 (P1/P2)** — any authenticated user could subscribe
  to arbitrary caller-provided rooms. A Patient-role token must be closed
  with 1008 BEFORE the room subscription, mirroring the canonical
  authenticated-queue policy (``_has_department_access``).
- **QUEUEWSRELAY-BE-001 (P2)** — ``_send_one`` evicted the last dead socket
  of a room without unsubscribing Redis; dead-room handlers leaked. The
  cleanup must mirror ``disconnect()``.

Synthetic fixtures only: no real patient data, no network, no Redis, no
PostgreSQL. The RED-first state of each finding was captured on the pre-fix
source (see the fix PR's RED→GREEN transcript comment).
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import jwt
import pytest
from fastapi import WebSocketDisconnect

import app.api.v1.endpoints.websocket_auth as ws_auth_module
import app.ws.queue_ws as queue_ws
from app.services.token_blacklist_service import TokenBlacklistService

_OFFERED = "bearer.SYNTHETIC-QUEUE-WS-JWT"
_ROOM = "specialist_7::2026-11-11"


class _FakeWebSocket:
    """Minimal WebSocket double for the ws_queue handler."""

    def __init__(self, headers: dict | None = None, fail_sends: bool = False) -> None:
        self.headers = dict(headers or {})
        self.url = SimpleNamespace(path="/ws/queue", query="")
        self.query_params: dict = {}
        self.fail_sends = fail_sends
        self.sent: list[dict] = []
        self.closed: list[dict] = []
        self.accepted_subprotocol: str | None | object = "UNSET"
        self.receive_calls = 0

    async def accept(self, subprotocol: str | None = None) -> None:
        self.accepted_subprotocol = subprotocol

    async def send_json(self, message: dict) -> None:
        if self.fail_sends:
            raise RuntimeError("synthetic dead socket")
        self.sent.append(message)

    async def close(self, code=None, reason=None) -> None:
        self.closed.append({"code": code, "reason": reason})

    async def receive_text(self) -> str:
        self.receive_calls += 1
        raise WebSocketDisconnect(code=1000)


class _FakeSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeSessionFactory:
    def __call__(self) -> _FakeSession:
        return _FakeSession()


def _stub_manager(monkeypatch: pytest.MonkeyPatch):
    manager = SimpleNamespace(connect=AsyncMock(), disconnect=Mock())
    monkeypatch.setattr(queue_ws, "ws_manager", manager)
    return manager


def _mint_jwt(*, sub, jti: str = "synthetic-jti") -> str:
    from app.core.config import settings

    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": sub, "jti": jti, "iat": now, "exp": now + timedelta(hours=1)},
        settings.SECRET_KEY,
        algorithm="HS256",
    )


def _stub_user_resolver(monkeypatch: pytest.MonkeyPatch, user) -> None:
    monkeypatch.setattr(
        ws_auth_module, "_resolve_websocket_user", lambda payload, db: user
    )
    monkeypatch.setattr("app.db.session.SessionLocal", _FakeSessionFactory())


def _stub_blacklist(monkeypatch: pytest.MonkeyPatch, fake) -> None:
    monkeypatch.setattr(
        TokenBlacklistService, "is_token_blacklisted", staticmethod(fake)
    )


@pytest.fixture()
def fresh_manager():
    """Isolate the WSManager singleton: fresh rooms/handlers + fake bridge."""
    mgr = queue_ws.ws_manager
    saved = (mgr.rooms, mgr._redis_handlers, mgr._pubsub)
    mgr.rooms = defaultdict(set)
    mgr._redis_handlers = {}
    mgr._pubsub = SimpleNamespace(
        subscribe=AsyncMock(return_value=True), unsubscribe=AsyncMock(), publish=AsyncMock()
    )
    yield mgr
    mgr.rooms, mgr._redis_handlers, mgr._pubsub = saved


# ---------------------------------------------------------------------------
# QUEUEWSDISPATCH-BE-001 — create_task(None) on every queue mutation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_queue_update_inside_event_loop_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict]] = []

    class FakeSyncManager:
        def broadcast(self, room, data):
            calls.append((room, data))

    monkeypatch.setattr(queue_ws, "ws_manager", FakeSyncManager())

    # Inside a running event loop (as from every FastAPI endpoint):
    # must not raise and must reach the manager exactly once.
    queue_ws.broadcast_queue_update(
        department="specialist_7",
        date="2026-11-11",
        event_type="queue_update",
        data={"action": "call_next", "entry_id": 123},
    )

    assert calls == [
        (
            _ROOM,
            {
                "type": "queue_update",
                "room": _ROOM,
                "data": {"action": "call_next", "entry_id": 123},
            },
        )
    ]


def test_broadcast_queue_update_without_event_loop_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict]] = []

    class FakeSyncManager:
        def broadcast(self, room, data):
            calls.append((room, data))

    monkeypatch.setattr(queue_ws, "ws_manager", FakeSyncManager())

    # Sync pytest context: no running event loop — must skip, not raise
    # (same effective behavior as the legacy no-loop path).
    queue_ws.broadcast_queue_update(
        department="specialist_7",
        date="2026-11-11",
        event_type="queue_update",
    )

    assert calls == []


# ---------------------------------------------------------------------------
# QUEUEWSHANDSHAKE-BE-001 — echo the offered Sec-WebSocket-Protocol
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ws_queue_echoes_offered_bearer_subprotocol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("CORS_DISABLE", "1")
    manager = _stub_manager(monkeypatch)
    ws = _FakeWebSocket(
        headers={
            "origin": "http://localhost:5173",
            "sec-websocket-protocol": _OFFERED,
        }
    )

    await asyncio.wait_for(
        queue_ws.ws_queue(ws, "specialist_7", "2026-11-11"), timeout=2
    )

    assert ws.accepted_subprotocol == _OFFERED
    assert ws.sent and ws.sent[0]["type"] == "queue.connected"
    manager.connect.assert_awaited_once_with(ws, _ROOM)
    manager.disconnect.assert_called_once_with(ws, _ROOM)


@pytest.mark.asyncio
async def test_ws_queue_plain_accept_when_nothing_offered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("CORS_DISABLE", "1")
    manager = _stub_manager(monkeypatch)
    ws = _FakeWebSocket(headers={"origin": "http://localhost:5173"})

    await asyncio.wait_for(
        queue_ws.ws_queue(ws, "specialist_7", "2026-11-11"), timeout=2
    )

    assert ws.accepted_subprotocol is None
    manager.connect.assert_awaited_once_with(ws, _ROOM)


# ---------------------------------------------------------------------------
# QUEUEWSAUTH-BE-001 — TESTING=1 must not silence auth in production
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_testing_bypass_refused_in_production(
    prod_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    # prod_env delenvs TESTING; the finding is exactly the misconfigured
    # combination ENV=production + TESTING=1 with no JWT.
    monkeypatch.setenv("TESTING", "1")
    manager = _stub_manager(monkeypatch)
    ws = _FakeWebSocket(headers={"origin": "http://localhost:5173"})

    await asyncio.wait_for(
        queue_ws.ws_queue(ws, "specialist_7", "2026-11-11"), timeout=2
    )

    manager.connect.assert_not_awaited()
    assert ws.closed and ws.closed[0]["code"] == 1008
    assert ws.sent and ws.sent[0]["reason"] == "Authentication required in production"


@pytest.mark.asyncio
async def test_testing_bypass_still_allows_dev_harness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("CORS_DISABLE", "1")
    manager = _stub_manager(monkeypatch)
    ws = _FakeWebSocket(headers={"origin": "http://localhost:5173"})

    await asyncio.wait_for(
        queue_ws.ws_queue(ws, "specialist_7", "2026-11-11"), timeout=2
    )

    manager.connect.assert_awaited_once_with(ws, _ROOM)


# ---------------------------------------------------------------------------
# QUEUEWSAUTH-BE-002 — username-sub revocation reaches the blacklist
# ---------------------------------------------------------------------------


def test_username_sub_revoked_jti_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("ENV", "dev")
    calls: list[tuple[str, int | None]] = []

    def fake_blacklist(db, jti, user_id=None):
        calls.append((jti, user_id))
        return jti == "syn-revoked-jti"

    _stub_blacklist(monkeypatch, fake_blacklist)
    _stub_user_resolver(
        monkeypatch, SimpleNamespace(id=7, role="Doctor", username="synthetic-staff")
    )

    token = _mint_jwt(sub="synthetic-staff", jti="syn-revoked-jti")
    assert queue_ws._auth_ok({"authorization": f"Bearer {token}"}, None) is False
    # Revocation must run for the RESOLVED stable user id — not be skipped
    # because the subject is a username string.
    assert calls == [("syn-revoked-jti", 7)]


def test_username_sub_all_user_sentinel_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("ENV", "dev")

    def fake_blacklist(db, jti, user_id=None):
        # The all_user_tokens sentinel for user 7 is active; the fresh jti
        # itself is NOT individually revoked.
        return user_id == 7

    _stub_blacklist(monkeypatch, fake_blacklist)
    _stub_user_resolver(
        monkeypatch, SimpleNamespace(id=7, role="Doctor", username="synthetic-staff")
    )

    token = _mint_jwt(sub="synthetic-staff", jti="syn-fresh-jti")
    assert queue_ws._auth_ok({"authorization": f"Bearer {token}"}, None) is False


def test_username_sub_unrevoked_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("ENV", "dev")

    _stub_blacklist(monkeypatch, lambda db, jti, user_id=None: False)
    _stub_user_resolver(
        monkeypatch, SimpleNamespace(id=7, role="Doctor", username="synthetic-staff")
    )

    token = _mint_jwt(sub="synthetic-staff", jti="syn-clean-jti")
    assert queue_ws._auth_ok({"authorization": f"Bearer {token}"}, None) is True


# ---------------------------------------------------------------------------
# QUEUEWSSCOPE-BE-001 — role gate before the room subscription
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patient_role_cannot_subscribe_to_queue_room(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("CORS_DISABLE", "1")
    _stub_blacklist(monkeypatch, lambda db, jti, user_id=None: False)
    _stub_user_resolver(
        monkeypatch, SimpleNamespace(id=9, role="Patient", username="syn-patient")
    )
    manager = _stub_manager(monkeypatch)
    token = _mint_jwt(sub="syn-patient", jti="syn-patient-jti")
    ws = _FakeWebSocket(
        headers={"origin": "http://localhost:5173", "authorization": f"Bearer {token}"}
    )

    await asyncio.wait_for(
        queue_ws.ws_queue(ws, "specialist_7", "2026-11-11"), timeout=2
    )

    manager.connect.assert_not_awaited()
    assert ws.closed and ws.closed[0]["code"] == 1008
    assert ws.sent and "queue room" in ws.sent[0]["reason"]
    assert ws.receive_calls == 0


@pytest.mark.asyncio
async def test_staff_role_can_subscribe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("CORS_DISABLE", "1")
    _stub_blacklist(monkeypatch, lambda db, jti, user_id=None: False)
    _stub_user_resolver(
        monkeypatch,
        SimpleNamespace(id=11, role="Registrar", username="syn-registrar"),
    )
    manager = _stub_manager(monkeypatch)
    token = _mint_jwt(sub="syn-registrar", jti="syn-registrar-jti")
    ws = _FakeWebSocket(
        headers={"origin": "http://localhost:5173", "authorization": f"Bearer {token}"}
    )

    await asyncio.wait_for(
        queue_ws.ws_queue(ws, "specialist_7", "2026-11-11"), timeout=2
    )

    manager.connect.assert_awaited_once_with(ws, _ROOM)
    assert ws.sent and ws.sent[0]["type"] == "queue.connected"


# ---------------------------------------------------------------------------
# QUEUEWSRELAY-BE-001 — dead-room Redis unsubscribe on send-failure eviction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dead_last_socket_unsubscribes_empty_room(
    fresh_manager,
) -> None:
    dead = _FakeWebSocket(fail_sends=True)
    await fresh_manager.connect(dead, _ROOM)
    fresh_manager._pubsub.subscribe.assert_awaited_once()

    await fresh_manager._send_one(dead, {"type": "queue_update"})

    assert _ROOM not in fresh_manager.rooms
    # Let the scheduled cleanup task run.
    await asyncio.sleep(0)
    fresh_manager._pubsub.unsubscribe.assert_awaited_once()
    assert _ROOM not in fresh_manager._redis_handlers


@pytest.mark.asyncio
async def test_send_failure_keeps_room_while_other_subscribers_remain(
    fresh_manager,
) -> None:
    live = _FakeWebSocket()
    dead = _FakeWebSocket(fail_sends=True)
    await fresh_manager.connect(live, _ROOM)
    await fresh_manager.connect(dead, _ROOM)
    # One Redis handler for the room, registered on the first subscribe.
    fresh_manager._pubsub.subscribe.assert_awaited_once()

    await fresh_manager._send_one(dead, {"type": "queue_update"})

    assert _ROOM in fresh_manager.rooms
    await asyncio.sleep(0)
    fresh_manager._pubsub.unsubscribe.assert_not_awaited()
