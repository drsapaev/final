from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import pytest

from app.services.telegram_mini_app_init_data import (
    TelegramMiniAppInitDataError,
    validate_telegram_mini_app_init_data,
)


BOT_TOKEN = "123456:test-mini-app-token"


def _signed_init_data(params: dict[str, str], bot_token: str = BOT_TOKEN) -> str:
    data_check_string = "\n".join(
        f"{key}={value}" for key, value in sorted(params.items())
    )
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    payload_hash = hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return urlencode({**params, "hash": payload_hash})


def test_validate_telegram_mini_app_init_data_accepts_signed_payload():
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    init_data = _signed_init_data(
        {
            "auth_date": str(int((now - timedelta(minutes=3)).timestamp())),
            "query_id": "AAEAAAE",
            "user": json.dumps(
                {"id": 42, "first_name": "Ali", "language_code": "ru"},
                separators=(",", ":"),
            ),
        }
    )

    result = validate_telegram_mini_app_init_data(
        init_data,
        bot_token=BOT_TOKEN,
        now=now,
    )

    assert result.user == {"id": 42, "first_name": "Ali", "language_code": "ru"}
    assert result.fields["query_id"] == "AAEAAAE"
    assert "hash" not in result.fields
    assert result.age_seconds == 180


def test_validate_telegram_mini_app_init_data_rejects_forged_hash():
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    init_data = _signed_init_data(
        {
            "auth_date": str(int(now.timestamp())),
            "query_id": "AAEAAAE",
            "user": json.dumps({"id": 42}, separators=(",", ":")),
        }
    ).replace("hash=", "hash=forged", 1)

    with pytest.raises(TelegramMiniAppInitDataError) as excinfo:
        validate_telegram_mini_app_init_data(
            init_data,
            bot_token=BOT_TOKEN,
            now=now,
        )

    assert excinfo.value.reason == "hash_mismatch"


def test_validate_telegram_mini_app_init_data_rejects_expired_auth_date():
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    init_data = _signed_init_data(
        {
            "auth_date": str(int((now - timedelta(days=2)).timestamp())),
            "query_id": "AAEAAAE",
            "user": json.dumps({"id": 42}, separators=(",", ":")),
        }
    )

    with pytest.raises(TelegramMiniAppInitDataError) as excinfo:
        validate_telegram_mini_app_init_data(
            init_data,
            bot_token=BOT_TOKEN,
            max_age_seconds=24 * 60 * 60,
            now=now,
        )

    assert excinfo.value.reason == "auth_date_expired"


def test_validate_telegram_mini_app_init_data_rejects_future_auth_date():
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    init_data = _signed_init_data(
        {
            "auth_date": str(int((now + timedelta(minutes=5)).timestamp())),
            "query_id": "AAEAAAE",
            "user": json.dumps({"id": 42}, separators=(",", ":")),
        }
    )

    with pytest.raises(TelegramMiniAppInitDataError) as excinfo:
        validate_telegram_mini_app_init_data(
            init_data,
            bot_token=BOT_TOKEN,
            max_future_skew_seconds=60,
            now=now,
        )

    assert excinfo.value.reason == "auth_date_in_future"


def test_validate_telegram_mini_app_init_data_rejects_duplicate_fields():
    now = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    init_data = _signed_init_data(
        {
            "auth_date": str(int(now.timestamp())),
            "query_id": "AAEAAAE",
            "user": json.dumps({"id": 42}, separators=(",", ":")),
        }
    )

    with pytest.raises(TelegramMiniAppInitDataError) as excinfo:
        validate_telegram_mini_app_init_data(
            f"{init_data}&query_id=duplicate",
            bot_token=BOT_TOKEN,
            now=now,
        )

    assert excinfo.value.reason == "duplicate_field"
