"""Data access helpers for registrar queue batch operations."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.crud import online_queue as crud_queue
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service

REGISTRAR_BATCH_ACTIVE_DUPLICATE_STATUSES = (
    "waiting",
    "called",
    "in_service",
    "diagnostics",
)


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
        """Returns (doctor_id, converted_from_legacy_user_id)."""
        doctor = self.db.query(Doctor).filter(Doctor.id == specialist_id).first()
        if doctor:
            return doctor.id, False

        return None, False

    def get_or_create_daily_queue(self, day: date, specialist_id: int) -> DailyQueue:
        return crud_queue.get_or_create_daily_queue(
            self.db,
            day=day,
            specialist_id=specialist_id,
            queue_tag=None,
        )

    def find_existing_active_entries(
        self,
        *,
        specialist_id: int,
        day: date,
        patient_id: int,
    ) -> list[OnlineQueueEntry]:
        return (
            self.db.query(OnlineQueueEntry)
            .join(DailyQueue, DailyQueue.id == OnlineQueueEntry.queue_id)
            .filter(
                DailyQueue.specialist_id == specialist_id,
                DailyQueue.day == day,
                OnlineQueueEntry.patient_id == patient_id,
                OnlineQueueEntry.status.in_(REGISTRAR_BATCH_ACTIVE_DUPLICATE_STATUSES),
            )
            .order_by(OnlineQueueEntry.id.asc())
            .all()
        )

    def find_existing_active_entry(
        self,
        *,
        specialist_id: int,
        day: date,
        patient_id: int,
    ) -> OnlineQueueEntry | None:
        entries = self.find_existing_active_entries(
            specialist_id=specialist_id,
            day=day,
            patient_id=patient_id,
        )
        return entries[0] if entries else None

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
