"""Read-only queue repository used by Wave 2C safe slices."""

from __future__ import annotations

from datetime import date
from typing import Sequence

from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.services.queue_status import REORDER_ACTIVE_RAW_STATUSES


class QueueReadRepository:
    """Encapsulates read-only queue lookups for the domain service."""

    def __init__(self, db: Session):
        self.db = db

    def get_queue(self, queue_id: int) -> DailyQueue | None:
        return self.db.query(DailyQueue).filter(DailyQueue.id == queue_id).first()

    def list_active_doctors(self, *, specialty: str | None) -> list[Doctor]:
        query = self.db.query(Doctor).filter(Doctor.active.is_(True))
        if specialty:
            query = query.filter(Doctor.specialty == specialty)
        return query.all()

    def list_daily_queues(
        self,
        *,
        day_obj: date | None = None,
        specialist_id: int | None = None,
        cabinet_number: str | None = None,
    ) -> list[DailyQueue]:
        query = self.db.query(DailyQueue)
        if day_obj:
            query = query.filter(DailyQueue.day == day_obj)
        if specialist_id:
            query = query.filter(DailyQueue.specialist_id == specialist_id)
        if cabinet_number:
            query = query.filter(DailyQueue.cabinet_number == cabinet_number)
        return query.order_by(DailyQueue.day.desc(), DailyQueue.specialist_id).all()

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

    def get_doctor(self, doctor_id: int) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.id == doctor_id).first()

    def count_entries(self, *, queue_id: int) -> int:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == queue_id)
            .count()
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
