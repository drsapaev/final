"""Service layer for visit confirmation endpoints."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.repositories.visit_confirmation_repository import VisitConfirmationRepository
from app.services.confirmation_security import ConfirmationSecurityService
from app.services.queue_service import queue_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VisitConfirmationDomainError(Exception):
    status_code: int
    detail: str
    headers: dict[str, str] | None = None


class VisitConfirmationService:
    """Contains confirmation business rules and orchestration."""

    def __init__(self, db):
        self.repository = VisitConfirmationRepository(db)
        self.security_service = ConfirmationSecurityService(db)

    def confirm_by_telegram(
        self,
        *,
        token: str,
        telegram_user_id: str | None,
        source_ip: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        visit = None
        try:
            security_check = self.security_service.validate_confirmation_request(
                token=token,
                source_ip=source_ip,
                user_agent=user_agent,
                channel="telegram",
            )

            if not security_check.allowed:
                self.security_service.record_confirmation_attempt(
                    visit_id=0,
                    success=False,
                    channel="telegram",
                    error_reason=security_check.reason,
                )
                if security_check.reason == "Недействительный токен подтверждения":
                    raise VisitConfirmationDomainError(
                        status_code=404,
                        detail="Визит не найден или уже подтвержден",
                    )
                raise VisitConfirmationDomainError(
                    status_code=429 if security_check.retry_after else 400,
                    detail=security_check.reason,
                    headers=(
                        {"Retry-After": str(security_check.retry_after)}
                        if security_check.retry_after
                        else None
                    ),
                )

            visit = self.repository.get_pending_visit_by_token(token)
            if not visit:
                self.security_service.record_confirmation_attempt(
                    visit_id=0,
                    success=False,
                    channel="telegram",
                    error_reason="Visit not found",
                )
                raise VisitConfirmationDomainError(
                    status_code=404,
                    detail="Визит не найден или уже подтвержден",
                )

            if visit.confirmation_channel not in ["telegram", "auto"]:
                self.security_service.record_confirmation_attempt(
                    visit_id=visit.id,
                    success=False,
                    channel="telegram",
                    error_reason="Wrong confirmation channel",
                )
                raise VisitConfirmationDomainError(
                    status_code=400,
                    detail="Этот визит нельзя подтвердить через Telegram",
                )

            result = self._confirm_visit(
                visit=visit,
                confirmed_by=f"telegram_{telegram_user_id or 'unknown'}",
                channel="telegram",
            )

            self.security_service.record_confirmation_attempt(
                visit_id=visit.id,
                success=True,
                channel="telegram",
            )
            return result
        except VisitConfirmationDomainError:
            self.repository.rollback()
            raise
        except Exception as exc:
            self.repository.rollback()
            try:
                self.security_service.record_confirmation_attempt(
                    visit_id=visit.id if visit else 0,
                    success=False,
                    channel="telegram",
                    error_reason=f"System error: {exc}",
                )
            except Exception:
                pass
            raise VisitConfirmationDomainError(
                status_code=500,
                detail=f"Ошибка подтверждения визита: {exc}",
            ) from exc

    def confirm_by_pwa(
        self,
        *,
        token: str,
        patient_phone: str | None,
        source_ip: str | None,
        user_agent: str | None,
    ) -> dict[str, Any]:
        try:
            security_check = self.security_service.validate_confirmation_request(
                token=token,
                source_ip=source_ip,
                user_agent=user_agent,
                channel="pwa",
            )
            if not security_check.allowed:
                self.security_service.record_confirmation_attempt(
                    visit_id=0,
                    success=False,
                    channel="pwa",
                    error_reason=security_check.reason,
                )
                if security_check.reason == "Недействительный токен подтверждения":
                    raise VisitConfirmationDomainError(
                        status_code=404,
                        detail="Визит не найден или уже подтвержден",
                    )
                raise VisitConfirmationDomainError(
                    status_code=429 if security_check.retry_after else 400,
                    detail=security_check.reason,
                )

            visit = self.repository.get_pending_visit_by_token(token)
            if not visit:
                self.security_service.record_confirmation_attempt(
                    visit_id=0,
                    success=False,
                    channel="pwa",
                    error_reason="Visit not found",
                )
                raise VisitConfirmationDomainError(
                    status_code=404,
                    detail="Визит не найден или уже подтвержден",
                )

            if (
                visit.confirmation_expires_at
                and visit.confirmation_expires_at < datetime.utcnow()
            ):
                raise VisitConfirmationDomainError(
                    status_code=400,
                    detail="Срок подтверждения истек",
                )

            if visit.confirmation_channel not in ["pwa", "auto"]:
                raise VisitConfirmationDomainError(
                    status_code=400,
                    detail="Этот визит нельзя подтвердить через PWA",
                )

            if patient_phone:
                patient = self.repository.get_patient(visit.patient_id)
                if patient and patient.phone and patient.phone != patient_phone:
                    raise VisitConfirmationDomainError(
                        status_code=400,
                        detail="Номер телефона не совпадает с записью",
                    )

            result = self._confirm_visit(
                visit=visit,
                confirmed_by=f"pwa_{source_ip or 'unknown'}",
                channel="pwa",
            )
            self.security_service.record_confirmation_attempt(
                visit_id=visit.id, success=True, channel="pwa"
            )
            return result
        except VisitConfirmationDomainError:
            self.repository.rollback()
            raise
        except Exception as exc:
            self.repository.rollback()
            raise VisitConfirmationDomainError(
                status_code=500,
                detail=f"Ошибка подтверждения визита: {exc}",
            ) from exc

    def get_visit_info(self, token: str) -> dict[str, Any]:
        try:
            visit = self.repository.get_visit_by_token(token)
            if not visit:
                raise VisitConfirmationDomainError(
                    status_code=404,
                    detail="Визит не найден",
                )

            if (
                visit.confirmation_expires_at
                and visit.confirmation_expires_at < datetime.utcnow()
            ):
                raise VisitConfirmationDomainError(
                    status_code=400,
                    detail="Срок подтверждения истек",
                )

            if visit.status != "pending_confirmation":
                raise VisitConfirmationDomainError(
                    status_code=400,
                    detail=f"Визит уже имеет статус: {visit.status}",
                )

            patient = self.repository.get_patient(visit.patient_id)
            visit_services = self.repository.get_visit_services(visit.id)

            services_info = []
            total_amount = 0.0
            for vs in visit_services:
                item_total = float(vs.price * vs.qty) if vs.price else 0.0
                services_info.append(
                    {
                        "name": vs.name,
                        "code": vs.code,
                        "quantity": vs.qty,
                        "price": float(vs.price) if vs.price else 0.0,
                        "total": item_total,
                    }
                )
                total_amount += item_total

            doctor = self.repository.get_doctor(visit.doctor_id) if visit.doctor_id else None
            doctor_name = doctor.user.full_name if doctor and doctor.user else "Не назначен"

            return {
                "success": True,
                "visit_id": visit.id,
                "status": visit.status,
                "patient_name": patient.short_name() if patient else "Неизвестный пациент",
                "doctor_name": doctor_name,
                "visit_date": visit.visit_date.isoformat(),
                "visit_time": visit.visit_time,
                "department": visit.department,
                "discount_mode": visit.discount_mode,
                "services": services_info,
                "total_amount": total_amount,
                "currency": "UZS",
                "confirmation_expires_at": (
                    visit.confirmation_expires_at.isoformat()
                    if visit.confirmation_expires_at
                    else None
                ),
                "notes": visit.notes,
            }
        except VisitConfirmationDomainError:
            raise
        except Exception as exc:
            raise VisitConfirmationDomainError(
                status_code=500,
                detail=f"Ошибка получения информации о визите: {exc}",
            ) from exc

    def _confirm_visit(
        self,
        *,
        visit,
        confirmed_by: str,
        channel: str,
    ) -> dict[str, Any]:
        visit.confirmed_at = datetime.utcnow()
        visit.confirmed_by = confirmed_by
        visit.status = "confirmed"

        queue_numbers: dict[str, Any] = {}
        print_tickets: list[dict[str, Any]] = []
        if visit.visit_date == date.today():
            queue_numbers, print_tickets = self._assign_queue_numbers_on_confirmation(visit)
            visit.status = "open"

        self.repository.commit()
        self.repository.refresh(visit)

        patient = self.repository.get_patient(visit.patient_id)
        queue_numbers_list = list(queue_numbers.values())
        return {
            "success": True,
            "message": (
                "✅ Визит подтвержден! "
                + (
                    "Номера в очередях присвоены."
                    if queue_numbers_list
                    else "Номера будут присвоены утром в день визита."
                )
            ),
            "visit_id": visit.id,
            "status": visit.status,
            "patient_name": patient.short_name() if patient else "Неизвестный пациент",
            "visit_date": visit.visit_date.isoformat(),
            "visit_time": visit.visit_time,
            "queue_numbers": queue_numbers_list,
            "print_tickets": print_tickets,
            "channel": channel,
        }

    def _assign_queue_numbers_on_confirmation(
        self, visit
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        visit_services = self.repository.get_visit_services(visit.id)

        unique_queue_tags: set[str] = set()
        for vs in visit_services:
            service = self.repository.get_service(vs.service_id)
            if service and service.queue_tag:
                unique_queue_tags.add(service.queue_tag)

        if not unique_queue_tags:
            department_to_queue = {
                "cardiology": "cardiology_common",
                "dermatology": "dermatology",
                "stomatology": "stomatology",
                "cosmetology": "cosmetology",
                "lab": "lab",
                "ecg": "ecg",
            }
            fallback_tag = department_to_queue.get((visit.department or "").lower())
            if fallback_tag:
                unique_queue_tags.add(fallback_tag)
            else:
                return {}, []

        today = date.today()
        queue_numbers: dict[str, Any] = {}
        print_tickets: list[dict[str, Any]] = []

        for queue_tag in unique_queue_tags:
            doctor_id = visit.doctor_id

            if queue_tag == "ecg" and not doctor_id:
                ecg_resource = self.repository.get_active_user_by_username("ecg_resource")
                if ecg_resource:
                    doctor_id = ecg_resource.id
                else:
                    continue
            elif queue_tag == "lab" and not doctor_id:
                lab_resource = self.repository.get_active_user_by_username("lab_resource")
                if not lab_resource:
                    continue
                lab_doctor = self.repository.get_doctor_by_user_id(lab_resource.id)
                if lab_doctor:
                    doctor_id = lab_doctor.id
                    logger.info(
                        "For queue_tag=%s using lab resource doctor id=%s",
                        queue_tag,
                        doctor_id,
                    )
                else:
                    logger.warning(
                        "Lab resource user id=%s has no doctor row",
                        lab_resource.id,
                    )
                    continue

            if not doctor_id:
                continue

            daily_queue = self.repository.get_or_create_daily_queue(
                day=today,
                specialist_id=doctor_id,
                queue_tag=queue_tag,
            )

            next_number = queue_service.get_next_queue_number(
                self.repository.db,
                daily_queue=daily_queue,
                queue_tag=queue_tag,
            )

            queue_service.create_queue_entry(
                self.repository.db,
                daily_queue=daily_queue,
                patient_id=visit.patient_id,
                visit_id=visit.id,
                number=next_number,
                source="confirmation",
            )

            queue_numbers[queue_tag] = {
                "queue_tag": queue_tag,
                "number": next_number,
                "queue_id": daily_queue.id,
            }

            queue_names = {
                "ecg": "ЭКГ",
                "cardiology_common": "Кардиолог",
                "dermatology": "Дерматолог",
                "stomatology": "Стоматолог",
                "cosmetology": "Косметолог",
                "lab": "Лаборатория",
                "general": "Общая очередь",
            }
            doctor = self.repository.get_doctor(visit.doctor_id) if visit.doctor_id else None
            patient = self.repository.get_patient(visit.patient_id)

            print_tickets.append(
                {
                    "visit_id": visit.id,
                    "queue_tag": queue_tag,
                    "queue_name": queue_names.get(queue_tag, queue_tag),
                    "queue_number": next_number,
                    "queue_id": daily_queue.id,
                    "patient_id": visit.patient_id,
                    "patient_name": (
                        patient.short_name() if patient else "Неизвестный пациент"
                    ),
                    "doctor_name": (
                        doctor.user.full_name if doctor and doctor.user else "Без врача"
                    ),
                    "department": visit.department,
                    "visit_date": visit.visit_date.isoformat(),
                    "visit_time": visit.visit_time,
                }
            )

        return queue_numbers, print_tickets
