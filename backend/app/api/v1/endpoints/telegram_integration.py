"""
API endpoints для интеграции с Telegram ботом
Основа: passport.md стр. 2064-2570
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles, get_current_user
from app.models.user import User
from app.services.telegram_service import get_telegram_service, send_telegram_notification
from app.crud import telegram_config as crud_telegram

router = APIRouter()

# ===================== УВЕДОМЛЕНИЯ =====================

@router.post("/send-notification")
async def send_notification(
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor"))
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
                detail="Не указан chat_id или template_key"
            )

        # Отправляем уведомление в фоне
        background_tasks.add_task(
            send_telegram_notification,
            chat_id,
            template_key,
            data,
            language
        )
        
        return {
            "success": True,
            "message": "Уведомление поставлено в очередь на отправку",
            "chat_id": chat_id,
            "template": template_key
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки уведомления: {str(e)}"
        )


@router.post("/appointment-reminder")
async def send_appointment_reminder(
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
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
                detail="Не указан телефон пациента или данные записи"
            )

        # Ищем Telegram пользователя по телефону
        telegram_user = crud_telegram.find_telegram_user_by_phone(db, patient_phone)
        
        if not telegram_user:
            return {
                "success": False,
                "message": "Пациент не зарегистрирован в Telegram боте",
                "phone": patient_phone
            }

        # Формируем данные для шаблона
        template_data = {
            "patient_name": appointment_data.get("patient_name", "Пациент"),
            "doctor_name": appointment_data.get("doctor_name", "Врач"),
            "specialty": appointment_data.get("specialty", "Специалист"),
            "appointment_date": appointment_data.get("date", "Не указано"),
            "appointment_time": appointment_data.get("time", "Не указано"),
            "cabinet": appointment_data.get("cabinet", "Уточните в регистратуре"),
            "clinic_address": "г. Ташкент, ул. Медицинская, 15",  # Из настроек
            "clinic_phone": "+998 71 123-45-67"  # Из настроек
        }

        # Отправляем напоминание
        background_tasks.add_task(
            send_telegram_notification,
            telegram_user.chat_id,
            "appointment_reminder",
            template_data,
            telegram_user.language_code
        )
        
        return {
            "success": True,
            "message": "Напоминание отправлено",
            "chat_id": telegram_user.chat_id,
            "patient": appointment_data.get("patient_name")
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки напоминания: {str(e)}"
        )


@router.post("/lab-results-notification")
async def send_lab_results_notification(
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Lab", "Doctor"))
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
                detail="Не указан телефон пациента или данные анализов"
            )

        # Ищем Telegram пользователя
        telegram_user = crud_telegram.find_telegram_user_by_phone(db, patient_phone)
        
        if not telegram_user:
            return {
                "success": False,
                "message": "Пациент не зарегистрирован в Telegram боте",
                "phone": patient_phone
            }

        # Формируем данные для шаблона
        template_data = {
            "patient_name": lab_data.get("patient_name", "Пациент"),
            "test_type": lab_data.get("test_type", "Лабораторное исследование"),
            "collection_date": lab_data.get("collection_date", "Не указано"),
            "ready_date": datetime.now().strftime("%d.%m.%Y"),
            "has_abnormalities": lab_data.get("has_abnormalities", False)
        }

        # Отправляем уведомление
        background_tasks.add_task(
            send_telegram_notification,
            telegram_user.chat_id,
            "lab_results_ready",
            template_data,
            telegram_user.language_code
        )
        
        return {
            "success": True,
            "message": "Уведомление о результатах отправлено",
            "chat_id": telegram_user.chat_id,
            "patient": lab_data.get("patient_name")
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки уведомления о результатах: {str(e)}"
        )


# ===================== QR КОДЫ =====================

@router.post("/send-qr-code")
async def send_qr_code(
    request: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
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
                detail="Не указан телефон пациента или данные QR"
            )

        # Ищем Telegram пользователя
        telegram_user = crud_telegram.find_telegram_user_by_phone(db, patient_phone)
        
        if not telegram_user:
            return {
                "success": False,
                "message": "Пациент не зарегистрирован в Telegram боте",
                "phone": patient_phone
            }

        # Формируем данные для шаблона QR
        template_data = {
            "doctor_name": qr_data.get("doctor_name", "Врач"),
            "specialty": qr_data.get("specialty", "Специалист"),
            "date": qr_data.get("date", "Не указано"),
            "time_window": qr_data.get("time_window", "07:00-09:00"),
            "qr_token": qr_data.get("token", ""),
            "queue_url": "https://clinic.example.com/queue"  # Из настроек
        }

        # Отправляем QR код
        background_tasks.add_task(
            send_telegram_notification,
            telegram_user.chat_id,
            "qr_code_message",
            template_data,
            telegram_user.language_code
        )
        
        return {
            "success": True,
            "message": "QR код отправлен в Telegram",
            "chat_id": telegram_user.chat_id,
            "token": qr_data.get("token")
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки QR кода: {str(e)}"
        )


# ===================== УПРАВЛЕНИЕ БОТОМ =====================

@router.get("/bot-status")
def get_bot_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
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
                "message": "Telegram бот не настроен"
            }

        telegram_service = get_telegram_service()
        
        return {
            "configured": bool(config.bot_token),
            "active": config.active,
            "bot_username": config.bot_username,
            "notifications_enabled": config.notifications_enabled,
            "supported_languages": config.supported_languages,
            "stats": {
                "total_users": len(crud_telegram.get_telegram_users(db, active_only=False)),
                "active_users": len(crud_telegram.get_telegram_users(db, active_only=True)),
                "templates": len(crud_telegram.get_telegram_templates(db))
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статуса бота: {str(e)}"
        )


@router.get("/users")
def get_telegram_users(
    active_only: bool = True,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Получить список пользователей Telegram
    """
    try:
        users = crud_telegram.get_telegram_users(db, active_only=active_only, limit=limit)
        
        users_data = []
        for user in users:
            users_data.append({
                "id": user.id,
                "chat_id": user.chat_id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "language_code": user.language_code,
                "notifications_enabled": user.notifications_enabled,
                "patient_linked": bool(user.patient_id),
                "last_activity": user.last_activity.isoformat() if user.last_activity else None,
                "active": user.active
            })
        
        return {
            "users": users_data,
            "total": len(users_data)
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения пользователей: {str(e)}"
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
    current_user: User = Depends(require_roles("Admin", "Registrar"))
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
        "cabinet": cabinet
    }
    
    return await send_appointment_reminder({
        "patient_phone": patient_phone,
        "appointment_data": appointment_data
    }, background_tasks, db, current_user)


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
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Быстрая отправка QR кода
    """
    qr_data = {
        "doctor_name": doctor_name,
        "specialty": specialty,
        "token": qr_token,
        "date": date,
        "time_window": time_window
    }
    
    return await send_qr_code({
        "patient_phone": patient_phone,
        "qr_data": qr_data
    }, background_tasks, db, current_user)
