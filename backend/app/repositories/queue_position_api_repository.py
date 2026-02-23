"""Repository helpers for queue_position endpoints."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.online_queue import DailyQueue, OnlineQueueEntry


class QueuePositionApiRepository:
    """Encapsulates queue/entry lookup queries for API layer."""

    def __init__(self, db: Session):
        self.db = db

    def get_entry(self, entry_id: int) -> OnlineQueueEntry | None:
        return self.db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()

    def get_diagnostics_entry(self, entry_id: int) -> OnlineQueueEntry | None:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.id == entry_id,
                OnlineQueueEntry.status == "diagnostics",
            )
            .first()
        )

    def get_waiting_entry(self, entry_id: int) -> OnlineQueueEntry | None:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.id == entry_id,
                OnlineQueueEntry.status == "waiting",
            )
            .first()
        )

    def get_queue(self, queue_id: int) -> DailyQueue | None:
        return self.db.query(DailyQueue).filter(DailyQueue.id == queue_id).first()

    def get_today_queue_by_specialist(self, *, specialist_id: int, day: date) -> DailyQueue | None:
        return (
            self.db.query(DailyQueue)
            .filter(
                DailyQueue.specialist_id == specialist_id,
                DailyQueue.day == day,
            )
            .first()
        )

    def get_queue_entry_by_number(
        self,
        *,
        queue_id: int,
        queue_number: int,
    ) -> OnlineQueueEntry | None:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == queue_id,
                OnlineQueueEntry.number == queue_number,
                OnlineQueueEntry.status != "cancelled",
            )
            .first()
        )

    def list_position_entries(self, *, queue_id: int) -> list[OnlineQueueEntry]:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == queue_id,
                OnlineQueueEntry.status.in_(["waiting", "called", "in_service", "diagnostics"]),
            )
            .order_by(
                OnlineQueueEntry.priority.desc(),
                OnlineQueueEntry.queue_time,
            )
            .all()
        )

