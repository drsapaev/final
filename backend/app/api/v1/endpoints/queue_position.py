"""
API endpoints для Push-уведомлений о позиции в очереди
согласно ONLINE_QUEUE_SYSTEM_V2.md раздел 16

Реализует:
1. Получение позиции в очереди
2. Ручная отправка уведомлений
3. Настройки уведомлений
"""

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.clinic import Doctor
from app.models.user import User
from app.services.queue_position_api_service import (
    QueuePositionApiDomainError,
    QueuePositionApiService,
)
from app.services.queue_position_notifications import get_queue_position_service

router = APIRouter()
logger = logging.getLogger(__name__)

QUEUE_POSITION_DOCTOR_NOTIFY_ROLES = {
    "doctor",
    "cardio",
    "cardiology",
    "cardiologist",
    "derma",
    "dermatologist",
    "dentist",
}


def _role_name(user: User) -> str:
    role = getattr(user, "role", "")
    return str(getattr(role, "value", role) or "")


def _ensure_doctor_can_notify_entry(
    db: Session,
    *,
    entry: Any,
    current_user: User,
) -> None:
    if _role_name(current_user).strip().lower() not in QUEUE_POSITION_DOCTOR_NOTIFY_ROLES:
        return

    doctor = (
        db.query(Doctor)
        .filter(Doctor.user_id == current_user.id, Doctor.active.is_(True))
        .first()
    )
    queue = getattr(entry, "queue", None)
    if not doctor or getattr(queue, "specialist_id", None) != doctor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )


# ========================= СХЕМЫ =========================

class QueuePositionResponse(BaseModel):
    """Ответ с информацией о позиции в очереди"""
    entry_id: int
    queue_number: int
    status: str
    people_ahead: int
    priority: int
    queue_time: str | None = None
    queue_info: dict[str, Any] = Field(default_factory=dict)


class NotificationResult(BaseModel):
    """Результат отправки уведомления"""
    success: bool
    sent: bool
    message_id: str | None = None
    reason: str | None = None
    error: str | None = None


class BatchNotificationResult(BaseModel):
    """Результат массовой отправки уведомлений"""
    success: bool
    total_notified: int
    details: list[dict[str, Any]] = Field(default_factory=list)


class SendPositionNotificationRequest(BaseModel):
    """Запрос на отправку уведомления о позиции"""
    entry_id: int = Field(..., description="ID записи в очереди")


class SendCallNotificationRequest(BaseModel):
    """Запрос на отправку уведомления о вызове"""
    entry_id: int = Field(..., description="ID записи в очереди")
    cabinet_number: str | None = Field(None, description="Номер кабинета")


# ========================= ЭНДПОИНТЫ =========================

@router.get("/{entry_id}", response_model=QueuePositionResponse)
async def get_queue_position(
    entry_id: int,
    db: Session = Depends(get_db),
    # QUEUE-AUDIT-28 P0-4: was public — sequential ID enumeration leaked all
    # positions + specialist names + cabinets to anonymous users.
    current_user: User = Depends(get_current_user),
):
    """
    Получить информацию о позиции в очереди.

    Требует аутентификации. Patient может видеть только свои записи;
    Admin/Registrar/Doctor — любые.
    """
    try:
        entry = QueuePositionApiService(db).get_position_entry(entry_id=entry_id)
    except QueuePositionApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    # Ownership check: non-staff users can only see their own entries
    if current_user.role not in ("Admin", "Registrar", "Doctor", "SuperAdmin"):
        # Verify the entry belongs to the current user via patient linkage
        if hasattr(entry, "patient_id") and entry.patient_id:
            from app.models.patient import Patient
            patient = db.query(Patient).filter(Patient.id == entry.patient_id).first()
            if not patient or patient.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Нет доступа к этой записи очереди")

    service = get_queue_position_service(db)
    position_info = service.get_queue_position_info(entry)

    return QueuePositionResponse(**position_info)


@router.get("/by-number/{queue_number}", response_model=QueuePositionResponse)
async def get_queue_position_by_number(
    queue_number: int,
    specialist_id: int = Query(..., description="ID специалиста"),
    db: Session = Depends(get_db),
    # QUEUE-AUDIT-28 P0-5: was public — scanning queue_number 1-1000 leaked
    # all positions for any specialist.
    current_user: User = Depends(get_current_user),
):
    """
    Получить информацию о позиции по номеру в очереди.

    Требует аутентификации.
    """
    try:
        entry = QueuePositionApiService(db).get_position_entry_by_number(
            queue_number=queue_number,
            specialist_id=specialist_id,
        )
    except QueuePositionApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    # Ownership check for non-staff
    if current_user.role not in ("Admin", "Registrar", "Doctor", "SuperAdmin"):
        if hasattr(entry, "patient_id") and entry.patient_id:
            from app.models.patient import Patient
            patient = db.query(Patient).filter(Patient.id == entry.patient_id).first()
            if not patient or patient.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Нет доступа к этой записи очереди")

    service = get_queue_position_service(db)
    position_info = service.get_queue_position_info(entry)

    return QueuePositionResponse(**position_info)


@router.post("/notify/position", response_model=NotificationResult)
async def send_position_notification(
    request: SendPositionNotificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor"))
):
    """
    Отправить уведомление о позиции в очереди

    Используется для ручной отправки уведомления пациенту.

    Доступно: Admin, Registrar, Doctor
    """
    try:
        entry = QueuePositionApiService(db).get_position_entry(entry_id=request.entry_id)
    except QueuePositionApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    _ensure_doctor_can_notify_entry(db, entry=entry, current_user=current_user)

    service = get_queue_position_service(db)
    people_ahead = service._count_people_ahead(entry)

    result = await service.notify_position_update(
        entry=entry,
        people_ahead=people_ahead
    )

    return NotificationResult(**result)


@router.post("/notify/call", response_model=NotificationResult)
async def send_call_notification(
    request: SendCallNotificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor"))
):
    """
    Отправить уведомление о вызове пациента

    Отправляется когда врач вызывает пациента.

    Доступно: Admin, Registrar, Doctor
    """
    try:
        entry = QueuePositionApiService(db).get_position_entry(entry_id=request.entry_id)
    except QueuePositionApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    _ensure_doctor_can_notify_entry(db, entry=entry, current_user=current_user)

    result = await get_queue_position_service(db).notify_patient_called(
        entry=entry,
        cabinet_number=request.cabinet_number
    )

    return NotificationResult(**result)


@router.post("/notify/queue-update/{queue_id}", response_model=BatchNotificationResult)
async def send_queue_update_notifications(
    queue_id: int,
    changed_after_number: int = Query(0, description="Номер, после которого изменились позиции"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Массовое уведомление об изменении очереди

    Отправляет уведомления всем пациентам после указанного номера.
    Используется после обслуживания пациента или его удаления из очереди.

    Доступно: Admin, Registrar
    """
    try:
        QueuePositionApiService(db).get_queue_or_error(queue_id=queue_id)
    except QueuePositionApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    service = get_queue_position_service(db)
    result = await service.notify_queue_changes_batch(
        queue_id=queue_id,
        changed_after_number=changed_after_number
    )

    return BatchNotificationResult(**result)


@router.post("/notify/diagnostics-return/{entry_id}", response_model=NotificationResult)
async def send_diagnostics_return_notification(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor"))
):
    """
    Отправить уведомление о возврате после диагностики

    Отправляется когда врач ожидает возвращения пациента с обследования.

    Доступно: Admin, Doctor
    """
    try:
        entry = QueuePositionApiService(db).get_diagnostics_entry_or_error(entry_id=entry_id)
    except QueuePositionApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    _ensure_doctor_can_notify_entry(db, entry=entry, current_user=current_user)

    # Doctor identity lives on the related User profile in the current schema.
    specialist_name = "врач"
    if entry.queue and entry.queue.specialist:
        specialist = entry.queue.specialist
        specialist_user = getattr(specialist, "user", None)
        if specialist_user and (
            getattr(specialist_user, "full_name", None)
            or getattr(specialist_user, "username", None)
        ):
            specialist_name = (
                specialist_user.full_name
                or specialist_user.username
            )
        else:
            fallback_name = " ".join(
                part
                for part in (
                    getattr(specialist, "last_name", None),
                    getattr(specialist, "first_name", None),
                )
                if part
            ).strip()
            if fallback_name:
                specialist_name = fallback_name

    logger.debug(
        "[send_diagnostics_return_notification] resolved specialist name '%s' for entry %s",
        specialist_name,
        entry_id,
    )

    result = await get_queue_position_service(db).notify_diagnostics_return_needed(
        entry=entry,
        specialist_name=specialist_name
    )

    return NotificationResult(**result)


@router.post("/notify/reminder/{entry_id}", response_model=NotificationResult)
async def send_waiting_reminder(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Отправить напоминание о нахождении в очереди

    Периодическое напоминание для пациентов, долго ожидающих в очереди.

    Доступно: Admin, Registrar
    """
    try:
        entry = QueuePositionApiService(db).get_waiting_entry_or_error(entry_id=entry_id)
    except QueuePositionApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    result = await get_queue_position_service(db).send_waiting_reminder(entry=entry)

    return NotificationResult(**result)


# ========================= СТАТИСТИКА =========================

@router.get("/stats/queue/{queue_id}", response_model=dict[str, Any])
async def get_queue_positions_stats(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить статистику позиций в очереди

    Возвращает список всех записей с их позициями.
    """
    try:
        queue, entries = QueuePositionApiService(db).get_queue_entries_stats(queue_id=queue_id)
    except QueuePositionApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    service = get_queue_position_service(db)

    result = []
    for i, entry in enumerate(entries):
        position_info = service.get_queue_position_info(entry)
        position_info["position_in_list"] = i + 1
        result.append(position_info)

    return {
        "queue_id": queue_id,
        "queue_day": str(queue.day),
        "total_entries": len(entries),
        "entries": result
    }
