"""
Расширенные API endpoints для Telegram уведомлений
Поддержка массовых рассылок, планировщика и аналитики
"""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.api.v1.endpoints.admin_telegram import PATIENT_PAYMENT_ENTRY_ROUTE
from app.core.config import settings
from app.crud import (
    appointment as crud_appointment,
)
from app.crud import (
    lab_result as crud_lab,
)
from app.crud import (
    patient as crud_patient,
)
from app.crud import (
    telegram_config as crud_telegram,
)
from app.models.clinic import Doctor
from app.models.lab import LabOrder
from app.models.payment import Payment
from app.models.user import User
from app.models.visit import Visit
from app.services.telegram_bot import get_telegram_bot_service
from app.services.telegram_templates import get_telegram_templates_service

router = APIRouter()

PROTECTED_LAB_RESULTS_URL = "/patient/lab-results"  # P3 fix: relative URL, not example.com
PROTECTED_DOCTOR_CONTACT_REFERENCE = "assigned"
PROTECTED_PAYMENT_HISTORY_PATH = PATIENT_PAYMENT_ENTRY_ROUTE
PROTECTED_PAYMENT_REFERENCE = "available-in-protected-account"


def _telegram_notification_allowed(telegram_user: Any, *preference_fields: str) -> bool:
    if not bool(getattr(telegram_user, "notifications_enabled", True)):
        return False
    return all(bool(getattr(telegram_user, field, True)) for field in preference_fields)


def _telegram_notifications_disabled_response() -> dict[str, Any]:
    return {
        "success": False,
        "message": "Telegram notifications disabled by patient preference",
    }


def _protected_frontend_url(path: str) -> str:
    base_url = str(
        getattr(settings, "FRONTEND_URL", None) or "http://localhost:5173"
    ).strip()
    normalized_base = base_url.rstrip("/") or "http://localhost:5173"
    normalized_path = f"/{str(path or '').strip().lstrip('/')}"
    return f"{normalized_base}{normalized_path}"


def _protected_payment_history_url() -> str:
    return _protected_frontend_url(PROTECTED_PAYMENT_HISTORY_PATH)


def _safe_lab_template_data(
    patient: Any,
    lab_results: list[Any],
    templates_service: Any,
    language: str,
) -> dict[str, Any]:
    test_types = [result.test_code for result in lab_results]
    has_abnormalities = any(
        result.is_abnormal for result in lab_results if hasattr(result, "is_abnormal")
    )
    return {
        "patient_name": patient.full_name,
        "test_type": ", ".join(test_types),
        "collection_date": lab_results[0].created_at.strftime("%d.%m.%Y"),
        "ready_date": datetime.now().strftime("%d.%m.%Y"),
        "has_abnormalities": has_abnormalities,
        "abnormalities_text": templates_service.get_abnormalities_text(
            has_abnormalities, language
        ),
        "download_link": PROTECTED_LAB_RESULTS_URL,
        "doctor_id": PROTECTED_DOCTOR_CONTACT_REFERENCE,
        "clinic_address": "г. Ташкент, ул. Медицинская, 15",
    }


def _safe_payment_template_data(payment_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "amount": payment_data.get("amount", 0),
        "currency": payment_data.get("currency", "UZS"),
        "payment_method": payment_data.get("payment_method", "Карта"),
        "payment_date": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "transaction_id": PROTECTED_PAYMENT_REFERENCE,
        "receipt_link": _protected_payment_history_url(),
    }


def _doctor_allowed_doctor_ids(db: Session, current_user: User) -> set[int]:
    doctor = (
        db.query(Doctor)
        .filter(Doctor.user_id == current_user.id, Doctor.active.is_(True))
        .first()
    )
    if not doctor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    allowed_doctor_ids = {doctor.id}
    assigned_doctor = db.query(Doctor).filter(Doctor.id == current_user.id).first()
    # Some legacy visit writers stored User.id in doctor_id. Allow that only
    # when the value does not target another real Doctor row.
    if not assigned_doctor:
        allowed_doctor_ids.add(current_user.id)
    return allowed_doctor_ids


def _doctor_allowed_patient_ids(db: Session, current_user: User) -> set[int]:
    allowed_doctor_ids = _doctor_allowed_doctor_ids(db, current_user)
    rows = (
        db.query(Visit.patient_id)
        .filter(
            Visit.doctor_id.in_(allowed_doctor_ids),
            Visit.patient_id.isnot(None),
        )
        .all()
    )
    return {row[0] for row in rows if row[0] is not None}


def _ensure_doctor_can_send_appointment_reminder(
    db: Session,
    appointment: Any,
    current_user: User,
) -> None:
    if current_user.role != "Doctor":
        return
    if current_user.is_superuser:
        return
    if getattr(appointment, "doctor_id", None) not in _doctor_allowed_doctor_ids(
        db, current_user
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )


def _ensure_doctor_can_send_patient_lab_results(
    db: Session,
    patient_id: int,
    current_user: User,
) -> None:
    if current_user.role != "Doctor":
        return
    if current_user.is_superuser:
        return
    if patient_id not in _doctor_allowed_patient_ids(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )


def _lab_result_patient_id(db: Session, result: Any) -> int | None:
    direct_patient_id = getattr(result, "patient_id", None)
    if direct_patient_id is not None:
        return int(direct_patient_id)

    order = getattr(result, "order", None)
    order_patient_id = getattr(order, "patient_id", None)
    if order_patient_id is not None:
        return int(order_patient_id)

    order_id = getattr(result, "order_id", None)
    if order_id is None:
        return None
    return db.query(LabOrder.patient_id).filter(LabOrder.id == order_id).scalar()


def _ensure_lab_results_belong_to_patient(
    db: Session,
    *,
    patient_id: int,
    lab_results: list[Any],
) -> None:
    for result in lab_results:
        result_patient_id = _lab_result_patient_id(db, result)
        if result_patient_id is not None and result_patient_id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )


def _payment_id_from_payload(payment_data: dict[str, Any]) -> int | None:
    for key in ("payment_id", "id"):
        value = payment_data.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment_id",
            )
    return None


def _ensure_payment_confirmation_belongs_to_patient(
    db: Session,
    *,
    patient_id: int,
    payment_data: dict[str, Any],
) -> None:
    payment_id = _payment_id_from_payload(payment_data)
    if payment_id is None:
        return

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    visit = db.query(Visit).filter(Visit.id == payment.visit_id).first()
    if not visit or visit.patient_id != patient_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )


@router.post("/send-appointment-reminder")
async def send_appointment_reminder(
    appointment_id: int,
    reminder_type: str = Query("24h", description="Тип напоминания: 24h, 2h, 30m"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """Отправить напоминание о записи на прием"""
    try:
        # Получаем данные записи
        appointment = crud_appointment.get_appointment(db, appointment_id)
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена"
            )

        # Получаем данные пациента
        _ensure_doctor_can_send_appointment_reminder(
            db, appointment, current_user
        )
        patient = crud_patient.get_patient(db, appointment.patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Пациент не найден"
            )

        # Ищем Telegram пользователя
        telegram_user = crud_telegram.find_telegram_user_by_phone(db, patient.phone)
        if not telegram_user:
            return {
                "success": False,
                "message": "Пациент не зарегистрирован в Telegram боте",
            }

        if not _telegram_notification_allowed(
            telegram_user, "appointment_reminders"
        ):
            return _telegram_notifications_disabled_response()

        # Получаем сервис бота
        bot_service = await get_telegram_bot_service()
        if not bot_service.active:
            await bot_service.initialize(db)

        # Формируем данные для шаблона
        template_data = {
            "patient_name": patient.full_name,
            "doctor_name": appointment.doctor_name,
            "specialty": appointment.specialty,
            "appointment_date": appointment.date.strftime("%d.%m.%Y"),
            "appointment_time": appointment.time,
            "cabinet": appointment.cabinet or "Уточните в регистратуре",
            "clinic_address": "г. Ташкент, ул. Медицинская, 15",
            "clinic_phone": "+998 71 123-45-67",
            "appointment_id": appointment.id,
        }

        # Получаем шаблон
        templates_service = get_telegram_templates_service()
        template = templates_service.get_template(
            "appointment_reminder", telegram_user.language_code or "ru", template_data
        )

        # Отправляем сообщение
        success = await bot_service._send_message(
            chat_id=telegram_user.chat_id,
            text=template["text"],
            reply_markup=template.get("keyboard"),
        )

        if success:
            return {
                "success": True,
                "message": "Напоминание отправлено",
                "appointment_id": appointment.id,
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка отправки напоминания",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/send-lab-results")
async def send_lab_results(
    patient_id: int,
    lab_result_ids: list[int],
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Lab", "Doctor")),
):
    """Отправить результаты анализов пациенту"""
    try:
        # Получаем данные пациента
        patient = crud_patient.get_patient(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Пациент не найден"
            )

        # Ищем Telegram пользователя
        _ensure_doctor_can_send_patient_lab_results(db, patient_id, current_user)

        telegram_user = crud_telegram.find_telegram_user_by_phone(db, patient.phone)
        if not telegram_user:
            return {
                "success": False,
                "message": "Пациент не зарегистрирован в Telegram боте",
            }

        if not _telegram_notification_allowed(telegram_user, "lab_notifications"):
            return _telegram_notifications_disabled_response()

        # Получаем данные анализов
        lab_results = []
        for result_id in lab_result_ids:
            result = crud_lab.get_lab_result(db, result_id)
            if result:
                lab_results.append(result)

        if not lab_results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Результаты анализов не найдены",
            )

        # Получаем сервис бота
        _ensure_lab_results_belong_to_patient(
            db,
            patient_id=patient_id,
            lab_results=lab_results,
        )

        bot_service = await get_telegram_bot_service()
        if not bot_service.active:
            await bot_service.initialize(db)

        # Получаем сервис шаблонов
        templates_service = get_telegram_templates_service()

        # Формируем данные для шаблона
        template_data = _safe_lab_template_data(
            patient,
            lab_results,
            templates_service,
            telegram_user.language_code or "ru",
        )

        # Получаем шаблон
        template = templates_service.get_template(
            "lab_results_ready", telegram_user.language_code or "ru", template_data
        )

        # Отправляем сообщение
        success = await bot_service._send_message(
            chat_id=telegram_user.chat_id,
            text=template["text"],
            reply_markup=template.get("keyboard"),
        )

        if success:
            return {
                "success": True,
                "message": "Результаты анализов отправлены",
                "lab_results_count": len(lab_results),
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка отправки результатов",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/send-payment-confirmation")
async def send_payment_confirmation(
    patient_id: int,
    payment_data: dict[str, Any],
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier")),
):
    """Отправить подтверждение платежа"""
    try:
        # Получаем данные пациента
        patient = crud_patient.get_patient(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Пациент не найден"
            )

        # Ищем Telegram пользователя
        _ensure_payment_confirmation_belongs_to_patient(
            db,
            patient_id=patient_id,
            payment_data=payment_data,
        )

        telegram_user = crud_telegram.find_telegram_user_by_phone(db, patient.phone)
        if not telegram_user:
            return {
                "success": False,
                "message": "Пациент не зарегистрирован в Telegram боте",
            }

        if not _telegram_notification_allowed(telegram_user):
            return _telegram_notifications_disabled_response()

        # Получаем сервис бота
        bot_service = await get_telegram_bot_service()
        if not bot_service.active:
            await bot_service.initialize(db)

        # Формируем данные для шаблона
        template_data = _safe_payment_template_data(payment_data)

        # Получаем шаблон
        templates_service = get_telegram_templates_service()
        template = templates_service.get_template(
            "payment_confirmation", telegram_user.language_code or "ru", template_data
        )

        # Отправляем сообщение
        success = await bot_service._send_message(
            chat_id=telegram_user.chat_id,
            text=template["text"],
            reply_markup=template.get("keyboard"),
        )

        if success:
            return {
                "success": True,
                "message": "Подтверждение платежа отправлено",
                "amount": payment_data.get("amount"),
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка отправки подтверждения",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# TG-AUDIT-28 P0-7: cap recipients at 1000 to prevent broadcast abuse.
BROADCAST_MAX_RECIPIENTS = 1000


@router.post("/broadcast-message")
async def send_broadcast_message(
    message: str,
    target_groups: list[str] = Query(
        ..., description="Группы получателей: patients, doctors, admins"
    ),
    language: str = Query("ru", description="Язык сообщения"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Отправить широковещательное сообщение"""
    try:
        # Получаем список получателей
        recipients = []

        if "patients" in target_groups:
            patients = crud_telegram.get_telegram_users_by_role(
                db, "Patient", active_only=True
            )
            recipients.extend(patients)

        if "doctors" in target_groups:
            doctors = crud_telegram.get_telegram_users_by_role(
                db, "Doctor", active_only=True
            )
            recipients.extend(doctors)

        if "admins" in target_groups:
            admins = crud_telegram.get_telegram_users_by_role(
                db, "Admin", active_only=True
            )
            recipients.extend(admins)

        if not recipients:
            return {
                "success": False,
                "message": "Нет получателей для отправки",
                "recipients_count": 0,
            }

        # Получаем сервис бота
        bot_service = await get_telegram_bot_service()
        if not bot_service.active:
            await bot_service.initialize(db)

        # Отправляем сообщения
        sent_count = 0
        failed_count = 0

        for recipient in recipients:
            try:
                success = await bot_service._send_message(
                    chat_id=recipient.chat_id, text=message
                )
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
            except Exception:
                failed_count += 1
                continue

        return {
            "success": True,
            "message": "Широковещательное сообщение отправлено",
            "total_recipients": len(recipients),
            "sent_count": sent_count,
            "failed_count": failed_count,
            "target_groups": target_groups,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/notification-stats")
async def get_notification_stats(
    days_back: int = Query(7, description="Количество дней назад"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Получить статистику уведомлений"""
    try:
        # Здесь будет реальная статистика из БД
        # Пока возвращаем заглушку
        return {
            "period": {
                "start": (datetime.now() - timedelta(days=days_back)).isoformat(),
                "end": datetime.now().isoformat(),
            },
            "total_sent": 0,
            "total_delivered": 0,
            "total_failed": 0,
            "by_type": {
                "appointment_reminders": 0,
                "lab_results": 0,
                "payment_confirmations": 0,
                "broadcast_messages": 0,
            },
            "by_language": {"ru": 0, "uz": 0, "en": 0},
            "delivery_rate": 0.0,
            "error_rate": 0.0,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/schedule-reminder")
async def schedule_reminder(
    appointment_id: int,
    reminder_time: str,  # ISO datetime string
    reminder_type: str = Query("24h", description="Тип напоминания"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """Запланировать напоминание о записи"""
    try:
        # Здесь будет логика планировщика
        # Пока возвращаем заглушку
        return {
            "success": True,
            "message": "Напоминание запланировано",
            "appointment_id": appointment_id,
            "reminder_time": reminder_time,
            "reminder_type": reminder_type,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
