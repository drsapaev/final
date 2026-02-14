"""Repository helpers for display_websocket endpoints."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry


class DisplayWebSocketApiRepository:
    """Encapsulates queue/doctor lookups used by display websocket API."""

    def __init__(self, db: Session):
        self.db = db

    def get_queue_entry(self, entry_id: int) -> OnlineQueueEntry | None:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.id == entry_id)
            .first()
        )

    def save(self) -> None:
        self.db.commit()

    def list_active_entries_for_day(self, *, day: date) -> list[OnlineQueueEntry]:
        return (
            self.db.query(OnlineQueueEntry)
            .join(DailyQueue)
            .filter(DailyQueue.day == day, DailyQueue.active.is_(True))
            .all()
        )

    def get_active_doctor_by_specialty(self, specialty: str) -> Doctor | None:
        return (
            self.db.query(Doctor)
            .filter(Doctor.specialty == specialty, Doctor.active.is_(True))
            .first()
        )

    def get_daily_queue_for_specialist(
        self,
        *,
        day: date,
        specialist_id: int,
    ) -> DailyQueue | None:
        return (
            self.db.query(DailyQueue)
            .filter(
                DailyQueue.day == day,
                DailyQueue.specialist_id == specialist_id,
            )
            .first()
        )

    def get_next_waiting_entry(self, *, queue_id: int) -> OnlineQueueEntry | None:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.queue_id == queue_id,
                OnlineQueueEntry.status == "waiting",
            )
            .order_by(OnlineQueueEntry.number)
            .first()
        )
