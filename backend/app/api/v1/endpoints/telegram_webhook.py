"""
Webhook endpoint для обработки входящих сообщений от Telegram
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.telegram_bot import get_telegram_bot_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/webhook")
async def telegram_webhook(
    update: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Webhook endpoint для получения обновлений от Telegram
    """
    try:
        # Логируем входящее обновление
        logger.info(f"Получено обновление от Telegram: {update}")
        
        # Получаем сервис бота
        bot_service = await get_telegram_bot_service()
        
        # Инициализируем бота если нужно
        if not bot_service.active:
            await bot_service.initialize(db)
        
        # Обрабатываем обновление
        await bot_service.process_webhook_update(update, db)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка обработки webhook"
        )


@router.get("/webhook")
async def verify_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Проверка webhook (для верификации)
    """
    try:
        # Telegram может отправлять GET запросы для проверки webhook
        return {"status": "webhook_verified"}
        
    except Exception as e:
        logger.error(f"Ошибка проверки webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка проверки webhook"
        )


@router.post("/send-message")
async def send_message_to_user(
    chat_id: int,
    message: str,
    parse_mode: str = "HTML",
    reply_markup: Dict[str, Any] = None,
    db: Session = Depends(get_db)
):
    """
    Отправка сообщения пользователю через бота
    """
    try:
        bot_service = await get_telegram_bot_service()
        
        if not bot_service.active:
            await bot_service.initialize(db)
        
        success = await bot_service._send_message(
            chat_id=chat_id,
            text=message,
            reply_markup=reply_markup
        )
        
        if success:
            return {"status": "sent", "chat_id": chat_id}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ошибка отправки сообщения"
            )
            
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка отправки сообщения: {str(e)}"
        )


@router.get("/bot-info")
async def get_bot_info(db: Session = Depends(get_db)):
    """
    Получить информацию о боте
    """
    try:
        bot_service = await get_telegram_bot_service()
        
        if not bot_service.active:
            await bot_service.initialize(db)
        
        if not bot_service.bot_token:
            return {
                "active": False,
                "message": "Бот не настроен"
            }
        
        # Получаем информацию о боте через API
        import requests
        
        response = requests.get(
            f"https://api.telegram.org/bot{bot_service.bot_token}/getMe",
            timeout=10
        )
        
        if response.status_code == 200:
            bot_data = response.json()
            if bot_data.get("ok"):
                return {
                    "active": True,
                    "bot_info": bot_data["result"],
                    "webhook_url": bot_service.webhook_url
                }
        
        return {
            "active": False,
            "message": "Ошибка получения информации о боте"
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения информации о боте: {e}")
        return {
            "active": False,
            "message": f"Ошибка: {str(e)}"
        }
