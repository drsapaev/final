"""
Telegram Bot API endpoints
"""

import logging
import secrets
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ....api.deps import get_db, require_roles
from ....crud import telegram_config as crud_telegram
from ....models.user import User
from ....services.telegram.bot import telegram_bot

logger = logging.getLogger(__name__)

router = APIRouter()


def _validate_webhook_secret(request: Request, db: Session) -> None:
    config = crud_telegram.get_telegram_config(db)
    expected_secret = getattr(config, "webhook_secret", None)
    if not expected_secret:
        return

    received_secret = request.headers.get("x-telegram-bot-api-secret-token")
    if received_secret != expected_secret:
        logger.warning("Telegram webhook rejected due to invalid secret token")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Telegram webhook secret",
        )


@router.post("/webhook")
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """Webhook для получения обновлений от Telegram"""
    try:
        if not telegram_bot.bot:
            raise HTTPException(status_code=503, detail="Telegram bot not configured")

        # Получаем JSON данные
        update_data = await request.json()

        _validate_webhook_secret(request, db)

        # Обрабатываем обновление через aiogram
        from aiogram.types import Update

        update = Update.model_validate(update_data)

        # Передаем обновление диспетчеру
        await telegram_bot.dp.feed_update(telegram_bot.bot, update)

        return JSONResponse({"status": "ok"})

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Telegram webhook error: {str(e)}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@router.post("/set-webhook")
async def set_telegram_webhook(
    webhook_data: Dict[str, str],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Установка webhook URL для Telegram бота"""
    try:
        if not telegram_bot.bot:
            raise HTTPException(status_code=503, detail="Telegram bot not configured")

        webhook_url = webhook_data.get("webhook_url")
        if not webhook_url:
            raise HTTPException(status_code=400, detail="webhook_url required")

        secret_token = secrets.token_urlsafe(32)
        success = await telegram_bot.setup_webhook(webhook_url, secret_token=secret_token)

        if success:
            config = crud_telegram.get_telegram_config(db)
            if config:
                crud_telegram.update_telegram_config(
                    db,
                    {
                        "webhook_url": webhook_url,
                        "webhook_secret": secret_token,
                    },
                )
            else:
                crud_telegram.create_telegram_config(
                    db,
                    {
                        "webhook_url": webhook_url,
                        "webhook_secret": secret_token,
                    },
                )
            return {"status": "success", "message": "Webhook установлен"}
        else:
            raise HTTPException(status_code=500, detail="Не удалось установить webhook")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Set webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/webhook")
async def remove_telegram_webhook(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Удаление webhook для Telegram бота"""
    try:
        if not telegram_bot.bot:
            raise HTTPException(status_code=503, detail="Telegram bot not configured")

        success = await telegram_bot.remove_webhook()

        if success:
            config = crud_telegram.get_telegram_config(db)
            if config:
                crud_telegram.update_telegram_config(
                    db,
                    {
                        "webhook_url": None,
                        "webhook_secret": None,
                    },
                )
            return {"status": "success", "message": "Webhook удален"}
        else:
            raise HTTPException(status_code=500, detail="Не удалось удалить webhook")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Remove webhook error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info")
async def get_bot_info(current_user: User = Depends(require_roles("Admin"))):
    """Получение информации о боте"""
    try:
        if not telegram_bot.bot:
            return {
                "status": "disabled",
                "message": "Telegram bot not configured. Set TELEGRAM_BOT_TOKEN.",
            }

        # Получаем информацию о боте
        bot_info = await telegram_bot.bot.get_me()
        webhook_info = await telegram_bot.bot.get_webhook_info()

        return {
            "status": "active",
            "bot": {
                "id": bot_info.id,
                "username": bot_info.username,
                "first_name": bot_info.first_name,
                "can_join_groups": bot_info.can_join_groups,
                "can_read_all_group_messages": bot_info.can_read_all_group_messages,
                "supports_inline_queries": bot_info.supports_inline_queries,
            },
            "webhook": {
                "url": webhook_info.url,
                "has_custom_certificate": webhook_info.has_custom_certificate,
                "pending_update_count": webhook_info.pending_update_count,
                "last_error_date": webhook_info.last_error_date,
                "last_error_message": webhook_info.last_error_message,
                "max_connections": webhook_info.max_connections,
                "allowed_updates": webhook_info.allowed_updates,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get bot info error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-notification")
async def send_telegram_notification(
    notification_data: Dict[str, Any],
    current_user: User = Depends(require_roles("Admin")),
):
    """Отправка уведомления через Telegram бота"""
    try:
        if not telegram_bot.bot:
            raise HTTPException(status_code=503, detail="Telegram bot not configured")

        user_id = notification_data.get("user_id")
        message = notification_data.get("message")

        if not user_id or not message:
            raise HTTPException(status_code=400, detail="user_id and message required")

        success = await telegram_bot.send_notification(user_id, message)

        if success:
            return {"status": "success", "message": "Уведомление отправлено"}
        else:
            raise HTTPException(
                status_code=500, detail="Не удалось отправить уведомление"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send notification error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-appointment-reminder")
async def send_appointment_reminder(
    reminder_data: Dict[str, Any],
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """Отправка напоминания о визите"""
    try:
        if not telegram_bot.bot:
            raise HTTPException(status_code=503, detail="Telegram bot not configured")

        user_id = reminder_data.get("user_id")
        appointment_data = reminder_data.get("appointment")

        if not user_id or not appointment_data:
            raise HTTPException(
                status_code=400, detail="user_id and appointment data required"
            )

        await telegram_bot.send_appointment_reminder(user_id, appointment_data)

        return {"status": "success", "message": "Напоминание отправлено"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send reminder error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send-lab-notification")
async def send_lab_results_notification(
    lab_data: Dict[str, Any],
    current_user: User = Depends(require_roles("Admin", "Doctor", "Lab")),
):
    """Уведомление о готовности результатов анализов"""
    try:
        if not telegram_bot.bot:
            raise HTTPException(status_code=503, detail="Telegram bot not configured")

        user_id = lab_data.get("user_id")
        results_info = lab_data.get("results")

        if not user_id or not results_info:
            raise HTTPException(
                status_code=400, detail="user_id and results data required"
            )

        await telegram_bot.send_lab_results_ready(user_id, results_info)

        return {"status": "success", "message": "Уведомление о результатах отправлено"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send lab notification error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_telegram_stats(current_user: User = Depends(require_roles("Admin"))):
    """Статистика Telegram бота"""
    try:
        if not telegram_bot.bot:
            return {"status": "disabled", "stats": None}

        # В реальном приложении здесь будет запрос к БД
        # для получения статистики использования бота
        stats = {
            "total_users": 0,  # Общее количество пользователей бота
            "active_users_today": 0,  # Активные пользователи сегодня
            "messages_sent_today": 0,  # Отправлено сообщений сегодня
            "notifications_sent": 0,  # Отправлено уведомлений
            "queue_registrations": 0,  # Записи в очередь через бота
            "last_activity": None,  # Последняя активность
        }

        return {"status": "active", "stats": stats}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get telegram stats error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
