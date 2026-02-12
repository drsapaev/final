"""Data access helpers for registrar queue batch operations."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.crud import online_queue as crud_queue
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User


class QueueBatchRepository:
    """Encapsulates ORM queries used by queue batch service."""

    def __init__(self, db: Session):
        self.db = db

    def get_patient(self, patient_id: int) -> Patient | None:
        return self.db.query(Patient).filter(Patient.id == patient_id).first()

    def get_active_service(self, service_id: int) -> Service | None:
        return (
            self.db.query(Service)
            .filter(Service.id == service_id, Service.is_active == True)
            .first()
        )

    def resolve_specialist_user_id(self, specialist_id: int) -> tuple[int | None, bool]:
        """Returns (user_id, converted_from_doctor_id)."""
        doctor = self.db.query(Doctor).filter(Doctor.id == specialist_id).first()
        if doctor and doctor.user_id:
            return doctor.user_id, True

        user = self.db.query(User).filter(User.id == specialist_id).first()
        if user:
            return user.id, False

        return None, False

    def get_or_create_daily_queue(self, day: date, specialist_id: int) -> DailyQueue:
        return crud_queue.get_or_create_daily_queue(
            self.db,
            day=day,
            specialist_id=specialist_id,
            queue_tag=None,
        )

    def find_existing_active_entry(
        self,
        *,
        specialist_id: int,
        day: date,
        patient_id: int,
    ) -> OnlineQueueEntry | None:
        return (
            self.db.query(OnlineQueueEntry)
            .join(DailyQueue, DailyQueue.id == OnlineQueueEntry.queue_id)
            .filter(
                DailyQueue.specialist_id == specialist_id,
                DailyQueue.day == day,
                OnlineQueueEntry.patient_id == patient_id,
                OnlineQueueEntry.status.in_(["waiting", "called"]),
            )
            .first()
        )

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

