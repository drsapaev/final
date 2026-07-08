import logging
import re
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.crud import patient as patient_crud
from app.crud import visit as visit_crud
from app.crud.notification import crud_notification_template
from app.crud.user_management import (
    user_notification_settings as crud_user_notification_settings,
)
from app.crud.user_management import (
    user_profile as crud_user_profile,
)
from app.models.user import User
from app.models.user_profile import UserPreferences
from app.schemas.notification import (
    BulkNotificationRequest,
    NotificationInboxResponse,
    NotificationMutationResponse,
    NotificationStatsResponse,
    NotificationTemplate,
    NotificationTemplateCreate,
    NotificationTemplateUpdate,
    NotificationUnreadCountResponse,
    SendNotificationRequest,
)
from app.schemas.user_management import (
    UserNotificationSettingsCreate,
    UserNotificationSettingsResponse,
    UserNotificationSettingsUpdate,
)
from app.services.notification_platform_service import get_notification_platform_service
from app.services.notifications import notification_sender_service
from app.schemas.notifications import SendSystemAlertRequest, UpdateNotificationPolicyRequest

router = APIRouter()
logger = logging.getLogger(__name__)
_TIME_PATTERN = re.compile(r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")


def _combine_date_and_time(date_value, time_value: str | None) -> datetime:
    if date_value is None:
        return datetime.now(UTC)

    if not time_value:
        return datetime.combine(date_value, datetime.min.time())

    try:
        parsed_time = datetime.strptime(time_value, "%H:%M").time()
    except ValueError:
        logger.warning(
            "[Notifications] falling back to midnight for invalid visit time",
            extra={"date": date_value.isoformat(), "time": time_value},
        )
        parsed_time = datetime.min.time()

    return datetime.combine(date_value, parsed_time)


def _validate_recipient_scope(
    *,
    platform_service,
    current_user: User,
    recipient_id: int | None,
    recipient_type: str | None,
) -> None:
    expected_recipient_id = current_user.id

    if recipient_id is not None and recipient_id != expected_recipient_id:
        logger.warning(
            "[Notifications] rejected cross-recipient inbox request",
            extra={
                "current_user_id": current_user.id,
                "requested_recipient_id": recipient_id,
                "requested_recipient_type": recipient_type,
            },
        )
        raise HTTPException(status_code=403, detail="Нет прав доступа")


def get_or_create_notification_settings(db: Session, user_id: int):
    settings = crud_user_notification_settings.get_by_user_id(db, user_id=user_id)
    if settings:
        return settings

    profile = crud_user_profile.get_by_user_id(db, user_id=user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль пользователя не найден")

    create_data = UserNotificationSettingsCreate(user_id=user_id, profile_id=profile.id)
    return crud_user_notification_settings.create(db, obj_in=create_data)


def get_or_create_user_preferences(db: Session, user_id: int):
    preferences = (
        db.query(UserPreferences)
        .filter(UserPreferences.user_id == user_id)
        .first()
    )
    if preferences:
        return preferences

    profile = crud_user_profile.get_by_user_id(db, user_id=user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Профиль пользователя не найден")

    preferences = UserPreferences(
        user_id=user_id,
        profile_id=profile.id,
    )
    db.add(preferences)
    db.commit()
    db.refresh(preferences)
    return preferences


def _assert_notification_policy_access(current_user: User, user_id: int) -> None:
    if current_user.id != user_id and (
        not hasattr(current_user, "role") or current_user.role != "Admin"
    ):
        raise HTTPException(status_code=403, detail="Нет прав доступа")


def _parse_policy_datetime(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise HTTPException(status_code=422, detail=f"{field_name} must be ISO datetime string")
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{field_name} has invalid ISO datetime") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.isoformat()


def _normalize_realtime_control(control: Any, *, field_name: str) -> bool | dict[str, Any]:
    if isinstance(control, bool):
        return control
    if not isinstance(control, dict):
        raise HTTPException(status_code=422, detail=f"{field_name} must be boolean or object")

    normalized: dict[str, Any] = {}
    for key in ("enabled", "realtime_enabled", "desktop"):
        value = control.get(key)
        if isinstance(value, bool):
            normalized[key] = value

    channels = control.get("channels")
    if channels is not None:
        if not isinstance(channels, dict):
            raise HTTPException(status_code=422, detail=f"{field_name}.channels must be an object")
        normalized_channels: dict[str, bool] = {}
        for channel_name in ("desktop", "push", "email", "sms"):
            channel_value = channels.get(channel_name)
            if isinstance(channel_value, bool):
                normalized_channels[channel_name] = channel_value
        if normalized_channels:
            normalized["channels"] = normalized_channels

    if not normalized:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} has no supported keys (enabled/realtime_enabled/desktop/channels)",
        )
    return normalized


def _normalize_notification_policy_payload(
    *,
    policy_data: dict[str, Any],
    platform_service,
) -> dict[str, Any]:
    supported_keys = {
        "muted_until",
        "snooze_until",
        "dnd",
        "event_controls",
        "family_controls",
        "channel_controls",
    }
    normalized_policy: dict[str, Any] = {}

    for key in supported_keys:
        if key not in policy_data:
            continue
        value = policy_data.get(key)
        if key in {"muted_until", "snooze_until"}:
            parsed_datetime = _parse_policy_datetime(value, field_name=key)
            if parsed_datetime:
                normalized_policy[key] = parsed_datetime
            continue

        if key == "dnd":
            if value is None:
                continue
            if not isinstance(value, dict):
                raise HTTPException(status_code=422, detail="dnd must be an object")
            dnd: dict[str, Any] = {}
            if "enabled" in value:
                if not isinstance(value["enabled"], bool):
                    raise HTTPException(status_code=422, detail="dnd.enabled must be boolean")
                dnd["enabled"] = value["enabled"]
            if "always_on" in value:
                if not isinstance(value["always_on"], bool):
                    raise HTTPException(status_code=422, detail="dnd.always_on must be boolean")
                dnd["always_on"] = value["always_on"]
            for time_key in ("start", "end"):
                if time_key not in value:
                    continue
                time_value = value[time_key]
                if time_value is None:
                    continue
                if not isinstance(time_value, str) or not _TIME_PATTERN.match(time_value):
                    raise HTTPException(status_code=422, detail=f"dnd.{time_key} must be HH:MM")
                dnd[time_key] = time_value
            if dnd:
                normalized_policy["dnd"] = dnd
            continue

        if key == "channel_controls":
            if value is None:
                continue
            normalized_policy["channel_controls"] = _normalize_realtime_control(
                value,
                field_name="channel_controls",
            )
            continue

        if key in {"event_controls", "family_controls"}:
            if value is None:
                continue
            if not isinstance(value, dict):
                raise HTTPException(status_code=422, detail=f"{key} must be an object")
            normalized_controls: dict[str, Any] = {}
            for raw_name, raw_control in value.items():
                if not isinstance(raw_name, str):
                    continue
                if key == "event_controls":
                    normalized_name = platform_service.normalize_event_type(raw_name)
                else:
                    normalized_name = platform_service.normalize_slug(raw_name) or ""
                if not normalized_name:
                    continue
                normalized_controls[normalized_name] = _normalize_realtime_control(
                    raw_control,
                    field_name=f"{key}.{raw_name}",
                )
            if normalized_controls:
                normalized_policy[key] = normalized_controls

    return normalized_policy


@router.post("/send-appointment-reminder", response_model=dict[str, Any])
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
        raise HTTPException(status_code=404, detail=t("patient.not_found"))

    # Отправляем уведомление в фоновом режиме
    background_tasks.add_task(
        notification_sender_service.send_appointment_reminder,
        patient.email,
        patient.phone,
        appointment_date,
        doctor_name,
        department,
        db,
        patient_id,
    )

    return {
        "message": "Напоминание отправлено",
        "patient_id": patient_id,
        "sent_at": datetime.now(UTC).isoformat(),
    }


@router.post("/send-visit-confirmation", response_model=dict[str, Any])
async def send_visit_confirmation(
    background_tasks: BackgroundTasks,
    visit_id: int,
    queue_number: int | None = None,
    current_user: User = Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db),
):
    """Отправка подтверждения визита"""
    # Получаем данные визита
    visit = visit_crud.get(db, id=visit_id)
    if not visit:
        raise HTTPException(status_code=404, detail=t("visit.not_found"))

    # Получаем данные пациента
    patient = patient_crud.get(db, id=visit.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=t("patient.not_found"))

    # Отправляем уведомление в фоновом режиме
    background_tasks.add_task(
        notification_sender_service.send_visit_confirmation,
        patient.email,
        patient.phone,
        _combine_date_and_time(visit.visit_date, visit.visit_time),
        "Врач",  # TODO: получить имя врача
        "Отделение",  # TODO: получить название отделения
        queue_number,
        db,
        visit.patient_id,
    )

    return {
        "message": "Подтверждение визита отправлено",
        "visit_id": visit_id,
        "sent_at": datetime.now(UTC).isoformat(),
    }


@router.post("/send-payment-notification", response_model=dict[str, Any])
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
        raise HTTPException(status_code=404, detail=t("visit.not_found"))

    # Получаем данные пациента
    patient = patient_crud.get(db, id=visit.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail=t("patient.not_found"))

    # Отправляем уведомление в фоновом режиме
    background_tasks.add_task(
        notification_sender_service.send_payment_notification,
        patient.email,
        patient.phone,
        amount,
        currency,
        _combine_date_and_time(visit.visit_date, visit.visit_time),
        "Врач",  # TODO: получить имя врача
        db,
        visit.patient_id,
    )

    return {
        "message": "Уведомление об оплате отправлено",
        "visit_id": visit_id,
        "sent_at": datetime.now(UTC).isoformat(),
    }


@router.post("/send-queue-update", response_model=dict[str, Any])
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
        notification_sender_service.send_queue_update,
        department,
        current_number,
        estimated_wait,
        None,
        db,
    )

    return {
        "message": "Обновление очереди отправлено",
        "department": department,
        "current_number": current_number,
        "sent_at": datetime.now(UTC).isoformat(),
    }


@router.post("/send-system-alert", response_model=dict[str, Any])
async def send_system_alert(
    background_tasks: BackgroundTasks,
    alert_type: str,
    message: str,
    body: SendSystemAlertRequest = SendSystemAlertRequest(),
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Отправка системного оповещения (только для админов)"""
    details = body.details.model_dump(exclude_none=True) if body.details else None
    # Отправляем уведомление в фоновом режиме
    background_tasks.add_task(
        notification_sender_service.send_system_alert,
        alert_type,
        message,
        details,
        db,
        current_user.id,
        current_user.role,
    )

    return {
        "message": "Системное оповещение отправлено",
        "alert_type": alert_type,
        "sent_at": datetime.now(UTC).isoformat(),
    }


@router.post("/test-notifications", response_model=dict[str, Any])
async def test_notifications(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_roles(["admin"])),
):
    """Тестирование всех типов уведомлений"""
    test_email = "test@example.com"
    test_phone = "+998901234567"
    test_date = datetime.now(UTC)

    # Тестируем все типы уведомлений
    background_tasks.add_task(
        notification_sender_service.send_appointment_reminder,
        test_email,
        test_phone,
        test_date,
        "Тестовый врач",
        "Тестовое отделение",
    )

    background_tasks.add_task(
        notification_sender_service.send_visit_confirmation,
        test_email,
        test_phone,
        test_date,
        "Тестовый врач",
        "Тестовое отделение",
        123,
    )

    background_tasks.add_task(
        notification_sender_service.send_payment_notification,
        test_email,
        test_phone,
        100.0,
        "UZS",
        test_date,
        "Тестовый врач",
    )

    background_tasks.add_task(
        notification_sender_service.send_queue_update, "Тестовое отделение", 123, "15 минут"
    )

    background_tasks.add_task(
        notification_sender_service.send_system_alert,
        "TEST",
        "Тестовое системное оповещение",
        {"test_key": "test_value"},
    )

    return {
        "message": "Тестовые уведомления отправлены",
        "sent_at": datetime.now(UTC).isoformat(),
    }


@router.get("/notification-status", response_model=dict[str, Any])
async def get_notification_status(
    current_user: User = Depends(require_roles(["admin"])),
):
    """Получение статуса настроек уведомлений"""
    return {
        "email": {
            "configured": bool(
                notification_sender_service.smtp_username
                and notification_sender_service.smtp_password
            ),
            "server": notification_sender_service.smtp_server,
            "port": notification_sender_service.smtp_port,
        },
        "telegram": {
            "configured": bool(
                notification_sender_service.telegram_bot_token
                and notification_sender_service.telegram_chat_id
            ),
            "bot_token": "***" if notification_sender_service.telegram_bot_token else None,
            "chat_id": notification_sender_service.telegram_chat_id,
        },
        "sms": {
            "configured": bool(
                notification_sender_service.sms_api_key and notification_sender_service.sms_api_url
            ),
            "api_url": notification_sender_service.sms_api_url,
        },
    }


# Управление шаблонами уведомлений
@router.get("/templates", response_model=list[NotificationTemplate])
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


@router.delete("/templates/{template_id}", response_model=dict[str, Any])
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


# История уведомлений и inbox
@router.get("/inbox", response_model=NotificationInboxResponse)
@router.get("/history", response_model=NotificationInboxResponse)
async def get_notification_history(
    role: str | None = Query(None),
    status: str = Query("all"),
    event_type: str | None = Query(None),
    severity: str | None = Query(None),
    department_key: str | None = Query(None),
    search: str | None = Query(None),
    cursor: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    recipient_id: int | None = Query(None),
    recipient_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получение inbox/history текущего пользователя."""
    platform_service = get_notification_platform_service(db)
    _validate_recipient_scope(
        platform_service=platform_service,
        current_user=current_user,
        recipient_id=recipient_id,
        recipient_type=recipient_type,
    )

    return platform_service.get_inbox(
        current_user=current_user,
        role=role,
        status=status,
        event_type=event_type,
        severity=severity,
        department_key=department_key,
        search=search,
        cursor=cursor,
        limit=limit,
    )


@router.get("/sync", response_model=NotificationInboxResponse)
async def sync_notifications(
    role: str | None = Query(None),
    status: str = Query("all"),
    event_type: str | None = Query(None),
    severity: str | None = Query(None),
    department_key: str | None = Query(None),
    search: str | None = Query(None),
    cursor: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    recipient_id: int | None = Query(None),
    recipient_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cursor-based inbox resync."""
    platform_service = get_notification_platform_service(db)
    _validate_recipient_scope(
        platform_service=platform_service,
        current_user=current_user,
        recipient_id=recipient_id,
        recipient_type=recipient_type,
    )
    return platform_service.get_inbox(
        current_user=current_user,
        role=role,
        status=status,
        event_type=event_type,
        severity=severity,
        department_key=department_key,
        search=search,
        cursor=cursor,
        limit=limit,
    )


@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
async def get_unread_notification_count(
    role: str | None = Query(None),
    department_key: str | None = Query(None),
    recipient_id: int | None = Query(None),
    recipient_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Server-authoritative unread counts."""
    platform_service = get_notification_platform_service(db)
    _validate_recipient_scope(
        platform_service=platform_service,
        current_user=current_user,
        recipient_id=recipient_id,
        recipient_type=recipient_type,
    )
    return platform_service.get_unread_counts(
        current_user=current_user,
        role=role,
        department_key=department_key,
    )


@router.post("/{delivery_id}/seen", response_model=NotificationMutationResponse)
async def mark_notification_seen(
    delivery_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a notification as seen."""
    platform_service = get_notification_platform_service(db)
    try:
        delivery = await platform_service.mark_seen(
            current_user=current_user, delivery_id=delivery_id
        )
    except PermissionError:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")

    unread_count = platform_service.get_unread_counts(current_user=current_user)["total"]
    return NotificationMutationResponse(
        id=delivery.delivery_id,
        delivery_status=delivery.delivery_status,
        unread_count=unread_count,
        message="Уведомление отмечено как просмотренное",
    )


@router.post("/{delivery_id}/read", response_model=NotificationMutationResponse)
async def mark_notification_read(
    delivery_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a notification as read."""
    platform_service = get_notification_platform_service(db)
    try:
        delivery = await platform_service.mark_read(
            current_user=current_user, delivery_id=delivery_id
        )
    except PermissionError:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")

    unread_count = platform_service.get_unread_counts(current_user=current_user)["total"]
    return NotificationMutationResponse(
        id=delivery.delivery_id,
        delivery_status=delivery.delivery_status,
        unread_count=unread_count,
        message="Уведомление отмечено как прочитанное",
    )


@router.post("/{delivery_id}/archive", response_model=NotificationMutationResponse)
async def archive_notification(
    delivery_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Archive a notification."""
    platform_service = get_notification_platform_service(db)
    try:
        delivery = await platform_service.archive(
            current_user=current_user, delivery_id=delivery_id
        )
    except PermissionError:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")

    unread_count = platform_service.get_unread_counts(current_user=current_user)["total"]
    return NotificationMutationResponse(
        id=delivery.delivery_id,
        delivery_status=delivery.delivery_status,
        unread_count=unread_count,
        message="Уведомление архивировано",
    )


@router.post("/mark-all-read", response_model=NotificationMutationResponse)
async def mark_all_notifications_read(
    role: str | None = Query(None),
    department_key: str | None = Query(None),
    recipient_id: int | None = Query(None),
    recipient_type: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read for the current user."""
    platform_service = get_notification_platform_service(db)
    _validate_recipient_scope(
        platform_service=platform_service,
        current_user=current_user,
        recipient_id=recipient_id,
        recipient_type=recipient_type,
    )
    count = await platform_service.mark_all_read(
        current_user=current_user,
        role=role,
        department_key=department_key,
    )
    unread_count = platform_service.get_unread_counts(current_user=current_user)["total"]
    return NotificationMutationResponse(
        id="mark-all-read",
        delivery_status="read",
        unread_count=unread_count,
        message=f"Отмечено как прочитанное: {count}",
    )


@router.get("/history/stats", response_model=NotificationStatsResponse)
async def get_notification_stats(
    days: int = Query(7, ge=1, le=365),
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db),
):
    """Получение статистики уведомлений."""
    platform_service = get_notification_platform_service(db)
    stats = platform_service.get_stats(days=days)

    return NotificationStatsResponse(
        total_sent=stats["total_sent"],
        successful=stats["successful"],
        failed=stats["failed"],
        pending=stats["pending"],
        by_channel=stats["by_channel"],
        by_type=stats["by_type"],
        recent_activity=stats["recent_activity"],
    )


# Настройки уведомлений
@router.get("/settings/{user_id}", response_model=UserNotificationSettingsResponse)
async def get_user_notification_settings(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получение настроек уведомлений пользователя"""
    _assert_notification_policy_access(current_user=current_user, user_id=user_id)

    # Используем UserNotificationSettings
    return get_or_create_notification_settings(db, user_id)


@router.put("/settings/{user_id}", response_model=UserNotificationSettingsResponse)
async def update_user_notification_settings(
    user_id: int,
    settings_data: UserNotificationSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Обновление настроек уведомлений пользователя"""
    _assert_notification_policy_access(current_user=current_user, user_id=user_id)

    settings = get_or_create_notification_settings(db, user_id)

    return crud_user_notification_settings.update(db, db_obj=settings, obj_in=settings_data)


@router.get("/settings/{user_id}/policy", response_model=dict[str, Any])
async def get_user_notification_policy(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получение runtime policy-override для anti-noise (mute/snooze/DND + controls)."""
    _assert_notification_policy_access(current_user=current_user, user_id=user_id)
    preferences = get_or_create_user_preferences(db, user_id)
    security_settings = preferences.security_settings if isinstance(preferences.security_settings, dict) else {}
    policy = security_settings.get("notification_policy")
    if not isinstance(policy, dict):
        policy = {}
    return {
        "user_id": user_id,
        "policy": policy,
        "updated_at": preferences.updated_at.isoformat() if preferences.updated_at else None,
    }


@router.put("/settings/{user_id}/policy", response_model=dict[str, Any])
async def update_user_notification_policy(
    user_id: int,
    body: UpdateNotificationPolicyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Обновление runtime policy-override для anti-noise (mute/snooze/DND + controls)."""
    _assert_notification_policy_access(current_user=current_user, user_id=user_id)
    platform_service = get_notification_platform_service(db)
    policy_data = body.model_dump(exclude_none=True)
    normalized_policy = _normalize_notification_policy_payload(
        policy_data=policy_data,
        platform_service=platform_service,
    )

    preferences = get_or_create_user_preferences(db, user_id)
    security_settings = preferences.security_settings if isinstance(preferences.security_settings, dict) else {}
    security_settings["notification_policy"] = normalized_policy
    preferences.security_settings = security_settings
    db.add(preferences)
    db.commit()
    db.refresh(preferences)

    return {
        "user_id": user_id,
        "policy": normalized_policy,
        "updated_at": preferences.updated_at.isoformat() if preferences.updated_at else None,
    }


# Отправка уведомлений с шаблонами
@router.post("/send", response_model=dict[str, Any])
async def send_notification(
    background_tasks: BackgroundTasks,
    request: SendNotificationRequest,
    current_user: User = Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db),
):
    """Отправка уведомления с использованием шаблона"""

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
            notification_sender_service.send_templated_notification,
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


@router.post("/send-bulk", response_model=dict[str, Any])
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
        notification_sender_service.send_bulk_notification,
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
