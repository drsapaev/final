"""Fail-closed queue WebSocket authentication with TESTING set in production.

All JWTs are synthetic and all sessions/sockets are fakes. The regression
guards a production misconfiguration; normal development pytest bypass
behavior remains unchanged for compatibility.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import jwt
import pytest
from fastapi import status

from app.core.config import settings
from app.ws import queue_ws


@pytest.mark.parametrize(
    "environment", ["prod", "production", "PRODUCTION", "staging", "qa"]
)
@pytest.mark.parametrize(
    "headers, token", [({}, None), ({"authorization": "Bearer not-a-jwt"}, None)]
)
def test_testing_flag_cannot_accept_missing_or_invalid_jwt_in_production(
    monkeypatch: pytest.MonkeyPatch,
    environment: str,
    headers: dict[str, str],
    token: str | None,
) -> None:
    monkeypatch.setenv("ENV", environment)
    monkeypatch.setenv("TESTING", "1")

    assert queue_ws._auth_ok(headers, token) is False


def test_testing_flag_still_allows_synthetic_dev_connections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("TESTING", "1")

    assert queue_ws._auth_ok({}, None) is True


def test_production_testing_flag_allows_only_verified_signed_jwt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("TESTING", "1")
    token = jwt.encode(
        {
            "sub": "417",
            "jti": "synthetic-queue-token-417",
            "exp": datetime.now(UTC) + timedelta(minutes=10),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    fake_session = SimpleNamespace(close=Mock())
    monkeypatch.setattr(
        "app.db.session.SessionLocal",
        lambda: fake_session,
    )
    resolve = Mock(return_value=SimpleNamespace(id=417, role="Doctor"))
    monkeypatch.setattr(
        "app.api.v1.endpoints.websocket_auth._resolve_websocket_user",
        resolve,
    )
    blacklist = Mock(return_value=False)
    monkeypatch.setattr(
        "app.services.token_blacklist_service.TokenBlacklistService.is_token_blacklisted",
        blacklist,
    )

    assert queue_ws._auth_ok({"authorization": f"Bearer {token}"}, None) is True
    assert resolve.call_count == 1
    blacklist.assert_called_once_with(
        fake_session, "synthetic-queue-token-417", user_id=417
    )
    fake_session.close.assert_called_once()


class _SyntheticQueueSocket:
    def __init__(self, *, token: str | None = None) -> None:
        self.headers = {"origin": "http://localhost:5173"}
        if token:
            self.headers["authorization"] = f"Bearer {token}"
        self.query_params = {}
        self.url = SimpleNamespace(path="/ws/queue", query="")
        self.accepted = False
        self.sent: list[dict] = []
        self.closed: list[int] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        self.sent.append(message)

    async def close(self, code: int) -> None:
        self.closed.append(code)


@pytest.mark.asyncio
@pytest.mark.parametrize("environment", ["prod", "production"])
@pytest.mark.parametrize("token", [None, "synthetic-invalid-jwt"])
async def test_production_queue_route_denies_unverified_connection_even_in_testing(
    monkeypatch: pytest.MonkeyPatch,
    environment: str,
    token: str | None,
) -> None:
    monkeypatch.setenv("ENV", environment)
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("CORS_DISABLE", "0")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")

    fake_socket = _SyntheticQueueSocket(token=token)
    manager = SimpleNamespace(connect=AsyncMock(), disconnect=Mock())
    monkeypatch.setattr(queue_ws, "ws_manager", manager)

    await queue_ws.ws_queue(fake_socket, "specialist_417", "2026-11-10")

    assert fake_socket.accepted is True
    assert fake_socket.sent == [
        {"type": "error", "reason": "Authentication required in production"}
    ]
    assert fake_socket.closed == [status.WS_1008_POLICY_VIOLATION]
    manager.connect.assert_not_awaited()
    manager.disconnect.assert_not_called()
