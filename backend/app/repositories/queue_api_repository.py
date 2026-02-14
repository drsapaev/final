"""Repository helpers for queue legacy endpoints."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.user import User


class QueueApiRepository:
    """Encapsulates ORM operations used by legacy queue endpoints."""

    def __init__(self, db: Session):
        self.db = db

    def get_doctor_user(self, specialist_id: int) -> User | None:
        return (
            self.db.query(User)
            .filter(User.id == specialist_id, User.role == "Doctor")
            .first()
        )

    def get_daily_queue(self, *, day: date, specialist_id: int) -> DailyQueue | None:
        return (
            self.db.query(DailyQueue)
            .filter(DailyQueue.day == day, DailyQueue.specialist_id == specialist_id)
            .first()
        )

    def create_daily_queue(self, *, day: date, specialist_id: int) -> DailyQueue:
        daily_queue = DailyQueue(day=day, specialist_id=specialist_id, active=True)
        self.db.add(daily_queue)
        self.db.commit()
        self.db.refresh(daily_queue)
        return daily_queue

    def set_opened_at_now(self, daily_queue: DailyQueue) -> None:
        daily_queue.opened_at = datetime.now()
        self.db.commit()

    def get_doctor(self, specialist_id: int) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.id == specialist_id).first()

    def list_queue_entries(self, *, queue_id: int) -> list[OnlineQueueEntry]:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == queue_id)
            .order_by(OnlineQueueEntry.number)
            .all()
        )

    def get_queue_entry(self, entry_id: int) -> OnlineQueueEntry | None:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.id == entry_id)
            .first()
        )

    def mark_entry_called(self, entry: OnlineQueueEntry) -> None:
        entry.status = "called"
        entry.called_at = datetime.now()
        self.db.commit()
