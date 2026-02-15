"""Repository helpers for appointments endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import appointment as appointment_models
from app.models.setting import Setting


class AppointmentsApiRepository:
    """Encapsulates ORM operations for appointments API."""

    def __init__(self, db: Session):
        self.db = db

    def get_queue_setting(self, *, key: str):
        return (
            self.db.query(Setting)
            .filter(Setting.category == "queue", Setting.key == key)
            .with_for_update(read=True)
            .first()
        )

    def add(self, obj) -> None:
        self.db.add(obj)

    def commit(self) -> None:
        self.db.commit()

    def list_pending_appointments(self):
        return (
            self.db.query(appointment_models.Appointment)
            .filter(appointment_models.Appointment.status.in_(["scheduled", "confirmed", "pending"]))
        )
