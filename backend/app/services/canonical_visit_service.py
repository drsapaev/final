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
        expected_visit_id: int | None = None,
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

        # A persisted source is authoritative; the initial read is only a
        # lock-order hint and must be rechecked after Visit → Encounter →
        # Appointment locks. Legacy heuristic matches never gain provenance.
        source_id = getattr(appointment, "source_visit_id", None)
        # A caller that already owns a Visit lock must never acquire another
        # Visit based on an appointment hint: cross-linked requests could each
        # hold the other's Visit. Legacy heuristic pairing also cannot prove
        # that this payment belongs to the already locked Visit.
        if expected_visit_id is not None and source_id != expected_visit_id:
            raise CanonicalVisitResolutionError(409, "Запись не подтверждает указанный визит")
        if source_id is not None:
            visit = self.repository.lock_source_visit(source_id)
            if visit is None:
                raise CanonicalVisitResolutionError(409, "Исходный визит недоступен")
            encounter = (self.repository.lock_encounter(visit.encounter_id)
                         if visit.encounter_id is not None else None)
            locked = self.repository.lock_appointment(appointment_id)
            if (locked is None or locked.source_visit_id != source_id or
                    locked.patient_id != visit.patient_id or
                    locked.encounter_id != visit.encounter_id or
                    (visit.encounter_id is not None and
                     (encounter is None or encounter.patient_id != visit.patient_id))):
                raise CanonicalVisitResolutionError(409, "Контекст записи изменился")
            locked_status = normalize_appointment_status(
                getattr(locked.status, "value", locked.status)
            )
            if locked_status in {AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW}:
                raise CanonicalVisitResolutionError(409, "Запись отменена")
            return visit.id

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
