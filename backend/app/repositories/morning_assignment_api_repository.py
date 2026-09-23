"""Repository helpers for morning_assignment endpoints."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.patient import Patient
from app.models.user import User
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

    def load_queue_summary_lookups(
        self, queues: list[DailyQueue]
    ) -> tuple[dict[int, int], dict[int, str | None], dict[int, str]]:
        queue_ids = [queue.id for queue in queues]
        if not queue_ids:
            return {}, {}, {}

        entry_counts = dict(
            self.db.query(OnlineQueueEntry.queue_id, func.count(OnlineQueueEntry.id))
            .filter(OnlineQueueEntry.queue_id.in_(queue_ids))
            .group_by(OnlineQueueEntry.queue_id)
            .all()
        )

        doctor_ids = {
            queue.specialist_id
            for queue in queues
            if queue.queue_resource_id is None and queue.specialist_id is not None
        }
        doctor_names: dict[int, str | None] = {}
        if doctor_ids:
            doctor_rows = (
                self.db.query(Doctor.id, User.id, User.full_name)
                .outerjoin(User, Doctor.user_id == User.id)
                .filter(Doctor.id.in_(doctor_ids))
                .all()
            )
            doctor_names = {
                doctor_id: full_name if user_id is not None else f"ID:{doctor_id}"
                for doctor_id, user_id, full_name in doctor_rows
            }

        resource_ids = {
            queue.queue_resource_id
            for queue in queues
            if queue.queue_resource_id is not None
        }
        resource_names: dict[int, str] = {}
        if resource_ids:
            resource_names = dict(
                self.db.query(QueueResource.id, QueueResource.display_name)
                .filter(QueueResource.id.in_(resource_ids))
                .all()
            )

        return entry_counts, doctor_names, resource_names

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
