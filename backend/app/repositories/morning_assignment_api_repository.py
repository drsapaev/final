"""Repository helpers for morning_assignment endpoints."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.visit import Visit


class MorningAssignmentApiRepository:
    """Encapsulates ORM lookups used by morning assignment API."""

    def __init__(self, db: Session):
        self.db = db

    def get_visit(self, visit_id: int) -> Visit | None:
        return self.db.query(Visit).filter(Visit.id == visit_id).first()

    def get_patient(self, patient_id: int) -> Patient | None:
        return self.db.query(Patient).filter(Patient.id == patient_id).first()

    def list_daily_queues(self, *, day: date) -> list[DailyQueue]:
        return self.db.query(DailyQueue).filter(DailyQueue.day == day).all()

    def count_queue_entries(self, *, queue_id: int) -> int:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id == queue_id)
            .count()
        )

    def get_doctor(self, doctor_id: int) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.id == doctor_id).first()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
