"""Service layer for derma endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.roles import normalize_role_value
from app.repositories.derma_api_repository import DermaApiRepository
from app.services.money_input import MoneyInputError, parse_money
from app.services.price_override_approval import (
    PENDING_DUPLICATE_DETAIL,
)
from app.services.profile_contact_security import ProfileBearerInvalid


@dataclass
class DermaApiDomainError(Exception):
    status_code: int
    detail: str


class DermaApiService:
    """Handles business rules for derma price override endpoints."""

    def __init__(
        self,
        db: Session,
        repository: DermaApiRepository | None = None,
    ):
        self.repository = repository or DermaApiRepository(db)

    def _visit_belongs_to_doctor(self, *, visit, doctor, user_id: int) -> bool:
        # User.id is not evidence that the assigned Doctor performed the visit.
        doctor_id = getattr(doctor, "id", None)
        return type(doctor_id) is int and doctor_id > 0 and getattr(visit, "doctor_id", None) == doctor_id

    def _prepare_override(self, *, override_data, user_id, bearer):
        # Keep the locks through insertion/commit: User -> Doctor -> Visit -> Service.
        if bearer.user_id != user_id or bearer.patient_id is not None:
            raise ProfileBearerInvalid("Bearer session unavailable")
        self.repository.reserve_request_writer()
        user = self.repository.lock_request_user(bearer)
        if not user.is_active or (not user.is_superuser and normalize_role_value(user.role) not in {"admin", "doctor", "derma", "dermatology", "dermatologist"}):
            raise DermaApiDomainError(403, "Access denied")
        doctor = self.repository.lock_request_doctor(user_id)
        if not doctor or not doctor.active or doctor.user_id != user_id:
            raise DermaApiDomainError(403, "Access denied")
        if doctor.specialty not in {"dermatology", "cosmetology"}:
            raise DermaApiDomainError(403, "Access denied")
        visit = self.repository.lock_request_visit(override_data.visit_id)
        if not visit:
            raise DermaApiDomainError(404, "Визит не найден")
        if not self._visit_belongs_to_doctor(visit=visit, doctor=doctor, user_id=user_id):
            raise DermaApiDomainError(403, "Access denied")
        service = self.repository.lock_request_service(override_data.service_id)
        if not service:
            raise DermaApiDomainError(404, "Услуга не найдена")
        if not service.active or not service.allow_doctor_price_override:
            raise DermaApiDomainError(400, "Данная услуга не разрешает изменение цены врачом")
        if not visit.confirmation_context_epoch or visit.confirmation_context_epoch < 1 or not doctor.repeat_owner_generation or doctor.repeat_owner_generation < 1:
            raise DermaApiDomainError(409, "Контекст визита недоступен")
        try:
            price = parse_money(override_data.new_price)
        except MoneyInputError:
            raise DermaApiDomainError(422, "Некорректная денежная сумма") from None
        rows = self.repository.request_visit_services(visit.id, service.id)
        target_id = getattr(override_data, "target_visit_service_id", None)
        if target_id is None and len(rows) != 1:
            raise DermaApiDomainError(409, "Укажите конкретную услугу визита")
        target = next((row for row in rows if row.id == target_id), None) if target_id else rows[0]
        if target is None:
            raise DermaApiDomainError(409, "Услуга не привязана к выбранному визиту")
        if self.repository.has_pending_override(visit_id=visit.id, service_id=service.id, target_id=target.id):
            raise DermaApiDomainError(409, PENDING_DUPLICATE_DETAIL)
        target = self.repository.protect_target_fk(visit.id, service.id, target.id)
        if target is None:
            raise DermaApiDomainError(409, "Услуга изменяется, повторите запрос")
        if (type(visit.price_context_generation) is not int or visit.price_context_generation < 1
                or type(target.price_line_generation) is not int or target.price_line_generation < 1
                or type(doctor.price_owner_generation) is not int or doctor.price_owner_generation < 1
                or type(user.auth_epoch) is not int or user.auth_epoch < 0):
            raise DermaApiDomainError(409, "Контекст визита недоступен")
        try:
            parse_money(target.price)
        except MoneyInputError:
            raise DermaApiDomainError(409, "Цена услуги визита недоступна") from None
        return user, doctor, visit, service, target, price

    def create_price_override(self, *, override_data, user_id: int, bearer):
        try:
            user, doctor, visit, service, visit_service, price = self._prepare_override(
                override_data=override_data, user_id=user_id, bearer=bearer,
            )
            return self.repository.create_price_override(
                visit_id=visit.id, doctor_id=doctor.id, service_id=service.id,
                original_price=service.price or Decimal("0"), new_price=price,
                reason=override_data.reason, details=override_data.details,
                visit_price_before=visit_service.price,
                target_visit_service_id=visit_service.id,
                visit_context_epoch=visit.confirmation_context_epoch,
                doctor_owner_user_id=user.id,
                doctor_owner_generation=doctor.repeat_owner_generation,
                price_context_generation=visit.price_context_generation,
                price_line_generation=visit_service.price_line_generation,
                price_owner_generation=doctor.price_owner_generation,
                requester_user_id=user.id, requester_auth_epoch=user.auth_epoch,
                context=bearer,
            )
        except ProfileBearerInvalid:
            self.repository.rollback()
            raise DermaApiDomainError(401, "Сессия недействительна") from None
        except DBAPIError as exc:
            self.repository.rollback()
            sqlite_code = getattr(exc.orig, "sqlite_errorcode", 0) or 0
            if getattr(exc.orig, "sqlstate", None) == "55P03" or sqlite_code & 255 in (5, 6):
                raise DermaApiDomainError(409, "Услуга изменяется, повторите запрос") from None
            raise
        except Exception:
            self.repository.rollback()
            raise

    def get_price_overrides(
        self,
        *,
        user_id: int,
        visit_id: int | None,
        status: str | None,
        limit: int,
        is_admin: bool = False,
    ):
        doctor = self.repository.get_doctor_by_user_id(user_id)
        if not doctor:
            if is_admin:
                # DERMAPRICE-BE-004 (audit #3892, group 15): DERMA_ROLES
                # includes Admin for the LIST route — an administrator
                # without a linked Doctor row gets the authorized aggregated
                # view instead of a domain 404 from doctor resolution.
                # CREATE stays dermatologist-profile-gated by design.
                return self.repository.list_price_overrides(
                    doctor_id=None,
                    visit_id=visit_id,
                    status=status,
                    limit=limit,
                )
            raise DermaApiDomainError(404, "Врач не найден")

        return self.repository.list_price_overrides(
            doctor_id=doctor.id,
            visit_id=visit_id,
            status=status,
            limit=limit,
        )

    def rollback(self) -> None:
        self.repository.rollback()
