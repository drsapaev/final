"""Repository helpers for queue cabinet management endpoints."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry


class QueueCabinetManagementApiRepository:
    """Encapsulates ORM operations for queue cabinet management API."""

    def __init__(self, db: Session):
        self.db = db

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

    def get_daily_queue(self, queue_id: int) -> DailyQueue | None:
        return self.db.query(DailyQueue).filter(DailyQueue.id == queue_id).first()

    def get_doctor(self, doctor_id: int) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.id == doctor_id).first()

    def count_entries(self, *, queue_id: int) -> int:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == queue_id)
            .count()
        )

    def list_queues_for_day(
        self,
        *,
        day_obj: date,
        specialist_id: int | None = None,
    ) -> list[DailyQueue]:
        query = self.db.query(DailyQueue).filter(DailyQueue.day == day_obj)
        if specialist_id:
            query = query.filter(DailyQueue.specialist_id == specialist_id)
        return query.all()

    def list_queues_for_period(
        self,
        *,
        date_from: date | None,
        date_to: date | None,
    ) -> list[DailyQueue]:
        query = self.db.query(DailyQueue)
        if date_from:
            query = query.filter(DailyQueue.day >= date_from)
        if date_to:
            query = query.filter(DailyQueue.day <= date_to)
        return query.all()

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)

    def rollback(self) -> None:
        self.db.rollback()
