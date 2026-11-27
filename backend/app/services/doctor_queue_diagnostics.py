"""Pause/resume a doctor's existing visit without modifying clinical state."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.visit import Visit


def matches_active_doctor_visit(
    entry: OnlineQueueEntry,
    queue: DailyQueue | None,
    visit: Visit | None,
) -> bool:
    return bool(
        queue is not None
        and queue.active
        and queue.id == entry.queue_id
        and queue.queue_resource_id is None
        and queue.specialist_id is not None
        and entry.patient_id is not None
        and visit is not None
        and visit.id == entry.visit_id
        and visit.patient_id == entry.patient_id
        and visit.doctor_id == queue.specialist_id
        and visit.status == "in_progress"
    )


def lock_active_doctor_visit(
    db: Session,
    entry: OnlineQueueEntry,
    queue: DailyQueue | None,
) -> Visit | None:
    if entry.visit_id is None:
        return None
    visit = (
        db.query(Visit)
        .filter(Visit.id == entry.visit_id)
        .populate_existing()
        .with_for_update(of=Visit)
        .one_or_none()
    )
    return visit if matches_active_doctor_visit(entry, queue, visit) else None


def change_diagnostic_queue_status(
    db: Session,
    entry: OnlineQueueEntry,
    visit: Visit,
    *,
    from_status: str,
    to_status: str,
) -> datetime | None:
    """With the exact Visit locked, compare-and-set the queue row only."""
    changed_at = datetime.now(UTC)
    changed = (
        db.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.id == entry.id,
            OnlineQueueEntry.queue_id == entry.queue_id,
            OnlineQueueEntry.visit_id == visit.id,
            OnlineQueueEntry.patient_id == visit.patient_id,
            OnlineQueueEntry.status == from_status,
            OnlineQueueEntry.queue.has(
                DailyQueue.active.is_(True)
                & (DailyQueue.specialist_id == visit.doctor_id)
                & DailyQueue.queue_resource_id.is_(None)
            ),
        )
        .update(
            {
                OnlineQueueEntry.status: to_status,
                OnlineQueueEntry.updated_at: changed_at,
                OnlineQueueEntry.diagnostics_started_at: (
                    changed_at if to_status == "diagnostics" else None
                ),
            },
            synchronize_session=False,
        )
    )
    return changed_at if changed == 1 else None
