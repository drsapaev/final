"""
Webhook endpoint для обработки входящих сообщений от Telegram
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.crud import telegram_config as crud_telegram
from app.db.session import get_db
from app.models.user import User
from app.services.telegram_bot import get_telegram_bot_service

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
async def telegram_webhook(
    update: Dict[str, Any], request: Request, db: Session = Depends(get_db)
):
    """
    Webhook endpoint для получения обновлений от Telegram
    """
    try:
        # Логируем входящее обновление
        logger.info(f"Получено обновление от Telegram: {update}")

        _validate_webhook_secret(request, db)

        # Получаем сервис бота
        bot_service = await get_telegram_bot_service()

        # Инициализируем бота если нужно
        if not bot_service.active:
            await bot_service.initialize(db)

        # Обрабатываем обновление
        await bot_service.process_webhook_update(update, db)

        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка обработки webhook",
        )


@router.get("/webhook")
async def verify_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Проверка webhook (для верификации)
    """
    try:
        # Telegram может отправлять GET запросы для проверки webhook
        return {"status": "webhook_verified"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка проверки webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка проверки webhook",
        )


@router.post("/send-message")
async def send_message_to_user(
    chat_id: int,
    message: str,
    parse_mode: str = "HTML",
    reply_markup: Dict[str, Any] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Отправка сообщения пользователю через бота
    """
    try:
        bot_service = await get_telegram_bot_service()

        if not bot_service.active:
            await bot_service.initialize(db)

        success = await bot_service._send_message(
            chat_id=chat_id, text=message, reply_markup=reply_markup
        )

        if success:
            return {"status": "sent", "chat_id": chat_id}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ошибка отправки сообщения",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки сообщения: {str(e)}",
        )


@router.get("/bot-info", operation_id="telegram_webhook_get_bot_info")
async def get_bot_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Получить информацию о боте
    """
    try:
        bot_service = await get_telegram_bot_service()

        if not bot_service.active:
            await bot_service.initialize(db)

        if not bot_service.bot_token:
            return {"active": False, "message": "Бот не настроен"}

        # Получаем информацию о боте через API
        import requests

        response = requests.get(
            f"https://api.telegram.org/bot{bot_service.bot_token}/getMe", timeout=10
        )

        if response.status_code == 200:
            bot_data = response.json()
            if bot_data.get("ok"):
                return {
                    "active": True,
                    "bot_info": bot_data["result"],
                    "webhook_url": bot_service.webhook_url,
                }

        return {"active": False, "message": "Ошибка получения информации о боте"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения информации о боте: {e}")
        return {"active": False, "message": f"Ошибка: {str(e)}"}
