"""Service layer for dental endpoints."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.roles import (
    DOCTOR_FAMILY_GATE_ROLES,
    is_doctor_role_spelling,
    normalize_role_value,
)
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.user import User
from app.repositories.dental_api_repository import DentalApiRepository
from app.services.money_input import MoneyInputError, parse_money
from app.services.notifications import notification_sender_service
from app.services.price_override_approval import (
    PENDING_DUPLICATE_DETAIL,
    PriceOverrideApprovalError,
    PriceOverrideApprovalService,
)
from app.services.profile_contact_security import ProfileBearerInvalid

logger = logging.getLogger(__name__)


@dataclass
class DentalApiDomainError(Exception):
    status_code: int
    detail: str


class DentalApiService:
    """Handles dental price override workflows."""

    def __init__(
        self,
        db: Session,
        repository: DentalApiRepository | None = None,
    ):
        # REGPRICE-BE-002: the canonical approval service needs the SAME
        # session for the locked transaction. The session is kept on the
        # SERVICE itself (repository internals are off-limits to the
        # service layer — repository-boundary test enforces this).
        self.db = db
        self.repository = repository or DentalApiRepository(db)

    @staticmethod
    def _service_code(service) -> str | None:
        if not service:
            return None
        service_code = getattr(service, "service_code", None)
        if service_code:
            return service_code
        service_id = getattr(service, "id", None)
        return str(service_id) if service_id is not None else None

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
        if not user.is_active or (not user.is_superuser and normalize_role_value(user.role) not in {"admin", *(normalize_role_value(role) for role in DOCTOR_FAMILY_GATE_ROLES)}):
            raise DentalApiDomainError(403, "Access denied")
        doctor = self.repository.lock_request_doctor(user_id)
        if not doctor or not doctor.active or doctor.user_id != user_id:
            raise DentalApiDomainError(403, "Access denied")
        if doctor.specialty not in {"stomatology", "dental", "dentistry"}:
            raise DentalApiDomainError(403, "Access denied")
        visit = self.repository.lock_request_visit(override_data.visit_id)
        if not visit:
            raise DentalApiDomainError(404, "Визит не найден")
        if not self._visit_belongs_to_doctor(visit=visit, doctor=doctor, user_id=user_id):
            raise DentalApiDomainError(403, "Access denied")
        service = self.repository.lock_request_service(override_data.service_id)
        if not service:
            raise DentalApiDomainError(404, "Услуга не найдена")
        if not service.active or not service.allow_doctor_price_override:
            raise DentalApiDomainError(400, "Данная услуга не разрешает изменение цены врачом")
        if not visit.confirmation_context_epoch or visit.confirmation_context_epoch < 1 or not doctor.repeat_owner_generation or doctor.repeat_owner_generation < 1:
            raise DentalApiDomainError(409, "Контекст визита недоступен")
        try:
            price = parse_money(override_data.new_price)
        except MoneyInputError:
            raise DentalApiDomainError(422, "Некорректная денежная сумма") from None
        rows = self.repository.request_visit_services(visit.id, service.id)
        target_id = getattr(override_data, "target_visit_service_id", None)
        if target_id is None and len(rows) != 1:
            raise DentalApiDomainError(409, "Укажите конкретную услугу визита")
        target = next((row for row in rows if row.id == target_id), None) if target_id else rows[0]
        if target is None:
            raise DentalApiDomainError(409, "Услуга не привязана к выбранному визиту")
        if self.repository.has_pending_override(visit_id=visit.id, service_id=service.id, target_id=target.id):
            raise DentalApiDomainError(409, PENDING_DUPLICATE_DETAIL)
        target = self.repository.protect_target_fk(visit.id, service.id, target.id)
        if target is None:
            raise DentalApiDomainError(409, "Услуга изменяется, повторите запрос")
        if (type(visit.price_context_generation) is not int or visit.price_context_generation < 1
                or type(target.price_line_generation) is not int or target.price_line_generation < 1
                or type(doctor.price_owner_generation) is not int or doctor.price_owner_generation < 1
                or type(user.auth_epoch) is not int or user.auth_epoch < 0):
            raise DentalApiDomainError(409, "Контекст визита недоступен")
        try:
            parse_money(target.price)
        except MoneyInputError:
            raise DentalApiDomainError(409, "Цена услуги визита недоступна") from None
        return user, doctor, visit, service, target, price

    async def create_dental_price_override(self, *, override_data, user: User, bearer) -> SimpleNamespace:
        try:
            user, doctor, visit, service, visit_service, price = self._prepare_override(
                override_data=override_data, user_id=user.id, bearer=bearer,
            )
            price_override = DoctorPriceOverride(
                visit_id=visit.id, doctor_id=doctor.id, service_id=service.id,
                original_price=service.price or Decimal("0"), new_price=price,
                reason=override_data.reason, details=override_data.details,
                visit_price_before=visit_service.price, status="pending",
                target_scope="visit_service", target_visit_service_id=visit_service.id,
                visit_context_epoch=visit.confirmation_context_epoch,
                doctor_owner_user_id=user.id,
                doctor_owner_generation=doctor.repeat_owner_generation,
                price_context_generation=visit.price_context_generation,
                price_line_generation=visit_service.price_line_generation,
                price_owner_generation=doctor.price_owner_generation,
                doctor_user_auth_epoch=user.auth_epoch,
                requester_type="doctor", requester_user_id=user.id,
                requester_user_id_snapshot=user.id, requester_auth_epoch=user.auth_epoch,
            )
            self.repository.add(price_override)
            # Capture all response scalars before commit ends the validated
            # transaction and its SET LOCAL search path.
            self.repository.flush()
            self.repository.refresh(price_override)
            response_snapshot = SimpleNamespace(**{
                column.key: getattr(price_override, column.key)
                for column in inspect(DoctorPriceOverride).column_attrs
            })
            self.repository.commit_request(bearer)
        except ProfileBearerInvalid:
            self.repository.rollback()
            raise DentalApiDomainError(401, "Сессия недействительна") from None
        except DBAPIError as exc:
            self.repository.rollback()
            sqlite_code = getattr(exc.orig, "sqlite_errorcode", 0) or 0
            if getattr(exc.orig, "sqlstate", None) == "55P03" or sqlite_code & 255 in (5, 6):
                raise DentalApiDomainError(409, "Услуга изменяется, повторите запрос") from None
            raise
        except Exception:
            self.repository.rollback()
            raise

        try:
            await self.send_price_override_notification(
                price_override=price_override, doctor=doctor, service=service, visit=visit,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Не удалось отправить уведомление о изменении цены: {exc}")
        return response_snapshot

    async def send_price_override_notification(
        self,
        *,
        price_override: DoctorPriceOverride,
        doctor,
        service,
        visit,
    ) -> None:
        registrars = self.repository.list_registrars()
        if not registrars:
            logger.warning("Не найдены пользователи с ролью Registrar для отправки уведомлений")
            return

        doctor_name = doctor.user.full_name if doctor.user else f"Врач #{doctor.id}"
        patient_info = f"Пациент #{visit.patient_id}" if visit else "Неизвестный пациент"
        details_line = f"Детали: {price_override.details}\n" if price_override.details else ""

        message = (
            "Изменение цены стоматологом\n\n"
            f"Врач: {doctor_name}\n"
            f"{patient_info}\n"
            f"Услуга: {service.name} ({self._service_code(service)})\n"
            f"Цена: {price_override.original_price} -> {price_override.new_price} UZS\n"
            f"Причина: {price_override.reason}\n"
            f"{details_line}"
            f"Время: {price_override.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            "Статус: Ожидает одобрения"
        )

        confirmed_deliveries = 0
        for registrar in registrars:
            try:
                result = await notification_sender_service.send_canonical_notification_to_user(
                    db=self.db,
                    recipient=registrar,
                    event_type="dental_price_override_pending",
                    title="Запрос стоматолога на изменение цены",
                    message=message,
                    source_module="dental",
                    metadata={
                        "override_id": price_override.id,
                        "visit_id": price_override.visit_id,
                        "patient_id": getattr(visit, "patient_id", None),
                        "doctor_id": getattr(doctor, "id", None),
                        "service_id": price_override.service_id,
                    },
                    entity_type="doctor_price_override",
                    entity_id=price_override.id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Ошибка отправки уведомления регистратору %s: %s",
                    registrar.username,
                    exc,
                )
                continue
            if result is True:
                confirmed_deliveries += 1
                logger.info(
                    "Уведомление о изменении цены доставлено регистратору %s",
                    registrar.username,
                )
            else:
                logger.error(
                    "Отправка уведомления регистратору %s не подтверждена: %s",
                    registrar.username,
                    result,
                )

        # The flag means at least one protected inbox delivery was created;
        # the pending request remains committed and reviewable either way.
        if confirmed_deliveries > 0:
            price_override.notification_sent = True
            price_override.notification_sent_at = datetime.now(UTC)
            self.repository.commit()
        else:
            logger.warning(
                "Ни одно уведомление об изменении цены не подтверждено — "
                "notification_sent остается False"
            )

    def get_dental_price_overrides(
        self,
        *,
        user_id: int,
        visit_id: int | None,
        status: str | None,
        limit: int,
    ) -> list[DoctorPriceOverride]:
        doctor = self.repository.get_doctor_by_user_id(user_id)
        if not doctor:
            raise DentalApiDomainError(404, "Врач не найден")

        return self.repository.list_price_overrides_for_doctor(
            doctor_id=doctor.id,
            visit_id=visit_id,
            status=status,
            limit=limit,
        )

    async def approve_price_override(
        self,
        *,
        override_id: int,
        approval_data,
        user: User,
        bearer,
    ) -> dict[str, Any]:
        # Both routes use the same transaction-bound review service.
        action = approval_data.action
        if action not in ["approve", "reject"]:
            raise DentalApiDomainError(
                400,
                "Действие должно быть 'approve' или 'reject'",
            )
        # Cheap pre-validation through the repository (unit tests drive this
        # path with fake repositories — no session available; the canonical
        # service below is the locked SSOT for the actual transition and
        # re-validates under the row lock).
        existing = self.repository.get_price_override(override_id)
        if existing is None:
            raise DentalApiDomainError(404, "Изменение цены не найдено")
        if action == "reject" and not (approval_data.rejection_reason or "").strip():
            raise DentalApiDomainError(
                400,
                "При отклонении необходимо указать причину",
            )

        try:
            price_override = PriceOverrideApprovalService(
                self.db
            ).process(
                override_id=override_id,
                action=action,
                rejection_reason=approval_data.rejection_reason,
                approver_id=user.id,
                bearer=bearer,
            )
        except PriceOverrideApprovalError as exc:
            raise DentalApiDomainError(exc.status_code, exc.detail) from exc

        try:
            await self.send_price_override_result_notification(
                price_override=price_override,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Не удалось отправить уведомление врачу о результате: {exc}")

        action_text = "одобрено" if action == "approve" else "отклонено"
        return {
            "success": True,
            "message": f"Изменение цены {action_text}",
            "override_id": override_id,
            "status": price_override.status,
            "approved_by": user.username,
            "approved_at": price_override.approved_at.isoformat(),
        }

    async def send_price_override_result_notification(
        self,
        *,
        price_override: DoctorPriceOverride,
    ) -> None:
        doctor = self.repository.get_doctor(price_override.doctor_id)
        if doctor is None or not doctor.active or doctor.user is None:
            return
        owner = doctor.user
        if (
            not owner.is_active or not is_doctor_role_spelling(owner.role)
            or owner.id != price_override.doctor_owner_user_id
            or owner.auth_epoch != price_override.doctor_user_auth_epoch
            or not price_override.doctor_owner_generation
            or doctor.repeat_owner_generation != price_override.doctor_owner_generation
            or not price_override.price_owner_generation
            or doctor.price_owner_generation != price_override.price_owner_generation
        ):
            return
        status_text = "одобрено" if price_override.status == "approved" else "отклонено"

        delivered = await notification_sender_service.send_canonical_notification_to_user(
            db=self.db,
            recipient=owner,
            event_type="dental_price_override_result",
            title=f"Изменение цены {status_text}",
            message="Решение доступно в списке изменений цены.",
            source_module="dental",
            metadata={
                "override_id": price_override.id,
                "status": price_override.status,
            },
            entity_type="doctor_price_override",
            entity_id=price_override.id,
        )

        if delivered:
            logger.info(
                "Уведомление о результате изменения цены "
                "записано в inbox врача %s",
                owner.username,
            )
        else:
            logger.warning(
                "Не удалось записать результат изменения "
                "цены в inbox врача %s",
                owner.username,
            )

    def get_pending_price_overrides(self, *, limit: int, offset: int = 0) -> dict[str, Any]:
        # REGPRICE-BE-004 (audit #3892, group 16): deterministic ordering and
        # offset pagination; total_count is the FULL pending total (not the
        # page size) so no older request is silently unreachable.
        overrides = self.repository.list_pending_price_overrides(
            limit=limit, offset=offset
        )
        total_count = self.repository.count_pending_price_overrides()
        result = []

        for override in overrides:
            doctor = self.repository.get_doctor(override.doctor_id)
            service = self.repository.get_service(override.service_id)
            visit = self.repository.get_visit(override.visit_id)

            result.append(
                {
                    "id": override.id,
                    "visit_id": override.visit_id,
                    "patient_id": visit.patient_id if visit else None,
                    "doctor": {
                        "id": doctor.id if doctor else None,
                        "name": (
                            doctor.user.full_name
                            if doctor and doctor.user
                            else f"Врач #{override.doctor_id}"
                        ),
                        "specialty": doctor.specialty if doctor else None,
                    },
                    "service": {
                        "id": service.id if service else None,
                        "name": service.name if service else f"Услуга #{override.service_id}",
                        "code": self._service_code(service),
                    },
                    "original_price": float(override.original_price),
                    # DERMAPRICE-BE-002 (audit #3892, group 15): the
                    # reviewer additionally sees the visit's ACTUAL
                    # before-price and the delta relative to it; the
                    # catalogue-based original_price/price_difference keep
                    # their immutable reference semantics.
                    "visit_price_before": (
                        float(override.visit_price_before)
                        if override.visit_price_before is not None
                        else None
                    ),
                    "visit_price_difference": (
                        float(override.new_price - override.visit_price_before)
                        if override.visit_price_before is not None
                        else None
                    ),
                    "new_price": float(override.new_price),
                    "price_difference": float(override.new_price - override.original_price),
                    "reason": override.reason,
                    "details": override.details,
                    "created_at": override.created_at.isoformat(),
                    "notification_sent": override.notification_sent,
                    "notification_sent_at": (
                        override.notification_sent_at.isoformat()
                        if override.notification_sent_at
                        else None
                    ),
                }
            )

        return {
            "success": True,
            "overrides": result,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
        }

    def rollback(self) -> None:
        self.repository.rollback()
