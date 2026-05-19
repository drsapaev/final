"""Telegram Mini App initData validation helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl


DEFAULT_MAX_AUTH_AGE_SECONDS = 24 * 60 * 60
DEFAULT_MAX_FUTURE_SKEW_SECONDS = 60
_HASH_FIELD = "hash"
_AUTH_DATE_FIELD = "auth_date"


class TelegramMiniAppInitDataError(ValueError):
    """Raised when Telegram Mini App initData cannot be trusted."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class TelegramMiniAppInitData:
    """Validated Telegram Mini App initData without the untrusted hash field."""

    fields: dict[str, str]
    auth_date: datetime
    age_seconds: int
    user: dict[str, Any] | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_init_data(init_data: str) -> dict[str, str]:
    pairs = parse_qsl(str(init_data or ""), keep_blank_values=True, strict_parsing=False)
    fields: dict[str, str] = {}
    for key, value in pairs:
        key_text = str(key)
        if key_text in fields:
            raise TelegramMiniAppInitDataError("duplicate_field")
        fields[key_text] = str(value)
    return fields


def _data_check_string(fields: dict[str, str]) -> str:
    return "\n".join(
        f"{key}={value}" for key, value in sorted(fields.items()) if key != _HASH_FIELD
    )


def _expected_hash(data_check_string: str, bot_token: str) -> str:
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return hmac.new(
        secret_key,
        data_check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _parse_auth_date(value: str) -> datetime:
    try:
        timestamp = int(value)
    except (TypeError, ValueError) as exc:
        raise TelegramMiniAppInitDataError("invalid_auth_date") from exc
    return datetime.fromtimestamp(timestamp, timezone.utc)


def _parse_user(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise TelegramMiniAppInitDataError("invalid_user_json") from exc
    if not isinstance(parsed, dict):
        raise TelegramMiniAppInitDataError("invalid_user_json")
    return parsed


def validate_telegram_mini_app_init_data(
    init_data: str,
    *,
    bot_token: str,
    max_age_seconds: int = DEFAULT_MAX_AUTH_AGE_SECONDS,
    max_future_skew_seconds: int = DEFAULT_MAX_FUTURE_SKEW_SECONDS,
    now: datetime | None = None,
) -> TelegramMiniAppInitData:
    """Validate Telegram Mini App initData before trusting Mini App identity."""

    token = str(bot_token or "").strip()
    if not token:
        raise TelegramMiniAppInitDataError("bot_token_required")

    fields = _parse_init_data(init_data)
    received_hash = fields.get(_HASH_FIELD)
    if not received_hash:
        raise TelegramMiniAppInitDataError("hash_required")
    if _AUTH_DATE_FIELD not in fields:
        raise TelegramMiniAppInitDataError("auth_date_required")

    data_check_string = _data_check_string(fields)
    expected_hash = _expected_hash(data_check_string, token)
    if not hmac.compare_digest(received_hash, expected_hash):
        raise TelegramMiniAppInitDataError("hash_mismatch")

    checked_at = now or _utc_now()
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    else:
        checked_at = checked_at.astimezone(timezone.utc)

    auth_date = _parse_auth_date(fields[_AUTH_DATE_FIELD])
    age_seconds = int((checked_at - auth_date).total_seconds())
    if age_seconds > int(max_age_seconds):
        raise TelegramMiniAppInitDataError("auth_date_expired")
    if age_seconds < -int(max_future_skew_seconds):
        raise TelegramMiniAppInitDataError("auth_date_in_future")

    trusted_fields = {key: value for key, value in fields.items() if key != _HASH_FIELD}
    return TelegramMiniAppInitData(
        fields=trusted_fields,
        auth_date=auth_date,
        age_seconds=age_seconds,
        user=_parse_user(trusted_fields.get("user")),
    )
