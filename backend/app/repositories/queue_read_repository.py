"""Read-only queue repository used by Wave 2C safe slices."""

from __future__ import annotations

from datetime import date
from typing import Sequence

from sqlalchemy.orm import Session

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.services.queue_status import REORDER_ACTIVE_RAW_STATUSES


class QueueReadRepository:
    """Encapsulates read-only queue lookups for the domain service."""

    def __init__(self, db: Session):
        self.db = db

    def get_queue(self, queue_id: int) -> DailyQueue | None:
        return self.db.query(DailyQueue).filter(DailyQueue.id == queue_id).first()

    def get_queue_by_specialist_day(
        self,
        *,
        specialist_id: int,
        day: date,
    ) -> DailyQueue | None:
        return (
            self.db.query(DailyQueue)
            .filter(
                DailyQueue.specialist_id == specialist_id,
                DailyQueue.day == day,
            )
            .first()
        )

    def list_snapshot_entries(
        self,
        *,
        queue_id: int,
        statuses: Sequence[str] = REORDER_ACTIVE_RAW_STATUSES,
    ) -> list[OnlineQueueEntry]:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == queue_id,
                OnlineQueueEntry.status.in_(tuple(statuses)),
            )
            .order_by(OnlineQueueEntry.number)
            .all()
        )
