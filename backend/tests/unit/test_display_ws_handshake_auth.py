"""Display WebSocket handshake authorization plane — audit PR #3961 findings.

Covers five source-observed findings from the 2026-11-09 queue-position /
notifications audit (draft PR #3961), display board handshake plane:

- DISPLAYWS-BE-001 (P1): ``/api/v1/display/ws/queue/{department}`` accepted a
  completely anonymous connection and sent patient names / queue rows before
  any credential check. Contract now: no token, invalid token or non-staff
  principal ⇒ policy close 1008 BEFORE ``manager.connect`` and BEFORE any
  department snapshot payload.
- DISPLAYWS-BE-002 (P1): ``/ws/board/{board_id}`` accepted ANY authenticated
  user (e.g. role=Patient) and sent the full clinic-day snapshot. Contract
  now: only display-staff principals (Admin/Registrar/Doctor-family or
  superuser) may subscribe; patient-role tokens are closed 1008 before any
  registration or snapshot.
- DISPLAYAUTH-BE-001 (P1): the board handshake must reject blacklisted JWTs
  (exact revoked ``jti`` and the ``all_user_tokens`` sentinel) exactly like
  canonical HTTP auth and the queue WebSocket already do — by reusing the
  canonical ``websocket_auth.authenticate_websocket_token`` instead of the
  previous display-local decode fork.
- DISPLAYAUTH-BE-002 (P1/P2): a disabled account (``User.is_active=False``)
  must not authenticate ANY WebSocket handshake — enforced centrally in
  ``websocket_auth._resolve_websocket_user``.
- DISPLAYSESSION-BE-002 (P2): the board handshake must release its auth DB
  session (``SessionLocal()``) on every path — including before entering the
  long-lived receive loop of a valid connection, not only at GC time.

Synthetic fixtures only: in-memory SQLite with the real ``users`` /
``token_blacklist`` tables, synthetic users, self-minted JWTs, stub display
manager and stub department-snapshot service. No real patients, no network,
no Redis. Tests call the endpoint coroutines directly.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from fastapi import WebSocketDisconnect
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.api.v1.endpoints.display_websocket as dw
from app.api.v1.endpoints.websocket_auth import _resolve_websocket_user
from app.core.config import settings
from app.db.base_class import Base
from app.models.authentication import TokenBlacklist
from app.models.user import User

# ---------------------------------------------------------------- fixtures


@pytest.fixture()
def handshake_env(monkeypatch):
    """Shared in-memory SQLite (users + token_blacklist) + stub manager."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[User.__table__, TokenBlacklist.__table__])
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    closed_sessions: list[int] = []

    real_session_cls = sessionmaker(bind=engine, autoflush=False).class_

    class _SpySession(real_session_cls):  # type: ignore[misc,valid-type]
        def close(self):  # noqa: D102
            closed_sessions.append(id(self))
            return super().close()

    spy_factory = sessionmaker(
        class_=_SpySession, bind=engine, autoflush=False, expire_on_commit=False
    )

    class _StubManager:
        def __init__(self):
            self.connected: list[dict] = []
            self.disconnected: list[str] = []

        async def connect(self, websocket, board_id, user=None):
            self.connected.append({"board_id": board_id, "user": user})

        async def disconnect(self, websocket, board_id):
            self.disconnected.append(board_id)

    manager = _StubManager()

    dept_calls: list[str] = []

    class _StubService:
        def __init__(self, db):
            self.db = db

        def get_department_queue_state_payload(self, *, department: str) -> dict:
            dept_calls.append(department)
            return {
                "type": "initial_state",
                "department": department,
                "entries": [],
            }

    monkeypatch.setattr(dw, "SessionLocal", spy_factory)
    monkeypatch.setattr(dw, "get_display_manager", lambda: manager)
    monkeypatch.setattr(dw, "DisplayWebSocketApiService", _StubService)

    return SimpleNamespace(
        manager=manager,
        dept_calls=dept_calls,
        closed_sessions=closed_sessions,
        factory=factory,
    )


class _FakeWebSocket:
    """Minimal WebSocket double: Bearer-token header + close/send recording."""

    def __init__(self, token: str | None = None, incoming: list[str] | None = None):
        self.headers = {"authorization": f"Bearer {token}"} if token else {}
        self.query_params = SimpleNamespace(get=lambda _k: None)
        self.client = SimpleNamespace(host="synthetic-test")
        self.closes: list[tuple[int | None, str | None]] = []
        self.sent: list[str] = []
        self._incoming = list(incoming or [])

    async def accept(self, subprotocol: str | None = None) -> None:
        return None

    async def close(self, code: int | None = None, reason: str | None = None) -> None:
        self.closes.append((code, reason))

    async def send_text(self, data: str) -> None:
        self.sent.append(data)

    async def receive_text(self) -> str:
        if self._incoming:
            return self._incoming.pop(0)
        raise WebSocketDisconnect()


# ------------------------------------------------------------- data helpers


def _make_user(factory, *, role: str, is_active: bool = True, username: str) -> User:
    session = factory()
    try:
        user = User(
            username=username,
            full_name=f"Synthetic {username}",
            hashed_password="x",
            role=role,
            is_active=is_active,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    finally:
        session.close()


def _mint(user: User, *, jti: str | None = None) -> str:
    payload = {
        "sub": str(user.id),
        "type": "access",
        "jti": jti or str(uuid.uuid4()),
        "exp": datetime.now(UTC) + timedelta(minutes=10),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _blacklist_exact_jti(factory, user: User, jti: str) -> None:
    session = factory()
    try:
        session.add(
            TokenBlacklist(
                jti=jti,
                user_id=user.id,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                reason="logout",
            )
        )
        session.commit()
    finally:
        session.close()


def _blacklist_all_user_tokens(factory, user: User) -> None:
    session = factory()
    try:
        session.add(
            TokenBlacklist(
                jti=f"all_user_tokens:{user.id}-{uuid.uuid4()}",
                user_id=user.id,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                reason="all_user_tokens:security",
            )
        )
        session.commit()
    finally:
        session.close()


# ----------------------------------------------- DISPLAYWS-BE-001 (department)


def test_department_ws_rejects_missing_token_before_any_payload(handshake_env):
    ws = _FakeWebSocket(token=None)
    asyncio.run(dw.websocket_queue_department(ws, "cardiology"))

    assert ws.closes, "anonymous department WS must be closed"
    code, reason = ws.closes[0]
    assert code == 1008
    assert handshake_env.manager.connected == [], "must not register the socket"
    assert handshake_env.dept_calls == [], "must not build/send any snapshot"
    assert ws.sent == [], "no payload may leak to an anonymous socket"


def test_department_ws_rejects_garbage_token_before_any_payload(handshake_env):
    ws = _FakeWebSocket(token="not-a-jwt")
    asyncio.run(dw.websocket_queue_department(ws, "cardiology"))

    assert ws.closes and ws.closes[0][0] == 1008
    assert handshake_env.manager.connected == []
    assert handshake_env.dept_calls == []
    assert ws.sent == []


def test_department_ws_rejects_patient_role(handshake_env):
    patient = _make_user(handshake_env.factory, role="Patient", username="dept_pat")
    ws = _FakeWebSocket(token=_mint(patient))
    asyncio.run(dw.websocket_queue_department(ws, "cardiology"))

    assert ws.closes and ws.closes[0][0] == 1008
    assert handshake_env.manager.connected == []
    assert handshake_env.dept_calls == []
    assert ws.sent == []


def test_department_ws_accepts_registrar_and_sends_snapshot(handshake_env):
    reg = _make_user(handshake_env.factory, role="Registrar", username="dept_reg")
    ws = _FakeWebSocket(token=_mint(reg), incoming=[])
    asyncio.run(dw.websocket_queue_department(ws, "cardiology"))

    assert ws.closes == [], "authorized staff must not be policy-closed"
    assert [c["board_id"] for c in handshake_env.manager.connected] == [
        "dept_cardiology"
    ]
    assert handshake_env.dept_calls == ["cardiology"]
    assert ws.sent and "initial_state" in ws.sent[0]


# ------------------------------------------------- DISPLAYWS-BE-002 (board)


def test_board_ws_rejects_patient_role_before_registration(handshake_env):
    patient = _make_user(handshake_env.factory, role="Patient", username="board_pat")
    ws = _FakeWebSocket(token=_mint(patient))
    asyncio.run(dw.websocket_display_board(ws, "main_board"))

    assert ws.closes and ws.closes[0][0] == 1008
    assert handshake_env.manager.connected == [], "patient must not subscribe"
    assert ws.sent == [], "no initial_state may reach a patient-role socket"


def test_board_ws_accepts_registrar_and_releases_auth_session(handshake_env):
    reg = _make_user(handshake_env.factory, role="Registrar", username="board_reg")
    ws = _FakeWebSocket(token=_mint(reg), incoming=[])
    asyncio.run(dw.websocket_display_board(ws, "main_board"))

    assert ws.closes == []
    assert len(handshake_env.manager.connected) == 1
    conn = handshake_env.manager.connected[0]
    assert conn["board_id"] == "main_board"
    assert getattr(conn["user"], "id", None) == reg.id
    # DISPLAYSESSION-BE-002: the auth session must be closed on the happy
    # path BEFORE the long-lived receive loop, not left to GC.
    assert handshake_env.closed_sessions, "auth DB session was never closed"


# -------------------------------------------- DISPLAYAUTH-BE-001 (revocation)


def test_board_ws_rejects_exact_blacklisted_jti(handshake_env):
    reg = _make_user(handshake_env.factory, role="Registrar", username="revoke_reg")
    jti = str(uuid.uuid4())
    _blacklist_exact_jti(handshake_env.factory, reg, jti)
    ws = _FakeWebSocket(token=_mint(reg, jti=jti))
    asyncio.run(dw.websocket_display_board(ws, "main_board"))

    assert ws.closes and ws.closes[0][0] == 1008
    assert handshake_env.manager.connected == []
    assert ws.sent == []


def test_board_ws_rejects_all_user_tokens_sentinel(handshake_env):
    reg = _make_user(handshake_env.factory, role="Registrar", username="sentinel_reg")
    _blacklist_all_user_tokens(handshake_env.factory, reg)
    ws = _FakeWebSocket(token=_mint(reg))
    asyncio.run(dw.websocket_display_board(ws, "main_board"))

    assert ws.closes and ws.closes[0][0] == 1008
    assert handshake_env.manager.connected == []
    assert ws.sent == []


# --------------------------------------------- DISPLAYAUTH-BE-002 (is_active)


def test_board_ws_rejects_inactive_user(handshake_env):
    inactive = _make_user(
        handshake_env.factory, role="Registrar", is_active=False, username="off_reg"
    )
    ws = _FakeWebSocket(token=_mint(inactive))
    asyncio.run(dw.websocket_display_board(ws, "main_board"))

    assert ws.closes and ws.closes[0][0] == 1008
    assert handshake_env.manager.connected == []
    assert ws.sent == []


def test_resolve_websocket_user_rejects_inactive_user_central(handshake_env):
    """DISPLAYAUTH-BE-002 is fixed at the shared resolver (queue WS parity)."""
    inactive = _make_user(
        handshake_env.factory, role="Doctor", is_active=False, username="off_doc"
    )
    session = handshake_env.factory()
    try:
        assert _resolve_websocket_user({"sub": str(inactive.id)}, session) is None
        active = _make_user(handshake_env.factory, role="Doctor", username="on_doc")
        resolved = _resolve_websocket_user({"sub": str(active.id)}, session)
        assert getattr(resolved, "id", None) == active.id
    finally:
        session.close()
