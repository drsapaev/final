"""Canonical QueueProfile manual and parent availability policy.

``QueueProfile.is_active`` records the administrator's manual archive
choice. A linked Department controls whether new booking is currently
available; it never overwrites that persisted choice. This module resolves
both documented parent conventions and fails closed for dangling or
conflicting links.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models.department import Department

AvailabilityState = Literal["available", "unavailable", "conflict"]


@dataclass(frozen=True)
class QueueProfileAvailability:
    """Persisted profile intent combined with its resolved parent state."""

    state: AvailabilityState
    is_available: bool
    reason_codes: tuple[str, ...]
    parent_department_key: str | None
    parent_active: bool | None

    def as_dict(self) -> dict[str, Any]:
        """Serialize safe configuration facts for existing admin read APIs."""
        return {
            "state": self.state,
            "is_available": self.is_available,
            "reason_codes": list(self.reason_codes),
            "parent_department_key": self.parent_department_key,
            "parent_active": self.parent_active,
        }


def normalize_department_key(value: Any) -> str | None:
    """Normalize the same blank-key convention used by profile updates."""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def resolve_queue_profile_availability(
    profile: Any,
    departments_by_key: dict[str, Department],
) -> QueueProfileAvailability:
    """Resolve one profile against a preloaded department map.

    An explicit ``department_key`` is a parent claim and must resolve. A
    matching profile/department key is the legacy own-profile convention
    only when that Department exists. If both conventions resolve to
    different departments, neither is selected.
    """
    profile_key = normalize_department_key(getattr(profile, "key", None))
    explicit_key = normalize_department_key(
        getattr(profile, "department_key", None)
    )
    explicit_parent = departments_by_key.get(explicit_key) if explicit_key else None
    own_parent = departments_by_key.get(profile_key) if profile_key else None

    reasons: list[str] = []
    if not bool(getattr(profile, "is_active", False)):
        reasons.append("manual_archived")

    if explicit_key and explicit_parent is None:
        reasons.append("parent_missing")

    if (
        explicit_parent is not None
        and own_parent is not None
        and explicit_parent.key != own_parent.key
    ):
        reasons.append("parent_conflict")
        resolved_parent = None
    elif explicit_parent is not None:
        resolved_parent = explicit_parent
    elif explicit_key:
        # A dangling explicit claim is not a standalone profile, even if an
        # unrelated own-key candidate exists.
        resolved_parent = None
        if own_parent is not None and own_parent.key != explicit_key:
            reasons.append("parent_conflict")
    else:
        resolved_parent = own_parent

    if resolved_parent is not None and not bool(resolved_parent.active):
        reasons.append("parent_inactive")

    has_parent_conflict = any(
        reason in {"parent_missing", "parent_conflict"} for reason in reasons
    )
    is_available = not reasons
    if has_parent_conflict:
        state: AvailabilityState = "conflict"
    elif is_available:
        state = "available"
    else:
        state = "unavailable"

    return QueueProfileAvailability(
        state=state,
        is_available=is_available,
        reason_codes=tuple(reasons),
        parent_department_key=(
            resolved_parent.key if resolved_parent is not None else None
        ),
        parent_active=(
            bool(resolved_parent.active) if resolved_parent is not None else None
        ),
    )


def load_queue_profile_availability(
    db: Session,
    profiles: list[Any] | tuple[Any, ...],
) -> dict[Any, QueueProfileAvailability]:
    """Resolve a collection with one bounded parent lookup (no N+1 reads)."""
    profile_rows = list(profiles)
    if not profile_rows:
        return {}

    candidate_keys: set[str] = set()
    for profile in profile_rows:
        for value in (
            getattr(profile, "department_key", None),
            getattr(profile, "key", None),
        ):
            normalized = normalize_department_key(value)
            if normalized:
                candidate_keys.add(normalized)

    departments_by_key: dict[str, Department] = {}
    if candidate_keys:
        departments = (
            db.query(Department)
            .filter(Department.key.in_(sorted(candidate_keys)))
            .all()
        )
        departments_by_key = {department.key: department for department in departments}

    return {
        profile: resolve_queue_profile_availability(profile, departments_by_key)
        for profile in profile_rows
    }


def queue_profile_is_qr_selectable(
    profile: Any,
    availability: QueueProfileAvailability,
) -> bool:
    """Return the shared profile/QR visibility contract for one profile."""
    return bool(
        normalize_department_key(getattr(profile, "key", None))
        and bool(getattr(profile, "is_active", False))
        and bool(getattr(profile, "show_on_qr_page", False))
        and availability.is_available
    )
