from datetime import UTC, datetime

from app.services.confirmation_datetime import (
    is_confirmation_expired,
    normalize_confirmation_datetime,
)


def test_normalize_confirmation_datetime_treats_naive_values_as_utc():
    naive_value = datetime(2026, 3, 11, 12, 0, 0)

    normalized = normalize_confirmation_datetime(naive_value)

    assert normalized is not None
    assert normalized.tzinfo == UTC
    assert normalized.hour == 12


def test_is_confirmation_expired_handles_aware_and_naive_values_consistently():
    now = datetime(2026, 3, 11, 12, 0, 0, tzinfo=UTC)
    future_naive = datetime(2026, 3, 11, 12, 30, 0)
    expired_aware = datetime(2026, 3, 11, 11, 30, 0, tzinfo=UTC)

    assert is_confirmation_expired(future_naive, now=now) is False
    assert is_confirmation_expired(expired_aware, now=now) is True
