"""
Расширенные API endpoints для Telegram уведомлений
Поддержка массовых рассылок, планировщика и аналитики
"""

from datetime import datetime, timedelta
from html import escape
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
from app.api.v1.endpoints.admin_telegram import PATIENT_PAYMENT_ENTRY_ROUTE
from app.core.config import settings
from app.core.i18n import t  # noqa: F401
from app.core.rate_limiter import limiter
from app.core.roles import DOCTOR_FAMILY_GATE_ROLES
from app.crud import (
    telegram_config as crud_telegram,
)
from app.models.lab import LabOrder, LabReportInstance
from app.models.payment import Payment
from app.models.telegram_config import TelegramConfig
from app.models.user import User
from app.models.visit import Visit
from app.schemas.notifications import PaymentData
from app.services.appointment_rsvp import make_appointment_callback
from app.services.lab_notification_scope import resolve_lab_notification
from app.services.notifications_pkg._helpers import _patient_telegram_event_message
from app.services.telegram_bot import get_telegram_bot_service
from app.services.telegram_delivery_authorization import (
    TelegramDeliveryError,
    _current_actor,
    _doctor_id,
    _link,
    _patient,
    _required_id,
    authorize_appointment,
)
from app.services.telegram_templates import get_telegram_templates_service

router = APIRouter()

PROTECTED_PAYMENT_HISTORY_PATH = PATIENT_PAYMENT_ENTRY_ROUTE
PROTECTED_PAYMENT_REFERENCE = "available-in-protected-account"

# Documentation of the existing patient-bound delivery error contract.
# The response model does not change the runtime status or delivery outcome.
_TELEGRAM_PATIENT_DELIVERY_ERRORS = {
    400: {"model": TelegramDeliveryError, "description": "Missing or ambiguous resource identifier"},
    403: {"model": TelegramDeliveryError, "description": "Staff role is not authorized"},
    404: {"model": TelegramDeliveryError, "description": "Recipient or resource is unavailable"},
    409: {"model": TelegramDeliveryError, "description": "The resource or recipient changed or is not eligible"},
    500: {"model": TelegramDeliveryError, "description": "Notification processing or report delivery failed"},
    502: {"model": TelegramDeliveryError, "description": "Telegram did not confirm delivery"},
    503: {"model": TelegramDeliveryError, "description": "Telegram is unavailable"},
}


def _telegram_notifications_disabled_response() -> dict[str, Any]:
    return {
        "success": False,
        "message": "Telegram notifications disabled by patient preference",
    }


def _linked_patient_chat(db: Session, patient_id: int, event_type: str):
    """An absent, revoked, opted-out, or non-private link is not deliverable."""
    try:
        return _link(db, patient_id, event_type)
    except HTTPException as exc:
        if exc.status_code == 404:
            return None
        raise


async def _fresh_bot(db: Session):
    from app.api.v1.endpoints.telegram_webhook._helpers import _ensure_bot_service_fresh

    service = await get_telegram_bot_service()
    await _ensure_bot_service_fresh(db, service)
    return service


def _require_active_bot(db: Session, service: Any) -> None:
    # The cached service can remain active after a different worker disables it.
    config = db.query(TelegramConfig).populate_existing().first()
    if not service.active or (config is not None and not config.active):
        raise HTTPException(status_code=503, detail="Telegram bot is unavailable")


def _report_access(db: Session, user: User, patient_id: int, instance: Any) -> None:
    """Check the report's own visit, not an unrelated visit of the patient."""
    actor = _current_actor(db, user, {"doctor", "lab"})
    _patient(db, patient_id)
    if instance.patient_id != patient_id:
        raise HTTPException(status_code=409, detail="Отчёт не принадлежит указанному пациенту")
    if instance.status not in LAB_REPORT_INSTANCE_NOTIFY_ALLOWED_STATUSES:
        raise HTTPException(status_code=409, detail="Only finalized reports can be sent to the patient")
    order = db.query(LabOrder).filter(LabOrder.id == instance.order_id).populate_existing().first() if instance.order_id else None
    if instance.order_id and (not order or (order.patient_id is not None and order.patient_id != patient_id)):
        raise HTTPException(status_code=403, detail="Access denied")
    if order and order.visit_id and instance.visit_id and order.visit_id != instance.visit_id:
        raise HTTPException(status_code=403, detail="Access denied")
    visit_id = instance.visit_id or (order.visit_id if order else None)
    visit = db.query(Visit).filter(Visit.id == visit_id).populate_existing().first() if visit_id else None
    if visit_id and (not visit or visit.patient_id != patient_id):
        raise HTTPException(status_code=403, detail="Access denied")
    doctor_id = _doctor_id(db, actor)
    if doctor_id is not None and (not visit or visit.doctor_id != doctor_id):
        raise HTTPException(status_code=403, detail="Access denied")


def _verified_payment(db: Session, user: User, patient_id: int, data: dict[str, Any]) -> Payment:
    _current_actor(db, user, {"cashier"})
    _patient(db, patient_id)
    payment_id = _required_id(data, ("payment_id", "id"))
    payment = db.query(Payment).filter(Payment.id == payment_id).populate_existing().first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    visit = db.query(Visit).filter(Visit.id == payment.visit_id).populate_existing().first()
    if not visit or visit.patient_id != patient_id:
        raise HTTPException(status_code=403, detail="Access denied")
    if (str(payment.status or "").lower() not in {"paid", "completed"}
            or (payment.refunded_amount is not None and payment.refunded_amount > 0)):
        raise HTTPException(status_code=409, detail="Payment is not eligible for confirmation")
    return payment


def _protected_frontend_url(path: str) -> str:
    base_url = str(
        getattr(settings, "FRONTEND_URL", None) or "http://localhost:5173"
    ).strip()
    normalized_base = base_url.rstrip("/") or "http://localhost:5173"
    normalized_path = f"/{str(path or '').strip().lstrip('/')}"
    return f"{normalized_base}{normalized_path}"


def _protected_payment_history_url() -> str:
    return _protected_frontend_url(PROTECTED_PAYMENT_HISTORY_PATH)


def _safe_payment_template_data(payment_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "amount": payment_data.get("amount", 0),
        "currency": payment_data.get("currency", "UZS"),
        "payment_method": payment_data.get("payment_method", "Карта"),
        "payment_date": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "transaction_id": PROTECTED_PAYMENT_REFERENCE,
        "receipt_link": _protected_payment_history_url(),
    }


@router.post("/send-appointment-reminder", response_model=dict[str, Any], responses=_TELEGRAM_PATIENT_DELIVERY_ERRORS)
async def send_appointment_reminder(
    appointment_id: int,
    reminder_type: str = Query("24h", description="Тип напоминания: 24h, 2h, 30m"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", *DOCTOR_FAMILY_GATE_ROLES)),
):
    """Send only to the current consenting, patient-linked private chat."""
    del reminder_type, background_tasks
    try:
        appointment, _, link = authorize_appointment(db, current_user, {"id": appointment_id})
        initial = (appointment.patient_id, appointment.occurrence_revision, link.id,
                   link.chat_id, link.patient_link_epoch)
        bot_service = await _fresh_bot(db)
        _require_active_bot(db, bot_service)
        appointment, _, link = authorize_appointment(
            db, current_user, {"id": appointment_id}, chat_id=initial[3]
        )
        if initial != (appointment.patient_id, appointment.occurrence_revision,
                       link.id, link.chat_id, link.patient_link_epoch):
            raise HTTPException(status_code=409, detail="Appointment changed; retry")
        callback = make_appointment_callback(
            "v", appointment.id, appointment.occurrence_revision,
            link.chat_id, link.id, link.patient_link_epoch,
        )
        # Authorization is refreshed immediately before dispatch; an external
        # send cannot be made atomic with a subsequent consent revocation.
        success = await bot_service._send_message(
            chat_id=link.chat_id,
            text="У вас новое уведомление. Откройте его в личном чате.",
            reply_markup={"inline_keyboard": [[{"text": "Просмотреть", "callback_data": callback}]]},
        )
        if not success:
            raise HTTPException(status_code=502, detail="Telegram delivery failed")
        return {"success": True, "message": "Напоминание отправлено", "appointment_id": appointment.id}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.post("/send-lab-results", response_model=dict[str, Any], responses=_TELEGRAM_PATIENT_DELIVERY_ERRORS)
async def send_lab_results(
    patient_id: int,
    lab_result_ids: list[int],
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Lab", *DOCTOR_FAMILY_GATE_ROLES)),
):
    """Notify only when every result belongs to the patient and is finalized.

    HTTP 200 with ``success: false`` means that no eligible chat was available.
    """
    del background_tasks
    try:
        if not lab_result_ids:
            raise HTTPException(status_code=400, detail="Lab result IDs are required")
        actor = _current_actor(db, current_user, {"doctor", "lab"})
        _patient(db, patient_id)
        for result_id in lab_result_ids:
            resolve_lab_notification(db, lab_result_id=result_id, patient_id=patient_id, current_user=actor)
        link = _linked_patient_chat(db, patient_id, "lab_results")
        if not link:
            return _telegram_notifications_disabled_response()
        identity = (link.id, link.chat_id, link.patient_link_epoch)
        bot_service = await _fresh_bot(db)
        _require_active_bot(db, bot_service)
        actor = _current_actor(db, current_user, {"doctor", "lab"})
        _patient(db, patient_id)
        for result_id in lab_result_ids:
            resolve_lab_notification(db, lab_result_id=result_id, patient_id=patient_id, current_user=actor)
        link = _link(db, patient_id, "lab_results", identity[1])
        if identity != (link.id, link.chat_id, link.patient_link_epoch):
            raise HTTPException(status_code=409, detail="Recipient changed; retry")
        message = _patient_telegram_event_message("lab_results", link.language_code)
        if not message:
            raise HTTPException(status_code=503, detail="Telegram notification is unavailable")
        if not await bot_service._send_message(chat_id=link.chat_id, text=message, reply_markup=None):
            raise HTTPException(status_code=502, detail="Telegram delivery failed")
        return {"success": True, "message": "Уведомление отправлено", "lab_results_count": len(lab_result_ids)}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error") from None


# LABN-FE-001 (audit 3886 round 10): the lab workbench «Отправить пациенту»
# action operates on a lab report INSTANCE (new lab-reporting module). The
# legacy /send-lab-results route serves legacy lab_result rows with a
# templated TEXT message and cannot accept an instance ID — the pre-fix
# frontend posted {patient_id, instance_id} JSON to it and was rejected 422
# at validation before any business logic. This dedicated route renders the
# same finalized-report PDF as GET /lab/report-instances/{id}/pdf and
# delivers it through the bot's sendDocument path. Patient binding, doctor
# scope and Telegram consent are enforced server-side.
LAB_REPORT_INSTANCE_NOTIFY_ALLOWED_STATUSES = {"FINALIZED", "PRINTED"}


class LabReportInstanceNotificationRequest(BaseModel):
    """Explicit body contract for the instance-scoped report notification.

    A wrong-shape request (e.g. the legacy field name ``instance_id`` or a
    legacy ``lab_result_ids`` list) fails Pydantic validation with a
    readable 422 instead of silently mapping unrelated ID spaces.
    """

    patient_id: int
    report_instance_id: int


@router.post(
    "/send-lab-report-instance", response_model=dict[str, Any],
    responses={code: response for code, response in _TELEGRAM_PATIENT_DELIVERY_ERRORS.items() if code != 502},
)
async def send_lab_report_instance_notification(
    payload: LabReportInstanceNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Lab", *DOCTOR_FAMILY_GATE_ROLES)),
):
    """Отправить финализированный лабораторный бланк пациенту в Telegram (PDF).

    Семантика статусов зеркалит legacy /send-lab-results: 200 +
    ``{"success": false, "message": ...}`` означает, что пациент
    НЕ получил отправку (не связан с ботом или отключил уведомления) —
    фронтенд обязан показывать это как неудачу (LABN-FE-002), а не как
    «отправлено».
    """
    from app.services.lab_report_pdf._context import build_report_pdf_context
    from app.services.lab_report_pdf_service import lab_report_pdf_service
    from app.services.lab_reporting import LabReportingDomainError, LabReportingService

    try:
        _current_actor(db, current_user, {"doctor", "lab"})
        _patient(db, payload.patient_id)
        service = LabReportingService(db)
        try:
            instance = service.get_instance(payload.report_instance_id)
        except LabReportingDomainError as exc:
            raise HTTPException(
                status_code=exc.status_code, detail=exc.detail
            ) from exc

        _report_access(db, current_user, payload.patient_id, instance)
        telegram_user = _linked_patient_chat(db, payload.patient_id, "lab_results")
        if not telegram_user:
            return _telegram_notifications_disabled_response()
        link_identity = (telegram_user.id, telegram_user.chat_id, telegram_user.patient_link_epoch)
        report_identity = (instance.id, instance.patient_id, instance.visit_id,
                           instance.order_id, instance.status, instance.updated_at)

        pdf_bytes = lab_report_pdf_service.render_report(
            build_report_pdf_context(service, instance)
        )

        bot_service = await _fresh_bot(db)
        _require_active_bot(db, bot_service)
        # Re-read both authorization and report state after awaited setup.
        instance = db.query(LabReportInstance).filter(
            LabReportInstance.id == payload.report_instance_id
        ).populate_existing().first()
        if not instance:
            raise HTTPException(status_code=404, detail="Report not found")
        _report_access(db, current_user, payload.patient_id, instance)
        if report_identity != (instance.id, instance.patient_id, instance.visit_id,
                               instance.order_id, instance.status, instance.updated_at):
            raise HTTPException(status_code=409, detail="Report changed; retry")
        telegram_user = _link(db, payload.patient_id, "lab_results", link_identity[1])
        if link_identity != (telegram_user.id, telegram_user.chat_id, telegram_user.patient_link_epoch):
            raise HTTPException(status_code=409, detail="Recipient changed; retry")

        filename = f"lab-report-{instance.id}.pdf"
        # Caption intentionally empty: the PDF itself is the payload and
        # carries the full report; no patient metadata is duplicated in
        # the message text and nothing is logged.
        sent, _message_id, _send_error = await bot_service._send_document(
            chat_id=telegram_user.chat_id,
            filename=filename,
            document_bytes=pdf_bytes,
        )

        if not sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка отправки отчёта",
            )

        return {
            "success": True,
            "message": "Отчёт отправлен пациенту",
            "report_instance_id": payload.report_instance_id,
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/send-payment-confirmation", response_model=dict[str, Any], responses=_TELEGRAM_PATIENT_DELIVERY_ERRORS)
async def send_payment_confirmation(
    patient_id: int,
    payment_data: PaymentData,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier")),
):
    """Use a verified paid record; caller-supplied amounts are ignored.

    HTTP 200 with ``success: false`` means that no eligible chat was available.
    """
    del background_tasks
    try:
        supplied = payment_data.model_dump(exclude_none=True)
        payment = _verified_payment(db, current_user, patient_id, supplied)
        link = _linked_patient_chat(db, patient_id, "payment_paid")
        if not link:
            return _telegram_notifications_disabled_response()
        identity = (link.id, link.chat_id, link.patient_link_epoch)
        snapshot = (payment.id, payment.visit_id, payment.status, payment.amount,
                    payment.currency, payment.method, payment.paid_at, payment.refunded_amount)
        bot_service = await _fresh_bot(db)
        _require_active_bot(db, bot_service)
        payment = _verified_payment(db, current_user, patient_id, supplied)
        if snapshot != (payment.id, payment.visit_id, payment.status, payment.amount,
                        payment.currency, payment.method, payment.paid_at, payment.refunded_amount):
            raise HTTPException(status_code=409, detail="Payment changed; retry")
        link = _link(db, patient_id, "payment_paid", identity[1])
        if identity != (link.id, link.chat_id, link.patient_link_epoch):
            raise HTTPException(status_code=409, detail="Recipient changed; retry")
        # Use a server-owned template and exact DB amount; never caller-provided
        # payment details, raw provider IDs, or URLs.
        data = _safe_payment_template_data({
            "amount": f"{payment.amount:.2f}",
            "currency": escape(str(payment.currency or "UZS")),
            "payment_method": escape(str(payment.method or "")),
        })
        data["payment_date"] = payment.paid_at.strftime("%d.%m.%Y %H:%M") if payment.paid_at else "—"
        template = get_telegram_templates_service().get_template(
            "payment_confirmation", link.language_code or "ru", data
        )
        if not await bot_service._send_message(
            chat_id=link.chat_id, text=template["text"], reply_markup=template.get("keyboard")
        ):
            raise HTTPException(status_code=502, detail="Telegram delivery failed")
        return {"success": True, "message": "Подтверждение платежа отправлено"}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error") from None


# TG-AUDIT-28 P0-7: cap recipients at 1000 to prevent broadcast abuse.
BROADCAST_MAX_RECIPIENTS = 1000


@router.post("/broadcast-message", response_model=dict[str, Any])
@limiter.limit("1/5minute")
async def send_broadcast_message(
    request: Request,
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
        # PR-2 (round 9): cross-process rotation/revocation visibility.
        from app.api.v1.endpoints.telegram_webhook._helpers import (
            _ensure_bot_service_fresh,
        )

        await _ensure_bot_service_fresh(db, bot_service)

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

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/notification-stats", response_model=dict[str, Any])
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

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/schedule-reminder", response_model=dict[str, Any])
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

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
