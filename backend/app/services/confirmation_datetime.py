from __future__ import annotations

from datetime import UTC, datetime


def confirmation_utc_now() -> datetime:
    return datetime.now(UTC)


def normalize_confirmation_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def is_confirmation_expired(
    expires_at: datetime | None,
    *,
    now: datetime | None = None,
) -> bool:
    normalized_expires_at = normalize_confirmation_datetime(expires_at)
    if normalized_expires_at is None:
        return False

    normalized_now = normalize_confirmation_datetime(now or confirmation_utc_now())
    assert normalized_now is not None
    return normalized_expires_at < normalized_now
