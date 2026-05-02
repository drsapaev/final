"""Repository helpers for queue_reorder endpoints."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.online_queue import DailyQueue, OnlineQueueEntry


class QueueReorderApiRepository:
    """Encapsulates ORM operations used for queue reorder operations."""

    ACTIVE_ENTRY_STATUSES = ["waiting", "called"]

    def __init__(self, db: Session):
        self.db = db

    def get_queue(self, queue_id: int) -> DailyQueue | None:
        return self.db.query(DailyQueue).filter(DailyQueue.id == queue_id).first()

    def get_queue_by_specialist_day(self, *, specialist_id: int, day: date) -> DailyQueue | None:
        return (
            self.db.query(DailyQueue)
            .filter(DailyQueue.specialist_id == specialist_id, DailyQueue.day == day)
            .first()
        )

    def list_active_entries(self, *, queue_id: int) -> list[OnlineQueueEntry]:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == queue_id,
                OnlineQueueEntry.status.in_(self.ACTIVE_ENTRY_STATUSES),
            )
            .order_by(OnlineQueueEntry.number)
            .all()
        )

    def get_active_entry(self, entry_id: int) -> OnlineQueueEntry | None:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.id == entry_id,
                OnlineQueueEntry.status.in_(self.ACTIVE_ENTRY_STATUSES),
            )
            .first()
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
