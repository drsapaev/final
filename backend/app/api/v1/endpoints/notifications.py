from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.crud import patient as patient_crud, visit as visit_crud
from app.models.user import User
from app.schemas.patient import Patient
from app.schemas.visit import Visit
from app.services.notifications import notification_service

router = APIRouter()


@router.post("/send-appointment-reminder")
async def send_appointment_reminder(
    background_tasks: BackgroundTasks,
    patient_id: int,
    appointment_date: datetime,
    doctor_name: str,
    department: str,
    current_user: User = Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db),
):
    """Отправка напоминания о записи"""
    # Получаем данные пациента
    patient = patient_crud.get(db, id=patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")

    # Отправляем уведомление в фоновом режиме
    background_tasks.add_task(
        notification_service.send_appointment_reminder,
        patient.email,
        patient.phone,
        appointment_date,
        doctor_name,
        department,
    )

    return {
        "message": "Напоминание отправлено",
        "patient_id": patient_id,
        "sent_at": datetime.utcnow().isoformat(),
    }


@router.post("/send-visit-confirmation")
async def send_visit_confirmation(
    background_tasks: BackgroundTasks,
    visit_id: int,
    queue_number: Optional[int] = None,
    current_user: User = Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db),
):
    """Отправка подтверждения визита"""
    # Получаем данные визита
    visit = visit_crud.get(db, id=visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Визит не найден")

    # Получаем данные пациента
    patient = patient_crud.get(db, id=visit.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")

    # Отправляем уведомление в фоновом режиме
    background_tasks.add_task(
        notification_service.send_visit_confirmation,
        patient.email,
        patient.phone,
        visit.date,
        "Врач",  # TODO: получить имя врача
        "Отделение",  # TODO: получить название отделения
        queue_number,
    )

    return {
        "message": "Подтверждение визита отправлено",
        "visit_id": visit_id,
        "sent_at": datetime.utcnow().isoformat(),
    }


@router.post("/send-payment-notification")
async def send_payment_notification(
    background_tasks: BackgroundTasks,
    visit_id: int,
    amount: float,
    currency: str,
    current_user: User = Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db),
):
    """Отправка уведомления об оплате"""
    # Получаем данные визита
    visit = visit_crud.get(db, id=visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail="Визит не найден")

    # Получаем данные пациента
    patient = patient_crud.get(db, id=visit.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Пациент не найден")

    # Отправляем уведомление в фоновом режиме
    background_tasks.add_task(
        notification_service.send_payment_notification,
        patient.email,
        patient.phone,
        amount,
        currency,
        visit.date,
        "Врач",  # TODO: получить имя врача
    )

    return {
        "message": "Уведомление об оплате отправлено",
        "visit_id": visit_id,
        "sent_at": datetime.utcnow().isoformat(),
    }


@router.post("/send-queue-update")
async def send_queue_update(
    background_tasks: BackgroundTasks,
    department: str,
    current_number: int,
    estimated_wait: str,
    current_user: User = Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db),
):
    """Отправка обновления очереди"""
    # Отправляем уведомление в фоновом режиме
    background_tasks.add_task(
        notification_service.send_queue_update,
        department,
        current_number,
        estimated_wait,
    )

    return {
        "message": "Обновление очереди отправлено",
        "department": department,
        "current_number": current_number,
        "sent_at": datetime.utcnow().isoformat(),
    }


@router.post("/send-system-alert")
async def send_system_alert(
    background_tasks: BackgroundTasks,
    alert_type: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    current_user: User = Depends(require_roles(["admin"])),
):
    """Отправка системного оповещения (только для админов)"""
    # Отправляем уведомление в фоновом режиме
    background_tasks.add_task(
        notification_service.send_system_alert, alert_type, message, details
    )

    return {
        "message": "Системное оповещение отправлено",
        "alert_type": alert_type,
        "sent_at": datetime.utcnow().isoformat(),
    }


@router.post("/test-notifications")
async def test_notifications(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_roles(["admin"])),
):
    """Тестирование всех типов уведомлений"""
    test_email = "test@example.com"
    test_phone = "+998901234567"
    test_date = datetime.utcnow()

    # Тестируем все типы уведомлений
    background_tasks.add_task(
        notification_service.send_appointment_reminder,
        test_email,
        test_phone,
        test_date,
        "Тестовый врач",
        "Тестовое отделение",
    )

    background_tasks.add_task(
        notification_service.send_visit_confirmation,
        test_email,
        test_phone,
        test_date,
        "Тестовый врач",
        "Тестовое отделение",
        123,
    )

    background_tasks.add_task(
        notification_service.send_payment_notification,
        test_email,
        test_phone,
        100.0,
        "UZS",
        test_date,
        "Тестовый врач",
    )

    background_tasks.add_task(
        notification_service.send_queue_update, "Тестовое отделение", 123, "15 минут"
    )

    background_tasks.add_task(
        notification_service.send_system_alert,
        "TEST",
        "Тестовое системное оповещение",
        {"test_key": "test_value"},
    )

    return {
        "message": "Тестовые уведомления отправлены",
        "sent_at": datetime.utcnow().isoformat(),
    }


@router.get("/notification-status")
async def get_notification_status(
    current_user: User = Depends(require_roles(["admin"])),
):
    """Получение статуса настроек уведомлений"""
    return {
        "email": {
            "configured": bool(
                notification_service.smtp_username
                and notification_service.smtp_password
            ),
            "server": notification_service.smtp_server,
            "port": notification_service.smtp_port,
        },
        "telegram": {
            "configured": bool(
                notification_service.telegram_bot_token
                and notification_service.telegram_chat_id
            ),
            "bot_token": "***" if notification_service.telegram_bot_token else None,
            "chat_id": notification_service.telegram_chat_id,
        },
        "sms": {
            "configured": bool(
                notification_service.sms_api_key and notification_service.sms_api_url
            ),
            "api_url": notification_service.sms_api_url,
        },
    }
