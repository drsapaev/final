"""
Расширенные API endpoints для Telegram уведомлений
Поддержка массовых рассылок, планировщика и аналитики
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_roles
from app.crud import (
    appointment as crud_appointment,
    lab_result as crud_lab,
    patient as crud_patient,
    telegram_config as crud_telegram,
)
from app.models.user import User
from app.services.telegram_bot import get_telegram_bot_service
from app.services.telegram_templates import get_telegram_templates_service

router = APIRouter()


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
                "patient_phone": patient.phone,
            }

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
                "chat_id": telegram_user.chat_id,
                "patient": patient.full_name,
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
            detail=f"Ошибка отправки напоминания: {str(e)}",
        )


@router.post("/send-lab-results")
async def send_lab_results(
    patient_id: int,
    lab_result_ids: List[int],
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
        telegram_user = crud_telegram.find_telegram_user_by_phone(db, patient.phone)
        if not telegram_user:
            return {
                "success": False,
                "message": "Пациент не зарегистрирован в Telegram боте",
                "patient_phone": patient.phone,
            }

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
        bot_service = await get_telegram_bot_service()
        if not bot_service.active:
            await bot_service.initialize(db)

        # Получаем сервис шаблонов
        templates_service = get_telegram_templates_service()

        # Формируем данные для шаблона
        test_types = [result.test_code for result in lab_results]
        has_abnormalities = any(
            result.is_abnormal
            for result in lab_results
            if hasattr(result, 'is_abnormal')
        )

        template_data = {
            "patient_name": patient.full_name,
            "test_type": ", ".join(test_types),
            "collection_date": lab_results[0].created_at.strftime("%d.%m.%Y"),
            "ready_date": datetime.now().strftime("%d.%m.%Y"),
            "has_abnormalities": has_abnormalities,
            "abnormalities_text": templates_service.get_abnormalities_text(
                has_abnormalities, telegram_user.language_code or "ru"
            ),
            "download_link": f"https://clinic.example.com/lab-results/{patient_id}",
            "doctor_id": lab_results[0].doctor_id,
        }

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
                "chat_id": telegram_user.chat_id,
                "patient": patient.full_name,
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
            detail=f"Ошибка отправки результатов: {str(e)}",
        )


@router.post("/send-payment-confirmation")
async def send_payment_confirmation(
    patient_id: int,
    payment_data: Dict[str, Any],
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
        telegram_user = crud_telegram.find_telegram_user_by_phone(db, patient.phone)
        if not telegram_user:
            return {
                "success": False,
                "message": "Пациент не зарегистрирован в Telegram боте",
                "patient_phone": patient.phone,
            }

        # Получаем сервис бота
        bot_service = await get_telegram_bot_service()
        if not bot_service.active:
            await bot_service.initialize(db)

        # Формируем данные для шаблона
        template_data = {
            "patient_name": patient.full_name,
            "amount": payment_data.get("amount", 0),
            "currency": payment_data.get("currency", "UZS"),
            "payment_method": payment_data.get("payment_method", "Карта"),
            "payment_date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "transaction_id": payment_data.get("transaction_id", "N/A"),
            "receipt_link": f"https://clinic.example.com/receipt/{payment_data.get('transaction_id')}",
        }

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
                "chat_id": telegram_user.chat_id,
                "patient": patient.full_name,
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
            detail=f"Ошибка отправки подтверждения: {str(e)}",
        )


@router.post("/broadcast-message")
async def send_broadcast_message(
    message: str,
    target_groups: List[str] = Query(
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
            except Exception as e:
                failed_count += 1
                continue

        return {
            "success": True,
            "message": f"Широковещательное сообщение отправлено",
            "total_recipients": len(recipients),
            "sent_count": sent_count,
            "failed_count": failed_count,
            "target_groups": target_groups,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки широковещательного сообщения: {str(e)}",
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
            detail=f"Ошибка получения статистики: {str(e)}",
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
            detail=f"Ошибка планирования напоминания: {str(e)}",
        )
