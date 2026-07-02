"""Central queue status vocabulary for Wave 2C Phase 1.

This module is intentionally compatibility-focused:
- it does not rewrite persisted queue statuses
- it keeps current raw-status query groups unchanged
- it exposes canonicalization only for internal comparisons
"""

from __future__ import annotations

from typing import Final

CANONICAL_QUEUE_STATUSES: Final[tuple[str, ...]] = (
    "waiting",
    "called",
    "in_service",
    "diagnostics",
    "served",
    "incomplete",
    "no_show",
    "cancelled",
    "rescheduled",
)

QUEUE_STATUS_ALIASES: Final[dict[str, str]] = {
    "canceled": "cancelled",
    "in_progress": "in_service",
    "completed": "served",
}

# Raw-status groups intentionally preserve current runtime behavior.
DUPLICATE_ACTIVE_RAW_STATUSES: Final[tuple[str, ...]] = ("waiting", "called")
REORDER_ACTIVE_RAW_STATUSES: Final[tuple[str, ...]] = ("waiting", "called")
POSITION_VISIBLE_RAW_STATUSES: Final[tuple[str, ...]] = (
    "waiting",
    "called",
    "in_service",
    "diagnostics",
)
SESSION_REUSE_RAW_STATUSES: Final[tuple[str, ...]] = (
    "waiting",
    "called",
    "in_service",
)


def normalize_queue_status(status: str | None) -> str | None:
    """Return the canonical status name for comparisons.

    The returned value is for internal logic only. Phase 1 keeps stored values
    and public payloads unchanged.
    """

    if status is None:
        return None

    normalized = status.strip().lower()
    return QUEUE_STATUS_ALIASES.get(normalized, normalized)


def is_visible_position_status(status: str | None) -> bool:
    raw_status = status.strip().lower() if status else None
    return raw_status in POSITION_VISIBLE_RAW_STATUSES


def is_reorder_active_status(status: str | None) -> bool:
    raw_status = status.strip().lower() if status else None
    return raw_status in REORDER_ACTIVE_RAW_STATUSES
