"""
Расширенный webhook endpoint для Telegram бота
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.telegram_bot_enhanced import get_enhanced_telegram_bot

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhook/enhanced")
async def telegram_webhook_enhanced(
    request: Request,
    db: Session = Depends(get_db)
):
    """Обработка webhook от Telegram для расширенного бота"""
    try:
        # Получаем данные от Telegram
        update_data = await request.json()
        
        # Получаем экземпляр расширенного бота
        bot = get_enhanced_telegram_bot()
        
        # Инициализируем бота если нужно
        if not bot.active:
            await bot.initialize(db)
        
        # Обрабатываем обновление
        await bot.process_webhook_update(update_data, db)
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Ошибка обработки webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/webhook/info")
async def webhook_info(db: Session = Depends(get_db)):
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
                "Многоязычность"
            ]
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения информации о webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/webhook/test")
async def test_webhook(
    test_data: Dict[str, Any],
    db: Session = Depends(get_db)
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
            "processed_data": test_data
        }
        
    except Exception as e:
        logger.error(f"Ошибка тестирования webhook: {e}")
        return {
            "status": "error",
            "message": str(e),
            "processed_data": test_data
        }


