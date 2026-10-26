"""Resolve exact service selections and capture their duration at write time."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.service import Service

MAX_SNAPSHOT_DURATION_MINUTES = 480


class InvalidServiceSelection(ValueError):
    """Raised when submitted service IDs are unknown or no longer active."""


@dataclass(frozen=True)
class ResolvedServiceSelection:
    service_ids: tuple[int, ...]
    names: tuple[str, ...]
    duration_minutes_snapshot: int | None


def resolve_exact_service_selection(
    db: Session,
    service_ids: list[int] | tuple[int, ...],
    *,
    doctor_id: int | None,
) -> ResolvedServiceSelection:
    """Resolve active catalog rows; only one compatible service has a duration.

    A snapshot is deliberately omitted for multi-service selections, a service
    assigned to another doctor, or an invalid duration. Callers must not infer
    a duration from display names or from a later catalog read.
    """
    ids = tuple(service_ids)
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value <= 0
        for value in ids
    ):
        raise InvalidServiceSelection("service_ids_invalid")
    if len(set(ids)) != len(ids):
        raise InvalidServiceSelection("service_ids_duplicate")
    if not ids:
        return ResolvedServiceSelection((), (), None)

    rows = db.query(Service).filter(Service.id.in_(ids), Service.active.is_(True)).all()
    rows_by_id = {row.id: row for row in rows}
    if len(rows_by_id) != len(ids):
        raise InvalidServiceSelection("service_not_found_or_inactive")

    ordered = [rows_by_id[service_id] for service_id in ids]
    duration: int | None = None
    if len(ordered) == 1 and doctor_id is not None:
        service = ordered[0]
        candidate = service.duration_minutes
        if (
            service.doctor_id in (None, doctor_id)
            and isinstance(candidate, int)
            and not isinstance(candidate, bool)
            and 1 <= candidate <= MAX_SNAPSHOT_DURATION_MINUTES
        ):
            duration = candidate

    return ResolvedServiceSelection(
        service_ids=ids,
        names=tuple(service.name for service in ordered),
        duration_minutes_snapshot=duration,
    )


def duration_snapshot_for_service_id(
    db: Session, service_id: int | None, *, doctor_id: int | None
) -> int | None:
    """Capture one VisitService duration from its active catalog row."""
    if (
        not isinstance(service_id, int)
        or isinstance(service_id, bool)
        or service_id <= 0
        or doctor_id is None
    ):
        return None
    try:
        resolved = resolve_exact_service_selection(
            db, [service_id], doctor_id=doctor_id
        )
    except InvalidServiceSelection:
        return None
    return resolved.duration_minutes_snapshot
