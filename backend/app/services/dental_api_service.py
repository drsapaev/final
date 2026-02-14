"""Service layer for dental endpoints."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.doctor_price_override import DoctorPriceOverride
from app.models.user import User
from app.repositories.dental_api_repository import DentalApiRepository
from app.services.notifications import notification_sender_service

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
        self.repository = repository or DentalApiRepository(db)

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
        if doctor.specialty not in ["stomatology", "dental"]:
            raise DentalApiDomainError(
                403,
                "Только стоматолог может указывать цену после лечения",
            )

        price_override = DoctorPriceOverride(
            visit_id=override_data.visit_id,
            doctor_id=doctor.id,
            service_id=override_data.service_id,
            original_price=service.price or Decimal("0"),
            new_price=override_data.new_price,
            reason=override_data.reason,
            details=override_data.details,
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
            f"Услуга: {service.name} ({service.code})\n"
            f"Цена: {price_override.original_price} -> {price_override.new_price} UZS\n"
            f"Причина: {price_override.reason}\n"
            f"{details_line}"
            f"Время: {price_override.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            "Статус: Ожидает одобрения"
        )

        for registrar in registrars:
            try:
                if hasattr(registrar, "telegram_id") and registrar.telegram_id:
                    await notification_sender_service.send_telegram_message(
                        user_id=registrar.telegram_id,
                        message=message,
                        parse_mode="HTML",
                    )
                logger.info(
                    "Уведомление о изменении цены отправлено регистратору %s",
                    registrar.username,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Ошибка отправки уведомления регистратору %s: %s",
                    registrar.username,
                    exc,
                )

        price_override.notification_sent = True
        price_override.notification_sent_at = datetime.utcnow()
        self.repository.commit()

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
        price_override = self.repository.get_price_override(override_id)
        if not price_override:
            raise DentalApiDomainError(404, "Изменение цены не найдено")
        if price_override.status != "pending":
            raise DentalApiDomainError(
                400,
                f"Изменение цены уже обработано (статус: {price_override.status})",
            )

        action = approval_data.action
        if action not in ["approve", "reject"]:
            raise DentalApiDomainError(
                400,
                "Действие должно быть 'approve' или 'reject'",
            )
        if action == "reject" and not approval_data.rejection_reason:
            raise DentalApiDomainError(
                400,
                "При отклонении необходимо указать причину",
            )

        price_override.status = "approved" if action == "approve" else "rejected"
        price_override.approved_by = user.id
        price_override.approved_at = datetime.utcnow()
        if action == "reject":
            price_override.rejection_reason = approval_data.rejection_reason

        if action == "approve":
            visit_service = self.repository.get_visit_service(
                visit_id=price_override.visit_id,
                service_id=price_override.service_id,
            )
            if visit_service:
                visit_service.price = price_override.new_price
                visit_service.custom_price = price_override.new_price

        self.repository.commit()

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

        if hasattr(doctor.user, "telegram_id") and doctor.user.telegram_id:
            await notification_sender_service.send_telegram_message(
                user_id=doctor.user.telegram_id,
                message=message,
                parse_mode="HTML",
            )

        logger.info(
            "Уведомление о результате изменения цены отправлено врачу %s",
            doctor.user.username,
        )

    def get_pending_price_overrides(self, *, limit: int) -> dict[str, Any]:
        overrides = self.repository.list_pending_price_overrides(limit=limit)
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
                        "code": service.code if service else None,
                    },
                    "original_price": float(override.original_price),
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

        return {"success": True, "overrides": result, "total_count": len(result)}

    def rollback(self) -> None:
        self.repository.rollback()
