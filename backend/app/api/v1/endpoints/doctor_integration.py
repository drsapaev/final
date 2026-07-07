"""
API endpoints для интеграции панелей врачей с системой
Основа: passport.md стр. 1141-2063
"""

import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.api.deps import (  # noqa: E402  # manual-review: conditional import after config — intentional
    get_db,
    require_roles,
)
from app.crud import (  # noqa: E402  # manual-review: conditional import after config — intentional
    clinic as crud_clinic,
)
from app.crud import (  # noqa: E402  # manual-review: conditional import after config — intentional
    visit as crud_visit,
)
from app.models.appointment import (  # noqa: E402  # manual-review: conditional import after config — intentional
    Appointment,  # noqa: E402  # manual-review: conditional import after config — intentional
)
from app.models.clinic import (  # noqa: E402  # manual-review: conditional import after config — intentional
    Doctor,  # noqa: E402  # manual-review: conditional import after config — intentional
)
from app.models.online_queue import (  # noqa: E402  # manual-review: conditional import after config — intentional
    DailyQueue,
    OnlineQueueEntry,
)
from app.models.service import (  # noqa: E402  # manual-review: conditional import after config — intentional
    Service,  # noqa: E402  # manual-review: conditional import after config — intentional
)
from app.models.user import (  # noqa: E402  # manual-review: conditional import after config — intentional
    User,  # noqa: E402  # manual-review: conditional import after config — intentional
)
from app.models.visit import (  # noqa: E402  # manual-review: conditional import after config — intentional
    Visit,
    VisitService,
)
from app.services.notification_service import (  # noqa: E402  # manual-review: conditional import after config — intentional
    NotificationService,  # noqa: E402  # manual-review: conditional import after config — intentional
)
from app.services.service_mapping import (  # noqa: E402  # manual-review: conditional import after config — intentional
    get_service_code,  # noqa: E402  # manual-review: conditional import after config — intentional
)

router = APIRouter()


DOCTOR_QUEUE_SPECIALTY_VARIANTS: dict[str, list[str]] = {
    "cardiology": ["cardiology", "cardio", "Cardiologist", "Cardio"],
    "cardio": ["cardiology", "cardio", "Cardiologist", "Cardio"],
    "derma": ["derma", "dermatology", "Dermatologist"],
    "dermatology": ["derma", "dermatology", "Dermatologist"],
    "dentist": ["dentist", "dental", "dentistry", "Dentist", "stomatology"],
    "dentistry": ["dentist", "dental", "dentistry", "Dentist", "stomatology"],
    "stomatology": ["dentist", "dental", "dentistry", "Dentist", "stomatology"],
    "lab": ["lab", "laboratory", "Laboratory"],
    "laboratory": ["lab", "laboratory", "Laboratory"],
    "general": ["general", "therapy", "therapist", "general_practice"],
}

DOCTOR_QUEUE_ALLOWED_TAGS: dict[str, list[str]] = {
    "cardiology": ["cardio", "cardiology", "cardiology_common"],
    "cardio": ["cardio", "cardiology", "cardiology_common"],
    "derma": ["derma", "dermatology"],
    "dermatology": ["derma", "dermatology"],
    "dentist": ["dentist", "dental", "dentistry", "stomatology"],
    "dentistry": ["dentist", "dental", "dentistry", "stomatology"],
    "stomatology": ["dentist", "dental", "dentistry", "stomatology"],
    "lab": ["lab", "laboratory"],
    "laboratory": ["lab", "laboratory"],
    "general": ["general"],
}

DOCTOR_SCHEDULE_NEXT_ROLES = {
    "doctor",
    "cardio",
    "cardiology",
    "derma",
    "dentist",
}


def _normalize_queue_specialty(value: str) -> str:
    return (value or "general").strip().lower()


def _resolve_queue_specialty_variants(specialty: str) -> list[str]:
    normalized = _normalize_queue_specialty(specialty)
    return DOCTOR_QUEUE_SPECIALTY_VARIANTS.get(normalized, [normalized])


def _resolve_queue_allowed_tags(specialty: str) -> list[str]:
    normalized = _normalize_queue_specialty(specialty)
    return DOCTOR_QUEUE_ALLOWED_TAGS.get(normalized, [normalized])


def _serialize_queue_doctor(doctor: Doctor | None, current_user: User, specialty: str):
    normalized = _normalize_queue_specialty(specialty)
    if doctor:
        return {
            "id": doctor.id,
            "name": doctor.user.full_name if doctor.user else f"Врач #{doctor.id}",
            "specialty": doctor.specialty,
            "cabinet": doctor.cabinet,
        }

    return {
        "id": current_user.id,
        "name": current_user.full_name or current_user.username or "Врач",
        "specialty": normalized,
        "cabinet": None,
    }

# ===================== МОДЕЛИ ДАННЫХ =====================


def _doctor_queue_available_actions(entry: OnlineQueueEntry) -> list[str]:
    status_value = (entry.status or "").strip().lower()
    actions_by_status = {
        "waiting": ["call", "no_show"],
        "called": ["start_visit", "send_to_diagnostics", "no_show"],
        "in_progress": ["complete"],
        "diagnostics": [
            "notify_diagnostics_return",
            "complete",
            "mark_incomplete",
        ],
        "no_show": ["restore_next"],
    }
    return actions_by_status.get(status_value, [])


def _doctor_queue_action_flags(entry: OnlineQueueEntry) -> dict[str, bool]:
    actions = set(_doctor_queue_available_actions(entry))
    return {
        "can_call": "call" in actions,
        "can_start_visit": "start_visit" in actions,
        "can_no_show": "no_show" in actions,
        "can_send_to_diagnostics": "send_to_diagnostics" in actions,
        "can_complete": "complete" in actions,
        "can_notify_diagnostics_return": "notify_diagnostics_return" in actions,
        "can_mark_incomplete": "mark_incomplete" in actions,
        "can_restore_next": "restore_next" in actions,
    }


def _ensure_visit_doctor_access(visit: Visit, current_user: User) -> None:
    if current_user.role == "Admin":
        return

    doctor = visit.doctor
    if doctor and doctor.user_id == current_user.id:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No access to this visit",
    )


def _ensure_legacy_complete_doctor_access(
    db: Session,
    *,
    record_doctor_id: int | None,
    current_user: User,
) -> None:
    if current_user.role == "Admin":
        return

    if record_doctor_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to complete this record",
        )

    assigned_doctor = db.query(Doctor).filter(Doctor.id == record_doctor_id).first()
    if assigned_doctor:
        if assigned_doctor.user_id == current_user.id:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to complete this record",
        )

    # Legacy writers sometimes stored User.id in doctor_id. Preserve that only
    # when the value does not point at another real Doctor row.
    if record_doctor_id == current_user.id:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No access to complete this record",
    )


def _visit_filter_doctor_id(db: Session, current_user: User) -> int:
    doctor = (
        db.query(Doctor)
        .filter(and_(Doctor.user_id == current_user.id, Doctor.active == True))
        .first()
    )
    if doctor:
        return doctor.id
    if current_user.role == "Admin":
        return current_user.id
    return -1


def _doctor_schedule_patient_context_exists(
    db: Session,
    *,
    patient_id: int,
    doctor: Doctor,
    current_user: User,
) -> bool:
    doctor_ids = {doctor.id}
    assigned_doctor = db.query(Doctor).filter(Doctor.id == current_user.id).first()
    # Some legacy visit writers stored User.id in doctor_id. Preserve that
    # compatibility only when current_user.id does not point to another Doctor row.
    if not assigned_doctor:
        doctor_ids.add(current_user.id)

    visit_exists = (
        db.query(Visit.id)
        .filter(Visit.patient_id == patient_id, Visit.doctor_id.in_(doctor_ids))
        .first()
        is not None
    )
    if visit_exists:
        return True

    return (
        db.query(Appointment.id)
        .filter(
            Appointment.patient_id == patient_id,
            Appointment.doctor_id.in_(doctor_ids),
        )
        .first()
        is not None
    )


def _ensure_schedule_next_patient_access(
    db: Session,
    *,
    patient_id: int,
    doctor: Doctor | None,
    current_user: User,
) -> None:
    if current_user.role == "Admin":
        return
    if (current_user.role or "").strip().lower() not in DOCTOR_SCHEDULE_NEXT_ROLES:
        return
    if not doctor or not _doctor_schedule_patient_context_exists(
        db,
        patient_id=patient_id,
        doctor=doctor,
        current_user=current_user,
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


class ScheduleNextVisitService(BaseModel):
    service_id: int
    quantity: int = 1
    custom_price: float | None = None


class ScheduleNextVisitRequest(BaseModel):
    patient_id: int
    services: list[ScheduleNextVisitService] = Field(default_factory=list)
    service_ids: list[int] | None = None
    visit_date: date
    visit_time: str | None = None
    discount_mode: str = Field(
        default="none", pattern="^(none|repeat|benefit|all_free)$"
    )
    all_free: bool = False
    notes: str | None = None
    confirmation_channel: str = Field(
        default="phone", pattern="^(phone|telegram|pwa|auto)$"
    )

    @model_validator(mode="after")
    def normalize_services_payload(self):
        # Backward-compatibility for tests/clients that still send `service_ids`.
        if not self.services and self.service_ids:
            self.services = [
                ScheduleNextVisitService(service_id=service_id)
                for service_id in self.service_ids
            ]

        if not self.services:
            raise ValueError("services or service_ids must be provided")

        return self


class ScheduleNextVisitResponse(BaseModel):
    success: bool
    message: str
    visit_id: int
    status: str  # pending_confirmation
    confirmation: dict[str, Any]


# ===================== ОЧЕРЕДЬ ВРАЧА =====================


@router.get("/doctor/{specialty}/queue/today")
def get_doctor_queue_today(
    specialty: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Doctor",
            "Registrar",
            "Cashier",
            "Receptionist",
            "cardio",
            "cardiology",
            "Cardiologist",
            "derma",
            "dentist",
            "Lab",
        )
    ),
):
    """
    Получить очередь врача на сегодня
    Из passport.md стр. 1419: GET /api/doctor/cardiology/queue/today
    """
    try:
        normalized_specialty = _normalize_queue_specialty(specialty)
        specialty_variants = _resolve_queue_specialty_variants(normalized_specialty)
        allowed_queue_tags = _resolve_queue_allowed_tags(normalized_specialty)

        doctor = None
        if normalized_specialty == "general":
            doctor = (
                db.query(Doctor)
                .filter(and_(Doctor.user_id == current_user.id, Doctor.active == True))
                .first()
            )
        else:
            doctor = (
                db.query(Doctor)
                .filter(
                    and_(
                        Doctor.specialty.in_(specialty_variants),
                        Doctor.user_id == current_user.id,
                        Doctor.active == True,
                    )
                )
                .first()
            )

        if not doctor and normalized_specialty != "general":
            doctor = (
                db.query(Doctor)
                .filter(
                    and_(
                        Doctor.specialty.in_(specialty_variants), Doctor.active == True
                    )
                )
                .first()
            )

        if not doctor and normalized_specialty != "general":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Врач специальности '{specialty}' не найден. Проверенные варианты: {specialty_variants}",
            )

        today = date.today()

        candidate_specialist_ids = (
            {doctor.id}
            if doctor
            else ({current_user.id} if normalized_specialty == "general" else set())
        )

        daily_queue_query = db.query(DailyQueue).filter(
            and_(
                DailyQueue.day == today,
                DailyQueue.specialist_id.in_(sorted(candidate_specialist_ids)),
            )
        )

        if allowed_queue_tags:
            queue_tag_filters = [DailyQueue.queue_tag.in_(allowed_queue_tags)]
            if normalized_specialty == "general":
                queue_tag_filters.append(DailyQueue.queue_tag.is_(None))
            daily_queue_query = daily_queue_query.filter(or_(*queue_tag_filters))

        daily_queues = daily_queue_query.order_by(DailyQueue.id.asc()).all()

        if not daily_queues:
            legacy_queue = (
                db.query(DailyQueue)
                .filter(
                    and_(
                        DailyQueue.day == today,
                        DailyQueue.specialist_id.in_(sorted(candidate_specialist_ids)),
                    )
                )
                .order_by(DailyQueue.id.asc())
                .first()
            )
            if legacy_queue and (
                normalized_specialty == "general"
                or legacy_queue.queue_tag in allowed_queue_tags
                or legacy_queue.queue_tag is None
            ):
                daily_queues = [legacy_queue]

        if not daily_queues:
            return {
                "queue_exists": False,
                "doctor": _serialize_queue_doctor(
                    doctor, current_user, normalized_specialty
                ),
                "date": today.isoformat(),
                "entries": [],
                "stats": {"total": 0, "waiting": 0, "called": 0, "served": 0},
                "can_call_next": False,
                "next_call_entry_id": None,
            }

        # Получаем записи очереди
        queue_ids = [queue.id for queue in daily_queues]
        entries = (
            db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id.in_(queue_ids))
            .order_by(OnlineQueueEntry.queue_id.asc(), OnlineQueueEntry.number.asc())
            .all()
        )

        # Формируем данные для врача
        queue_entries = []
        next_call_entry_id = None
        for entry in entries:
            available_actions = _doctor_queue_available_actions(entry)
            action_flags = _doctor_queue_action_flags(entry)
            if next_call_entry_id is None and action_flags["can_call"]:
                next_call_entry_id = entry.id

            patient_data = None
            if entry.patient:
                patient_data = {
                    "id": entry.patient.id,
                    "first_name": entry.patient.first_name,
                    "last_name": entry.patient.last_name,
                    "middle_name": entry.patient.middle_name,
                    "phone": entry.patient.phone,
                    "birth_date": (
                        entry.patient.birth_date.isoformat()
                        if entry.patient.birth_date
                        else None
                    ),
                }

            queue_entries.append(
                {
                    "id": entry.id,
                    "number": entry.number,
                    "patient_name": entry.patient_name
                    or (
                        f"{entry.patient.last_name} {entry.patient.first_name}"
                        if entry.patient
                        else "Пациент"
                    ),
                    "phone": entry.phone,
                    "source": entry.source,
                    "status": entry.status,
                    "created_at": entry.created_at.isoformat() if entry.created_at else None,
                    "queue_time": entry.queue_time.isoformat() if entry.queue_time else None,
                    "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
                    "last_changed_at": entry.updated_at.isoformat() if entry.updated_at else None,
                    "display_time_kind": "queue_time" if entry.queue_time else "created_at",
                    "timezone": "Asia/Tashkent",
                    "called_at": (
                        entry.called_at.isoformat() if entry.called_at else None
                    ),
                    "patient": patient_data,
                    "available_actions": available_actions,
                    **action_flags,
                }
            )

        # Статистика очереди
        stats = {
            "total": len(entries),
            "waiting": len([e for e in entries if e.status == "waiting"]),
            "called": len([e for e in entries if e.status == "called"]),
            "served": len([e for e in entries if e.status == "served"]),
            "online_entries": len([e for e in entries if e.source == "online"]),
            "desk_entries": len([e for e in entries if e.source == "desk"]),
        }

        return {
            "queue_exists": True,
            "queue_id": queue_ids[0],
            "queue_ids": queue_ids,
            "opened_at": (
                daily_queues[0].opened_at.isoformat()
                if daily_queues[0].opened_at
                else None
            ),
            "doctor": _serialize_queue_doctor(doctor, current_user, normalized_specialty),
            "date": today.isoformat(),
            "entries": queue_entries,
            "stats": stats,
            "can_call_next": next_call_entry_id is not None,
            "next_call_entry_id": next_call_entry_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== УПРАВЛЕНИЕ СТАТУСАМИ ПАЦИЕНТОВ =====================


@router.post("/doctor/queue/{entry_id}/call")
def call_patient(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Doctor",
            "Registrar",
            "Cashier",
            "Receptionist",
            "cardio",
            "cardiology",
            "Cardiologist",
            "derma",
            "dentist",
            "Lab",
        )
    ),
):
    """
    Вызвать пациента в кабинет
    Из passport.md стр. 1425: POST /api/visits/:id/complete
    """
    try:
        # Получаем запись в очереди
        queue_entry = (
            db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        )

        if not queue_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись в очереди не найдена",
            )

        # Проверяем что врач имеет право работать с этой очередью
        daily_queue = queue_entry.queue

        if not daily_queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Очередь не найдена"
            )

        doctor = daily_queue.specialist

        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Врач не найден для этой очереди",
            )

        if (
            current_user.role != "Admin"
            and doctor.user_id
            and doctor.user_id != current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет прав для работы с этой очередью",
            )

        # Обновляем статус на "вызван"
        if "call" not in _doctor_queue_available_actions(queue_entry):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Р’С‹Р·РІР°С‚СЊ РјРѕР¶РЅРѕ С‚РѕР»СЊРєРѕ waiting, С‚РµРєСѓС‰РёР№: {queue_entry.status}",
            )

        changed_at = datetime.now(UTC)
        queue_entry.status = "called"
        queue_entry.called_at = changed_at
        queue_entry.updated_at = changed_at

        db.commit()
        db.refresh(queue_entry)

        # Отправляем событие в WebSocket для табло
        try:
            import asyncio

            from app.services.display_websocket import get_display_manager

            async def send_to_display():
                manager = get_display_manager()
                doctor_name = (
                    doctor.user.full_name if doctor.user else f"Врач #{doctor.id}"
                )
                cabinet = doctor.cabinet

                await manager.broadcast_patient_call(
                    queue_entry=queue_entry, doctor_name=doctor_name, cabinet=cabinet
                )

            # Запускаем асинхронную отправку в фоне
            asyncio.create_task(send_to_display())

        except Exception as ws_error:
            # Не прерываем основной процесс если WebSocket не работает
            logger.warning("Не удалось отправить на табло: %s", ws_error, exc_info=True)

        return {
            "success": True,
            "message": f"Пациент #{queue_entry.number} вызван в кабинет",
            "entry": {
                "id": queue_entry.id,
                "number": queue_entry.number,
                "status": queue_entry.status,
                "called_at": queue_entry.called_at.isoformat(),
                "updated_at": queue_entry.updated_at.isoformat() if queue_entry.updated_at else None,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/doctor/queue/{entry_id}/start-visit")
def start_patient_visit(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Doctor",
            "Registrar",
            "Cashier",
            "Receptionist",
            "cardio",
            "cardiology",
            "Cardiologist",
            "derma",
            "dentist",
            "Lab",
        )
    ),
):
    """
    Начать прием пациента (статус в процессе)
    """
    try:
        queue_entry = (
            db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        )

        if not queue_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись в очереди не найдена",
            )

        daily_queue = queue_entry.queue
        doctor = daily_queue.specialist if daily_queue else None
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Врач не найден для этой очереди",
            )

        if (
            current_user.role != "Admin"
            and doctor.user_id
            and doctor.user_id != current_user.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет прав для работы с этой очередью",
            )

        # Обновляем статус
        if "start_visit" not in _doctor_queue_available_actions(queue_entry):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Start visit is not available for current queue status: "
                    f"{queue_entry.status}"
                ),
            )

        changed_at = datetime.now(UTC)
        queue_entry.status = "in_progress"
        queue_entry.updated_at = changed_at

        # Создаем или обновляем визит в таблице visits
        visit = crud_visit.find_or_create_today_visit(
            db=db,
            patient_id=queue_entry.patient_id,
            doctor_id=doctor.id,
            department=getattr(daily_queue, "queue_tag", None) or "general",
        )

        # Обновляем время начала приема
        visit.visit_time = datetime.now().strftime("%H:%M")
        visit.notes = f"Прием начат в {datetime.now().strftime('%H:%M')}"

        visit.updated_at = changed_at

        db.commit()

        return {
            "success": True,
            "message": "Прием пациента начат",
            "entry_id": entry_id,
            "status": "in_progress",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/doctor/queue/{entry_id}/complete")
def complete_patient_visit(
    entry_id: int,
    visit_data: dict[str, Any] | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Doctor",
            "Registrar",
            "Cashier",
            "Receptionist",
            "cardio",
            "cardiology",
            "Cardiologist",
            "derma",
            "dentist",
            "Lab",
        )
    ),
):
    """
    Завершить прием пациента
    Из passport.md стр. 1425: POST /api/visits/:id/complete
    """
    try:
        from app.models.appointment import Appointment
        from app.models.online_queue import OnlineQueueEntry
        from app.models.visit import Visit

        # Канонический путь этого endpoint работает по queue_entries.id.
        # Лишь если такой записи в очереди нет, допускаем legacy fallback на Visit/Appointment.
        queue_entry = (
            db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        )
        requested_patient_id = None
        if isinstance(visit_data, dict):
            raw_patient_id = visit_data.get("patient_id")
            try:
                requested_patient_id = (
                    int(raw_patient_id) if raw_patient_id is not None else None
                )
            except (TypeError, ValueError):
                requested_patient_id = None

        if (
            queue_entry
            and requested_patient_id is not None
            and queue_entry.patient_id is not None
            and queue_entry.patient_id != requested_patient_id
        ):
            # Some legacy doctor flows pass appointment/visit IDs to this route.
            # If the numeric ID collides with an unrelated queue entry, do not
            # mutate the queue entry; allow the typed legacy fallback below.
            logger.warning(
                "complete_patient_visit: route id matched a queue entry for a different patient than the request payload; trying legacy record fallback"
            )
            queue_entry = None

        visit = None
        if not queue_entry:
            visit = db.query(Visit).filter(Visit.id == entry_id).first()
            if (
                visit
                and requested_patient_id is not None
                and visit.patient_id is not None
                and visit.patient_id != requested_patient_id
            ):
                logger.warning(
                    "complete_patient_visit: route id matched a Visit for a different patient than the request payload; trying appointment fallback"
                )
                visit = None
        if visit:
            _ensure_legacy_complete_doctor_access(
                db,
                record_doctor_id=visit.doctor_id,
                current_user=current_user,
            )
            # Обновляем статус визита
            visit.status = "completed"
            visit.updated_at = datetime.now(UTC)

            # Payment state remains in Payment; completion must not rewrite
            # registration discount_mode.
            db.commit()
            db.refresh(visit)

            # Завершаем визит с медицинскими данными
            if visit_data:
                crud_visit.complete_visit(
                    db=db, visit_id=visit.id, medical_data=visit_data
                )

            return {
                "success": True,
                "message": "Прием пациента завершен",
                "entry_id": entry_id,
                "status": "completed",
            }

        # Если не найден в Visit, ищем в Appointment
        appointment = None
        if not queue_entry:
            appointment = (
                db.query(Appointment).filter(Appointment.id == entry_id).first()
            )
            if (
                appointment
                and requested_patient_id is not None
                and appointment.patient_id is not None
                and appointment.patient_id != requested_patient_id
            ):
                logger.warning(
                    "complete_patient_visit: route id matched an Appointment for a different patient than the request payload"
                )
                appointment = None
        if appointment:
            _ensure_legacy_complete_doctor_access(
                db,
                record_doctor_id=appointment.doctor_id,
                current_user=current_user,
            )
            # Обновляем статус appointment
            appointment.status = "completed"

            db.commit()
            db.refresh(appointment)

            return {
                "success": True,
                "message": "Прием пациента завершен",
                "entry_id": entry_id,
                "status": "completed",
            }

        # Если найден queue entry, завершаем канонический queue flow
        if queue_entry:
            # Проверяем права врача на эту очередь
            daily_queue = queue_entry.queue
            doctor = daily_queue.specialist if daily_queue else None
            if (
                doctor
                and current_user.role != "Admin"
                and doctor.user_id != current_user.id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Нет прав для работы с этой очередью",
                )

            # Отмечаем запись очереди как обслуженную
            if "complete" not in _doctor_queue_available_actions(queue_entry):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Complete visit is not available for current queue status: "
                        f"{queue_entry.status}"
                    ),
                )

            changed_at = datetime.now(UTC)
            queue_entry.status = "served"
            queue_entry.updated_at = changed_at
            db.commit()
            db.refresh(queue_entry)

            # Создаем или обновляем визит на сегодня и помечаем как завершенный,
            # чтобы это отразилось в registrar/queues/today, который читает Visit/Appointment
            try:
                visit = crud_visit.find_or_create_today_visit(
                    db=db,
                    patient_id=queue_entry.patient_id,
                    doctor_id=doctor.id if doctor else None,
                    department=(
                        daily_queue.department
                        if daily_queue and hasattr(daily_queue, 'department')
                        else "cardiology"
                    ),
                )
                # ✅ Обновляем статус визита на completed
                visit.status = "completed"
                visit.updated_at = changed_at

                # ✅ ИСПРАВЛЕНО: Проверяем и сохраняем информацию об оплате, создаем платеж через SSOT
                # Если визит был оплачен (есть записи в Payment или статус указывает на оплату)
                from app.models.payment import Payment

                payment = (
                    db.query(Payment)
                    .filter(Payment.visit_id == visit.id)
                    .order_by(Payment.created_at.desc())
                    .first()
                )
                payment_is_paid = bool(
                    payment
                    and (
                        (payment.status and payment.status.lower() == "paid")
                        or payment.paid_at
                    )
                )
                if payment_is_paid:
                    # Paid payment may update explicit payment markers only;
                    # registration discount_mode must be preserved.
                    if (
                        hasattr(visit, 'payment_processed_at')
                        and not visit.payment_processed_at
                    ):
                        visit.payment_processed_at = (
                            payment.paid_at or datetime.now(UTC)
                        )
                # ✅ Также обновляем соответствующий Appointment, если он существует
                from app.models.appointment import Appointment

                appointment = (
                    db.query(Appointment)
                    .filter(
                        and_(
                            Appointment.patient_id == queue_entry.patient_id,
                            (
                                Appointment.appointment_date == visit.visit_date
                                if visit.visit_date
                                else date.today()
                            ),
                            Appointment.doctor_id == visit.doctor_id,
                        )
                    )
                    .first()
                )

                if appointment:
                    appointment.status = "completed"
                    # Appointment has no discount_mode; use its explicit payment marker.
                    if (
                        payment_is_paid
                        and not appointment.payment_processed_at
                    ):
                        appointment.payment_processed_at = (
                            payment.paid_at or datetime.now(UTC)
                        )

                if visit_data:
                    # Сохраняем медицинские данные, если переданы
                    crud_visit.complete_visit(
                        db=db, visit_id=visit.id, medical_data=visit_data
                    )

                # ✅ Коммитим все изменения (Visit и Appointment)
                db.commit()
                db.refresh(visit)
                if appointment:
                    db.refresh(appointment)
            except Exception as e:
                # Не блокируем основной флоу очереди, если с визитом что-то пошло не так
                logger.warning(
                    f"Ошибка создания/обновления визита при завершении приема: {e}"
                )
                db.rollback()

            return {
                "success": True,
                "message": "Прием пациента завершен",
                "entry_id": entry_id,
                "status": "completed",
            }

        # Иначе действительно не найдено
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== УСЛУГИ ДЛЯ ВРАЧА =====================


@router.get("/doctor/{specialty}/services")
def get_doctor_services(
    specialty: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Doctor",
            "Registrar",
            "Cashier",
            "Receptionist",
            "cardio",
            "cardiology",
            "Cardiologist",
            "derma",
            "dentist",
            "Lab",
        )
    ),
):
    """
    Получить услуги для врача конкретной специальности
    Из passport.md стр. 1254: услуги визита по специальности
    """
    try:
        # Получаем категории услуг для специальности
        categories = crud_clinic.get_service_categories(
            db, specialty=specialty, active_only=True
        )

        # Получаем услуги
        from app.models.service import Service

        services = db.query(Service).filter(Service.active == True).all()

        # Группируем по категориям
        grouped_services = {}

        for category in categories:
            category_services = [
                {
                    "id": service.id,
                    "name": service.name,
                    "code": service.service_code or get_service_code(service.id, db),
                    "price": float(service.price) if service.price else 0,
                    "currency": service.currency or "UZS",
                    "duration_minutes": service.duration_minutes or 30,
                    "category": {
                        "id": category.id,
                        "code": category.code,
                        "name_ru": category.name_ru,
                    },
                }
                for service in services
                if service.category_id == category.id
            ]

            if category_services:
                grouped_services[category.code] = {
                    "category": {
                        "id": category.id,
                        "code": category.code,
                        "name_ru": category.name_ru,
                        "name_uz": category.name_uz,
                        "specialty": category.specialty,
                    },
                    "services": category_services,
                }

        return {
            "specialty": specialty,
            "services_by_category": grouped_services,
            "total_services": sum(
                len(group["services"]) for group in grouped_services.values()
            ),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== ИНФОРМАЦИЯ О ВРАЧЕ =====================


@router.get("/doctor/my-info")
def get_doctor_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin", "Doctor", "Registrar", "cardio", "cardiology", "derma", "dentist"
        )
    ),
):
    """
    Получить информацию о текущем враче
    """
    try:
        doctor = (
            db.query(Doctor)
            .filter(and_(Doctor.user_id == current_user.id, Doctor.active == True))
            .first()
        )

        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Профиль врача не найден"
            )

        # Получаем расписание
        schedules = crud_clinic.get_doctor_schedules(db, doctor.id)

        # Получаем настройки очереди
        queue_settings = crud_clinic.get_queue_settings(db)
        specialty_settings = queue_settings.get("start_numbers", {}).get(
            doctor.specialty, 1
        )
        max_per_day = queue_settings.get("max_per_day", {}).get(doctor.specialty, 15)

        return {
            "doctor": {
                "id": doctor.id,
                "user_id": doctor.user_id,
                "specialty": doctor.specialty,
                "cabinet": doctor.cabinet,
                "price_default": (
                    float(doctor.price_default) if doctor.price_default else 0
                ),
                "start_number_online": doctor.start_number_online,
                "max_online_per_day": doctor.max_online_per_day,
            },
            "user": {
                "id": current_user.id,
                "username": current_user.username,
                "full_name": current_user.full_name,
                "email": current_user.email,
                "role": current_user.role,
            },
            "schedules": [
                {
                    "weekday": s.weekday,
                    "start_time": (
                        s.start_time.strftime("%H:%M") if s.start_time else None
                    ),
                    "end_time": s.end_time.strftime("%H:%M") if s.end_time else None,
                    "breaks": s.breaks,
                    "active": s.active,
                }
                for s in schedules
            ],
            "queue_settings": {
                "start_number": specialty_settings,
                "max_per_day": max_per_day,
                "timezone": queue_settings.get("timezone", "Asia/Tashkent"),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== КАЛЕНДАРЬ ВРАЧА =====================


@router.get("/doctor/calendar")
def get_doctor_calendar(
    start_date: date = Query(..., description="Начальная дата"),
    end_date: date = Query(..., description="Конечная дата"),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin", "Doctor", "Registrar", "cardio", "cardiology", "derma", "dentist"
        )
    ),
):
    """
    Календарь врача с будущими записями
    Из passport.md стр. 1223: будущие записи с цветами статусов
    """
    try:
        # Получаем врача
        doctor = (
            db.query(Doctor)
            .filter(and_(Doctor.user_id == current_user.id, Doctor.active == True))
            .first()
        )

        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Профиль врача не найден"
            )

        # Здесь будет логика получения записей из таблицы appointments
        # Пока возвращаем заглушку

        return {
            "doctor_id": doctor.id,
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "appointments": [],  # Будет заполнено при интеграции с appointments
            "schedule": [
                {
                    "weekday": s.weekday,
                    "start_time": (
                        s.start_time.strftime("%H:%M") if s.start_time else None
                    ),
                    "end_time": s.end_time.strftime("%H:%M") if s.end_time else None,
                    "active": s.active,
                }
                for s in crud_clinic.get_doctor_schedules(db, doctor.id)
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== СТАТИСТИКА ВРАЧА =====================


@router.get("/doctor/stats")
def get_doctor_stats(
    days_back: int = Query(7, ge=1, le=30, description="Дней назад"),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin", "Doctor", "Registrar", "cardio", "cardiology", "derma", "dentist"
        )
    ),
):
    """Статистика работы врача"""
    try:
        # Получаем врача
        doctor = (
            db.query(Doctor)
            .filter(and_(Doctor.user_id == current_user.id, Doctor.active == True))
            .first()
        )

        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Профиль врача не найден"
            )

        from datetime import timedelta

        start_date = date.today() - timedelta(days=days_back)

        # Получаем очереди за период
        daily_queues = (
            db.query(DailyQueue)
            .filter(
                and_(
                    DailyQueue.specialist_id == doctor.id,
                    DailyQueue.day >= start_date,
                )
            )
            .all()
        )

        total_patients = 0
        served_patients = 0
        online_patients = 0

        for queue in daily_queues:
            entries = (
                db.query(OnlineQueueEntry)
                .filter(OnlineQueueEntry.queue_id == queue.id)
                .all()
            )
            total_patients += len(entries)
            served_patients += len([e for e in entries if e.status == "served"])
            online_patients += len([e for e in entries if e.source == "online"])

        return {
            "doctor": {
                "name": doctor.user.full_name if doctor.user else f"Врач #{doctor.id}",
                "specialty": doctor.specialty,
                "cabinet": doctor.cabinet,
            },
            "period": {
                "start": start_date.isoformat(),
                "end": date.today().isoformat(),
                "days": days_back,
            },
            "stats": {
                "total_patients": total_patients,
                "served_patients": served_patients,
                "online_patients": online_patients,
                "completion_rate": (
                    (served_patients / total_patients * 100)
                    if total_patients > 0
                    else 0
                ),
                "online_rate": (
                    (online_patients / total_patients * 100)
                    if total_patients > 0
                    else 0
                ),
            },
            "daily_breakdown": [
                {
                    "date": queue.day.isoformat(),
                    "opened_at": (
                        queue.opened_at.isoformat() if queue.opened_at else None
                    ),
                    "total_entries": db.query(OnlineQueueEntry)
                    .filter(OnlineQueueEntry.queue_id == queue.id)
                    .count(),
                    "served_entries": db.query(OnlineQueueEntry)
                    .filter(
                        and_(
                            OnlineQueueEntry.queue_id == queue.id,
                            OnlineQueueEntry.status == "served",
                        )
                    )
                    .count(),
                }
                for queue in daily_queues
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== НАЗНАЧЕНИЕ СЛЕДУЮЩЕГО ВИЗИТА =====================


@router.post("/doctor/visits/schedule-next", response_model=ScheduleNextVisitResponse)
async def schedule_next_visit(
    request: ScheduleNextVisitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Doctor",
            "Registrar",
            "Cashier",
            "Receptionist",
            "cardio",
            "cardiology",
            "derma",
            "dentist",
        )
    ),
):
    """
    Назначение следующего визита врачом (без номера в очереди)
    Номер будет присвоен только после подтверждения пациентом
    """
    try:
        # Получаем врача
        doctor = (
            db.query(Doctor)
            .filter(and_(Doctor.user_id == current_user.id, Doctor.active == True))
            .first()
        )

        if not doctor and current_user.role != "Admin":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Профиль врача не найден"
            )

        # Проверяем что дата не в прошлом
        if request.visit_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя назначить визит на прошедшую дату",
            )

        # Проверяем существование пациента
        from app.models.patient import Patient

        patient = db.query(Patient).filter(Patient.id == request.patient_id).first()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Пациент не найден"
            )

        # Проверяем существование услуг
        _ensure_schedule_next_patient_access(
            db,
            patient_id=request.patient_id,
            doctor=doctor,
            current_user=current_user,
        )

        service_ids = [s.service_id for s in request.services]
        services = db.query(Service).filter(Service.id.in_(service_ids)).all()

        if len(services) != len(service_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Некоторые услуги не найдены",
            )

        # Генерируем токен подтверждения
        confirmation_token = str(uuid.uuid4())
        expires_at = datetime.now(UTC) + timedelta(
            hours=48
        )  # 48 часов на подтверждение

        # Создаем визит со статусом pending_confirmation
        visit = Visit(
            patient_id=request.patient_id,
            # Backward compatibility for admin/test flows without Doctor profile.
            doctor_id=doctor.id if doctor else current_user.id,
            visit_date=request.visit_date,
            visit_time=request.visit_time,
            status="pending_confirmation",  # Ожидает подтверждения
            discount_mode=request.discount_mode,
            department="mixed",  # Будет определен по услугам
            notes=request.notes,
            confirmation_token=confirmation_token,
            confirmation_channel=request.confirmation_channel,
            confirmation_expires_at=expires_at,
            source="desk",  # ✅ SSOT: Врач назначает = desk
        )
        db.add(visit)
        db.flush()  # Получаем ID визита

        # Добавляем услуги к визиту
        total_amount = 0
        for service_req in request.services:
            service = next(s for s in services if s.id == service_req.service_id)

            # Вычисляем цену
            service_price = service_req.custom_price or (
                float(service.price) if service.price else 0
            )

            # Применяем скидки для консультаций
            if service.is_consultation:
                if request.discount_mode in ["repeat", "benefit"] or request.all_free:
                    service_price = 0

            # All Free делает всё бесплатным
            if request.all_free:
                service_price = 0

            visit_service = VisitService(
                visit_id=visit.id,
                service_id=service.id,
                name=service.name,
                # ✅ SSOT: Используем service_mapping.get_service_code() вместо дублирующей логики
                code=service.service_code or get_service_code(service.id, db),
                qty=service_req.quantity,
                price=service_price,
                currency="UZS",
            )
            db.add(visit_service)

            total_amount += service_price * service_req.quantity

        db.commit()
        db.refresh(visit)

        # Отправляем приглашение на подтверждение
        notification_service = NotificationService(db)
        try:
            notification_result = (
                await notification_service.send_visit_confirmation_invitation(
                    visit=visit, channel=request.confirmation_channel
                )
            )
            logger.info(
                f"Приглашение отправлено для визита {visit.id}: {notification_result}"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки приглашения для визита {visit.id}: {e}")
            # Не прерываем выполнение, визит уже создан

        # Формируем ответ
        confirmation_data = {
            "token": confirmation_token,
            "channel": request.confirmation_channel,
            "expires_at": expires_at.isoformat(),
            "patient_name": patient.short_name(),
            "visit_date": request.visit_date.isoformat(),
            "visit_time": request.visit_time,
            "total_amount": total_amount,
            "services_count": len(request.services),
            "notification_sent": (
                notification_result.get("success", False)
                if 'notification_result' in locals()
                else False
            ),
        }

        return ScheduleNextVisitResponse(
            success=True,
            message=f"Визит назначен на {request.visit_date}. Ожидает подтверждения пациентом.",
            visit_id=visit.id,
            status="pending_confirmation",
            confirmation=confirmation_data,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка назначения следующего визита: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== УПРАВЛЕНИЕ ВИЗИТАМИ =====================


@router.get("/doctor/visits/today")
def get_today_visits(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Doctor",
            "Registrar",
            "Cashier",
            "Receptionist",
            "cardio",
            "cardiology",
            "derma",
            "dentist",
        )
    ),
):
    """Получить сегодняшние визиты врача"""
    try:
        visits = crud_visit.get_today_visits_by_doctor(
            db=db,
            doctor_id=_visit_filter_doctor_id(db, current_user),
        )

        result = []
        for visit in visits:
            # Получаем услуги визита
            visit_services = crud_visit.get_visit_services(db=db, visit_id=visit.id)

            services_data = []
            total_amount = 0

            for vs in visit_services:
                service = db.query(Service).filter(Service.id == vs.service_id).first()
                service_data = {
                    "id": vs.id,
                    "service_id": vs.service_id,
                    "service_name": (
                        service.name if service else f"Услуга #{vs.service_id}"
                    ),
                    "quantity": vs.quantity,
                    "price": vs.price,
                    "custom_price": vs.custom_price,
                    "total": vs.price * vs.quantity,
                }
                services_data.append(service_data)
                total_amount += service_data["total"]

            result.append(
                {
                    "id": visit.id,
                    "patient_id": visit.patient_id,
                    "visit_date": (
                        visit.visit_date.isoformat() if visit.visit_date else None
                    ),
                    "visit_time": visit.visit_time,
                    "status": visit.status,
                    "department": visit.department,
                    "discount_mode": visit.discount_mode,
                    "notes": visit.notes,
                    "services": services_data,
                    "total_amount": total_amount,
                    "created_at": (
                        visit.created_at.isoformat() if visit.created_at else None
                    ),
                }
            )

        return {"success": True, "visits": result, "total_count": len(result)}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/doctor/visits/statistics")
def get_visit_statistics(
    date_from: str | None = Query(
        None, description="Дата начала в формате YYYY-MM-DD"
    ),
    date_to: str | None = Query(
        None, description="Дата окончания в формате YYYY-MM-DD"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dentist")
    ),
):
    """Получить статистику визитов врача"""
    try:
        from datetime import datetime

        date_from_obj = None
        date_to_obj = None

        if date_from:
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()

        if date_to:
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()

        stats = crud_visit.get_visit_statistics(
            db=db,
            doctor_id=_visit_filter_doctor_id(db, current_user),
            date_from=date_from_obj,
            date_to=date_to_obj,
        )

        return {
            "success": True,
            "statistics": stats,
            "period": {"date_from": date_from, "date_to": date_to},
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    except HTTPException:
        raise
    except Exception as e:  # noqa: B025  # manual-review: duplicate exception in try block — manual review
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

@router.get("/doctor/visits/{visit_id}")
def get_visit_details(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Doctor",
            "Registrar",
            "Cashier",
            "Receptionist",
            "cardio",
            "cardiology",
            "derma",
            "dentist",
        )
    ),
):
    """Получить детали визита"""
    try:
        visit = crud_visit.get_visit(db=db, visit_id=visit_id)

        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Визит не найден"
            )

        # Проверяем права доступа
        _ensure_visit_doctor_access(visit, current_user)

        # Получаем услуги визита
        visit_services = crud_visit.get_visit_services(db=db, visit_id=visit.id)

        services_data = []
        total_amount = 0

        for vs in visit_services:
            service = db.query(Service).filter(Service.id == vs.service_id).first()
            service_data = {
                "id": vs.id,
                "service_id": vs.service_id,
                "service_name": service.name if service else f"Услуга #{vs.service_id}",
                "service_code": (service.service_code or get_service_code(service.id, db)) if service else None,
                "quantity": vs.quantity,
                "price": vs.price,
                "custom_price": vs.custom_price,
                "total": vs.price * vs.quantity,
            }
            services_data.append(service_data)
            total_amount += service_data["total"]

        return {
            "success": True,
            "visit": {
                "id": visit.id,
                "patient_id": visit.patient_id,
                "doctor_id": visit.doctor_id,
                "visit_date": (
                    visit.visit_date.isoformat() if visit.visit_date else None
                ),
                "visit_time": visit.visit_time,
                "status": visit.status,
                "department": visit.department,
                "discount_mode": visit.discount_mode,
                "approval_status": visit.approval_status,
                "notes": visit.notes,
                "services": services_data,
                "total_amount": total_amount,
                "created_at": (
                    visit.created_at.isoformat() if visit.created_at else None
                ),
                "confirmed_at": (
                    visit.confirmed_at.isoformat() if visit.confirmed_at else None
                ),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/doctor/visits/{visit_id}/add-service")
def add_service_to_visit(
    visit_id: int,
    service_id: int,
    quantity: int = 1,
    custom_price: float | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dentist")
    ),
):
    """Добавить услугу к визиту"""
    try:
        visit = crud_visit.get_visit(db=db, visit_id=visit_id)

        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Визит не найден"
            )

        # Проверяем права доступа
        _ensure_visit_doctor_access(visit, current_user)

        # Проверяем, что услуга существует
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена"
            )

        # Добавляем услугу
        visit_service = crud_visit.add_visit_service(
            db=db,
            visit_id=visit_id,
            service_id=service_id,
            quantity=quantity,
            custom_price=custom_price,
        )

        return {
            "success": True,
            "message": "Услуга добавлена к визиту",
            "visit_service": {
                "id": visit_service.id,
                "service_id": visit_service.service_id,
                "service_name": service.name,
                "quantity": visit_service.quantity,
                "price": visit_service.price,
                "custom_price": visit_service.custom_price,
                "total": visit_service.price * visit_service.quantity,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/doctor/visits/{visit_id}/services/{visit_service_id}")
def remove_service_from_visit(
    visit_id: int,
    visit_service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dentist")
    ),
):
    """Удалить услугу из визита"""
    try:
        visit = crud_visit.get_visit(db=db, visit_id=visit_id)

        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Визит не найден"
            )

        # Проверяем права доступа
        _ensure_visit_doctor_access(visit, current_user)

        # Удаляем услугу
        visit_service = (
            db.query(VisitService)
            .filter(
                VisitService.id == visit_service_id,
                VisitService.visit_id == visit.id,
            )
            .first()
        )

        if not visit_service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Услуга в визите не найдена",
            )

        db.delete(visit_service)
        db.commit()

        return {"success": True, "message": "Услуга удалена из визита"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
