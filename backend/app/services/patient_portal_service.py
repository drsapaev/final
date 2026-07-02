"""Service layer for patient self-service endpoints."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories.patient_portal_repository import PatientPortalRepository


@dataclass
class PatientPortalDomainError(Exception):
    status_code: int
    detail: str


class PatientPortalService:
    """Orchestrates appointment/results retrieval for patient endpoints."""

    def __init__(
        self,
        db: Session,
        repository: PatientPortalRepository | None = None,
    ):
        self.repository = repository or PatientPortalRepository(db)

    def get_my_appointment_details(
        self,
        *,
        appointment_id: int,
        patient_id: int,
    ):
        appointment = self.repository.get_patient_appointment(
            appointment_id=appointment_id,
            patient_id=patient_id,
        )
        if not appointment:
            raise PatientPortalDomainError(status_code=404, detail="Запись не найдена")
        return appointment

    def get_my_results(self, *, patient_id: int):
        return self.repository.list_patient_lab_orders(patient_id=patient_id)

