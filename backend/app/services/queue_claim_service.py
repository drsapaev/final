"""Transaction-scoped identity claims across queues sharing a routing tag."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.crud.queue_resource_routing import lock_queue_tag_claim_scope
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.utils.validators import normalize_phone_uz

ACTIVE_TAG_CLAIM_STATUSES = (
    "waiting",
    "called",
    "in_service",
    "diagnostics",
    "in_progress",
)

_CONFLICT_MESSAGE = "Cannot unambiguously resolve an active queue claim"


class QueueClaimConflictError(RuntimeError):
    """Raised when supplied identifiers do not resolve to one safe claim."""

    def __init__(self) -> None:
        super().__init__(_CONFLICT_MESSAGE)


@dataclass(frozen=True, slots=True)
class ActiveQueueClaim:
    """An active queue entry together with its actual routing owner row."""

    daily_queue: DailyQueue
    entry: OnlineQueueEntry


def _normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    normalized = normalize_phone_uz(phone)
    return normalized.strip() or None


def _entry_name_matches(entry_name: str | None, patient_name: str) -> bool:
    """The typed-name narrowing of the legacy phone bridge (RQ-25.a.1
    S-22): a legacy row with the shared family phone belongs to THIS
    patient only when its stored entry name matches the supplied one."""
    return (entry_name or "").strip().casefold() == patient_name.strip().casefold()


def _normalize_telegram_id(telegram_id: int | str | None) -> int | None:
    if telegram_id in (None, ""):
        return None
    try:
        return int(str(telegram_id).strip())
    except (TypeError, ValueError):
        return None


def lock_and_resolve_active_tag_claim(
    db: Session,
    *,
    day: date,
    queue_tag: str,
    patient_id: int | None = None,
    phone: str | None = None,
    telegram_id: int | str | None = None,
    patient_name: str | None = None,
) -> ActiveQueueClaim | None:
    """Lock and resolve one active patient claim across an exact tag scope.

    The transaction advisory lock is acquired before any claim read. The caller
    owns the surrounding transaction and is responsible for comparing the
    returned queue owner with its intended owner before mutating anything.

    Identity signals are OR-matched and folded by queue-entry id. Two distinct
    matching entries are ambiguous. A contact match that points at another
    non-null patient id is also ambiguous. Both cases fail closed without
    exposing an identifier in the exception text.

    RQ-25.a.1 (S-22, the merged-main ruling reconciled onto the coordinator):
    the identity scope is the PATIENT, not the phone. ``patient_id`` is the
    primary signal; the phone arm only bridges LEGACY entries that carry no
    ``patient_id`` (narrowed by the typed entry name when ``patient_name``
    is supplied), so family members sharing one phone each keep their own
    claim instead of colliding. The telegram arm is unchanged.
    """
    lock_queue_tag_claim_scope(db, queue_tag, day)

    normalized_phone = _normalize_phone(phone)
    normalized_telegram_id = _normalize_telegram_id(telegram_id)
    if (
        patient_id is None
        and normalized_phone is None
        and normalized_telegram_id is None
    ):
        return None

    rows = (
        db.query(DailyQueue, OnlineQueueEntry)
        .join(OnlineQueueEntry, OnlineQueueEntry.queue_id == DailyQueue.id)
        .filter(
            DailyQueue.day == day,
            DailyQueue.queue_tag == queue_tag,
            DailyQueue.active.is_(True),
            OnlineQueueEntry.status.in_(ACTIVE_TAG_CLAIM_STATUSES),
        )
        .order_by(DailyQueue.id.asc(), OnlineQueueEntry.id.asc())
        .all()
    )

    candidates: dict[int, ActiveQueueClaim] = {}
    for daily_queue, entry in rows:
        matches_patient = patient_id is not None and entry.patient_id == patient_id
        # RQ-25.a.1 (S-22): the phone arm bridges only LEGACY entries with
        # no patient link (name-narrowed when the caller supplies the typed
        # name) — a typed row of ANOTHER patient sharing the family phone
        # is that patient's claim, never this one's.
        matches_phone = (
            normalized_phone is not None
            and entry.patient_id is None
            and _normalize_phone(entry.phone) == normalized_phone
            and (
                patient_name is None
                or _entry_name_matches(entry.patient_name, patient_name)
            )
        )
        matches_telegram = (
            normalized_telegram_id is not None
            and _normalize_telegram_id(entry.telegram_id) == normalized_telegram_id
        )
        if matches_patient or matches_phone or matches_telegram:
            candidates[entry.id] = ActiveQueueClaim(
                daily_queue=daily_queue,
                entry=entry,
            )

    if not candidates:
        return None
    if len(candidates) > 1:
        raise QueueClaimConflictError()

    claim = next(iter(candidates.values()))
    if (
        patient_id is not None
        and claim.entry.patient_id is not None
        and claim.entry.patient_id != patient_id
    ):
        raise QueueClaimConflictError()
    return claim
