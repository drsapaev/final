"""
Telegram Bot API endpoints

P0-6 FIX (ENDPOINT-VALIDATION-AUDIT):
Previously these endpoints accepted `notification_data: dict[str, Any]`,
`reminder_data: dict[str, Any]`, `lab_data: dict[str, Any]`, and
`webhook_data: dict[str, str]` with no validation. Replaced with typed
Pydantic request models from app.schemas.notifications.
"""

import hmac
import json
import logging
import secrets
from json import JSONDecodeError
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ....api.deps import get_db, require_roles
from ....crud import telegram_config as crud_telegram
from ....models.user import User
from ....services.telegram.bot import telegram_bot
from ....schemas.notifications import (
    SendAppointmentReminderRequest,
    SendLabNotificationRequest,
    SendTelegramNotificationRequest,
    SetWebhookRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()
WEBHOOK_SECRET_HEADER = "x-telegram-bot-api-secret-token"
INTERNAL_ERROR_DETAIL = "Internal server error"
MAX_TELEGRAM_WEBHOOK_BODY_BYTES = 256 * 1024


async def _read_telegram_webhook_json(request: Request) -> dict[str, Any]:
    chunks: list[bytes] = []
    total_size = 0

    async for chunk in request.stream():
        total_size += len(chunk)
        if total_size > MAX_TELEGRAM_WEBHOOK_BODY_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Telegram webhook payload is too large",
            )
        chunks.append(chunk)

    try:
        update_data = json.loads(b"".join(chunks).decode("utf-8") or "{}")
    except (JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Telegram webhook JSON",
        ) from exc

    if not isinstance(update_data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram webhook JSON must be an object",
        )

    return update_data


def _validate_webhook_secret(request: Request, db: Session) -> None:
    config = crud_telegram.get_telegram_config(db)
    expected_secret = getattr(config, "webhook_secret", None)
    if not expected_secret:
        logger.error("Telegram bot webhook rejected because webhook secret is not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram webhook secret is not configured",
        )

    received_secret = request.headers.get(WEBHOOK_SECRET_HEADER)
    if not hmac.compare_digest(received_secret or "", expected_secret or ""):
        logger.warning("Telegram webhook rejected due to invalid secret token")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Telegram webhook secret",
        )


@router.post("/webhook", response_model=dict[str, Any])
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """Webhook для получения обновлений от Telegram"""
    try:
        if not telegram_bot.bot:
            raise HTTPException(status_code=503, detail="Telegram bot not configured")

        _validate_webhook_secret(request, db)

        # Получаем JSON данные
        update_data = await _read_telegram_webhook_json(request)

        # Обрабатываем обновление через aiogram
        from aiogram.types import Update

        update = Update.model_validate(update_data)

        # Передаем обновление диспетчеру
        await telegram_bot.dp.feed_update(telegram_bot.bot, update)

        return JSONResponse({"status": "ok"})

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Telegram webhook error",
            extra={"error_class": e.__class__.__name__},
        )
        return JSONResponse(
            {"status": "error", "message": INTERNAL_ERROR_DETAIL},
            status_code=500,
        )


@router.post("/set-webhook", response_model=dict[str, Any])
async def set_telegram_webhook(
    webhook_data: SetWebhookRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Установка webhook URL для Telegram бота"""
    try:
        if not telegram_bot.bot:
            raise HTTPException(status_code=503, detail="Telegram bot not configured")

        webhook_url = webhook_data.webhook_url
        # Validation (URL format) already done by Pydantic

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
        logger.exception(
            "Set Telegram webhook error",
            extra={"error_class": e.__class__.__name__},
        )
        raise HTTPException(status_code=500, detail=INTERNAL_ERROR_DETAIL)


@router.delete("/webhook", response_model=dict[str, Any])
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
        logger.exception(
            "Remove Telegram webhook error",
            extra={"error_class": e.__class__.__name__},
        )
        raise HTTPException(status_code=500, detail=INTERNAL_ERROR_DETAIL)


@router.get("/info", response_model=dict[str, Any])
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
        logger.exception(
            "Get Telegram bot info error",
            extra={"error_class": e.__class__.__name__},
        )
        raise HTTPException(status_code=500, detail=INTERNAL_ERROR_DETAIL)


@router.post("/send-notification", response_model=dict[str, Any])
async def send_telegram_notification(
    notification_data: SendTelegramNotificationRequest,
    current_user: User = Depends(require_roles("Admin")),
):
    """Отправка уведомления через Telegram бота"""
    try:
        if not telegram_bot.bot:
            raise HTTPException(status_code=503, detail="Telegram bot not configured")

        user_id = notification_data.user_id
        message = notification_data.message
        # Validation already done by Pydantic

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
        logger.exception(
            "Send Telegram notification error",
            extra={"error_class": e.__class__.__name__},
        )
        raise HTTPException(status_code=500, detail=INTERNAL_ERROR_DETAIL)


@router.post("/send-appointment-reminder", response_model=dict[str, Any])
async def send_appointment_reminder(
    reminder_data: SendAppointmentReminderRequest,
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar")),
):
    """Отправка напоминания о визите"""
    try:
        if not telegram_bot.bot:
            raise HTTPException(status_code=503, detail="Telegram bot not configured")

        user_id = reminder_data.user_id
        appointment_data = reminder_data.appointment.model_dump(exclude_none=True)
        # Validation already done by Pydantic

        await telegram_bot.send_appointment_reminder(user_id, appointment_data)

        return {"status": "success", "message": "Напоминание отправлено"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Send Telegram reminder error",
            extra={"error_class": e.__class__.__name__},
        )
        raise HTTPException(status_code=500, detail=INTERNAL_ERROR_DETAIL)


@router.post("/send-lab-notification", response_model=dict[str, Any])
async def send_lab_results_notification(
    lab_data: SendLabNotificationRequest,
    current_user: User = Depends(require_roles("Admin", "Doctor", "Lab")),
):
    """Уведомление о готовности результатов анализов"""
    try:
        if not telegram_bot.bot:
            raise HTTPException(status_code=503, detail="Telegram bot not configured")

        user_id = lab_data.user_id
        results_info = lab_data.results.model_dump(exclude_none=True)
        # Validation already done by Pydantic

        await telegram_bot.send_lab_results_ready(user_id, results_info)

        return {"status": "success", "message": "Уведомление о результатах отправлено"}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Send Telegram lab notification error",
            extra={"error_class": e.__class__.__name__},
        )
        raise HTTPException(status_code=500, detail=INTERNAL_ERROR_DETAIL)


@router.get("/stats", response_model=dict[str, Any])
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
        logger.exception(
            "Get Telegram stats error",
            extra={"error_class": e.__class__.__name__},
        )
        raise HTTPException(status_code=500, detail=INTERNAL_ERROR_DETAIL)
