"""Service layer for registrar_notifications endpoints."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories.registrar_notifications_api_repository import (
    RegistrarNotificationsApiRepository,
)


@dataclass
class RegistrarNotificationsApiDomainError(Exception):
    status_code: int
    detail: str


class RegistrarNotificationsApiService:
    """Builds notification contexts for registrar endpoint handlers."""

    def __init__(
        self,
        db: Session,
        repository: RegistrarNotificationsApiRepository | None = None,
    ):
        self.repository = repository or RegistrarNotificationsApiRepository(db)

    def get_appointment_context(
        self,
        *,
        appointment_id: int,
        appointment_type: str,
    ):
        if appointment_type == "visit":
            appointment = self.repository.get_visit(appointment_id)
        else:
            appointment = self.repository.get_appointment(appointment_id)

        if not appointment:
            raise RegistrarNotificationsApiDomainError(404, "Запись не найдена")

        patient = self.repository.get_patient(appointment.patient_id)
        if not patient:
            raise RegistrarNotificationsApiDomainError(404, "Пациент не найден")

        services = []
        if appointment_type == "visit":
            visit_services = self.repository.list_visit_services(appointment.id)
            for visit_service in visit_services:
                service_obj = self.repository.get_service_by_code(visit_service.service_code)
                if service_obj:
                    services.append(service_obj)

        return appointment, patient, services

    def get_price_change_context(self, *, price_override_id: int):
        price_override = self.repository.get_price_override(price_override_id)
        if not price_override:
            raise RegistrarNotificationsApiDomainError(404, "Изменение цены не найдено")

        doctor = self.repository.get_doctor(price_override.doctor_id)
        if not doctor:
            raise RegistrarNotificationsApiDomainError(404, "Врач не найден")

        service_obj = self.repository.get_service(price_override.service_id)
        if not service_obj:
            raise RegistrarNotificationsApiDomainError(404, "Услуга не найдена")

        visit = None
        patient = None
        if price_override.visit_id:
            visit = self.repository.get_visit(price_override.visit_id)
            if visit:
                patient = self.repository.get_patient(visit.patient_id)

        return price_override, doctor, service_obj, visit, patient

    def get_queue_entry(self, *, queue_entry_id: int):
        queue_entry = self.repository.get_queue_entry(queue_entry_id)
        if not queue_entry:
            raise RegistrarNotificationsApiDomainError(
                404,
                "Запись в очереди не найдена",
            )
        return queue_entry
