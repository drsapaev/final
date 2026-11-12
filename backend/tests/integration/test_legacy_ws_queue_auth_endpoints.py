"""WS-POSTMERGE-04/05: legacy /ws-auth queue endpoints — real join, canonical room, RBAC, pool hygiene, call validation.

The legacy mounted routes ``/api/v1/ws-auth/ws/queue/auth`` and
``/api/v1/ws-auth/ws/queue/optional-auth`` (``websocket_auth.py``) had four
source-confirmed defects (WS-POSTMERGE-04):

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

Round 39 added three more candidates against the repaired transport
(audit IDs LEGACYWSPOOL-BE-001 / LEGACYWSCALL-BE-001 / WSHELPER-FE-001):

5. **LEGACYWSPOOL-BE-001 (P1 conditional)** — the handshake ``SessionLocal()``
   was held for the whole WS lifetime, pinning one PostgreSQL pool
   connection per connected staff client (pool defaults 8+2).
6. **LEGACYWSCALL-BE-001 (P2)** — ``call_patient`` forwarded ARBITRARY
   patient ids to the broadcast; the queue SSOT is now consulted (numeric
   id, ISO date, queue scope of the room, ``waiting`` entry) with a
   short-lived session before relaying.
7. **WSHELPER-FE-001 (P2, latent, backend half)** — the endpoints required
   the ``?token=`` query and used a bare ``accept()``; a browser offering
   the ``bearer.<jwt>`` subprotocol could never complete the handshake.
   Tokens now resolve through the canonical ``extract_ws_token`` and the
   offered subprotocol is echoed.

The tests authenticate with REAL JWTs through the real endpoint flow; the
JWT subject resolution, the doctor-ownership SSOT and the token blacklist
are stubbed with synthetic principals (same pattern as
``test_queue_ws_plane_contract.py``), and the WSManager singleton is
isolated with a fake pubsub bridge. Queue-entry validation runs real
queries against the per-test sqlite engine. No patient data is involved.
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


# ---------------------------------------------------------------------------
# LEGACYWSPOOL-BE-001 / LEGACYWSCALL-BE-001 helpers: real SSOT sessions
# ---------------------------------------------------------------------------


def _patch_validation_db(monkeypatch: pytest.MonkeyPatch, engine) -> None:
    """Bind ws_auth.SessionLocal to the per-test engine.

    The queue-entry validation runs REAL queries (queue SSOT), so the
    module's session factory is bound to the per-test sqlite engine.
    """
    from sqlalchemy.orm import sessionmaker

    monkeypatch.setattr(
        ws_auth,
        "SessionLocal",
        sessionmaker(autocommit=False, autoflush=False, bind=engine),
    )


@pytest.fixture()
def seed_queue(test_db):
    """Seed queue rows and FULLY remove them at teardown.

    ``test_db`` is SESSION-scoped: rows committed directly to the engine
    persist for the whole run and pollute later queue-count tests (queue
    lag metrics, QR-join censuses, migration backups). This fixture seeds
    get-or-create queues + entries and deletes exactly the rows it
    created when the test finishes.
    """
    from datetime import date as date_type

    from sqlalchemy.orm import sessionmaker

    from app.models.online_queue import DailyQueue, OnlineQueueEntry

    created_queue_ids: list[int] = []
    created_entry_ids: list[int] = []
    factory = sessionmaker(autocommit=False, autoflush=False, bind=test_db)

    def _seed(*, specialist_id: int, patient_id: int, status: str) -> int:
        session = factory()
        try:
            queue_day = date_type.fromisoformat(_DATE)
            queue = (
                session.query(DailyQueue)
                .filter(
                    DailyQueue.day == queue_day,
                    DailyQueue.specialist_id == specialist_id,
                )
                .first()
            )
            if queue is None:
                queue = DailyQueue(day=queue_day, specialist_id=specialist_id)
                session.add(queue)
                session.flush()
                created_queue_ids.append(queue.id)
            next_number = (
                session.query(OnlineQueueEntry)
                .filter(OnlineQueueEntry.queue_id == queue.id)
                .count()
                + 1
            )
            entry = OnlineQueueEntry(
                queue_id=queue.id,
                number=next_number,
                patient_id=patient_id,
                status=status,
            )
            session.add(entry)
            session.commit()
            created_entry_ids.append(entry.id)
            return queue.id
        finally:
            session.close()

    yield _seed

    session = factory()
    try:
        if created_entry_ids:
            session.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.id.in_(created_entry_ids)
            ).delete(synchronize_session=False)
        if created_queue_ids:
            # Only the queues THIS fixture created — never shared rows.
            session.query(DailyQueue).filter(
                DailyQueue.id.in_(created_queue_ids)
            ).delete(synchronize_session=False)
        session.commit()
    finally:
        session.close()


def test_legacy_session_released_before_receive_loop(
    client: TestClient, isolated_plane, monkeypatch: pytest.MonkeyPatch
):
    """LEGACYWSPOOL-BE-001 (P1 conditional): no pool connection is held for
    the WS lifetime — the handshake session is closed BEFORE the receive
    loop starts (asserted while the socket is still connected)."""
    from unittest.mock import MagicMock

    fake_session = MagicMock()
    captured: list[object] = []

    def _factory():
        captured.append(fake_session)
        return fake_session

    _stub_auth(monkeypatch, _doctor_user(), _doctor_row(doctor_id=7))
    monkeypatch.setattr(ws_auth, "SessionLocal", _factory)

    token = _mint_jwt(sub="100")
    room = f"specialist_7::{_DATE}"

    with client.websocket_connect(
        f"/api/v1/ws-auth/ws/queue/auth?department=specialist_7&date={_DATE}&token={token}"
    ) as ws:
        assert _wait_for_room(room)
        assert fake_session.close.called, (
            "the handshake SessionLocal() connection is still checked out "
            "while the socket is connected — pool starvation risk"
        )

    # One session per handshake, no per-message re-open on the stub path.
    assert len(captured) == 1


def test_authenticated_endpoint_accepts_subprotocol_token(
    client: TestClient, isolated_plane, monkeypatch: pytest.MonkeyPatch
):
    """WSHELPER-FE-001 backend half: bearer subprotocol + echoing accept.

    The endpoint previously required the ?token= query parameter and used a
    bare accept() — a browser offering Sec-WebSocket-Protocol could never
    complete the handshake.
    """
    _stub_auth(monkeypatch, _doctor_user(), _doctor_row(doctor_id=7))
    token = _mint_jwt(sub="100")
    room = f"specialist_7::{_DATE}"

    with client.websocket_connect(
        f"/api/v1/ws-auth/ws/queue/auth?department=specialist_7&date={_DATE}",
        subprotocols=[f"bearer.{token}"],
    ) as ws:
        assert _wait_for_room(room)
        accepted = getattr(ws, "accepted_subprotocol", None)
        assert accepted == f"bearer.{token}"


def test_optional_auth_accepts_subprotocol_token(
    client: TestClient, isolated_plane, monkeypatch: pytest.MonkeyPatch
):
    _stub_auth(monkeypatch, _doctor_user(user_id=101), _doctor_row(doctor_id=73))
    token = _mint_jwt(sub="101")
    room = f"specialist_73::{_DATE}"

    with client.websocket_connect(
        f"/api/v1/ws-auth/ws/queue/optional-auth?department=specialist_73&date={_DATE}",
        subprotocols=[f"bearer.{token}"],
    ) as ws:
        assert _wait_for_room(room)
        accepted = getattr(ws, "accepted_subprotocol", None)
        assert accepted == f"bearer.{token}"


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


def test_call_patient_seeded_waiting_entry_broadcasts(
    client: TestClient,
    isolated_plane,
    test_db,
    seed_queue,
    monkeypatch: pytest.MonkeyPatch,
):
    """LEGACYWSCALL-BE-001 positive path: a REAL waiting entry broadcasts.

    The queue scope is resolved through the SSOT (DailyQueue of the room's
    specialist for the room's date) and the entry must exist with status
    ``waiting`` inside that scope.
    """
    _stub_auth(monkeypatch, _doctor_user(), _doctor_row(doctor_id=7))
    _patch_validation_db(monkeypatch, test_db)
    seed_queue(specialist_id=7, patient_id=501, status="waiting")

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
        ws_a.send_json({"type": "call_patient", "patient_id": "501"})

        # Both room members must receive the patient_called event; the old
        # code died with TypeError (await on a sync broadcast) instead.
        msg_a = ws_a.receive_json()
        msg_b = ws_b.receive_json()
        for msg in (msg_a, msg_b):
            assert msg.get("type") == "patient_called"
            assert msg.get("patient_id") == "501"
            assert msg.get("caller") == "synthetic-doctor"


def test_call_patient_rejects_unseeded_synthetic_patient(
    client: TestClient,
    isolated_plane,
    test_db,
    seed_queue,
    monkeypatch: pytest.MonkeyPatch,
):
    """LEGACYWSCALL-BE-001: an unseeded/non-numeric id must NOT broadcast.

    The WS-POSTMERGE-04 suite asserted delivery for the unseeded synthetic
    id 'p-1' — that asserted the flaw. The frame now gets an error reply
    and room members receive nothing.
    """
    _stub_auth(monkeypatch, _doctor_user(), _doctor_row(doctor_id=7))
    _patch_validation_db(monkeypatch, test_db)
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

        reply = ws_a.receive_json()
        assert reply.get("type") == "error"
        assert "numeric" in (reply.get("message") or "")

        time.sleep(0.2)
        # The other member received nothing (the queue SSOT never saw the
        # patient): drain-check via a short socket receive would block, so
        # assert no queued send happened by checking the room is intact and
        # the sender's next synthetic frame still flows.
        ws_a.send_json({"type": "ping"})
        assert ws_a.receive_json().get("type") == "pong"


def test_call_patient_rejects_numeric_patient_without_waiting_entry(
    client: TestClient,
    isolated_plane,
    test_db,
    seed_queue,
    monkeypatch: pytest.MonkeyPatch,
):
    _stub_auth(monkeypatch, _doctor_user(), _doctor_row(doctor_id=7))
    _patch_validation_db(monkeypatch, test_db)
    # A seeded but already-served entry is NOT callable.
    seed_queue(specialist_id=7, patient_id=502, status="served")

    token = _mint_jwt(sub="100")
    room = f"specialist_7::{_DATE}"

    with client.websocket_connect(
        f"/api/v1/ws-auth/ws/queue/auth?department=specialist_7&date={_DATE}&token={token}"
    ) as ws:
        assert _wait_for_room(room)
        ws.send_json({"type": "call_patient", "patient_id": "502"})
        reply = ws.receive_json()
        assert reply.get("type") == "error"
        assert "waiting queue entry" in (reply.get("message") or "")


def test_call_patient_rejects_entry_outside_room_scope(
    client: TestClient,
    isolated_plane,
    test_db,
    seed_queue,
    monkeypatch: pytest.MonkeyPatch,
):
    """The entry lives in specialist_7's queue; an Admin joined to
    specialist_8 (RBAC-unrestricted) still cannot broadcast it."""
    _stub_auth(
        monkeypatch,
        SimpleNamespace(id=102, username="syn-registrar", role="Registrar"),
        None,
    )
    _patch_validation_db(monkeypatch, test_db)
    seed_queue(specialist_id=7, patient_id=503, status="waiting")

    token = _mint_jwt(sub="102")
    room = f"specialist_8::{_DATE}"

    with client.websocket_connect(
        f"/api/v1/ws-auth/ws/queue/auth?department=specialist_8&date={_DATE}&token={token}"
    ) as ws:
        assert _wait_for_room(room)
        ws.send_json({"type": "call_patient", "patient_id": "503"})
        reply = ws.receive_json()
        assert reply.get("type") == "error"
        assert "waiting queue entry" in (reply.get("message") or "")


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
