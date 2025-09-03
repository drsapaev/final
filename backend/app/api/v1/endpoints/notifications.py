from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.crud import patient as patient_crud, visit as visit_crud
from app.crud.notification import (
    crud_notification_history,
    crud_notification_settings,
    crud_notification_template,
)
from app.models.user import User
from app.schemas.notification import (
    BulkNotificationRequest,
    NotificationHistory,
    NotificationSettings,
    NotificationSettingsUpdate,
    NotificationStatsResponse,
    NotificationTemplate,
    NotificationTemplateCreate,
    NotificationTemplateUpdate,
    SendNotificationRequest,
)
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


# Управление шаблонами уведомлений
@router.get("/templates", response_model=List[NotificationTemplate])
async def get_notification_templates(
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Получение списка шаблонов уведомлений"""
    return crud_notification_template.get_multi(db)


@router.post("/templates", response_model=NotificationTemplate)
async def create_notification_template(
    template_data: NotificationTemplateCreate,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Создание шаблона уведомления"""
    return crud_notification_template.create(db, obj_in=template_data)


@router.put("/templates/{template_id}", response_model=NotificationTemplate)
async def update_notification_template(
    template_id: int,
    template_data: NotificationTemplateUpdate,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Обновление шаблона уведомления"""
    template = crud_notification_template.get(db, id=template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    return crud_notification_template.update(db, db_obj=template, obj_in=template_data)


@router.delete("/templates/{template_id}")
async def delete_notification_template(
    template_id: int,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Удаление шаблона уведомления"""
    template = crud_notification_template.get(db, id=template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    crud_notification_template.remove(db, id=template_id)
    return {"message": "Шаблон удален"}


# История уведомлений
@router.get("/history", response_model=List[NotificationHistory])
async def get_notification_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    recipient_id: Optional[int] = Query(None),
    recipient_type: Optional[str] = Query(None),
    notification_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db),
):
    """Получение истории уведомлений"""
    if recipient_id and recipient_type:
        return crud_notification_history.get_by_recipient(
            db, recipient_id=recipient_id, recipient_type=recipient_type, limit=limit
        )
    elif status:
        return crud_notification_history.get_by_status(db, status=status, limit=limit)
    else:
        return crud_notification_history.get_multi(db, skip=skip, limit=limit)


@router.get("/history/stats", response_model=NotificationStatsResponse)
async def get_notification_stats(
    days: int = Query(7, ge=1, le=365),
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Получение статистики уведомлений"""
    stats = crud_notification_history.get_stats(db, days=days)
    recent_activity = crud_notification_history.get_recent(db, hours=24, limit=10)

    return NotificationStatsResponse(
        total_sent=stats["total_sent"],
        successful=stats["successful"],
        failed=stats["failed"],
        pending=stats["pending"],
        by_channel=stats["by_channel"],
        by_type=stats["by_type"],
        recent_activity=recent_activity,
    )


# Настройки уведомлений
@router.get("/settings/{user_id}", response_model=NotificationSettings)
async def get_user_notification_settings(
    user_id: int,
    user_type: str = Query(..., description="Тип пользователя: patient, doctor, admin"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получение настроек уведомлений пользователя"""
    # Проверяем права доступа
    if current_user.id != user_id and (
        not hasattr(current_user, "role") or current_user.role != "Admin"
    ):
        raise HTTPException(status_code=403, detail="Нет прав доступа")

    settings = crud_notification_settings.get_or_create(
        db, user_id=user_id, user_type=user_type
    )
    return settings


@router.put("/settings/{user_id}", response_model=NotificationSettings)
async def update_user_notification_settings(
    user_id: int,
    settings_data: NotificationSettingsUpdate,
    user_type: str = Query(..., description="Тип пользователя"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Обновление настроек уведомлений пользователя"""
    # Проверяем права доступа
    if current_user.id != user_id and (
        not hasattr(current_user, "role") or current_user.role != "Admin"
    ):
        raise HTTPException(status_code=403, detail="Нет прав доступа")

    settings = crud_notification_settings.get_or_create(
        db, user_id=user_id, user_type=user_type
    )

    return crud_notification_settings.update(db, db_obj=settings, obj_in=settings_data)


# Отправка уведомлений с шаблонами
@router.post("/send", response_model=List[NotificationHistory])
async def send_notification(
    background_tasks: BackgroundTasks,
    request: SendNotificationRequest,
    current_user: User = Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db),
):
    """Отправка уведомления с использованием шаблона"""
    results = []

    for channel in request.channels:
        # Получаем контакт получателя
        contact = None
        if request.recipient_id:
            if request.recipient_type == "patient":
                patient = patient_crud.get(db, id=request.recipient_id)
                if patient:
                    if channel == "email":
                        contact = patient.email
                    elif channel == "sms":
                        contact = patient.phone

        if not contact:
            continue

        # Отправляем в фоновом режиме
        background_tasks.add_task(
            notification_service.send_templated_notification,
            db=db,
            notification_type=request.notification_type,
            channel=channel,
            recipient_contact=contact,
            template_data=request.template_data,
            recipient_type=request.recipient_type,
            recipient_id=request.recipient_id,
            related_entity_type=request.related_entity_type,
            related_entity_id=request.related_entity_id,
        )

    return {"message": "Уведомления отправлены в фоновом режиме"}


@router.post("/send-bulk", response_model=Dict[str, Any])
async def send_bulk_notification(
    background_tasks: BackgroundTasks,
    request: BulkNotificationRequest,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Массовая отправка уведомлений"""
    recipients = []

    # Формируем список получателей
    for recipient_id in request.recipient_ids:
        if request.recipient_type == "patient":
            patient = patient_crud.get(db, id=recipient_id)
            if patient:
                recipients.append(
                    {
                        "id": recipient_id,
                        "type": "patient",
                        "email": patient.email,
                        "phone": patient.phone,
                        "name": patient.full_name
                        or f"{patient.first_name} {patient.last_name}",
                    }
                )

    # Отправляем в фоновом режиме
    background_tasks.add_task(
        notification_service.send_bulk_notification,
        db=db,
        notification_type=request.notification_type,
        channels=request.channels,
        recipients=recipients,
        template_data=request.template_data,
    )

    return {
        "message": "Массовая отправка запущена",
        "recipients_count": len(recipients),
        "channels": request.channels,
    }
