from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import telegram_bot as telegram_bot_endpoint
from app.models.telegram_config import TelegramConfig


def _configure_telegram_webhook(db_session, *, secret: str = "topsecret") -> None:
    db_session.add(
        TelegramConfig(
            bot_token="bot-token",
            webhook_secret=secret,
            active=True,
        )
    )
    db_session.commit()


def _enable_fake_bot(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    feed_update = AsyncMock()
    monkeypatch.setattr(telegram_bot_endpoint.telegram_bot, "bot", object())
    monkeypatch.setattr(
        telegram_bot_endpoint.telegram_bot,
        "dp",
        SimpleNamespace(feed_update=feed_update),
    )
    return feed_update


def test_telegram_bot_webhook_rejects_invalid_secret_before_json_parse(
    client: TestClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_telegram_webhook(db_session)
    feed_update = _enable_fake_bot(monkeypatch)

    response = client.post(
        "/api/v1/telegram/bot/webhook",
        content=b"{not-json",
        headers={
            "Content-Type": "application/json",
            "x-telegram-bot-api-secret-token": "wrong-secret",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid Telegram webhook secret"
    feed_update.assert_not_awaited()


def test_telegram_bot_webhook_rejects_oversized_json_before_dispatch(
    client: TestClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_telegram_webhook(db_session)
    feed_update = _enable_fake_bot(monkeypatch)
    monkeypatch.setattr(telegram_bot_endpoint, "MAX_TELEGRAM_WEBHOOK_BODY_BYTES", 3)

    response = client.post(
        "/api/v1/telegram/bot/webhook",
        content=b'{"update_id": 42}',
        headers={
            "Content-Type": "application/json",
            "x-telegram-bot-api-secret-token": "topsecret",
        },
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Telegram webhook payload is too large"
    feed_update.assert_not_awaited()
