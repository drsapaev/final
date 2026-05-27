from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import telegram_webhook_enhanced
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


def test_enhanced_telegram_webhook_rejects_invalid_secret_before_json_parse(
    client: TestClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called():
        raise AssertionError("enhanced Telegram bot should not be resolved")

    _configure_telegram_webhook(db_session)
    monkeypatch.setattr(
        telegram_webhook_enhanced,
        "get_enhanced_telegram_bot",
        fail_if_called,
    )

    response = client.post(
        "/api/v1/telegram/webhook/enhanced",
        content=b"{not-json",
        headers={
            "Content-Type": "application/json",
            "x-telegram-bot-api-secret-token": "wrong-secret",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid Telegram webhook secret"


def test_enhanced_telegram_webhook_rejects_oversized_json_before_dispatch(
    client: TestClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called():
        raise AssertionError("enhanced Telegram bot should not be resolved")

    _configure_telegram_webhook(db_session)
    monkeypatch.setattr(
        telegram_webhook_enhanced,
        "get_enhanced_telegram_bot",
        fail_if_called,
    )
    monkeypatch.setattr(
        telegram_webhook_enhanced,
        "MAX_TELEGRAM_ENHANCED_WEBHOOK_BODY_BYTES",
        3,
    )

    response = client.post(
        "/api/v1/telegram/webhook/enhanced",
        content=b'{"update_id": 42}',
        headers={
            "Content-Type": "application/json",
            "x-telegram-bot-api-secret-token": "topsecret",
        },
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "Telegram webhook payload is too large"
