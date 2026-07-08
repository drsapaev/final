"""
API endpoints для управления уведомлениями регистратуры
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.services.registrar_notification_service import (
    get_registrar_notification_service,
)
from app.services.registrar_notifications_api_service import (
    RegistrarNotificationsApiDomainError,
    RegistrarNotificationsApiService,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ===================== PYDANTIC СХЕМЫ =====================


class NotificationRequest(BaseModel):
    """Базовая схема для запроса уведомления"""

    message: str = Field(..., description="Текст уведомления")
    priority: str = Field(
        default="normal", description="Приоритет: normal, high, urgent, critical"
    )
    department: str | None = Field(None, description="Отделение (опционально)")


class AppointmentNotificationRequest(BaseModel):
    """Схема для уведомления о записи"""

    appointment_id: int = Field(..., description="ID записи или визита")
    appointment_type: str = Field(..., description="Тип: appointment или visit")
    priority: str = Field(default="normal", description="Приоритет уведомления")


class PriceChangeNotificationRequest(BaseModel):
    """Схема для уведомления об изменении цены"""

    price_override_id: int = Field(..., description="ID изменения цены")


class QueueStatusNotificationRequest(BaseModel):
    """Схема для уведомления о статусе очереди"""

    queue_entry_id: int = Field(..., description="ID записи в очереди")
    status_change: str = Field(..., description="Изменение статуса")
    additional_info: str | None = Field(
        None, description="Дополнительная информация"
    )


class SystemAlertRequest(BaseModel):
    """Схема для системного уведомления"""

    alert_type: str = Field(..., description="Тип уведомления")
    message: str = Field(..., description="Текст уведомления")
    priority: str = Field(default="normal", description="Приоритет")
    department: str | None = Field(None, description="Отделение")


class NotificationResponse(BaseModel):
    """Схема ответа уведомления"""

    success: bool
    message: str
    sent_count: int | None = None
    results: list[dict[str, Any]] | None = None


class RegistrarListResponse(BaseModel):
    """Схема списка регистраторов"""

    registrars: list[dict[str, Any]]
    total_count: int


class NotificationStatsResponse(BaseModel):
    """Схема статистики уведомлений"""

    total_sent: int
    successful_deliveries: int
    failed_deliveries: int
    channels_stats: dict[str, int]
    recent_notifications: list[dict[str, Any]]


# ===================== ENDPOINTS =====================


@router.get("/registrars", response_model=RegistrarListResponse)
async def get_active_registrars(    limit: int = Query(default=100, ge=1, le=500, description="Количество записей"),
    offset: int = Query(default=0, ge=0, description="Смещение"),
department: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar"])),
):
    """Получить список активных регистраторов"""
    try:
        service = get_registrar_notification_service(db)

        if department:
            registrars = service.get_registrars_by_department(department)
        else:
            registrars = service.get_active_registrars()

        registrars_data = []
        for registrar in registrars:
            registrars_data.append(
                {
                    "id": registrar.id,
                    "username": registrar.username,
                    "full_name": registrar.full_name,
                    "email": registrar.email,
                    "phone": getattr(registrar, 'phone', None),
                    "telegram_id": getattr(registrar, 'telegram_id', None),
                    "is_active": registrar.is_active,
                    "last_login": (
                        registrar.last_login.isoformat()
                        if registrar.last_login
                        else None
                    ),
                }
            )

        return RegistrarListResponse(
            registrars=registrars_data, total_count=len(registrars_data)
        )

    except Exception as e:
        logger.error(f"Ошибка получения списка регистраторов: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/appointment", response_model=NotificationResponse)
async def notify_new_appointment(
    request_data: AppointmentNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Doctor", "Registrar"])),
):
    """Отправить уведомление о новой записи"""
    try:
        service = get_registrar_notification_service(db)
        appointment, patient, services = RegistrarNotificationsApiService(
            db
        ).get_appointment_context(
            appointment_id=request_data.appointment_id,
            appointment_type=request_data.appointment_type,
        )

        # Отправляем уведомление
        result = await service.notify_new_appointment(
            appointment=appointment,
            patient=patient,
            services=services,
            priority=request_data.priority,
        )

        return NotificationResponse(
            success=result["success"],
            message=result.get("message", ""),
            sent_count=len(result.get("results", [])),
            results=result.get("results", []),
        )

    except RegistrarNotificationsApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о записи: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/price-change", response_model=NotificationResponse)
async def notify_price_change(
    request_data: PriceChangeNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Doctor"])),
):
    """Отправить уведомление об изменении цены"""
    try:
        service = get_registrar_notification_service(db)
        (
            price_override,
            doctor,
            service_obj,
            visit,
            patient,
        ) = RegistrarNotificationsApiService(db).get_price_change_context(
            price_override_id=request_data.price_override_id
        )

        # Отправляем уведомление
        result = await service.notify_price_change(
            price_override=price_override,
            doctor=doctor,
            service=service_obj,
            visit=visit,
            patient=patient,
        )

        return NotificationResponse(
            success=result["success"],
            message=result.get("message", ""),
            sent_count=len(result.get("results", [])),
            results=result.get("results", []),
        )

    except RegistrarNotificationsApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об изменении цены: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/queue-status", response_model=NotificationResponse)
async def notify_queue_status(
    request_data: QueueStatusNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar", "Doctor"])),
):
    """Отправить уведомление о статусе очереди"""
    try:
        service = get_registrar_notification_service(db)
        queue_entry = RegistrarNotificationsApiService(db).get_queue_entry(
            queue_entry_id=request_data.queue_entry_id
        )

        # Отправляем уведомление
        result = await service.notify_queue_status(
            queue_entry=queue_entry,
            status_change=request_data.status_change,
            additional_info=request_data.additional_info,
        )

        return NotificationResponse(
            success=result["success"],
            message=result.get("message", ""),
            sent_count=len(result.get("results", [])),
            results=result.get("results", []),
        )

    except RegistrarNotificationsApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о статусе очереди: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/system-alert", response_model=NotificationResponse)
async def send_system_alert(
    request_data: SystemAlertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin"])),
):
    """Отправить системное уведомление"""
    try:
        service = get_registrar_notification_service(db)

        # Отправляем системное уведомление
        result = await service.notify_system_alert(
            alert_type=request_data.alert_type,
            message=request_data.message,
            priority=request_data.priority,
            department=request_data.department,
        )

        return NotificationResponse(
            success=result["success"],
            message=result.get("message", ""),
            sent_count=len(result.get("results", [])),
            results=result.get("results", []),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка отправки системного уведомления: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/daily-summary", response_model=NotificationResponse)
async def send_daily_summary(
    target_date: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar"])),
):
    """Отправить ежедневную сводку"""
    try:
        service = get_registrar_notification_service(db)

        # Парсим дату
        summary_date = None
        if target_date:
            try:
                summary_date = datetime.strptime(target_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неверный формат даты. Используйте YYYY-MM-DD",
                )

        # Отправляем ежедневную сводку
        result = await service.send_daily_summary(target_date=summary_date)

        return NotificationResponse(
            success=result["success"],
            message=result.get("message", ""),
            sent_count=len(result.get("results", [])),
            results=result.get("results", []),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка отправки ежедневной сводки: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/stats", response_model=NotificationStatsResponse)
async def get_notification_stats(
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar"])),
):
    """Получить статистику уведомлений"""
    try:
        # Базовая статистика (заглушка, можно расширить)
        stats = {
            "total_sent": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "channels_stats": {"telegram": 0, "email": 0, "sms": 0},
            "recent_notifications": [],
        }

        # Здесь можно добавить реальную логику сбора статистики
        # из логов или специальной таблицы уведомлений

        return NotificationStatsResponse(**stats)

    except Exception as e:
        logger.error(f"Ошибка получения статистики уведомлений: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/test", response_model=NotificationResponse)
async def test_notifications(
    message: str = "Тестовое уведомление регистратуры",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin"])),
):
    """Отправить тестовое уведомление"""
    try:
        service = get_registrar_notification_service(db)

        # Отправляем тестовое системное уведомление
        result = await service.notify_system_alert(
            alert_type="test", message=f"🧪 ТЕСТ: {message}", priority="normal"
        )

        return NotificationResponse(
            success=result["success"],
            message=result.get("message", ""),
            sent_count=len(result.get("results", [])),
            results=result.get("results", []),
        )

    except Exception as e:
        logger.error(f"Ошибка отправки тестового уведомления: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
