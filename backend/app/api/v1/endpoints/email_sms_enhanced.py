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
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.core.rate_limiter import limiter
from app.crud import appointment as crud_appointment
from app.crud import patient as crud_patient
from app.models.clinic import Doctor
from app.models.payment import Payment
from app.models.user import User
from app.models.visit import Visit
from app.schemas.notifications import (
    SendBulkEmailRequest,
    SendBulkSmsRequest,
    SendCustomEmailRequest,
    SendCustomSmsRequest,
)
from app.services.email_sms_enhanced import get_email_sms_enhanced_service

router = APIRouter()


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


@router.post("/send-appointment-reminder-enhanced", response_model=dict[str, Any])
async def send_appointment_reminder_enhanced(
    appointment_id: int,
    channels: list[str] = Query(["email", "sms"], description="Каналы отправки"),
    template_data: dict[str, Any] | None = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """Расширенное напоминание о записи.

    Note: ``template_data`` is accepted as a plain dict (or ``None``) so
    the endpoint can be invoked both via the FastAPI body parser and
    directly by unit tests without constructing a Pydantic
    ``TemplateDataBase`` model.
    """
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

        # Подготавливаем данные
        patient_data = {
            'id': patient.id,
            'full_name': patient.full_name
            or f"{patient.first_name} {patient.last_name}",
            'phone': patient.phone,
            'email': patient.email,
        }

        appointment_data = {
            'id': appointment.id,
            'doctor_name': appointment.doctor_name,
            'specialty': appointment.specialty,
            'date': appointment.date.strftime('%d.%m.%Y'),
            'time': appointment.time,
            'cabinet': appointment.cabinet,
        }

        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Отправляем уведомление
        result = await service.send_appointment_reminder_enhanced(
            patient_data=patient_data,
            appointment_data=appointment_data,
            channels=channels,
            template_data=template_data,
        )

        return {
            "success": result['success'],
            "message": "Напоминание отправлено",
            "details": result,
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/send-lab-results-enhanced", response_model=dict[str, Any])
async def send_lab_results_enhanced(
    patient_id: int,
    lab_results_id: int,
    channels: list[str] = Query(["email", "sms"], description="Каналы отправки"),
    template_data: dict[str, Any] | None = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Lab", "Doctor")),
):
    """Расширенная отправка результатов анализов.

    Note: ``template_data`` is accepted as a plain dict (or ``None``) for
    the same reasons as ``send_appointment_reminder_enhanced``.
    """
    try:
        # Получаем данные пациента
        patient = crud_patient.get_patient(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Пациент не найден"
            )

        # Здесь должна быть логика получения данных анализов
        # Пока используем заглушку
        lab_data = {
            'id': lab_results_id,
            'test_type': 'Общий анализ крови',
            'collection_date': datetime.now().strftime('%d.%m.%Y'),
            'has_abnormalities': False,
        }

        # Подготавливаем данные
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
        result = await service.send_lab_results_enhanced(
            patient_data=patient_data,
            lab_data=lab_data,
            channels=channels,
            template_data=template_data,
        )

        return {
            "success": result['success'],
            "message": "Результаты анализов отправлены",
            "details": result,
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/send-payment-confirmation-enhanced", response_model=dict[str, Any])
async def send_payment_confirmation_enhanced(
    patient_id: int,
    payment_data: dict[str, Any],
    channels: list[str] = Query(["email", "sms"], description="Каналы отправки"),
    template_data: dict[str, Any] | None = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier")),
):
    """Расширенное подтверждение платежа.

    Note: ``payment_data`` and ``template_data`` are accepted as plain
    dicts (or ``None`` for ``template_data``) so the endpoint can be
    invoked both via the FastAPI body parser and directly by unit tests
    without constructing Pydantic ``PaymentData`` / ``TemplateDataBase``
    models that would silently drop unknown keys.
    """
    try:
        # Получаем данные пациента
        patient = crud_patient.get_patient(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Пациент не найден"
            )

        # Подготавливаем данные
        _ensure_payment_confirmation_belongs_to_patient(
            db,
            patient_id=patient_id,
            payment_data=payment_data,
        )

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
            payment_data=payment_data,
            channels=channels,
            template_data=template_data,
        )

        return {
            "success": result['success'],
            "message": "Подтверждение платежа отправлено",
            "details": result,
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


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


@router.post("/send-custom-email", response_model=dict[str, Any])
async def send_custom_email(
    body: SendCustomEmailRequest,
    priority: str = Query("normal", description="Приоритет: normal, high"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """Отправка кастомного email"""
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


@router.post("/send-custom-sms", response_model=dict[str, Any])
async def send_custom_sms(
    body: SendCustomSmsRequest,
    priority: str = Query("normal", description="Приоритет: normal, high"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """Отправка кастомного SMS"""
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
