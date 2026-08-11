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

# Terminal queue statuses: no outgoing transitions. A batch update or
# cancel action on a terminal queue entry must be rejected — the entry
# has reached a final state and must not be silently regressed.
#
# P2-2 (post-merge stabilization): added to close the
# batch_patient_service._update_entry bypass where a cancelled queue
# entry could be resurrected by a direct entry.status = action.status
# mutation (no state machine check, no terminal-status filter in
# _find_online_queue_entry_for_action).
#
# Active statuses are exactly POSITION_VISIBLE_RAW_STATUSES — anything
# else in CANONICAL_QUEUE_STATUSES is terminal. This deliberately does
# NOT introduce a competing definition of "active"; it reuses the
# existing canonical vocabulary.
TERMINAL_QUEUE_STATUSES: Final[frozenset[str]] = frozenset(
    s for s in CANONICAL_QUEUE_STATUSES if s not in POSITION_VISIBLE_RAW_STATUSES
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


def is_terminal_queue(status: str | None) -> bool:
    """Return True if a queue status is terminal (no outgoing transitions).

    Terminal statuses are: served, incomplete, no_show, cancelled,
    rescheduled. Anything in POSITION_VISIBLE_RAW_STATUSES (waiting,
    called, in_service, diagnostics) is non-terminal.

    Used by batch_patient_service to reject update/cancel actions on
    queue entries that have reached a final state.
    """
    if not status:
        return False
    raw_status = status.strip().lower()
    canonical = QUEUE_STATUS_ALIASES.get(raw_status, raw_status)
    return canonical in TERMINAL_QUEUE_STATUSES
