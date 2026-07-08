"""
API endpoints для управления расширенным Telegram ботом
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User
from app.services.telegram_bot_enhanced import get_enhanced_telegram_bot
from app.services.telegram_bot_management_api_service import (
    TelegramBotManagementApiService,
)

router = APIRouter()
logger = logging.getLogger(__name__)

TELEGRAM_BOT_MANAGEMENT_PUBLIC_ERROR = "Telegram bot management operation failed"


def _telegram_bot_management_http_error(
    exc: Exception, operation: str
) -> HTTPException:
    logger.warning(
        "Telegram bot management endpoint failed operation=%s error_type=%s",
        operation,
        type(exc).__name__,
    )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=TELEGRAM_BOT_MANAGEMENT_PUBLIC_ERROR,
    )


class TelegramNotificationRequest(BaseModel):
    """Запрос на отправку Telegram уведомления"""

    message: str
    user_ids: list[int] | None = None
    send_to_all_admins: bool = False
    send_to_all_users: bool = False


class TelegramBotStatsResponse(BaseModel):
    """Статистика Telegram бота"""

    total_users: int
    active_users: int
    admin_users: int
    messages_sent_today: int
    commands_processed_today: int


class TelegramBotConfigRequest(BaseModel):
    """Конфигурация Telegram бота"""

    bot_token: str | None = None
    webhook_url: str | None = None
    active: bool = True


@router.get("/stats", response_model=TelegramBotStatsResponse)
async def get_telegram_bot_stats(
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"])),
    db: Session = Depends(get_db),
):
    """Получить статистику Telegram бота"""
    try:
        payload = TelegramBotManagementApiService(db).get_stats_payload()
        return TelegramBotStatsResponse(**payload)

    except Exception as e:
        raise _telegram_bot_management_http_error(e, "get_telegram_bot_stats") from e


@router.post(
    "/send-notification",
    operation_id="telegram_bot_management_send_notification",
response_model=dict[str, Any],
)
async def send_telegram_notification(
    request: TelegramNotificationRequest,
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"])),
    db: Session = Depends(get_db),
):
    """Отправить уведомление через Telegram бота"""
    try:
        bot = get_enhanced_telegram_bot()
        api_service = TelegramBotManagementApiService(db)

        if not bot.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram bot is not active",
            )

        success_count = 0

        if request.send_to_all_admins:
            # Отправляем всем администраторам
            await bot.send_admin_notification(request.message, db)
            success_count = api_service.count_admin_recipients()

        elif request.send_to_all_users:
            # Отправляем всем пользователям
            all_user_ids = api_service.list_active_user_recipients()
            success_count = await bot.send_bulk_notification(
                request.message, all_user_ids, db
            )

        elif request.user_ids:
            # Отправляем конкретным пользователям
            success_count = await bot.send_bulk_notification(
                request.message, request.user_ids, db
            )

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No recipients specified",
            )

        return {
            "success": True,
            "message": f"Notification sent to {success_count} users",
            "sent_count": success_count,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise _telegram_bot_management_http_error(
            e, "send_telegram_notification"
        ) from e


@router.post("/send-admin-alert", response_model=dict[str, Any])
async def send_admin_alert(
    message: str,
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"])),
    db: Session = Depends(get_db),
):
    """Отправить срочное уведомление администраторам"""
    try:
        bot = get_enhanced_telegram_bot()

        if not bot.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram bot is not active",
            )

        alert_message = f"🚨 **СРОЧНОЕ УВЕДОМЛЕНИЕ**\\n\\n{message}\\n\\n⏰ {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"

        await bot.send_admin_notification(alert_message, db)

        return {"success": True, "message": "Admin alert sent successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise _telegram_bot_management_http_error(e, "send_admin_alert") from e


@router.get("/users-with-telegram", response_model=dict[str, Any])
async def get_users_with_telegram(
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"])),
    db: Session = Depends(get_db),
):
    """Получить список пользователей с настроенным Telegram"""
    try:
        return TelegramBotManagementApiService(db).get_users_with_telegram_payload()

    except Exception as e:
        raise _telegram_bot_management_http_error(e, "get_users_with_telegram") from e


@router.post("/test-bot", response_model=dict[str, Any])
async def test_telegram_bot(
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"])),
    db: Session = Depends(get_db),
):
    """Тестирование Telegram бота"""
    try:
        bot = get_enhanced_telegram_bot()

        if not current_user.telegram_chat_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your account is not linked to Telegram",
            )

        test_message = f"""🤖 **Тест Telegram бота**

✅ Бот работает корректно!
👤 Администратор: {current_user.full_name}
⏰ Время теста: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}

Все системы функционируют нормально."""

        success = await bot._send_message(
            current_user.telegram_chat_id, test_message, parse_mode="Markdown"
        )

        if success:
            return {"success": True, "message": "Test message sent successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send test message",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise _telegram_bot_management_http_error(e, "test_telegram_bot") from e


@router.post("/broadcast-system-message", response_model=dict[str, Any])
async def broadcast_system_message(
    message: str,
    message_type: str = "info",  # info, warning, error, success
    current_user: User = Depends(require_roles(["SuperAdmin"])),
    db: Session = Depends(get_db),
):
    """Системное сообщение для всех пользователей (только для SuperAdmin)"""
    try:
        bot = get_enhanced_telegram_bot()
        api_service = TelegramBotManagementApiService(db)

        if not bot.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram bot is not active",
            )

        # Иконки для разных типов сообщений
        icons = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "success": "✅"}

        icon = icons.get(message_type, "📢")

        system_message = f"""{icon} **СИСТЕМНОЕ СООБЩЕНИЕ**

{message}

⏰ {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
👤 Отправитель: {current_user.full_name}"""

        # Отправляем всем активным пользователям
        all_user_ids = api_service.list_active_user_recipients()

        success_count = await bot.send_bulk_notification(
            system_message, all_user_ids, db
        )

        return {
            "success": True,
            "message": f"System message broadcast to {success_count} users",
            "sent_count": success_count,
            "total_users": len(all_user_ids),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise _telegram_bot_management_http_error(e, "broadcast_system_message") from e


@router.get("/bot-commands", response_model=dict[str, Any])
async def get_bot_commands(
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"]))
):
    """Получить список доступных команд бота"""
    try:
        user_commands = [
            {"command": "/start", "description": "Начать работу с ботом"},
            {"command": "/help", "description": "Показать справку"},
            {"command": "/menu", "description": "Главное меню"},
            {"command": "/appointments", "description": "Мои записи"},
            {"command": "/book", "description": "Записаться на прием"},
            {"command": "/cancel", "description": "Отменить запись"},
            {"command": "/reschedule", "description": "Перенести запись"},
            {"command": "/profile", "description": "Мой профиль"},
            {"command": "/doctors", "description": "Список врачей"},
            {"command": "/services", "description": "Наши услуги"},
            {"command": "/queue", "description": "Текущая очередь"},
            {"command": "/status", "description": "Статус записей"},
            {"command": "/feedback", "description": "Обратная связь"},
            {"command": "/emergency", "description": "Экстренная помощь"},
            {"command": "/language", "description": "Изменить язык"},
            {"command": "/notifications", "description": "Настройки уведомлений"},
        ]

        admin_commands = [
            {"command": "/admin_stats", "description": "Статистика клиники"},
            {"command": "/admin_queues", "description": "Управление очередями"},
            {"command": "/admin_patients", "description": "Управление пациентами"},
            {"command": "/admin_appointments", "description": "Управление записями"},
            {"command": "/admin_doctors", "description": "Управление врачами"},
            {"command": "/admin_services", "description": "Управление услугами"},
            {
                "command": "/admin_notifications",
                "description": "Управление уведомлениями",
            },
            {"command": "/admin_reports", "description": "Отчеты"},
            {"command": "/admin_backup", "description": "Резервное копирование"},
            {"command": "/admin_settings", "description": "Настройки системы"},
        ]

        return {
            "user_commands": user_commands,
            "admin_commands": admin_commands,
            "total_commands": len(user_commands) + len(admin_commands),
        }

    except Exception as e:
        raise _telegram_bot_management_http_error(e, "get_bot_commands") from e
