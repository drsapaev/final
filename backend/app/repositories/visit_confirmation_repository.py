"""Repository helpers for visit confirmation flow."""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.crud import clinic as crud_clinic
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.service import Service
from app.models.online_queue import DailyQueue
from app.models.user import User
from app.models.visit import Visit, VisitService

logger = logging.getLogger(__name__)


class VisitConfirmationRepository:
    """Encapsulates ORM operations for confirmation service."""

    def __init__(self, db: Session):
        self.db = db

    def get_pending_visit_by_token(self, token: str) -> Visit | None:
        return (
            self.db.query(Visit)
            .filter(Visit.confirmation_token == token, Visit.status == "pending_confirmation")
            .first()
        )

    def get_visit_by_token(self, token: str) -> Visit | None:
        return self.db.query(Visit).filter(Visit.confirmation_token == token).first()

    def get_patient(self, patient_id: int) -> Patient | None:
        return self.db.query(Patient).filter(Patient.id == patient_id).first()

    def get_visit_services(self, visit_id: int) -> list[VisitService]:
        return self.db.query(VisitService).filter(VisitService.visit_id == visit_id).all()

    def get_service(self, service_id: int) -> Service | None:
        return self.db.query(Service).filter(Service.id == service_id).first()

    def get_doctor(self, doctor_id: int) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.id == doctor_id).first()

    def get_doctor_by_user_id(self, user_id: int) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.user_id == user_id).first()

    def get_active_user_by_username(self, username: str) -> User | None:
        return (
            self.db.query(User)
            .filter(User.username == username, User.is_active == True)
            .first()
        )

    def get_or_create_daily_queue(self, day: date, specialist_id: int, queue_tag: str):
        doctor = self.db.query(Doctor).filter(Doctor.id == specialist_id).first()
        if not doctor:
            logger.error(
                "[FIX] Cannot create DailyQueue: Doctor with ID=%s does not exist",
                specialist_id,
            )
            raise ValueError(
                f"Врач с ID {specialist_id} не найден. Невозможно создать очередь."
            )

        actual_specialist_id = doctor.id

        if queue_tag:
            existing_by_tag = (
                self.db.query(DailyQueue)
                .filter(
                    DailyQueue.day == day,
                    DailyQueue.queue_tag == queue_tag,
                    DailyQueue.active == True,
                )
                .first()
            )
            if existing_by_tag:
                logger.info(
                    "[FIX] Reusing existing DailyQueue id=%s day=%s specialist=%s queue_tag=%s",
                    existing_by_tag.id,
                    day,
                    actual_specialist_id,
                    queue_tag,
                )
                return existing_by_tag

        query = self.db.query(DailyQueue).filter(
            DailyQueue.day == day,
            DailyQueue.specialist_id == actual_specialist_id,
        )
        if queue_tag:
            query = query.filter(DailyQueue.queue_tag == queue_tag)

        daily_queue = query.first()
        if daily_queue:
            logger.info(
                "[FIX] Reusing existing DailyQueue id=%s day=%s specialist=%s queue_tag=%s",
                daily_queue.id,
                day,
                actual_specialist_id,
                queue_tag,
            )
            return daily_queue

        settings = crud_clinic.get_queue_settings(self.db)
        queue_start_hour = settings.get("queue_start_hour", 7)
        queue_end_hour = settings.get("queue_end_hour", 9)

        daily_queue = DailyQueue(
            day=day,
            specialist_id=actual_specialist_id,
            queue_tag=queue_tag,
            active=True,
            online_start_time=f"{int(queue_start_hour):02d}:00",
            online_end_time=f"{int(queue_end_hour):02d}:00",
        )
        self.db.add(daily_queue)

        try:
            self.db.flush()
            logger.info(
                "[FIX] Created DailyQueue id=%s day=%s specialist=%s queue_tag=%s",
                daily_queue.id,
                day,
                actual_specialist_id,
                queue_tag,
            )
            return daily_queue
        except Exception:
            self.db.rollback()
            logger.exception(
                "[FIX] Failed to create DailyQueue day=%s specialist=%s queue_tag=%s",
                day,
                actual_specialist_id,
                queue_tag,
            )
            raise

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, obj) -> None:  # type: ignore[no-untyped-def]
        self.db.refresh(obj)
