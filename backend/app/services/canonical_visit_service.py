"""Deterministic appointment -> canonical visit resolver."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.enums import AppointmentStatus, normalize_appointment_status
from app.models.visit import Visit
from app.repositories.canonical_visit_repository import CanonicalVisitRepository

logger = logging.getLogger(__name__)


@dataclass
class CanonicalVisitResolutionError(Exception):
    status_code: int
    detail: str


class CanonicalVisitService:
    """Guarantees a single canonical visit for any EMR-related appointment flow."""

    def __init__(
        self,
        db: Session,
        repository: CanonicalVisitRepository | None = None,
    ):
        self.repository = repository or CanonicalVisitRepository(db)

    def resolve_canonical_visit(
        self,
        appointment_id: int,
        *,
        create_if_missing: bool = True,
    ) -> int:
        appointment = self.repository.get_appointment(appointment_id)
        if not appointment:
            raise CanonicalVisitResolutionError(404, "Запись не найдена")

        normalized_status = normalize_appointment_status(
            getattr(appointment.status, "value", appointment.status)
        )
        if normalized_status in {AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW}:
            raise CanonicalVisitResolutionError(
                409,
                f"Нельзя резолвить визит для отмененной записи ({appointment.status})",
            )

        candidates = self.repository.list_visits_for_appointment(appointment)
        if len(candidates) > 1:
            logger.error(
                "[canonical-visit] multiple visit candidates",
                extra={
                    "appointment_id": appointment_id,
                    "patient_id": appointment.patient_id,
                    "doctor_id": appointment.doctor_id,
                    "visit_ids": [visit.id for visit in candidates],
                },
            )
            raise CanonicalVisitResolutionError(
                409,
                "Для записи найдено несколько визитов. Требуется ручная сверка.",
            )

        if candidates:
            return candidates[0].id

        if not create_if_missing:
            raise CanonicalVisitResolutionError(
                404,
                "Для записи не найден канонический визит",
            )

        visit = Visit(
            patient_id=appointment.patient_id,
            status=self._map_visit_status(normalized_status),
            notes=appointment.notes,
            doctor_id=appointment.doctor_id,
            visit_date=appointment.appointment_date,
            visit_time=appointment.appointment_time,
            department_id=appointment.department_id,
            source="desk",
            created_at=appointment.created_at,
        )
        created = self.repository.create_visit(visit)
        logger.warning(
            "[canonical-visit] created missing visit",
            extra={"appointment_id": appointment_id, "visit_id": created.id},
        )
        return created.id

    @staticmethod
    def _map_visit_status(status: AppointmentStatus) -> str:
        if status == AppointmentStatus.COMPLETED:
            return "closed"
        if status == AppointmentStatus.IN_VISIT:
            return "in_progress"
        return "open"
