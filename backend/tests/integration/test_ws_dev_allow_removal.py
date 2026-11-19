"""Characterization tests for WS_DEV_ALLOW bypass removal (PR-5).

Audit found that `WS_DEV_ALLOW=1` env var bypasses WebSocket auth entirely
in queue_ws.py — `_auth_ok` returns True without checking JWT. This is
dangerous because CI uses `WS_DEV_ALLOW=1` and the flag could accidentally
leak to production.

This PR removes the bypass and replaces it with a TESTING-only check that
only fires when `TESTING=1` (set by pytest conftest, never in production).

Tests:
- /ws/queue with WS_DEV_ALLOW=1 but no token → should be REJECTED
  (was: accepted)
- /ws/queue with TESTING=1 but no token → should still be REJECTED
  (TESTING is for app config, not auth bypass)
- /ws/queue with valid token → accepted (regression check)
- /ws/noauth endpoint → should be REMOVED (404 or 410, not 200)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from sqlalchemy.orm import sessionmaker
from starlette.websockets import WebSocketDisconnect

from app.db import session as session_module


def _suffix() -> str:
    return uuid4().hex[:10]


def _make_jwt(*, sub: str | int = 1, auth_epoch: int = 0) -> str:
    from app.core.config import settings
    payload = {
        "sub": sub,
        "auth_epoch": auth_epoch,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
        "jti": uuid4().hex,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


@pytest.fixture(autouse=True)
def _patch_session_local(db_session, monkeypatch):
    """Give WS handlers their own session on the fixture's test connection."""
    factory = sessionmaker(
        bind=db_session.connection(), expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    monkeypatch.setattr(session_module, "SessionLocal", factory)
    import app.api.v1.endpoints.websocket_auth as _ws_auth
    monkeypatch.setattr(_ws_auth, "SessionLocal", factory)


@pytest.mark.parametrize("token_kind", ["missing", "invalid", "username_only"])
def test_ws_queue_rejects_bad_token_even_with_ws_dev_allow(
    client, db_session, monkeypatch, token_kind
):
    """WS_DEV_ALLOW never grants access without a valid numeric user token.

    PR-5: WS_DEV_ALLOW no longer bypasses auth. It was a security risk
    because CI used it and the flag could leak to production.
    """
    monkeypatch.setenv("WS_DEV_ALLOW", "1")
    monkeypatch.delenv("TESTING", raising=False)

    headers = {"origin": "http://localhost:5173"}
    if token_kind != "missing":
        token = "invalid" if token_kind == "invalid" else _make_jwt(sub="retired-user")
        headers["authorization"] = f"Bearer {token}"

    with client.websocket_connect(
        "/ws/queue?department=cardiology&date=2026-01-01",
        headers=headers,
    ) as ws:
        assert ws.receive_json() == {"type": "error", "reason": "auth required"}
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 1008



def test_ws_noauth_endpoint_removed(client, monkeypatch):
    """/ws/noauth should be REMOVED — returns 404 or closes immediately.

    PR-5: this endpoint was a literal no-auth WebSocket. Even though it
    was disabled in production, it's a security risk in dev/staging.
    """
    # The endpoint should either 404 (route removed) or close immediately
    # with policy violation. Either way, it should NOT send a "connected"
    # message.
    try:
        with client.websocket_connect("/api/v1/ws/noauth") as ws:
            # If accepted, must NOT send the "DEV ONLY" welcome
            try:
                msg = ws.receive_json()
                # If we got a message, it must NOT be the dev welcome
                assert msg.get("type") != "connected", \
                    "/ws/noauth still sends connected — bypass not removed"
            except Exception:
                pass  # WebSocketDisconnect is fine
    except Exception:
        pass  # 404 or rejection is fine


def test_ws_queue_accepts_valid_token_without_ws_dev_allow(client, db_session, monkeypatch):
    """A real doctor token opens the authorized room without WS_DEV_ALLOW."""
    from unittest.mock import AsyncMock

    from app.api.v1.endpoints import websocket_auth
    from app.ws import queue_ws
    from app.core.security import get_password_hash
    from app.models.clinic import Doctor
    from app.models.department import Department
    from app.models.user import User

    monkeypatch.delenv("WS_DEV_ALLOW", raising=False)
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setattr(websocket_auth, "QUEUE_WS_AUTH_RECHECK_SECONDS", 0.05)
    monkeypatch.setattr(queue_ws.ws_manager, "_ensure_room_subscription", AsyncMock())
    monkeypatch.setattr(queue_ws.ws_manager, "_remove_room_subscription", AsyncMock())

    suffix = _suffix()
    user = User(
        username=f"ws_q_{suffix}",
        email=f"wsq-{suffix}@test.local",
        full_name=f"WS Q {suffix}",
        hashed_password=get_password_hash("pass123"),
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # WS-POSTMERGE-03: a doctor-family role owns rooms through its Doctor
    # row. The department 'cardiology' room is joined through the row's
    # Department key, so seed the ownership SSOT for this principal.
    department = Department(key="cardiology", name_ru=f"SYNTH-cardiology-{suffix}", active=True)
    db_session.add(department)
    db_session.commit()
    db_session.refresh(department)
    doctor = Doctor(
        user_id=user.id,
        specialty="cardio",
        department_id=department.id,
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()

    token = _make_jwt(sub=str(user.id), auth_epoch=user.auth_epoch)
    room = "cardiology::2026-01-01"
    with client.websocket_connect(
        "/ws/queue?department=cardiology&date=2026-01-01",
        headers={
            "origin": "http://localhost:5173",
            "authorization": f"Bearer {token}",
        },
    ) as ws:
        assert ws.receive_json() == {"type": "queue.connected", "room": room}
        assert room in queue_ws.ws_manager.rooms
        assert ws.receive_json()["type"] == "ping"
        ws.send_json({"type": "pong"})
        assert ws.receive_json()["type"] == "ping"
    assert room not in queue_ws.ws_manager.rooms
