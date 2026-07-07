"""
Расширенный webhook endpoint для Telegram бота
"""

import hmac
import json
import logging
from json import JSONDecodeError
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.crud import telegram_config as crud_telegram
from app.db.session import get_db
from app.models.user import User
from app.services.telegram_bot_enhanced import get_enhanced_telegram_bot

router = APIRouter()
logger = logging.getLogger(__name__)
WEBHOOK_SECRET_HEADER = "x-telegram-bot-api-secret-token"
TELEGRAM_ENHANCED_PUBLIC_ERROR = "Internal server error"
MAX_TELEGRAM_ENHANCED_WEBHOOK_BODY_BYTES = 256 * 1024


async def _read_telegram_enhanced_webhook_json(request: Request) -> dict[str, Any]:
    chunks: list[bytes] = []
    total_size = 0

    async for chunk in request.stream():
        total_size += len(chunk)
        if total_size > MAX_TELEGRAM_ENHANCED_WEBHOOK_BODY_BYTES:
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
        logger.error("Enhanced Telegram webhook rejected because webhook secret is not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram webhook secret is not configured",
        )

    received_secret = request.headers.get(WEBHOOK_SECRET_HEADER)
    if not hmac.compare_digest(received_secret or "", expected_secret or ""):
        logger.warning("Enhanced Telegram webhook rejected due to invalid secret token")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Telegram webhook secret",
        )


def _raise_telegram_enhanced_internal_error(
    operation: str, exc: Exception
) -> NoReturn:
    logger.warning(
        "Enhanced Telegram webhook endpoint failed operation=%s error_type=%s",
        operation,
        type(exc).__name__,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=TELEGRAM_ENHANCED_PUBLIC_ERROR,
    ) from exc


def _telegram_enhanced_test_failure(exc: Exception) -> dict[str, Any]:
    logger.warning(
        "Enhanced Telegram webhook endpoint failed operation=test_webhook error_type=%s",
        type(exc).__name__,
    )
    return {
        "status": "error",
        "message": TELEGRAM_ENHANCED_PUBLIC_ERROR,
        "processed_data": None,
    }


@router.post("/webhook/enhanced")
async def telegram_webhook_enhanced(request: Request, db: Session = Depends(get_db)):
    """Обработка webhook от Telegram для расширенного бота"""
    try:
        _validate_webhook_secret(request, db)

        # Получаем данные от Telegram
        update_data = await _read_telegram_enhanced_webhook_json(request)

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
        _raise_telegram_enhanced_internal_error("telegram_webhook_enhanced", e)


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
        _raise_telegram_enhanced_internal_error("webhook_info", e)


@router.post("/webhook/test")
async def test_webhook(
    test_data: dict[str, Any],
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
        return _telegram_enhanced_test_failure(e)
