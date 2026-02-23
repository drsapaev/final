"""Service layer for appointment_flow endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.audit import extract_model_changes, log_critical_change
from app.models.enums import AppointmentStatus
from app.repositories.appointment_flow_api_repository import (
    AppointmentFlowApiRepository,
)


@dataclass
class AppointmentFlowApiDomainError(Exception):
    status_code: int
    detail: str


class AppointmentFlowApiService:
    """Handles endpoint-level DB interactions for EMR flow operations."""

    def __init__(
        self,
        db: Session,
        repository: AppointmentFlowApiRepository | None = None,
    ):
        self.repository = repository or AppointmentFlowApiRepository(db)

    def resolve_appointment_from_visit(self, *, appointment_id: int, emr_data):
        visit = self.repository.get_visit(appointment_id)
        if not visit:
            raise AppointmentFlowApiDomainError(404, "Запись не найдена")

        existing_appointment = self.repository.get_existing_appointment_for_visit(visit)
        if existing_appointment:
            emr_data.appointment_id = existing_appointment.id
            return existing_appointment, visit

        appointment = self.repository.create_appointment_from_visit(visit)
        return appointment, visit

    def promote_appointment_to_in_visit(self, *, appointment: Any) -> None:
        appointment.status = AppointmentStatus.IN_VISIT
        self.repository.commit()
        self.repository.refresh(appointment)

    def finalize_emr_update_audit(
        self,
        *,
        request,
        user_id: int,
        appointment_id: int,
        updated_emr: Any,
        old_data: dict | None,
    ) -> None:
        self.repository.refresh(updated_emr)
        _, new_data = extract_model_changes(None, updated_emr)
        log_critical_change(
            db=self.repository.db,
            user_id=user_id,
            action="UPDATE",
            table_name="emr",
            row_id=updated_emr.id,
            old_data=old_data,
            new_data=new_data,
            request=request,
            description=f"Обновлен EMR ID={updated_emr.id} для записи {appointment_id}",
        )
        self.repository.commit()

    def finalize_emr_create_audit(
        self,
        *,
        request,
        user_id: int,
        appointment_id: int,
        new_emr: Any,
    ) -> None:
        self.repository.refresh(new_emr)
        _, new_data = extract_model_changes(None, new_emr)
        log_critical_change(
            db=self.repository.db,
            user_id=user_id,
            action="CREATE",
            table_name="emr",
            row_id=new_emr.id,
            old_data=None,
            new_data=new_data,
            request=request,
            description=f"Создан EMR ID={new_emr.id} для записи {appointment_id}",
        )
        self.repository.commit()

    def rollback(self) -> None:
        self.repository.rollback()
