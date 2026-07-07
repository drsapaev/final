"""
API endpoints для интеграции с Telegram ботом
Основа: passport.md стр. 2064-2570
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api.deps import get_db, require_roles
from app.crud import patient as crud_patient
from app.crud import telegram_config as crud_telegram
from app.models.appointment import Appointment
from app.models.lab import LabOrder, LabResult
from app.models.user import User
from app.services.telegram_service import (
    get_telegram_service,
    send_telegram_notification,
)

router = APIRouter()


def _appointment_id_from_payload(appointment_data: dict[str, Any]) -> int | None:
    for key in ("appointment_id", "id"):
        value = appointment_data.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid appointment_id",
            )
    return None


def _ensure_appointment_reminder_belongs_to_phone(
    db: Session,
    *,
    patient_phone: str,
    appointment_data: dict[str, Any],
) -> None:
    appointment_id = _appointment_id_from_payload(appointment_data)
    if appointment_id is None:
        return

    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    patient = crud_patient.find_patient(db, phone=patient_phone)
    if not patient or appointment.patient_id != patient.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

def _lab_result_id_from_payload(lab_data: dict[str, Any]) -> int | None:
    for key in ("lab_results_id", "lab_result_id", "id"):
        value = lab_data.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid lab_results_id",
            )
    return None


def _ensure_lab_notification_belongs_to_phone(
    db: Session,
    *,
    patient_phone: str,
    lab_data: dict[str, Any],
) -> None:
    lab_result_id = _lab_result_id_from_payload(lab_data)
    if lab_result_id is None:
        return

    lab_result = db.query(LabResult).filter(LabResult.id == lab_result_id).first()
    if not lab_result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lab result not found",
        )

    lab_order = db.query(LabOrder).filter(LabOrder.id == lab_result.order_id).first()
    patient = crud_patient.find_patient(db, phone=patient_phone)
    if not lab_order or not patient or lab_order.patient_id != patient.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )


# ===================== УВЕДОМЛЕНИЯ =====================


@router.post("/send-notification")
async def send_notification(
    request: dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Отправка уведомления пациенту
    """
    try:
        chat_id = request.get("chat_id")
        template_key = request.get("template_key")
        data = request.get("data", {})
        language = request.get("language", "ru")

        if not chat_id or not template_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не указан chat_id или template_key",
            )

        # Отправляем уведомление в фоне
        background_tasks.add_task(
            send_telegram_notification, chat_id, template_key, data, language
        )

        return {
            "success": True,
            "message": "Уведомление поставлено в очередь на отправку",
            "chat_id": chat_id,
            "template": template_key,
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/appointment-reminder")
async def send_appointment_reminder(
    request: dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Отправка напоминания о записи
    """
    try:
        patient_phone = request.get("patient_phone")
        appointment_data = request.get("appointment_data")

        if not patient_phone or not appointment_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не указан телефон пациента или данные записи",
            )

        # Ищем Telegram пользователя по телефону
        telegram_user = crud_telegram.find_telegram_user_by_phone(db, patient_phone)

        if not telegram_user:
            return {
                "success": False,
                "message": "Пациент не зарегистрирован в Telegram боте",
                "phone": patient_phone,
            }

        # Формируем данные для шаблона
        _ensure_appointment_reminder_belongs_to_phone(
            db,
            patient_phone=patient_phone,
            appointment_data=appointment_data,
        )

        template_data = {
            "patient_name": appointment_data.get("patient_name", "Пациент"),
            "doctor_name": appointment_data.get("doctor_name", "Врач"),
            "specialty": appointment_data.get("specialty", "Специалист"),
            "appointment_date": appointment_data.get("date", "Не указано"),
            "appointment_time": appointment_data.get("time", "Не указано"),
            "cabinet": appointment_data.get("cabinet", "Уточните в регистратуре"),
            "clinic_address": "г. Ташкент, ул. Медицинская, 15",  # Из настроек
            "clinic_phone": "+998 71 123-45-67",  # Из настроек
        }

        # Отправляем напоминание
        background_tasks.add_task(
            send_telegram_notification,
            telegram_user.chat_id,
            "appointment_reminder",
            template_data,
            telegram_user.language_code,
        )

        return {
            "success": True,
            "message": "Напоминание отправлено",
            "chat_id": telegram_user.chat_id,
            "patient": appointment_data.get("patient_name"),
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/lab-results-notification")
async def send_lab_results_notification(
    request: dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Lab", "Doctor")),
):
    """
    Уведомление о готовности результатов анализов
    """
    try:
        patient_phone = request.get("patient_phone")
        lab_data = request.get("lab_data")

        if not patient_phone or not lab_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не указан телефон пациента или данные анализов",
            )

        # Ищем Telegram пользователя
        telegram_user = crud_telegram.find_telegram_user_by_phone(db, patient_phone)

        if not telegram_user:
            return {
                "success": False,
                "message": "Пациент не зарегистрирован в Telegram боте",
                "phone": patient_phone,
            }

        # Формируем данные для шаблона
        _ensure_lab_notification_belongs_to_phone(
            db,
            patient_phone=patient_phone,
            lab_data=lab_data,
        )

        template_data = {
            "patient_name": lab_data.get("patient_name", "Пациент"),
            "test_type": lab_data.get("test_type", "Лабораторное исследование"),
            "collection_date": lab_data.get("collection_date", "Не указано"),
            "ready_date": datetime.now().strftime("%d.%m.%Y"),
            "has_abnormalities": lab_data.get("has_abnormalities", False),
        }

        # Отправляем уведомление
        background_tasks.add_task(
            send_telegram_notification,
            telegram_user.chat_id,
            "lab_results_ready",
            template_data,
            telegram_user.language_code,
        )

        return {
            "success": True,
            "message": "Уведомление о результатах отправлено",
            "chat_id": telegram_user.chat_id,
            "patient": lab_data.get("patient_name"),
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== QR КОДЫ =====================


@router.post("/send-qr-code")
async def send_qr_code(
    request: dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Отправка QR кода для онлайн-очереди
    """
    try:
        patient_phone = request.get("patient_phone")
        qr_data = request.get("qr_data")

        if not patient_phone or not qr_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не указан телефон пациента или данные QR",
            )

        # Ищем Telegram пользователя
        telegram_user = crud_telegram.find_telegram_user_by_phone(db, patient_phone)

        if not telegram_user:
            return {
                "success": False,
                "message": "Пациент не зарегистрирован в Telegram боте",
                "phone": patient_phone,
            }

        # Формируем данные для шаблона QR
        template_data = {
            "doctor_name": qr_data.get("doctor_name", "Врач"),
            "specialty": qr_data.get("specialty", "Специалист"),
            "date": qr_data.get("date", "Не указано"),
            "time_window": qr_data.get("time_window", "07:00-09:00"),
            "qr_token": qr_data.get("token", ""),
            # TG-AUDIT-28 P0-4: real URL (was clinic.example.com — regression)
            "queue_url": f"{str(getattr(settings, 'FRONTEND_URL', '') or 'http://localhost:5173').rstrip('/')}/queue",
        }

        # Отправляем QR код
        background_tasks.add_task(
            send_telegram_notification,
            telegram_user.chat_id,
            "qr_code_message",
            template_data,
            telegram_user.language_code,
        )

        return {
            "success": True,
            "message": "QR код отправлен в Telegram",
            "chat_id": telegram_user.chat_id,
            "token": qr_data.get("token"),
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== УПРАВЛЕНИЕ БОТОМ =====================


@router.get("/bot-status")
def get_bot_status(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """
    Получить статус Telegram бота
    """
    try:
        config = crud_telegram.get_telegram_config(db)

        if not config:
            return {
                "configured": False,
                "active": False,
                "message": "Telegram бот не настроен",
            }

        telegram_service = get_telegram_service()  # noqa: F841  # manual-review: variable intentionally kept for debugging/future use

        return {
            "configured": bool(config.bot_token),
            "active": config.active,
            "bot_username": config.bot_username,
            "notifications_enabled": config.notifications_enabled,
            "supported_languages": config.supported_languages,
            "stats": {
                "total_users": len(
                    crud_telegram.get_telegram_users(db, active_only=False)
                ),
                "active_users": len(
                    crud_telegram.get_telegram_users(db, active_only=True)
                ),
                "templates": len(crud_telegram.get_telegram_templates(db)),
            },
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/users")
def get_telegram_users(
    active_only: bool = True,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Получить список пользователей Telegram
    """
    try:
        users = crud_telegram.get_telegram_users(
            db, active_only=active_only, limit=limit
        )

        users_data = []
        for user in users:
            users_data.append(
                {
                    "id": user.id,
                    "chat_id": user.chat_id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "language_code": user.language_code,
                    "notifications_enabled": user.notifications_enabled,
                    "patient_linked": bool(user.patient_id),
                    "last_activity": (
                        user.last_activity.isoformat() if user.last_activity else None
                    ),
                    "active": user.active,
                }
            )

        return {"users": users_data, "total": len(users_data)}

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== БЫСТРЫЕ ДЕЙСТВИЯ =====================


@router.post("/quick/appointment-reminder")
async def quick_appointment_reminder(
    patient_phone: str,
    doctor_name: str,
    appointment_date: str,
    appointment_time: str,
    specialty: str = "Врач",
    cabinet: str = "Уточните в регистратуре",
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Быстрая отправка напоминания о записи
    """
    appointment_data = {
        "patient_name": "Пациент",  # Получать из БД по телефону
        "doctor_name": doctor_name,
        "specialty": specialty,
        "date": appointment_date,
        "time": appointment_time,
        "cabinet": cabinet,
    }

    return await send_appointment_reminder(
        {"patient_phone": patient_phone, "appointment_data": appointment_data},
        background_tasks,
        db,
        current_user,
    )


@router.post("/quick/qr-notification")
async def quick_qr_notification(
    patient_phone: str,
    doctor_name: str,
    specialty: str,
    qr_token: str,
    date: str,
    time_window: str = "07:00-09:00",
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Быстрая отправка QR кода
    """
    qr_data = {
        "doctor_name": doctor_name,
        "specialty": specialty,
        "token": qr_token,
        "date": date,
        "time_window": time_window,
    }

    return await send_qr_code(
        {"patient_phone": patient_phone, "qr_data": qr_data},
        background_tasks,
        db,
        current_user,
    )
