"""Synthetic role and specialist-scope guards for /ws/queue rooms.

Room identifiers represent Doctor.id, not User.id.  No real credentials,
database, Redis subscriptions or patient records are used by these tests.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import jwt
import pytest
from fastapi import WebSocketDisconnect, status

from app.core.config import settings
from app.ws import queue_ws


class _DoctorQuery:
    def __init__(self, doctor):
        self.doctor = doctor
        self.clauses = []

    def filter(self, *clauses):
        self.clauses.extend(clauses)
        return self

    def first(self):
        return self.doctor


class _Session:
    def __init__(self, doctor=None):
        self.closed = 0
        self.doctor = doctor
        self.query_count = 0
        self.doctor_query = _DoctorQuery(doctor)

    def query(self, _model):
        self.query_count += 1
        return self.doctor_query

    def close(self):
        self.closed += 1


def _signed(subject: str = "test-identity") -> str:
    return jwt.encode(
        {
            "sub": subject,
            "jti": "synthetic-queue-room-identity",
            "exp": datetime.now(UTC) + timedelta(minutes=10),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _patch_auth(
    monkeypatch: pytest.MonkeyPatch,
    *,
    role: str,
    user_id: int = 19,
    active: bool = True,
    superuser: bool = False,
    doctor_id: int | None = None,
    doctor_active: bool = True,
    revoked: bool = False,
):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("TESTING", "0")
    user = SimpleNamespace(
        id=user_id,
        role=role,
        is_active=active,
        is_superuser=superuser,
    )
    doctor = (
        SimpleNamespace(
            id=doctor_id, user_id=user_id, active=doctor_active
        )
        if doctor_id is not None and doctor_active else None
    )
    session = _Session(doctor=doctor)
    resolve = Mock(return_value=user)
    blacklist = Mock(return_value=revoked)
    monkeypatch.setattr("app.db.session.SessionLocal", lambda: session)
    monkeypatch.setattr(
        "app.api.v1.endpoints.websocket_auth._resolve_websocket_user",
        resolve,
    )
    monkeypatch.setattr(
        "app.services.token_blacklist_service.TokenBlacklistService.is_token_blacklisted",
        blacklist,
    )
    return session, resolve, blacklist


@pytest.mark.parametrize("role", ["Admin", "Registrar"])
def test_queue_manager_can_watch_other_specialist_room(monkeypatch, role):
    session, _resolve, blacklist = _patch_auth(monkeypatch, role=role)
    assert queue_ws._queue_room_permitted(
        _signed(), "specialist_101", "2026-11-11"
    )
    blacklist.assert_called_once()
    assert session.query_count == 0
    assert session.closed == 1


def test_superuser_retains_queue_management_access(monkeypatch):
    session, _resolve, _blacklist = _patch_auth(
        monkeypatch, role="Patient", superuser=True
    )
    assert queue_ws._queue_room_permitted(
        _signed(), "specialist_101", "2026-11-11"
    )
    assert session.closed == 1


@pytest.mark.parametrize(
    ("own_doctor", "selected_doctor", "allowed"),
    [
        (101, 101, True),
        (101, 102, False),
        (None, 101, False),
    ],
)
def test_doctor_can_watch_only_own_active_doctor_profile(
    monkeypatch, own_doctor, selected_doctor, allowed
):
    session, _resolve, _blacklist = _patch_auth(
        monkeypatch, role="Doctor", user_id=19, doctor_id=own_doctor
    )
    assert queue_ws._queue_room_permitted(
        _signed(), f"specialist_{selected_doctor}", "2026-11-11"
    ) is allowed
    assert session.query_count == 1
    assert session.closed == 1


@pytest.mark.parametrize(
    "role", ["Cashier", "Patient", "Lab", "Nurse", "UnknownRole"]
)
def test_non_queue_roles_cannot_watch_doctor_rooms(monkeypatch, role):
    session, _resolve, _blacklist = _patch_auth(monkeypatch, role=role)
    assert not queue_ws._queue_room_permitted(
        _signed(), "specialist_101", "2026-11-11"
    )
    assert session.query_count == 0
    assert session.closed == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"role": "Registrar", "active": False},
        {"role": "Doctor", "doctor_id": 101, "doctor_active": False},
        {"role": "Doctor", "doctor_id": 101, "revoked": True},
    ],
)
def test_inactive_or_revoked_staff_are_rejected(monkeypatch, kwargs):
    session, _resolve, _blacklist = _patch_auth(monkeypatch, **kwargs)
    assert not queue_ws._queue_room_permitted(
        _signed(), "specialist_101", "2026-11-11"
    )
    assert session.closed == 1


@pytest.mark.parametrize(
    ("room", "day"),
    [
        ("specialist_0", "2026-11-11"),
        ("specialist_1:other", "2026-11-11"),
        ("general", "2026-11-11"),
        ("specialist_2", "2026-99-99"),
        ("specialist_2", "2026-W46-3"),
    ],
)
def test_malformed_room_or_day_denied_without_database(
    monkeypatch, room, day
):
    called = Mock(side_effect=AssertionError("unexpected SessionLocal"))
    monkeypatch.setattr("app.db.session.SessionLocal", called)
    assert not queue_ws._queue_room_permitted(_signed(), room, day)
    called.assert_not_called()


def test_invalid_signature_denied_before_database(monkeypatch):
    called = Mock(side_effect=AssertionError("unexpected SessionLocal"))
    monkeypatch.setattr("app.db.session.SessionLocal", called)
    assert not queue_ws._queue_room_permitted(
        "invalid-synthetic-jwt", "specialist_101", "2026-11-11"
    )
    called.assert_not_called()


@pytest.mark.parametrize(
    ("room", "day"),
    [(None, "2026-11-11"), ("specialist_101", None), (17, "2026-11-11")],
)
def test_non_string_room_fields_are_denied_without_db(
    monkeypatch, room, day
):
    connect = Mock(side_effect=AssertionError("unexpected auth DB access"))
    monkeypatch.setattr("app.db.session.SessionLocal", connect)
    assert not queue_ws._queue_room_permitted(_signed(), room, day)
    connect.assert_not_called()


def test_authorization_database_unavailable_denies(monkeypatch):
    def unavailable():
        raise RuntimeError("synthetic database unavailable")

    monkeypatch.setattr("app.db.session.SessionLocal", unavailable)
    assert not queue_ws._queue_room_permitted(
        _signed(), "specialist_101", "2026-11-11"
    )



@pytest.mark.parametrize("use_own_room", [True, False])
def test_sqlalchemy_doctor_profile_owner_id_is_not_user_id(
    db_session, monkeypatch, use_own_room
):
    """Real ORM filter must bind Doctor.user_id, not JWT User.id as room."""
    from app.models.clinic import Doctor
    from app.models.user import User

    suffix = uuid4().hex[:12]
    user = User(
        username=f"synthetic_ws_{suffix}",
        email=f"synthetic_ws_{suffix}@example.test",
        full_name="Synthetic doctor",
        hashed_password="!disabled:synthetic-websocket-test",
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Intentional explicit mismatch: the room's Doctor.id is never User.id.
    doctor = Doctor(
        id=user.id + 500000,
        user_id=user.id,
        specialty="cardiology",
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    assert doctor.id != user.id

    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("TESTING", "0")
    monkeypatch.setattr("app.db.session.SessionLocal", lambda: db_session)
    monkeypatch.setattr(
        "app.services.token_blacklist_service.TokenBlacklistService.is_token_blacklisted",
        lambda _db, _jti, user_id=None: False,
    )

    selected = doctor.id if use_own_room else doctor.id + 1
    assert queue_ws._queue_room_permitted(
        _signed(str(user.id)), f"specialist_{selected}", "2026-11-11"
    ) is use_own_room


class _Socket:
    def __init__(self):
        self.headers = {"origin": "http://localhost:5173"}
        self.url = SimpleNamespace(path="/ws/queue", query="")
        self.query_params = {}
        self.sent = []
        self.closed = []
        self.accepted = False

    async def accept(self):
        self.accepted = True

    async def send_json(self, msg):
        self.sent.append(msg)

    async def close(self, code):
        self.closed.append(code)

    async def receive_text(self):
        raise WebSocketDisconnect(code=1000)


@pytest.mark.asyncio
async def test_queue_route_rejects_unauthorized_room_before_connect(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("TESTING", "0")
    monkeypatch.setattr(queue_ws, "_auth_ok", lambda *_args: True)
    monkeypatch.setattr(queue_ws, "_origin_allowed", lambda *_args: True)
    monkeypatch.setattr(
        queue_ws, "_queue_room_permitted", lambda *_args: False
    )
    manager = SimpleNamespace(connect=AsyncMock(), disconnect=Mock())
    monkeypatch.setattr(queue_ws, "ws_manager", manager)
    ws = _Socket()

    await queue_ws.ws_queue(ws, "specialist_777", "2026-11-11", "synthetic")
    assert ws.accepted
    assert ws.sent == [{"type": "error", "reason": "queue room access denied"}]
    assert ws.closed == [status.WS_1008_POLICY_VIOLATION]
    manager.connect.assert_not_awaited()
    manager.disconnect.assert_not_called()


@pytest.mark.asyncio
async def test_queue_route_allows_approved_scope(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("TESTING", "0")
    monkeypatch.setattr(queue_ws, "_auth_ok", lambda *_args: True)
    monkeypatch.setattr(queue_ws, "_origin_allowed", lambda *_args: True)
    monkeypatch.setattr(
        queue_ws, "_queue_room_permitted", lambda *_args: True
    )
    manager = SimpleNamespace(connect=AsyncMock(), disconnect=Mock())
    monkeypatch.setattr(queue_ws, "ws_manager", manager)
    ws = _Socket()

    await queue_ws.ws_queue(ws, "specialist_101", "2026-11-11", "synthetic")
    assert ws.sent == [
        {"type": "queue.connected", "room": "specialist_101::2026-11-11"}
    ]
    assert ws.closed == []
    manager.connect.assert_awaited_once_with(
        ws, "specialist_101::2026-11-11"
    )
    manager.disconnect.assert_called_once_with(
        ws, "specialist_101::2026-11-11"
    )
