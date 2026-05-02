"""
Расширенный webhook endpoint для Telegram бота
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.crud import telegram_config as crud_telegram
from app.models.user import User
from app.db.session import get_db
from app.services.telegram_bot_enhanced import get_enhanced_telegram_bot

router = APIRouter()
logger = logging.getLogger(__name__)


def _validate_webhook_secret(request: Request, db: Session) -> None:
    config = crud_telegram.get_telegram_config(db)
    expected_secret = getattr(config, "webhook_secret", None)
    if not expected_secret:
        return

    received_secret = request.headers.get("x-telegram-bot-api-secret-token")
    if received_secret != expected_secret:
        logger.warning("Enhanced Telegram webhook rejected due to invalid secret token")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Telegram webhook secret",
        )


@router.post("/webhook/enhanced")
async def telegram_webhook_enhanced(request: Request, db: Session = Depends(get_db)):
    """Обработка webhook от Telegram для расширенного бота"""
    try:
        # Получаем данные от Telegram
        update_data = await request.json()
        _validate_webhook_secret(request, db)

        # Получаем экземпляр расширенного бота
        bot = get_enhanced_telegram_bot()

        # Инициализируем бота если нужно
        if not bot.active:
            await bot.initialize(db)

        # Обрабатываем обновление
        await bot.process_webhook_update(update_data, db)

        return {"status": "ok"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/webhook/info")
async def webhook_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Информация о webhook"""
    try:
        bot = get_enhanced_telegram_bot()

        return {
            "active": bot.active,
            "bot_username": bot.bot_username,
            "webhook_url": bot.webhook_url,
            "features": [
                "Расширенные команды администратора",
                "Улучшенное пользовательское меню",
                "Статистика клиники",
                "Управление очередями",
                "Массовые уведомления",
                "Экстренная помощь",
                "Обратная связь",
                "Многоязычность",
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения информации о webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/webhook/test")
async def test_webhook(
    test_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """Тестирование webhook с произвольными данными"""
    try:
        bot = get_enhanced_telegram_bot()

        if not bot.active:
            await bot.initialize(db)

        # Обрабатываем тестовые данные
        await bot.process_webhook_update(test_data, db)

        return {
            "status": "success",
            "message": "Test webhook processed successfully",
            "processed_data": test_data,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка тестирования webhook: {e}")
        return {"status": "error", "message": str(e), "processed_data": test_data}
