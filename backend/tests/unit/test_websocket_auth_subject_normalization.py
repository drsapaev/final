from types import SimpleNamespace

import pytest

from app.api.v1.endpoints.display_websocket import authenticate_websocket_token as authenticate_display_token
from app.api.v1.endpoints.websocket_auth import authenticate_websocket_token
from app.ws.chat_ws import authenticate_websocket as authenticate_chat_websocket


class DummyQuery:
    def __init__(self, user):
        self.user = user

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.user


class DummyDB:
    def __init__(self, user):
        self.user = user

    def query(self, _model):
        return DummyQuery(self.user)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected_id"),
    [
        ({"sub": "19"}, 19),
        ({"sub": 19}, 19),
        ({"sub": "admin@example.com"}, 19),
    ],
)
async def test_websocket_auth_accepts_string_int_and_username(
    monkeypatch, payload, expected_id
):
    user = SimpleNamespace(id=19, username="admin@example.com")
    db = DummyDB(user)

    monkeypatch.setattr(
        "app.api.v1.endpoints.websocket_auth.jwt.decode",
        lambda *_args, **_kwargs: payload,
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.websocket_auth.crud_user.get",
        lambda _db, id: user if id == expected_id else None,
    )

    authenticated = await authenticate_websocket_token("token", db)

    assert authenticated is user


@pytest.mark.asyncio
async def test_display_websocket_auth_reuses_subject_normalization(monkeypatch):
    user = SimpleNamespace(id=19, username="admin@example.com")
    db = DummyDB(user)

    monkeypatch.setattr(
        "app.api.v1.endpoints.display_websocket.jwt.decode",
        lambda *_args, **_kwargs: {"sub": "19"},
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.websocket_auth.crud_user.get",
        lambda _db, id: user if id == 19 else None,
    )

    authenticated = await authenticate_display_token("token", db)

    assert authenticated is user


@pytest.mark.asyncio
async def test_chat_websocket_auth_accepts_numeric_subject(monkeypatch):
    user = SimpleNamespace(id=19, username="admin@example.com")
    db = DummyDB(user)

    monkeypatch.setattr(
        "app.ws.chat_ws.jwt.decode",
        lambda *_args, **_kwargs: {"sub": "19"},
    )

    authenticated = await authenticate_chat_websocket(None, "token", db)

    assert authenticated is user
