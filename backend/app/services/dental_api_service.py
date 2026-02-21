import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api import deps
from app.models.clinic import Doctor
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit
from app.repositories.dental_api_repository import DentalApiRepository
from app.services.notifications import notification_sender_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dental", tags=["dental"])


# ===================== ФУНКЦИИ УВЕДОМЛЕНИЙ =====================


async def send_price_override_notification(
    repository: DentalApiRepository,
    price_override: DoctorPriceOverride,
    doctor: Doctor,
    service: Service,
    visit: Visit,
):
    """Отправить уведомление в регистратуру об изменении цены"""
    try:

        # Получаем всех пользователей с ролью Registrar
        registrars = repository.list_registrars()

        if not registrars:
            logger.warning(
                "Не найдены пользователи с ролью Registrar для отправки уведомлений"
            )
            return

        # Формируем сообщение
        doctor_name = doctor.user.full_name if doctor.user else f"Врач #{doctor.id}"
        patient_info = (
            f"Пациент #{visit.patient_id}" if visit else "Неизвестный пациент"
        )

        message = f"""
🦷 ИЗМЕНЕНИЕ ЦЕНЫ СТОМАТОЛОГОМ

👨‍⚕️ Врач: {doctor_name}
👤 {patient_info}
🔧 Услуга: {service.name} ({service.code})
💰 Цена: {price_override.original_price} → {price_override.new_price} UZS
📝 Причина: {price_override.reason}
{f"📋 Детали: {price_override.details}" if price_override.details else ""}

⏰ Время: {price_override.created_at.strftime('%d.%m.%Y %H:%M')}
🔄 Статус: Ожидает одобрения

Для одобрения/отклонения перейдите в панель регистратора.
        """.strip()

        # Отправляем уведомления всем регистраторам
        for registrar in registrars:
            try:
                # Отправляем через Telegram, если есть telegram_id
                if hasattr(registrar, 'telegram_id') and registrar.telegram_id:
                    await notification_sender_service.send_telegram_message(
                        user_id=registrar.telegram_id,
                        message=message,
                        parse_mode="HTML",
                    )

                # Также можем отправить через другие каналы (email, SMS)
                # if registrar.email:
                #     await notification_service.send_email(
                #         to_email=registrar.email,
                #         subject="Изменение цены стоматологом",
                #         body=message
                #     )

                logger.info(
                    f"Уведомление о изменении цены отправлено регистратору {registrar.username}"
                )

            except Exception as e:
                logger.error(
                    f"Ошибка отправки уведомления регистратору {registrar.username}: {e}"
                )

        # Сохраняем информацию об отправленном уведомлении
        price_override.notification_sent = True
        price_override.notification_sent_at = datetime.utcnow()
        repository.commit()

    except Exception as e:
        logger.error(f"Ошибка отправки уведомлений об изменении цены: {e}")
        raise


class DentalPriceOverrideRequest(BaseModel):
    visit_id: int
    service_id: int
    new_price: Decimal
    reason: str
    details: str | None = None
    treatment_completed: bool = True  # Для стоматолога - указание цены после лечения


class DentalPriceOverrideResponse(BaseModel):
    id: int
    visit_id: int
    service_id: int
    original_price: Decimal
    new_price: Decimal
    reason: str
    details: str | None
    status: str
    treatment_completed: bool
    created_at: datetime


@router.get("/examinations", summary="Стоматологические осмотры")
async def get_dental_examinations(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Получить список стоматологических осмотров
    """
    try:
        # Пока возвращаем пустой список - можно расширить при наличии модели
        return []
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения осмотров: {str(e)}"
        )


@router.post("/examinations", summary="Создать стоматологический осмотр")
async def create_dental_examination(
    examination_data: dict[str, Any],
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> dict[str, Any]:
    """
    Создать новый стоматологический осмотр
    """
    try:
        # Пока возвращаем заглушку - можно расширить при наличии модели
        return {"message": "Стоматологический осмотр создан", "id": 1}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка создания осмотра: {str(e)}"
        )


@router.get("/treatments", summary="Планы лечения")
async def get_treatment_plans(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Получить список планов лечения
    """
    try:
        # Пока возвращаем пустой список - можно расширить при наличии модели
        return []
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения планов лечения: {str(e)}"
        )


@router.post("/treatments", summary="Создать план лечения")
async def create_treatment_plan(
    treatment_data: dict[str, Any],
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> dict[str, Any]:
    """
    Создать новый план лечения
    """
    try:
        # Пока возвращаем заглушку - можно расширить при наличии модели
        return {"message": "План лечения создан", "id": 1}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка создания плана лечения: {str(e)}"
        )


@router.get("/prosthetics", summary="Протезирование")
async def get_prosthetics(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Получить список протезов
    """
    try:
        # Пока возвращаем пустой список - можно расширить при наличии модели
        return []
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения протезов: {str(e)}"
        )


@router.post("/prosthetics", summary="Создать протез")
async def create_prosthetic(
    prosthetic_data: dict[str, Any],
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> dict[str, Any]:
    """
    Создать новый протез
    """
    try:
        # Пока возвращаем заглушку - можно расширить при наличии модели
        return {"message": "Протез создан", "id": 1}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка создания протеза: {str(e)}"
        )


@router.get("/xray", summary="Рентгеновские снимки")
async def get_xray_images(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
    patient_id: int | None = None,
) -> dict[str, Any]:
    """
    Получить рентгеновские снимки пациента
    """
    try:
        return {
            "message": "Модуль рентгеновских снимков будет доступен в следующей версии"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения снимков: {str(e)}"
        )


@router.post(
    "/price-override",
    summary="Указать цену после лечения",
    response_model=DentalPriceOverrideResponse,
)
async def create_dental_price_override(
    override_data: DentalPriceOverrideRequest,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
) -> DentalPriceOverrideResponse:
    """
    Стоматолог указывает цену после проведенного лечения
    """
    repository = DentalApiRepository(db)
    try:
        # Проверяем существование визита
        visit = repository.get_visit_by_id(override_data.visit_id)
        if not visit:
            raise HTTPException(status_code=404, detail="Визит не найден")

        # Проверяем существование услуги
        service = repository.get_service_by_id(override_data.service_id)
        if not service:
            raise HTTPException(status_code=404, detail="Услуга не найдена")

        # Проверяем, что услуга разрешает изменение цены врачом
        if not service.allow_doctor_price_override:
            raise HTTPException(
                status_code=400,
                detail="Данная услуга не разрешает изменение цены врачом",
            )

        # Получаем врача по пользователю
        doctor = repository.get_doctor_by_user_id(user.id)
        if not doctor:
            raise HTTPException(status_code=404, detail="Врач не найден")

        # Проверяем, что врач - стоматолог
        if doctor.specialty not in ["stomatology", "dental"]:
            raise HTTPException(
                status_code=403,
                detail="Только стоматолог может указывать цену после лечения",
            )

        # Создаём запись об изменении цены
        price_override = DoctorPriceOverride(
            visit_id=override_data.visit_id,
            doctor_id=doctor.id,
            service_id=override_data.service_id,
            original_price=service.price or Decimal("0"),
            new_price=override_data.new_price,
            reason=override_data.reason,
            details=override_data.details,
            status="pending",  # Требует одобрения регистратуры
        )

        repository.add(price_override)
        repository.commit()
        repository.refresh(price_override)

        # Отправляем уведомление в регистратуру
        try:
            await send_price_override_notification(
                repository=repository,
                price_override=price_override,
                doctor=doctor,
                service=service,
                visit=visit,
            )
        except Exception as e:
            # Не прерываем выполнение, если уведомление не отправилось
            logger.warning(f"Не удалось отправить уведомление о изменении цены: {e}")

        return DentalPriceOverrideResponse(
            id=price_override.id,
            visit_id=price_override.visit_id,
            service_id=price_override.service_id,
            original_price=price_override.original_price,
            new_price=price_override.new_price,
            reason=price_override.reason,
            details=price_override.details,
            status=price_override.status,
            treatment_completed=override_data.treatment_completed,
            created_at=price_override.created_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        repository.rollback()
        raise HTTPException(
            status_code=500, detail=f"Ошибка создания изменения цены: {str(e)}"
        )


@router.get("/price-overrides", summary="Получить изменения цен стоматолога")
async def get_dental_price_overrides(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Doctor")),
    visit_id: int | None = Query(None, description="ID визита"),
    status: str | None = Query(
        None, description="Статус (pending, approved, rejected)"
    ),
    limit: int = Query(50, ge=1, le=100),
) -> list[DentalPriceOverrideResponse]:
    """
    Получить список изменений цен стоматолога
    """
    repository = DentalApiRepository(db)
    try:
        # Получаем врача по пользователю
        doctor = repository.get_doctor_by_user_id(user.id)
        if not doctor:
            raise HTTPException(status_code=404, detail="Врач не найден")

        overrides = repository.list_price_overrides_for_doctor(
            doctor_id=doctor.id,
            visit_id=visit_id,
            status=status,
            limit=limit,
        )

        return [
            DentalPriceOverrideResponse(
                id=override.id,
                visit_id=override.visit_id,
                service_id=override.service_id,
                original_price=override.original_price,
                new_price=override.new_price,
                reason=override.reason,
                details=override.details,
                status=override.status,
                treatment_completed=True,  # Для стоматолога всегда True
                created_at=override.created_at,
            )
            for override in overrides
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения изменений цен: {str(e)}"
        )


# ===================== УПРАВЛЕНИЕ ИЗМЕНЕНИЯМИ ЦЕН (РЕГИСТРАТУРА) =====================


class PriceOverrideApprovalRequest(BaseModel):
    action: str  # "approve" или "reject"
    rejection_reason: str | None = None


@router.put(
    "/price-override/{override_id}/approve", summary="Одобрить/отклонить изменение цены"
)
async def approve_price_override(
    override_id: int,
    approval_data: PriceOverrideApprovalRequest,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Registrar")),
):
    """
    Одобрить или отклонить изменение цены стоматологом
    Доступно только для регистраторов и администраторов
    """
    repository = DentalApiRepository(db)
    try:
        # Находим запись об изменении цены
        price_override = repository.get_price_override_by_id(override_id)

        if not price_override:
            raise HTTPException(status_code=404, detail="Изменение цены не найдено")

        # Проверяем, что изменение еще не обработано
        if price_override.status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Изменение цены уже обработано (статус: {price_override.status})",
            )

        # Валидируем действие
        if approval_data.action not in ["approve", "reject"]:
            raise HTTPException(
                status_code=400, detail="Действие должно быть 'approve' или 'reject'"
            )

        # Если отклоняем, требуем причину
        if approval_data.action == "reject" and not approval_data.rejection_reason:
            raise HTTPException(
                status_code=400, detail="При отклонении необходимо указать причину"
            )

        # Обновляем статус
        price_override.status = (
            "approved" if approval_data.action == "approve" else "rejected"
        )
        price_override.approved_by = user.id
        price_override.approved_at = datetime.utcnow()

        if approval_data.action == "reject":
            price_override.rejection_reason = approval_data.rejection_reason

        # Если одобряем, обновляем цену услуги в визите
        if approval_data.action == "approve":
            visit_service = repository.get_visit_service(
                visit_id=price_override.visit_id,
                service_id=price_override.service_id,
            )

            if visit_service:
                visit_service.price = price_override.new_price
                visit_service.custom_price = price_override.new_price

        repository.commit()

        # Отправляем уведомление врачу о результате
        try:
            await send_price_override_result_notification(
                repository=repository,
                price_override=price_override,
                approved_by=user,
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление врачу о результате: {e}")

        action_text = "одобрено" if approval_data.action == "approve" else "отклонено"

        return {
            "success": True,
            "message": f"Изменение цены {action_text}",
            "override_id": override_id,
            "status": price_override.status,
            "approved_by": user.username,
            "approved_at": price_override.approved_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        repository.rollback()
        raise HTTPException(
            status_code=500, detail=f"Ошибка обработки изменения цены: {str(e)}"
        )


@router.get(
    "/price-overrides/pending", summary="Получить ожидающие одобрения изменения цен"
)
async def get_pending_price_overrides(
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "Registrar")),
    limit: int = Query(50, ge=1, le=100),
):
    """
    Получить список изменений цен, ожидающих одобрения
    Доступно только для регистраторов и администраторов
    """
    repository = DentalApiRepository(db)
    try:
        overrides = repository.list_pending_price_overrides(limit=limit)

        result = []
        for override in overrides:
            # Получаем дополнительную информацию
            doctor = repository.get_doctor_by_id(override.doctor_id)
            service = repository.get_service_by_id(override.service_id)
            visit = repository.get_visit_by_id(override.visit_id)

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
                        "name": (
                            service.name
                            if service
                            else f"Услуга #{override.service_id}"
                        ),
                        "code": service.code if service else None,
                    },
                    "original_price": float(override.original_price),
                    "new_price": float(override.new_price),
                    "price_difference": float(
                        override.new_price - override.original_price
                    ),
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

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения ожидающих изменений цен: {str(e)}",
        )


async def send_price_override_result_notification(
    repository: DentalApiRepository,
    price_override: DoctorPriceOverride,
    approved_by: User,
):
    """Отправить уведомление врачу о результате рассмотрения изменения цены"""
    try:

        # Получаем врача
        doctor = repository.get_doctor_by_id(price_override.doctor_id)
        if not doctor or not doctor.user:
            return

        # Получаем услугу
        service = repository.get_service_by_id(price_override.service_id)

        # Формируем сообщение
        status_emoji = "✅" if price_override.status == "approved" else "❌"
        status_text = "ОДОБРЕНО" if price_override.status == "approved" else "ОТКЛОНЕНО"

        message = f"""
{status_emoji} ИЗМЕНЕНИЕ ЦЕНЫ {status_text}

🔧 Услуга: {service.name if service else f"Услуга #{price_override.service_id}"}
💰 Цена: {price_override.original_price} → {price_override.new_price} UZS
📝 Ваша причина: {price_override.reason}

👤 Рассмотрел: {approved_by.full_name or approved_by.username}
⏰ Время: {price_override.approved_at.strftime('%d.%m.%Y %H:%M')}
{f"❌ Причина отклонения: {price_override.rejection_reason}" if price_override.rejection_reason else ""}
        """.strip()

        # Отправляем уведомление врачу
        if hasattr(doctor.user, 'telegram_id') and doctor.user.telegram_id:
            await notification_sender_service.send_telegram_message(
                user_id=doctor.user.telegram_id, message=message, parse_mode="HTML"
            )

        logger.info(
            f"Уведомление о результате изменения цены отправлено врачу {doctor.user.username}"
        )

    except Exception as e:
        logger.error(f"Ошибка отправки уведомления врачу о результате: {e}")
        raise
