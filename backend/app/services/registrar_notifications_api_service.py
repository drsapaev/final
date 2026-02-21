"""
API endpoints для управления уведомлениями регистратуры
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.online_queue import OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit
from app.repositories.registrar_notifications_api_repository import RegistrarNotificationsApiRepository
from app.services.registrar_notification_service import (
    get_registrar_notification_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _repo(db: Session) -> RegistrarNotificationsApiRepository:
    return RegistrarNotificationsApiRepository(db)

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
async def get_active_registrars(
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
            detail=f"Ошибка получения списка регистраторов: {str(e)}",
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

        # Получаем запись
        if request_data.appointment_type == "visit":
            appointment = (
                _repo(db).query(Visit).filter(Visit.id == request_data.appointment_id).first()
            )
        else:
            appointment = (
                _repo(db).query(Appointment)
                .filter(Appointment.id == request_data.appointment_id)
                .first()
            )

        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена"
            )

        # Получаем пациента
        patient = _repo(db).query(Patient).filter(Patient.id == appointment.patient_id).first()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Пациент не найден"
            )

        # Получаем услуги (если есть)
        services = []
        if request_data.appointment_type == "visit":
            from app.models.visit import VisitService

            visit_services = (
                _repo(db).query(VisitService)
                .filter(VisitService.visit_id == appointment.id)
                .all()
            )
            for vs in visit_services:
                service = (
                    _repo(db).query(Service).filter(Service.code == vs.service_code).first()
                )
                if service:
                    services.append(service)

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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о записи: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки уведомления: {str(e)}",
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

        # Получаем изменение цены
        price_override = (
            _repo(db).query(DoctorPriceOverride)
            .filter(DoctorPriceOverride.id == request_data.price_override_id)
            .first()
        )

        if not price_override:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Изменение цены не найдено",
            )

        # Получаем врача
        doctor = _repo(db).query(Doctor).filter(Doctor.id == price_override.doctor_id).first()
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Врач не найден"
            )

        # Получаем услугу
        service_obj = (
            _repo(db).query(Service).filter(Service.id == price_override.service_id).first()
        )
        if not service_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена"
            )

        # Получаем визит и пациента (если есть)
        visit = None
        patient = None
        if price_override.visit_id:
            visit = _repo(db).query(Visit).filter(Visit.id == price_override.visit_id).first()
            if visit:
                patient = (
                    _repo(db).query(Patient).filter(Patient.id == visit.patient_id).first()
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления об изменении цены: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки уведомления: {str(e)}",
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

        # Получаем запись в очереди
        queue_entry = (
            _repo(db).query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.id == request_data.queue_entry_id)
            .first()
        )

        if not queue_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись в очереди не найдена",
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о статусе очереди: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки уведомления: {str(e)}",
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
            detail=f"Ошибка отправки уведомления: {str(e)}",
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
            detail=f"Ошибка отправки сводки: {str(e)}",
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
            detail=f"Ошибка получения статистики: {str(e)}",
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
            detail=f"Ошибка отправки тестового уведомления: {str(e)}",
        )
