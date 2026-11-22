"""Service layer for dental endpoints."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.doctor_price_override import DoctorPriceOverride
from app.models.user import User
from app.repositories.dental_api_repository import DentalApiRepository
from app.services.notifications import notification_sender_service
from app.services.price_override_approval import (
    PENDING_DUPLICATE_DETAIL,
    PriceOverrideApprovalError,
    PriceOverrideApprovalService,
)

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
        visit_doctor_id = getattr(visit, "doctor_id", None)
        if visit_doctor_id == getattr(doctor, "id", None):
            return True

        get_doctor = getattr(self.repository, "get_doctor", None)
        assigned_doctor = get_doctor(user_id) if get_doctor else None
        # Some legacy visit writers stored User.id in doctor_id. Allow that only
        # when the value does not target another real Doctor row.
        return assigned_doctor is None and visit_doctor_id == user_id

    async def create_dental_price_override(self, *, override_data, user: User) -> DoctorPriceOverride:
        visit = self.repository.get_visit(override_data.visit_id)
        if not visit:
            raise DentalApiDomainError(404, "Визит не найден")

        service = self.repository.get_service(override_data.service_id)
        if not service:
            raise DentalApiDomainError(404, "Услуга не найдена")
        if not service.allow_doctor_price_override:
            raise DentalApiDomainError(
                400,
                "Данная услуга не разрешает изменение цены врачом",
            )

        doctor = self.repository.get_doctor_by_user_id(user.id)
        if not doctor:
            raise DentalApiDomainError(404, "Врач не найден")
        # Vocabulary note: the system provisions dentists with different
        # specialty spellings — queue machinery seeds 'stomatology'
        # (service_mapping.py), user provisioning & dev_seed create
        # 'dentistry' (user_mgmt/_core.py), departments use 'dental'. All
        # three denote the same dental clinician, so all are accepted here.
        # (Repo-wide canonical vocabulary is a separate pending decision.)
        if doctor.specialty not in ("stomatology", "dental", "dentistry"):
            raise DentalApiDomainError(
                403,
                "Только стоматолог может указывать цену после лечения",
            )

        if not self._visit_belongs_to_doctor(visit=visit, doctor=doctor, user_id=user.id):
            raise DentalApiDomainError(403, "Access denied")

        # DERMAPRICE-BE-001 shared policy (audit #3892, group 15): the dental
        # sibling feeds the SAME DoctorPriceOverride workflow and the SAME
        # shared approval — the requested service must be attached to the
        # visit (VisitService membership), otherwise the approval would
        # either silently skip the price update (old false-success) or be
        # refused later at fail-closed approval time.
        visit_service = self.repository.get_visit_service(
            visit_id=override_data.visit_id,
            service_id=override_data.service_id,
        )
        if visit_service is None:
            raise DentalApiDomainError(
                409,
                "Услуга не привязана к выбранному визиту",
            )

        # REGPRICE-BE-003 (audit #3892, group 16): two sequential pending
        # overrides for the same visit/service can be approved in reverse
        # order — each approval validated against the SAME captured
        # before-price, silently overwriting the newer intent. Creation is
        # refused while one intent is still awaiting review. The probe goes
        # through the repository (session access is boundary-forbidden in
        # this service layer).
        if self.repository.has_pending_override(
            visit_id=override_data.visit_id,
            service_id=override_data.service_id,
        ):
            raise DentalApiDomainError(409, PENDING_DUPLICATE_DETAIL)

        price_override = DoctorPriceOverride(
            visit_id=override_data.visit_id,
            doctor_id=doctor.id,
            service_id=override_data.service_id,
            original_price=service.price or Decimal("0"),
            new_price=override_data.new_price,
            reason=override_data.reason,
            details=override_data.details,
            # DERMAPRICE-BE-002: visit-level before-price (may differ from the
            # catalogue reference after discounts/overrides).
            visit_price_before=visit_service.price,
            status="pending",
        )

        self.repository.add(price_override)
        self.repository.commit()
        self.repository.refresh(price_override)

        try:
            await self.send_price_override_notification(
                price_override=price_override,
                doctor=doctor,
                service=service,
                visit=visit,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Не удалось отправить уведомление о изменении цены: {exc}")

        return price_override

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
    ) -> dict[str, Any]:
        # REGPRICE-BE-001/002/003/005 (audit #3892, group 16): the dental
        # route previously mutated ONLY the chargeable VisitService rows and
        # left the Visit.doctor_price_override JSON mirror stale, while the
        # registrar sibling route mutated ONLY the JSON. Both routes now
        # delegate to the canonical PriceOverrideApprovalService: locked
        # decision (concurrent loser gets 409), identical approve outcome
        # (chargeable price + JSON mirror in ONE commit), stale-intent
        # validation (visit_price_before vs current price → 409) and the
        # mandatory non-blank rejection reason (absent/whitespace → 400).
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
            )
        except PriceOverrideApprovalError as exc:
            raise DentalApiDomainError(exc.status_code, exc.detail) from exc

        try:
            await self.send_price_override_result_notification(
                price_override=price_override,
                approved_by=user,
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
        approved_by: User,
    ) -> None:
        doctor = self.repository.get_doctor(price_override.doctor_id)
        if not doctor or not doctor.user:
            return

        service = self.repository.get_service(price_override.service_id)
        status_text = "ОДОБРЕНО" if price_override.status == "approved" else "ОТКЛОНЕНО"

        message = (
            f"Изменение цены {status_text}\n\n"
            f"Услуга: {service.name if service else f'Услуга #{price_override.service_id}'}\n"
            f"Цена: {price_override.original_price} -> {price_override.new_price} UZS\n"
            f"Ваша причина: {price_override.reason}\n\n"
            f"Рассмотрел: {approved_by.full_name or approved_by.username}\n"
            f"Время: {price_override.approved_at.strftime('%d.%m.%Y %H:%M')}\n"
            f"{f'Причина отклонения: {price_override.rejection_reason}' if price_override.rejection_reason else ''}"
        )

        delivered = await notification_sender_service.send_canonical_notification_to_user(
            db=self.db,
            recipient=doctor.user,
            event_type="dental_price_override_result",
            title=f"Изменение цены {status_text.lower()}",
            message=message,
            source_module="dental",
            metadata={
                "override_id": price_override.id,
                "visit_id": price_override.visit_id,
                "service_id": price_override.service_id,
                "status": price_override.status,
            },
            entity_type="doctor_price_override",
            entity_id=price_override.id,
        )

        if delivered:
            logger.info(
                "Уведомление о результате изменения цены "
                "записано в inbox врача %s",
                doctor.user.username,
            )
        else:
            logger.warning(
                "Не удалось записать результат изменения "
                "цены в inbox врача %s",
                doctor.user.username,
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
