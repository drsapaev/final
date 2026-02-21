"""Repository helpers for queue cabinet management API."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry

class QueueCabinetManagementApiRepository:
    """Shared DB session adapter for queue cabinet management service."""

    def __init__(self, db: Session):
        self.db = db

    def query_daily_queues(self):
        return self.db.query(DailyQueue)

    def get_daily_queue_by_id(self, queue_id: int):
        return self.db.query(DailyQueue).filter(DailyQueue.id == queue_id).first()

    def get_doctor_by_id(self, doctor_id: int):
        return self.db.query(Doctor).filter(Doctor.id == doctor_id).first()

    def count_entries_for_queue(self, queue_id: int) -> int:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == queue_id)
            .count()
        )

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)

    def rollback(self) -> None:
        self.db.rollback()
