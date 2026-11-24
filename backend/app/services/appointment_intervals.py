"""Shared clinic-local time and duration rules for appointment intervals."""

from datetime import datetime, time
from typing import TypeGuard

MAX_SERVICE_DURATION_MINUTES = 480


def clock_seconds(value: time | str | None) -> int | None:
    """Return the offset of a local wall-clock time."""
    if isinstance(value, str):
        parsed: time | None = None
        for format_string in ("%H:%M", "%H:%M:%S"):
            try:
                parsed = datetime.strptime(value, format_string).time()
                break
            except ValueError:
                continue
        value = parsed

    if not isinstance(value, time) or value.tzinfo is not None:
        return None
    if value.microsecond != 0:
        return None
    return value.hour * 3600 + value.minute * 60 + value.second


def clock_minutes(value: time | str | None) -> int | None:
    """Return a minute-aligned time for shift and availability calculations."""
    seconds = clock_seconds(value)
    return seconds // 60 if seconds is not None and seconds % 60 == 0 else None


def valid_duration(value: int | None) -> TypeGuard[int]:
    """Accept only trusted positive whole-minute duration snapshots."""
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 1 <= value <= MAX_SERVICE_DURATION_MINUTES
    )


def intervals_overlap(start: int, end: int, other_start: int, other_end: int) -> bool:
    """Compare half-open intervals. A shared endpoint is allowed."""
    return start < other_end and end > other_start
