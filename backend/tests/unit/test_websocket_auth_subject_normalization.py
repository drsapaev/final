from types import SimpleNamespace

import pytest

from app.api.v1.endpoints.display_websocket import (
    authenticate_websocket_token as authenticate_display_token,
)
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


def _user(*, epoch=0, active=True):
    return SimpleNamespace(id=19, username="admin@example.com", role="Admin",
                           auth_epoch=epoch, is_active=active, is_superuser=False)


@pytest.mark.asyncio
async def test_websocket_auth_accepts_numeric_string_subject(monkeypatch):
    payload = {"sub": "19"}
    expected_id = 19
    user = _user()
    db = DummyDB(user)

    monkeypatch.setattr(
        "app.api.v1.endpoints.websocket_auth.jwt.decode",
        lambda *_args, **_kwargs: payload,
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.websocket_auth.crud_user.get",
        lambda _db, id: user if id == expected_id else None,
    )

    # The shared validator now performs the user-scoped blacklist lookup even
    # for legacy synthetic payloads without a JTI.
    monkeypatch.setattr(
        "app.services.token_blacklist_service.TokenBlacklistService.is_token_blacklisted",
        lambda _db, _jti, user_id=None, *, auth_epoch=0: False,
    )

    authenticated = await authenticate_websocket_token("token", db)

    assert authenticated is user


@pytest.mark.asyncio
@pytest.mark.parametrize("subject", ["19"])
@pytest.mark.parametrize("jti", ["synthetic-jti-1", None])
async def test_websocket_auth_checks_all_user_revocation_for_resolved_subject(
    monkeypatch, subject, jti
):
    """The all-user sentinel must be checked by stable user ID, not JWT sub."""
    user = _user()
    db = DummyDB(user)
    payload = {"sub": subject}
    if jti is not None:
        payload["jti"] = jti

    monkeypatch.setattr(
        "app.api.v1.endpoints.websocket_auth.jwt.decode",
        lambda *_args, **_kwargs: payload,
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.websocket_auth.crud_user.get",
        lambda _db, id: user if id == 19 else None,
    )

    checked = []

    def blocked(_db, checked_jti, user_id=None, *, auth_epoch=0):
        checked.append((checked_jti, user_id))
        return True  # Synthetic active all_user_tokens sentinel

    monkeypatch.setattr(
        "app.services.token_blacklist_service.TokenBlacklistService.is_token_blacklisted",
        blocked,
    )

    assert await authenticate_websocket_token("signed-test-token", db) is None
    assert checked == [(jti or "", user.id)]


@pytest.mark.asyncio
@pytest.mark.parametrize("subject", [19, True, "19_1", "admin@example.com", "0", "١٩"])
async def test_websocket_auth_rejects_unstable_or_ambiguous_subject(monkeypatch, subject):
    user = _user()
    db = DummyDB(user)
    monkeypatch.setattr(
        "app.api.v1.endpoints.websocket_auth.jwt.decode",
        lambda *_args, **_kwargs: {"sub": subject, "jti": "synthetic-jti"},
    )
    # Even a lookup capable of resolving an unstable subject must not permit it.
    monkeypatch.setattr(
        "app.api.v1.endpoints.websocket_auth.crud_user.get",
        lambda *_args, **_kwargs: user,
    )
    assert await authenticate_websocket_token("signed-test-token", db) is None


@pytest.mark.asyncio
async def test_display_websocket_auth_reuses_subject_normalization(monkeypatch):
    user = _user()
    db = DummyDB(user)

    # DISPLAYAUTH-BE-001 (audit PR #3961): the display board WebSocket no
    # longer carries its own decode fork — it reuses the canonical
    # websocket_auth.authenticate_websocket_token (subject normalization +
    # TokenBlacklist revocation). Patch the canonical module only.
    monkeypatch.setattr(
        "app.api.v1.endpoints.websocket_auth.jwt.decode",
        lambda *_args, **_kwargs: {"sub": "19"},
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.websocket_auth.crud_user.get",
        lambda _db, id: user if id == 19 else None,
    )
    monkeypatch.setattr(
        "app.services.token_blacklist_service.TokenBlacklistService.is_token_blacklisted",
        lambda _db, _jti, user_id=None, *, auth_epoch=0: False,
    )

    authenticated = await authenticate_display_token("token", db)

    assert authenticated is user


@pytest.mark.asyncio
@pytest.mark.parametrize("subject", ["19"])
async def test_chat_websocket_auth_accepts_subject(monkeypatch, subject):
    user = _user()
    db = DummyDB(user)

    monkeypatch.setattr(
        "app.ws.chat_ws.jwt.decode",
        lambda *_args, **_kwargs: {"sub": subject},
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.websocket_auth.crud_user.get",
        lambda _db, id: user if id == 19 else None,
    )
    monkeypatch.setattr(
        "app.services.token_blacklist_service.TokenBlacklistService.is_token_blacklisted",
        lambda _db, _jti, user_id=None, *, auth_epoch=0: False,
    )

    authenticated = await authenticate_chat_websocket(None, "token", db)

    assert authenticated is user


@pytest.mark.asyncio
@pytest.mark.parametrize("subject", [19, True, "19_1", "admin@example.com", "0", "١٩"])
async def test_chat_websocket_auth_rejects_unstable_or_ambiguous_subject(monkeypatch, subject):
    user = _user()
    db = DummyDB(user)
    monkeypatch.setattr(
        "app.ws.chat_ws.jwt.decode",
        lambda *_args, **_kwargs: {"sub": subject},
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.websocket_auth.crud_user.get",
        lambda *_args, **_kwargs: user,
    )
    assert await authenticate_chat_websocket(None, "token", db) is None
