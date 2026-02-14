"""Repository helpers for queue_limits endpoints."""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry


class QueueLimitsRepository:
    """Encapsulates doctor/queue lookups used by queue limit API."""

    def __init__(self, db: Session):
        self.db = db

    def list_active_doctors(self, *, specialty: str | None) -> list[Doctor]:
        query = self.db.query(Doctor).filter(Doctor.active.is_(True))
        if specialty:
            query = query.filter(Doctor.specialty == specialty)
        return query.all()

    def get_daily_queue(self, *, day: date, specialist_id: int) -> DailyQueue | None:
        return (
            self.db.query(DailyQueue)
            .filter(
                and_(
                    DailyQueue.day == day,
                    DailyQueue.specialist_id == specialist_id,
                )
            )
            .first()
        )

    def count_entries(self, *, queue_id: int) -> int:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == queue_id)
            .count()
        )

    def get_doctor(self, doctor_id: int) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.id == doctor_id).first()

    def get_or_create_daily_queue(
        self,
        *,
        day: date,
        specialist_id: int,
        max_online_entries: int,
    ) -> DailyQueue:
        queue = self.get_daily_queue(day=day, specialist_id=specialist_id)
        if not queue:
            queue = DailyQueue(
                day=day,
                specialist_id=specialist_id,
                active=True,
                max_online_entries=max_online_entries,
            )
            self.db.add(queue)
        return queue

    def save(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

