"""
Расширенные API endpoints для Email и SMS уведомлений
Поддержка массовых рассылок, шаблонов и аналитики
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles, get_current_user
from app.models.user import User
from app.services.email_sms_enhanced import get_email_sms_enhanced_service
from app.crud import patient as crud_patient
from app.crud import appointment as crud_appointment

router = APIRouter()


@router.post("/send-appointment-reminder-enhanced")
async def send_appointment_reminder_enhanced(
    appointment_id: int,
    channels: List[str] = Query(["email", "sms"], description="Каналы отправки"),
    template_data: Optional[Dict[str, Any]] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor"))
):
    """Расширенное напоминание о записи"""
    try:
        # Получаем данные записи
        appointment = crud_appointment.get_appointment(db, appointment_id)
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись не найдена"
            )

        # Получаем данные пациента
        patient = crud_patient.get_patient(db, appointment.patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пациент не найден"
            )

        # Подготавливаем данные
        patient_data = {
            'id': patient.id,
            'full_name': patient.full_name or f"{patient.first_name} {patient.last_name}",
            'phone': patient.phone,
            'email': patient.email
        }

        appointment_data = {
            'id': appointment.id,
            'doctor_name': appointment.doctor_name,
            'specialty': appointment.specialty,
            'date': appointment.date.strftime('%d.%m.%Y'),
            'time': appointment.time,
            'cabinet': appointment.cabinet
        }

        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Отправляем уведомление
        result = await service.send_appointment_reminder_enhanced(
            patient_data=patient_data,
            appointment_data=appointment_data,
            channels=channels,
            template_data=template_data
        )

        return {
            "success": result['success'],
            "message": "Напоминание отправлено",
            "details": result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки напоминания: {str(e)}"
        )


@router.post("/send-lab-results-enhanced")
async def send_lab_results_enhanced(
    patient_id: int,
    lab_results_id: int,
    channels: List[str] = Query(["email", "sms"], description="Каналы отправки"),
    template_data: Optional[Dict[str, Any]] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Lab", "Doctor"))
):
    """Расширенная отправка результатов анализов"""
    try:
        # Получаем данные пациента
        patient = crud_patient.get_patient(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пациент не найден"
            )

        # Здесь должна быть логика получения данных анализов
        # Пока используем заглушку
        lab_data = {
            'id': lab_results_id,
            'test_type': 'Общий анализ крови',
            'collection_date': datetime.now().strftime('%d.%m.%Y'),
            'has_abnormalities': False
        }

        # Подготавливаем данные
        patient_data = {
            'id': patient.id,
            'full_name': patient.full_name or f"{patient.first_name} {patient.last_name}",
            'phone': patient.phone,
            'email': patient.email
        }

        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Отправляем уведомление
        result = await service.send_lab_results_enhanced(
            patient_data=patient_data,
            lab_data=lab_data,
            channels=channels,
            template_data=template_data
        )

        return {
            "success": result['success'],
            "message": "Результаты анализов отправлены",
            "details": result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки результатов: {str(e)}"
        )


@router.post("/send-payment-confirmation-enhanced")
async def send_payment_confirmation_enhanced(
    patient_id: int,
    payment_data: Dict[str, Any],
    channels: List[str] = Query(["email", "sms"], description="Каналы отправки"),
    template_data: Optional[Dict[str, Any]] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Cashier"))
):
    """Расширенное подтверждение платежа"""
    try:
        # Получаем данные пациента
        patient = crud_patient.get_patient(db, patient_id)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пациент не найден"
            )

        # Подготавливаем данные
        patient_data = {
            'id': patient.id,
            'full_name': patient.full_name or f"{patient.first_name} {patient.last_name}",
            'phone': patient.phone,
            'email': patient.email
        }

        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Отправляем уведомление
        result = await service.send_payment_confirmation_enhanced(
            patient_data=patient_data,
            payment_data=payment_data,
            channels=channels,
            template_data=template_data
        )

        return {
            "success": result['success'],
            "message": "Подтверждение платежа отправлено",
            "details": result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки подтверждения: {str(e)}"
        )


@router.post("/send-bulk-email")
async def send_bulk_email(
    recipients: List[Dict[str, Any]],
    subject: str,
    template_name: Optional[str] = None,
    template_data: Optional[Dict[str, Any]] = None,
    html_content: Optional[str] = None,
    text_content: Optional[str] = None,
    batch_size: int = Query(50, description="Размер батча"),
    delay_between_batches: float = Query(1.0, description="Задержка между батчами (сек)"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Массовая отправка email"""
    try:
        if not recipients:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Список получателей пуст"
            )

        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Отправляем массовую рассылку
        result = await service.send_bulk_email(
            recipients=recipients,
            subject=subject,
            template_name=template_name,
            template_data=template_data,
            html_content=html_content,
            text_content=text_content,
            batch_size=batch_size,
            delay_between_batches=delay_between_batches
        )

        return {
            "success": True,
            "message": "Массовая рассылка email запущена",
            "details": result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка массовой рассылки: {str(e)}"
        )


@router.post("/send-bulk-sms")
async def send_bulk_sms(
    recipients: List[Dict[str, Any]],
    message: Optional[str] = None,
    template_name: Optional[str] = None,
    template_data: Optional[Dict[str, Any]] = None,
    batch_size: int = Query(100, description="Размер батча"),
    delay_between_batches: float = Query(0.5, description="Задержка между батчами (сек)"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Массовая отправка SMS"""
    try:
        if not recipients:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Список получателей пуст"
            )

        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Отправляем массовую рассылку
        result = await service.send_bulk_sms(
            recipients=recipients,
            message=message,
            template_name=template_name,
            template_data=template_data,
            batch_size=batch_size,
            delay_between_batches=delay_between_batches
        )

        return {
            "success": True,
            "message": "Массовая рассылка SMS запущена",
            "details": result
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка массовой рассылки: {str(e)}"
        )


@router.post("/send-custom-email")
async def send_custom_email(
    to_email: str,
    subject: str,
    template_name: Optional[str] = None,
    template_data: Optional[Dict[str, Any]] = None,
    html_content: Optional[str] = None,
    text_content: Optional[str] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    priority: str = Query("normal", description="Приоритет: normal, high"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor"))
):
    """Отправка кастомного email"""
    try:
        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Отправляем email
        success, message = await service.send_email_enhanced(
            to_email=to_email,
            subject=subject,
            template_name=template_name,
            template_data=template_data,
            html_content=html_content,
            text_content=text_content,
            attachments=attachments,
            priority=priority
        )

        return {
            "success": success,
            "message": message,
            "to_email": to_email,
            "subject": subject
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки email: {str(e)}"
        )


@router.post("/send-custom-sms")
async def send_custom_sms(
    phone: str,
    message: Optional[str] = None,
    template_name: Optional[str] = None,
    template_data: Optional[Dict[str, Any]] = None,
    sender: Optional[str] = None,
    priority: str = Query("normal", description="Приоритет: normal, high"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor"))
):
    """Отправка кастомного SMS"""
    try:
        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Отправляем SMS
        success, message = await service.send_sms_enhanced(
            phone=phone,
            message=message,
            template_name=template_name,
            template_data=template_data,
            sender=sender,
            priority=priority
        )

        return {
            "success": success,
            "message": message,
            "phone": phone
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки SMS: {str(e)}"
        )


@router.get("/statistics")
async def get_email_sms_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
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
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}"
        )


@router.post("/reset-statistics")
async def reset_email_sms_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
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
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка сброса статистики: {str(e)}"
        )


@router.get("/templates")
async def get_available_templates(
    template_type: str = Query("all", description="Тип шаблона: email, sms, all"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor"))
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
                    "variables": ["patient_name", "doctor_name", "appointment_date", "appointment_time"]
                },
                {
                    "name": "lab_results_ready",
                    "title": "Результаты анализов готовы",
                    "description": "Шаблон для уведомления о готовности результатов",
                    "variables": ["patient_name", "test_type", "ready_date", "download_link"]
                },
                {
                    "name": "payment_confirmation",
                    "title": "Подтверждение платежа",
                    "description": "Шаблон для подтверждения оплаты",
                    "variables": ["patient_name", "amount", "currency", "payment_date"]
                }
            ],
            "sms": [
                {
                    "name": "appointment_reminder_sms",
                    "title": "Напоминание о записи (SMS)",
                    "description": "Краткий шаблон для SMS напоминания",
                    "variables": ["patient_name", "doctor_name", "appointment_date", "appointment_time"]
                },
                {
                    "name": "lab_results_ready_sms",
                    "title": "Результаты анализов готовы (SMS)",
                    "description": "Краткий шаблон для SMS уведомления",
                    "variables": ["patient_name", "test_type", "ready_date"]
                },
                {
                    "name": "payment_confirmation_sms",
                    "title": "Подтверждение платежа (SMS)",
                    "description": "Краткий шаблон для SMS подтверждения",
                    "variables": ["patient_name", "amount", "currency"]
                }
            ]
        }

        if template_type == "all":
            return {
                "success": True,
                "templates": templates
            }
        elif template_type in templates:
            return {
                "success": True,
                "templates": {template_type: templates[template_type]}
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный тип шаблона"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения шаблонов: {str(e)}"
        )


@router.post("/test-email")
async def test_email_sending(
    to_email: str,
    subject: str = "Тестовое письмо",
    message: str = "Это тестовое письмо от Programma Clinic",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
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
            text_content=f"Programma Clinic - Тестовое письмо\n\n{message}\n\nВремя отправки: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
        )

        return {
            "success": success,
            "message": result_message,
            "to_email": to_email,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка тестирования email: {str(e)}"
        )


@router.post("/test-sms")
async def test_sms_sending(
    phone: str,
    message: str = "Тестовое SMS от Programma Clinic",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Тестирование отправки SMS"""
    try:
        # Получаем сервис
        service = get_email_sms_enhanced_service()

        # Отправляем тестовое SMS
        success, result_message = await service.send_sms_enhanced(
            phone=phone,
            message=f"{message} - {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
        )

        return {
            "success": success,
            "message": result_message,
            "phone": phone,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка тестирования SMS: {str(e)}"
        )
