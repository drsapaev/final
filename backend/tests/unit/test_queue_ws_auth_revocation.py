"""Synthetic regressions for standalone queue WS JWT revocation by user ID.

These tests use signed disposable JWTs, fake DB sessions, and an in-memory
blacklist probe. They do not access actual clinic users or production secrets.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import jwt
import pytest

from app.core.config import settings
from app.ws import queue_ws


def _signed_token(subject: str, jti: str | None) -> str:
    payload = {
        "sub": subject,
        "exp": datetime.now(UTC) + timedelta(minutes=10),
    }
    if jti is not None:
        payload["jti"] = jti
    return jwt.encode(
        payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )


def _configure_production_auth(
    monkeypatch: pytest.MonkeyPatch,
    *,
    resolved_user_id: int | None = 81,
    revoked: bool = False,
) -> tuple[Mock, Mock, Mock]:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("TESTING", "1")  # parent PR requires real JWT in prod

    session = SimpleNamespace(close=Mock())
    monkeypatch.setattr("app.db.session.SessionLocal", lambda: session)
    user = (
        SimpleNamespace(id=resolved_user_id, role="Doctor")
        if resolved_user_id is not None
        else None
    )
    resolver = Mock(return_value=user)
    monkeypatch.setattr(
        "app.api.v1.endpoints.websocket_auth._resolve_websocket_user",
        resolver,
    )
    blacklist = Mock(return_value=revoked)
    monkeypatch.setattr(
        "app.services.token_blacklist_service.TokenBlacklistService.is_token_blacklisted",
        blacklist,
    )
    return resolver, blacklist, session.close


@pytest.mark.parametrize("subject", ["synthetic-doctor", "81"])
@pytest.mark.parametrize("jti", ["synthetic-jti-81", None])
def test_queue_websocket_rejects_individual_or_all_user_revocation(
    monkeypatch: pytest.MonkeyPatch, subject: str, jti: str | None
) -> None:
    resolver, blacklist, close = _configure_production_auth(
        monkeypatch, revoked=True
    )
    token = _signed_token(subject, jti)

    assert queue_ws._auth_ok({"authorization": f"Bearer {token}"}, None) is False
    resolver.assert_called_once()
    blacklist.assert_called_once()
    args, kwargs = blacklist.call_args
    assert args[1] == (jti or "")
    assert kwargs == {"user_id": 81}
    close.assert_called_once()


@pytest.mark.parametrize("subject", ["synthetic-doctor", "81"])
@pytest.mark.parametrize("jti", ["synthetic-jti-81", None])
def test_queue_websocket_accepts_unrevoked_resolved_user(
    monkeypatch: pytest.MonkeyPatch, subject: str, jti: str | None
) -> None:
    resolver, blacklist, close = _configure_production_auth(monkeypatch)
    token = _signed_token(subject, jti)

    assert queue_ws._auth_ok({"authorization": f"Bearer {token}"}, None) is True
    resolver.assert_called_once()
    blacklist.assert_called_once()
    assert blacklist.call_args.kwargs == {"user_id": 81}
    close.assert_called_once()


def test_queue_websocket_rejects_nonexistent_user_before_blacklist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver, blacklist, close = _configure_production_auth(
        monkeypatch, resolved_user_id=None
    )
    token = _signed_token("nonexistent-synthetic-user", "synthetic-jti-81")

    assert queue_ws._auth_ok({"authorization": f"Bearer {token}"}, None) is False
    resolver.assert_called_once()
    blacklist.assert_not_called()
    close.assert_called_once()
