"""WS-POSTMERGE-04: legacy /ws-auth queue endpoints — real join, canonical room, RBAC.

The legacy mounted routes ``/api/v1/ws-auth/ws/queue/auth`` and
``/api/v1/ws-auth/ws/queue/optional-auth`` (``websocket_auth.py``) had four
source-confirmed defects:

1. ``ws_manager.connect(websocket, room)`` was called WITHOUT ``await`` —
   the accepted socket never entered the manager room and could not
   receive queue broadcasts (coroutine-never-awaited).
2. They built ``room = f"{department}:{date}"`` (single colon) while the
   active queue plane and every broadcaster use the canonical
   ``f"{department}::{date}"`` (double colon) — even a fixed ``await``
   would subscribe to a dead room.
3. ``_broadcast_patient_call`` executed ``await ws_manager.broadcast(...)``
   although ``WSManager.broadcast`` is a SYNCHRONOUS dispatcher — a
   guaranteed ``TypeError`` once an authorized ``call_patient`` message
   arrived.
4. ``ws_queue_optional_auth`` authenticated any active JWT but never
   invoked ``_has_department_access`` — a latent RBAC trap: repairing the
   ``await`` without RBAC would subscribe Patients/foreign specialists to
   caller-selected rooms.

The tests authenticate with REAL JWTs through the real endpoint flow; the
JWT subject resolution, the doctor-ownership SSOT and the token blacklist
are stubbed with synthetic principals (same pattern as
``test_queue_ws_plane_contract.py``), and the WSManager singleton is
isolated with a fake pubsub bridge. No patient data is involved.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import app.api.v1.endpoints.websocket_auth as ws_auth
from app.middleware.websocket_rate_limit import websocket_rate_limiter
from app.services.token_blacklist_service import TokenBlacklistService
from app.ws.queue_ws import ws_manager

_DATE = "2026-11-12"


# ---------------------------------------------------------------------------
# Isolation + stubbing helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_plane():
    """Fresh WSManager room state + fake pubsub bridge + clean rate limiter."""
    saved_rooms = ws_manager.rooms
    saved_handlers = ws_manager._redis_handlers
    saved_pubsub = ws_manager._pubsub
    saved_connections = dict(websocket_rate_limiter.connections_per_ip)
    saved_timestamps = dict(websocket_rate_limiter.connection_timestamps)

    ws_manager.rooms = defaultdict(set)
    ws_manager._redis_handlers = {}
    ws_manager._pubsub = SimpleNamespace(
        subscribe=AsyncMock(return_value=True),
        unsubscribe=AsyncMock(),
        publish=AsyncMock(),
    )
    websocket_rate_limiter.connections_per_ip.clear()
    websocket_rate_limiter.connection_timestamps.clear()

    yield ws_manager

    ws_manager.rooms = saved_rooms
    ws_manager._redis_handlers = saved_handlers
    ws_manager._pubsub = saved_pubsub
    websocket_rate_limiter.connections_per_ip.clear()
    websocket_rate_limiter.connection_timestamps.clear()
    websocket_rate_limiter.connections_per_ip.update(saved_connections)
    websocket_rate_limiter.connection_timestamps.update(saved_timestamps)


def _mint_jwt(*, sub: str, jti: str = "synthetic-legacy-jti") -> str:
    from app.core.config import settings

    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": sub, "jti": jti, "iat": now, "exp": now + timedelta(hours=1)},
        settings.SECRET_KEY,
        algorithm="HS256",
    )


def _stub_auth(
    monkeypatch: pytest.MonkeyPatch,
    user: SimpleNamespace,
    doctor: SimpleNamespace | None,
) -> None:
    """Resolve any JWT to ``user`` and any user to ``doctor`` (synthetic)."""
    monkeypatch.setattr(ws_auth, "_resolve_websocket_user", lambda payload, db: user)
    monkeypatch.setattr(ws_auth, "_resolve_doctor_for_user", lambda db, u: doctor)
    monkeypatch.setattr(
        TokenBlacklistService,
        "is_token_blacklisted",
        staticmethod(lambda db, jti, user_id=None: False),
    )


def _doctor_user(user_id: int = 100) -> SimpleNamespace:
    return SimpleNamespace(id=user_id, username="synthetic-doctor", role="Doctor")


def _doctor_row(doctor_id: int = 7) -> SimpleNamespace:
    return SimpleNamespace(id=doctor_id, specialty="cardio", department=None)


def _wait_for_room(room: str, timeout: float = 2.0) -> bool:
    """Poll for server-side room registration (runs on the app loop)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if room in ws_manager.rooms:
            return True
        time.sleep(0.01)
    return False


# ---------------------------------------------------------------------------
# /ws-auth/ws/queue/auth — join + canonical room + delivery
# ---------------------------------------------------------------------------


def test_authenticated_legacy_endpoint_joins_canonical_room(
    client: TestClient, isolated_plane, monkeypatch: pytest.MonkeyPatch
):
    _stub_auth(monkeypatch, _doctor_user(), _doctor_row(doctor_id=7))
    token = _mint_jwt(sub="100")
    room = f"specialist_7::{_DATE}"

    with client.websocket_connect(
        f"/api/v1/ws-auth/ws/queue/auth?department=specialist_7&date={_DATE}&token={token}"
    ) as ws:
        assert _wait_for_room(room), (
            "accepted socket never joined the canonical room — "
            "ws_manager.connect is not awaited or the room name is not canonical"
        )


def test_authenticated_legacy_endpoint_wrong_room_never_joined(
    client: TestClient, isolated_plane, monkeypatch: pytest.MonkeyPatch
):
    # The legacy single-colon room must NOT be subscribed: broadcasts use
    # the canonical double-colon identity only.
    _stub_auth(monkeypatch, _doctor_user(), _doctor_row(doctor_id=7))
    token = _mint_jwt(sub="100")

    with client.websocket_connect(
        f"/api/v1/ws-auth/ws/queue/auth?department=specialist_7&date={_DATE}&token={token}"
    ) as ws:
        time.sleep(0.15)
        assert f"specialist_7:{_DATE}" not in ws_manager.rooms


def test_call_patient_real_dispatcher_delivers_no_typeerror(
    client: TestClient, isolated_plane, monkeypatch: pytest.MonkeyPatch
):
    """call_patient through the real dispatcher: no TypeError, canonical room."""
    _stub_auth(monkeypatch, _doctor_user(), _doctor_row(doctor_id=7))
    token = _mint_jwt(sub="100")
    room = f"specialist_7::{_DATE}"

    with (
        client.websocket_connect(
            f"/api/v1/ws-auth/ws/queue/auth?department=specialist_7&date={_DATE}&token={token}"
        ) as ws_a,
        client.websocket_connect(
            f"/api/v1/ws-auth/ws/queue/auth?department=specialist_7&date={_DATE}&token={token}"
        ) as ws_b,
    ):
        assert _wait_for_room(room)
        ws_a.send_json({"type": "call_patient", "patient_id": "p-1"})

        # Both room members must receive the patient_called event; the old
        # code died with TypeError (await on a sync broadcast) instead.
        msg_a = ws_a.receive_json()
        msg_b = ws_b.receive_json()
        for msg in (msg_a, msg_b):
            assert msg.get("type") == "patient_called"
            assert msg.get("patient_id") == "p-1"
            assert msg.get("caller") == "synthetic-doctor"


def test_authenticated_legacy_endpoint_disconnect_cleans_room(
    client: TestClient, isolated_plane, monkeypatch: pytest.MonkeyPatch
):
    _stub_auth(monkeypatch, _doctor_user(), _doctor_row(doctor_id=7))
    token = _mint_jwt(sub="100")
    room = f"specialist_7::{_DATE}"

    with client.websocket_connect(
        f"/api/v1/ws-auth/ws/queue/auth?department=specialist_7&date={_DATE}&token={token}"
    ) as ws:
        assert _wait_for_room(room)

    time.sleep(0.1)
    assert room not in ws_manager.rooms


# ---------------------------------------------------------------------------
# /ws-auth/ws/queue/optional-auth — latent RBAC trap closed
# ---------------------------------------------------------------------------


def test_optional_auth_patient_token_rejected_before_accept(
    client: TestClient, isolated_plane, monkeypatch: pytest.MonkeyPatch
):
    _stub_auth(
        monkeypatch,
        SimpleNamespace(id=9, username="syn-patient", role="Patient"),
        None,
    )
    token = _mint_jwt(sub="9")

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"/api/v1/ws-auth/ws/queue/optional-auth?department=specialist_7&date={_DATE}&token={token}"
        ):
            pass

    assert not ws_manager.rooms


def test_optional_auth_doctor_foreign_specialist_denied(
    client: TestClient, isolated_plane, monkeypatch: pytest.MonkeyPatch
):
    # WS-POSTMERGE-03 ownership: doctor row 73 must not join specialist_42.
    _stub_auth(monkeypatch, _doctor_user(user_id=101), _doctor_row(doctor_id=73))
    token = _mint_jwt(sub="101")

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"/api/v1/ws-auth/ws/queue/optional-auth?department=specialist_42&date={_DATE}&token={token}"
        ):
            pass

    assert not ws_manager.rooms


def test_optional_auth_doctor_own_room_joins_canonical_room(
    client: TestClient, isolated_plane, monkeypatch: pytest.MonkeyPatch
):
    _stub_auth(monkeypatch, _doctor_user(user_id=101), _doctor_row(doctor_id=73))
    token = _mint_jwt(sub="101")
    room = f"specialist_73::{_DATE}"

    with client.websocket_connect(
        f"/api/v1/ws-auth/ws/queue/optional-auth?department=specialist_73&date={_DATE}&token={token}"
    ) as ws:
        assert _wait_for_room(room)


def test_optional_auth_missing_token_rejected(client: TestClient, isolated_plane):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"/api/v1/ws-auth/ws/queue/optional-auth?department=specialist_7&date={_DATE}"
        ):
            pass

    assert not ws_manager.rooms


# ---------------------------------------------------------------------------
# _broadcast_patient_call — sync broadcast must not be awaited
# ---------------------------------------------------------------------------


def test_broadcast_patient_call_uses_canonical_room_without_typeerror(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[tuple[str, dict]] = []

    manager = SimpleNamespace(
        broadcast=Mock(side_effect=lambda room, data: calls.append((room, data)))
    )
    monkeypatch.setattr(ws_auth, "ws_manager", manager)

    result = asyncio.run(
        ws_auth._broadcast_patient_call("specialist_7", _DATE, "p-1", "tester")
    )

    assert result is None
    assert len(calls) == 1
    room, payload = calls[0]
    assert room == f"specialist_7::{_DATE}"
    assert payload["type"] == "patient_called"
    assert payload["patient_id"] == "p-1"
    assert payload["caller"] == "tester"
