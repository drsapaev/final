from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.api.v1.endpoints.registrar_integration import _serialize_registrar_datetime


def test_serialize_registrar_datetime_preserves_aware_offset() -> None:
    value = datetime(2026, 4, 16, 9, 30, tzinfo=ZoneInfo("Asia/Tashkent"))

    result = _serialize_registrar_datetime(value)

    assert result == "2026-04-16T09:30:00+05:00"


def test_serialize_registrar_datetime_normalizes_naive_to_utc() -> None:
    value = datetime(2026, 4, 16, 4, 30)

    result = _serialize_registrar_datetime(value)

    assert result == "2026-04-16T04:30:00+00:00"


def test_serialize_registrar_datetime_keeps_iso_strings_unchanged() -> None:
    value = "2026-04-16T09:30:00+05:00"

    result = _serialize_registrar_datetime(value)

    assert result == value
