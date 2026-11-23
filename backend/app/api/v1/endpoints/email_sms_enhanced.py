"""
Расширенные API endpoints для Email и SMS уведомлений
Поддержка массовых рассылок, шаблонов и аналитики

P0-6 FIX (ENDPOINT-VALIDATION-AUDIT):
Previously these endpoints accepted `template_data: dict[str, Any] | None`,
`payment_data: dict[str, Any]`, and `recipients: list[dict[str, Any]]`
with no validation. Replaced with typed Pydantic request models from
app.schemas.notifications. Endpoints that previously took individual
query params now take a single Pydantic body model.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.core.rate_limiter import limiter
from app.core.roles import is_doctor_role_spelling, normalize_role_value
from app.crud import appointment as crud_appointment
from app.crud import patient as crud_patient
from app.models.clinic import Doctor
from app.models.payment import Payment
from app.models.user import User
from app.models.visit import Visit
from app.schemas.notifications import (
    PaymentData,
    SendBulkEmailRequest,
    SendBulkSmsRequest,
    SendCustomEmailRequest,
    SendCustomSmsRequest,
    TemplateDataBase,
)
from app.services.email_sms_enhanced import get_email_sms_enhanced_service
from app.services.lab_notification_scope import resolve_lab_notification

router = APIRouter()


class NotificationDeliveryError(BaseModel):
    detail: str


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

    # The FK in Appointment/Visit references Doctor.id, never User.id.
    return {doctor.id}


def _ensure_doctor_can_send_appointment_reminder(
    db: Session,
    appointment: Any,
    current_user: User,
) -> None:
    if not is_doctor_role_spelling(current_user.role):
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


def _payment_id_from_payload(payment_data: dict[str, Any]) -> int | None:
    found = []
    for key in ("payment_id", "id"):
        value = payment_data.get(key)
        if value is None:
            continue
        try:
            found.append(int(value))
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment_id",
            )
    if len(set(found)) > 1:
        raise HTTPException(status_code=400, detail="Conflicting payment IDs")
    return found[0] if found else None


def _ensure_payment_confirmation_belongs_to_patient(
    db: Session,
    *,
    patient_id: int,
    payment_data: dict[str, Any],
) -> Payment:
    payment_id = _payment_id_from_payload(payment_data)
    if payment_id is None:
        raise HTTPException(status_code=400, detail="Payment ID is required")

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
    if payment.status.lower() not in {"paid", "completed"}:
        raise HTTPException(status_code=409, detail="Payment is not paid")
    if payment.refunded_amount is not None and payment.refunded_amount > 0:
        raise HTTPException(status_code=409, detail="Payment has been refunded")
    return payment


def _deny_unscoped_doctor(current_user: User) -> None:
    """Free-form destinations cannot prove a doctor's patient assignment."""
    if not getattr(current_user, "is_superuser", False) and is_doctor_role_spelling(
        current_user.role
    ):
        raise HTTPException(status_code=403, detail="Access denied")


def _delivery_response(result: dict[str, Any], delivered: str) -> dict[str, Any]:
    success = result.get("success") is True
    channel_results = result.get("channels") or {}
    any_delivered = any(
        isinstance(channel, dict) and channel.get("success") is True
        for channel in channel_results.values()
    )
    failure_message = (
        "Уведомление доставлено не по всем выбранным каналам"
        if any_delivered else "Не удалось отправить уведомление"
    )
    return {
        "success": success,
        "message": delivered if success else failure_message,
        "details": result,
    }


def _delivery_guard(
    db: Session,
    *,
    current_user: User,
    patient_data: dict[str, Any],
    resource_is_current: Callable[[User], bool],
) -> Callable[[str], bool]:
    """Freshly recheck actor, destination and resource before each send.

    This is a best-effort last check, not an atomic guarantee across a network
    provider call. No database lock is held while awaiting the provider.
    """
    actor_id = current_user.id
    role = normalize_role_value(current_user.role)
    superuser = bool(current_user.is_superuser)
    patient_id = patient_data['id']

    def allow(channel: str) -> bool:
        try:
            db.expire_all()
            actor = db.query(User).filter(User.id == actor_id).populate_existing().first()
            if (
                not actor or not actor.is_active
                or normalize_role_value(actor.role) != role
                or bool(actor.is_superuser) != superuser
            ):
                return False
            patient = crud_patient.get(db, id=patient_id)
            contact = 'email' if channel == 'email' else 'phone'
            if (
                not patient
                or getattr(patient, contact) != patient_data.get(contact)
                or patient.full_name != patient_data.get('full_name')
            ):
                return False
            return resource_is_current(actor)
        except Exception:
            # The API has made no DB writes; rollback releases any failed
            # read transaction and prevents sending when the check is unknown.
            db.rollback()
            return False

    return allow


def _appointment_notification_data(db: Session, appointment: Any) -> dict[str, Any]:
    if (appointment.status or '').lower() not in {
        'scheduled', 'pending', 'paid', 'confirmed'
    }:
        raise HTTPException(status_code=409, detail="Запись не ожидает напоминания")
    doctor = (
        db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()
        if appointment.doctor_id else None
    )
    return {
        'id': appointment.id,
        'doctor_name': (doctor.user.full_name if doctor and doctor.user else None) or 'Врач',
        'specialty': (doctor.specialty if doctor else None) or 'Специалист',
        'date': appointment.appointment_date.strftime('%d.%m.%Y'),
        'time': appointment.appointment_time or '',
        'cabinet': (doctor.cabinet if doctor else None) or 'Уточните в регистратуре',
    }


def _lab_notification_data(result: Any, order: Any) -> dict[str, Any]:
    return {
        'id': result.id,
        'test_type': result.test_name,
        'collection_date': order.created_at.strftime('%d.%m.%Y') if order.created_at else '',
        'has_abnormalities': bool(result.abnormal),
    }


def _payment_notification_data(payment: Payment) -> dict[str, Any]:
    return {
        'id': payment.id,
        'amount': payment.amount,
        'currency': payment.currency,
        'payment_method': payment.method,
        'payment_date': payment.paid_at.strftime('%d.%m.%Y %H:%M') if payment.paid_at else '',
        'transaction_id': payment.receipt_no or '',
    }


@router.post(
    "/send-appointment-reminder-enhanced", response_model=dict[str, Any],
    responses={
        403: {"model": NotificationDeliveryError, "description": "Visit is not assigned to the doctor"},
        404: {"model": NotificationDeliveryError, "description": "Appointment or patient not found"},
        409: {"model": NotificationDeliveryError, "description": "Appointment is not eligible for a reminder"},
        500: {"model": NotificationDeliveryError, "description": "Notification processing failed"},
    },
)
async def send_appointment_reminder_enhanced(
    appointment_id: int,
    channels: list[str] = Query(["email", "sms"], description="Каналы отправки"),
    template_data: TemplateDataBase | None = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """Расширенное напоминание о записи.

    HTTP 200 reports the attempt. Check ``success`` and per-channel details;
    missing contacts, unsupported channels and provider failures are not sent.

    ``template_data`` is accepted for compatibility but ignored; resource
    notification content comes from the database.
    """
    try:
        # Получаем данные записи
        appointment = crud_appointment.get(db, appointment_id)
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена"
            )

        # Получаем данные пациента
        _ensure_doctor_can_send_appointment_reminder(
            db, appointment, current_user
        )
        patient = crud_patient.get(db, id=appointment.patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Пациент не найден"
            )

        # Подготавливаем данные
        patient_data = {
            'id': patient.id,
            'full_name': patient.full_name
            or f"{patient.first_name} {patient.last_name}",
            'phone': patient.phone,
            'email': patient.email,
        }

        appointment_data = _appointment_notification_data(db, appointment)
        doctor_id = appointment.doctor_id
        def appointment_current(actor: User) -> bool:
            refreshed = crud_appointment.get(db, appointment_id)
            if not refreshed or refreshed.patient_id != patient_data['id'] or refreshed.doctor_id != doctor_id:
                return False
            _ensure_doctor_can_send_appointment_reminder(db, refreshed, actor)
            return _appointment_notification_data(db, refreshed) == appointment_data

        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Отправляем уведомление
        result = await service.send_appointment_reminder_enhanced(
            patient_data=patient_data,
            appointment_data=appointment_data,
            channels=channels,
            template_data=template_data.model_dump(exclude_none=True) if template_data else None,
            delivery_guard=_delivery_guard(
                db, current_user=current_user, patient_data=patient_data,
                resource_is_current=appointment_current,
            ),
        )

        return _delivery_response(result, "Напоминание отправлено")

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/send-lab-results-enhanced", response_model=dict[str, Any],
    responses={
        403: {"model": NotificationDeliveryError, "description": "Result is not assigned to the requested patient or doctor"},
        404: {"model": NotificationDeliveryError, "description": "Patient or result not found"},
        409: {"model": NotificationDeliveryError, "description": "Lab result is not ready"},
        500: {"model": NotificationDeliveryError, "description": "Notification processing failed"},
    },
)
async def send_lab_results_enhanced(
    patient_id: int,
    lab_results_id: int,
    channels: list[str] = Query(["email", "sms"], description="Каналы отправки"),
    template_data: TemplateDataBase | None = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Lab", "Doctor")),
):
    """Расширенная отправка результатов анализов.

    HTTP 200 reports the attempt; ``success`` is false unless every requested
    channel has an available contact and reports successful delivery.

    ``template_data`` is accepted for compatibility but ignored; resource
    notification content comes from the database.
    """
    try:
        # Получаем данные пациента
        patient = crud_patient.get(db, id=patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Пациент не найден"
            )

        lab_result, order, _ = resolve_lab_notification(
            db, lab_result_id=lab_results_id, patient_id=patient_id,
            current_user=current_user,
        )
        lab_data = _lab_notification_data(lab_result, order)

        # Подготавливаем данные
        patient_data = {
            'id': patient.id,
            'full_name': patient.full_name
            or f"{patient.first_name} {patient.last_name}",
            'phone': patient.phone,
            'email': patient.email,
        }
        def lab_current(actor: User) -> bool:
            refreshed_result, refreshed_order, _ = resolve_lab_notification(
                db, lab_result_id=lab_results_id, patient_id=patient_id,
                current_user=actor,
            )
            return _lab_notification_data(refreshed_result, refreshed_order) == lab_data

        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Отправляем уведомление
        result = await service.send_lab_results_enhanced(
            patient_data=patient_data,
            lab_data=lab_data,
            channels=channels,
            template_data=template_data.model_dump(exclude_none=True) if template_data else None,
            delivery_guard=_delivery_guard(
                db, current_user=current_user, patient_data=patient_data,
                resource_is_current=lab_current,
            ),
        )

        return _delivery_response(result, "Результаты анализов отправлены")

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/send-payment-confirmation-enhanced", response_model=dict[str, Any],
    responses={
        400: {"model": NotificationDeliveryError, "description": "Missing or conflicting payment ID"},
        403: {"model": NotificationDeliveryError, "description": "Payment belongs to another patient"},
        404: {"model": NotificationDeliveryError, "description": "Patient or payment not found"},
        409: {"model": NotificationDeliveryError, "description": "Payment is not paid"},
        500: {"model": NotificationDeliveryError, "description": "Notification processing failed"},
    },
)
async def send_payment_confirmation_enhanced(
    patient_id: int,
    payment_data: PaymentData,
    channels: list[str] = Query(["email", "sms"], description="Каналы отправки"),
    template_data: TemplateDataBase | None = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier")),
):
    """Расширенное подтверждение платежа.

    A payment ID is required. Amount, currency, method and receipt details
    are loaded from the matching paid payment, not from the request body.
    HTTP 200 reports the attempt; inspect ``success`` and per-channel details.
    ``template_data`` is accepted for compatibility but ignored.
    """
    try:
        # Получаем данные пациента
        patient = crud_patient.get(db, id=patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Пациент не найден"
            )

        # Подготавливаем данные
        payment = _ensure_payment_confirmation_belongs_to_patient(
            db,
            patient_id=patient_id,
            payment_data=payment_data.model_dump(),
        )
        payment_data_snapshot = _payment_notification_data(payment)
        payment_id = payment.id
        def payment_current(_actor: User) -> bool:
            refreshed = _ensure_payment_confirmation_belongs_to_patient(
                db, patient_id=patient_id, payment_data={'payment_id': payment_id}
            )
            return _payment_notification_data(refreshed) == payment_data_snapshot

        patient_data = {
            'id': patient.id,
            'full_name': patient.full_name
            or f"{patient.first_name} {patient.last_name}",
            'phone': patient.phone,
            'email': patient.email,
        }

        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Отправляем уведомление
        result = await service.send_payment_confirmation_enhanced(
            patient_data=patient_data,
            payment_data=payment_data_snapshot,
            channels=channels,
            template_data=template_data.model_dump(exclude_none=True) if template_data else None,
            delivery_guard=_delivery_guard(
                db, current_user=current_user, patient_data=patient_data,
                resource_is_current=payment_current,
            ),
        )

        return _delivery_response(result, "Подтверждение платежа отправлено")

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/send-bulk-email", response_model=dict[str, Any])
@limiter.limit("1/5minute")
async def send_bulk_email(
    request: Request,
    body: SendBulkEmailRequest,
    batch_size: int = Query(50, description="Размер батча"),
    delay_between_batches: float = Query(
        1.0, description="Задержка между батчами (сек)"
    ),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Массовая отправка email"""
    try:
        recipients = [r.model_dump(exclude_none=True) for r in body.recipients]
        # Validation already done by Pydantic (min 1, max 1000 recipients)

        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Отправляем массовую рассылку
        result = await service.send_bulk_email(
            recipients=recipients,
            subject=body.subject,
            template_name=body.template_name,
            template_data=body.template_data.model_dump(exclude_none=True) if body.template_data else None,
            html_content=body.html_content,
            text_content=body.text_content,
            batch_size=batch_size,
            delay_between_batches=delay_between_batches,
        )

        return {
            "success": True,
            "message": "Массовая рассылка email запущена",
            "details": result,
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/send-bulk-sms", response_model=dict[str, Any])
@limiter.limit("1/5minute")
async def send_bulk_sms(
    request: Request,
    body: SendBulkSmsRequest,
    batch_size: int = Query(100, description="Размер батча"),
    delay_between_batches: float = Query(
        0.5, description="Задержка между батчами (сек)"
    ),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Массовая отправка SMS"""
    try:
        recipients = [r.model_dump(exclude_none=True) for r in body.recipients]
        # Validation already done by Pydantic

        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Отправляем массовую рассылку
        result = await service.send_bulk_sms(
            recipients=recipients,
            message=body.message,
            template_name=body.template_name,
            template_data=body.template_data.model_dump(exclude_none=True) if body.template_data else None,
            batch_size=batch_size,
            delay_between_batches=delay_between_batches,
        )

        return {
            "success": True,
            "message": "Массовая рассылка SMS запущена",
            "details": result,
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/send-custom-email", response_model=dict[str, Any],
    responses={403: {"model": NotificationDeliveryError, "description": "Unscoped doctor destination is forbidden"}},
)
async def send_custom_email(
    body: SendCustomEmailRequest,
    priority: str = Query("normal", description="Приоритет: normal, high"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """Отправка кастомного email"""
    _deny_unscoped_doctor(current_user)
    try:
        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Отправляем email
        success, message = await service.send_email_enhanced(
            to_email=str(body.to_email),
            subject=body.subject,
            template_name=body.template_name,
            template_data=body.template_data.model_dump(exclude_none=True) if body.template_data else None,
            html_content=body.html_content,
            text_content=body.text_content,
            attachments=body.attachments,
            priority=priority,
        )

        return {
            "success": success,
            "message": message,
            "to_email": str(body.to_email),
            "subject": body.subject,
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post(
    "/send-custom-sms", response_model=dict[str, Any],
    responses={403: {"model": NotificationDeliveryError, "description": "Unscoped doctor destination is forbidden"}},
)
async def send_custom_sms(
    body: SendCustomSmsRequest,
    priority: str = Query("normal", description="Приоритет: normal, high"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """Отправка кастомного SMS"""
    _deny_unscoped_doctor(current_user)
    try:
        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Отправляем SMS
        success, message = await service.send_sms_enhanced(
            phone=body.phone,
            message=body.message,
            template_name=body.template_name,
            template_data=body.template_data.model_dump(exclude_none=True) if body.template_data else None,
            sender=body.sender,
            priority=priority,
        )

        return {"success": success, "message": message, "phone": body.phone}

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/statistics", response_model=dict[str, Any])
async def get_email_sms_statistics(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """Получить статистику Email/SMS отправки"""
    try:
        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Получаем статистику
        stats = service.get_statistics()

        return {
            "success": True,
            "statistics": stats,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/reset-statistics", response_model=dict[str, Any])
async def reset_email_sms_statistics(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
):
    """Сбросить статистику Email/SMS отправки"""
    try:
        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Сбрасываем статистику
        service.reset_statistics()

        return {
            "success": True,
            "message": "Статистика сброшена",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/templates", response_model=dict[str, Any])
async def get_available_templates(    limit: int = Query(default=100, ge=1, le=500, description="Количество записей"),
    offset: int = Query(default=0, ge=0, description="Смещение"),
template_type: str = Query("all", description="Тип шаблона: email, sms, all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """Получить список доступных шаблонов"""
    try:
        # Здесь должна быть логика получения шаблонов из БД или файловой системы
        # Пока возвращаем заглушку
        templates = {
            "email": [
                {
                    "name": "appointment_reminder",
                    "title": "Напоминание о записи",
                    "description": "Шаблон для напоминания о записи к врачу",
                    "variables": [
                        "patient_name",
                        "doctor_name",
                        "appointment_date",
                        "appointment_time",
                    ],
                },
                {
                    "name": "lab_results_ready",
                    "title": "Результаты анализов готовы",
                    "description": "Шаблон для уведомления о готовности результатов",
                    "variables": [
                        "patient_name",
                        "test_type",
                        "ready_date",
                        "download_link",
                    ],
                },
                {
                    "name": "payment_confirmation",
                    "title": "Подтверждение платежа",
                    "description": "Шаблон для подтверждения оплаты",
                    "variables": ["patient_name", "amount", "currency", "payment_date"],
                },
            ],
            "sms": [
                {
                    "name": "appointment_reminder_sms",
                    "title": "Напоминание о записи (SMS)",
                    "description": "Краткий шаблон для SMS напоминания",
                    "variables": [
                        "patient_name",
                        "doctor_name",
                        "appointment_date",
                        "appointment_time",
                    ],
                },
                {
                    "name": "lab_results_ready_sms",
                    "title": "Результаты анализов готовы (SMS)",
                    "description": "Краткий шаблон для SMS уведомления",
                    "variables": ["patient_name", "test_type", "ready_date"],
                },
                {
                    "name": "payment_confirmation_sms",
                    "title": "Подтверждение платежа (SMS)",
                    "description": "Краткий шаблон для SMS подтверждения",
                    "variables": ["patient_name", "amount", "currency"],
                },
            ],
        }

        if template_type == "all":
            return {"success": True, "templates": templates}
        elif template_type in templates:
            return {
                "success": True,
                "templates": {template_type: templates[template_type]},
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный тип шаблона"
            )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/test-email", response_model=dict[str, Any])
async def test_email_sending(
    to_email: str,
    subject: str = "Тестовое письмо",
    message: str = "Это тестовое письмо от Programma Clinic",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Тестирование отправки email"""
    try:
        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Отправляем тестовый email
        success, result_message = await service.send_email_enhanced(
            to_email=to_email,
            subject=subject,
            html_content=f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <title>Тестовое письмо</title>
            </head>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2c5aa0;">Programma Clinic - Тестовое письмо</h2>
                    <p>{message}</p>
                    <p>Время отправки: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
                    <hr style="margin: 20px 0;">
                    <p style="font-size: 12px; color: #666;">
                        Programma Clinic<br>
                        г. Ташкент, ул. Медицинская, 15<br>
                        Телефон: +998 71 123-45-67
                    </p>
                </div>
            </body>
            </html>
            """,
            text_content=f"Programma Clinic - Тестовое письмо\n\n{message}\n\nВремя отправки: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
        )

        return {
            "success": success,
            "message": result_message,
            "to_email": to_email,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/test-sms", response_model=dict[str, Any])
async def test_sms_sending(
    phone: str,
    message: str = "Тестовое SMS от Programma Clinic",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Тестирование отправки SMS"""
    try:
        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Отправляем тестовое SMS
        success, result_message = await service.send_sms_enhanced(
            phone=phone,
            message=f"{message} - {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
        )

        return {
            "success": success,
            "message": result_message,
            "phone": phone,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
