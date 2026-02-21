"""
API endpoints для управления расширенным Telegram ботом
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import User
from app.services.telegram_bot_enhanced import get_enhanced_telegram_bot
from app.repositories.telegram_bot_management_api_repository import TelegramBotManagementApiRepository

router = APIRouter()



def _repo(db: Session) -> TelegramBotManagementApiRepository:
    return TelegramBotManagementApiRepository(db)

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
        # Подсчитываем пользователей с Telegram
        total_users = _repo(db).query(User).filter(User.telegram_chat_id.isnot(None)).count()

        # Активные пользователи (с активным Telegram)
        active_users = (
            _repo(db).query(User)
            .filter(User.telegram_chat_id.isnot(None), User.is_active == True)
            .count()
        )

        # Администраторы с Telegram
        admin_users = (
            _repo(db).query(User)
            .filter(
                User.telegram_chat_id.isnot(None),
                User.role.in_(["Admin", "SuperAdmin"]),
            )
            .count()
        )

        # TODO: Добавить статистику сообщений и команд из базы данных
        messages_sent_today = 0
        commands_processed_today = 0

        return TelegramBotStatsResponse(
            total_users=total_users,
            active_users=active_users,
            admin_users=admin_users,
            messages_sent_today=messages_sent_today,
            commands_processed_today=commands_processed_today,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting bot stats: {str(e)}",
        )


@router.post("/send-notification")
async def send_telegram_notification(
    request: TelegramNotificationRequest,
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"])),
    db: Session = Depends(get_db),
):
    """Отправить уведомление через Telegram бота"""
    try:
        bot = get_enhanced_telegram_bot()

        if not bot.active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram bot is not active",
            )

        success_count = 0

        if request.send_to_all_admins:
            # Отправляем всем администраторам
            await bot.send_admin_notification(request.message, db)
            success_count = (
                _repo(db).query(User)
                .filter(
                    User.role.in_(["Admin", "SuperAdmin"]),
                    User.telegram_chat_id.isnot(None),
                )
                .count()
            )

        elif request.send_to_all_users:
            # Отправляем всем пользователям
            all_user_ids = [
                user.id
                for user in _repo(db).query(User)
                .filter(User.telegram_chat_id.isnot(None), User.is_active == True)
                .all()
            ]
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending notification: {str(e)}",
        )


@router.post("/send-admin-alert")
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending admin alert: {str(e)}",
        )


@router.get("/users-with-telegram")
async def get_users_with_telegram(
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"])),
    db: Session = Depends(get_db),
):
    """Получить список пользователей с настроенным Telegram"""
    try:
        users = _repo(db).query(User).filter(User.telegram_chat_id.isnot(None)).all()

        result = []
        for user in users:
            result.append(
                {
                    "id": user.id,
                    "username": user.username,
                    "full_name": user.full_name,
                    "role": user.role,
                    "telegram_chat_id": user.telegram_chat_id,
                    "is_active": user.is_active,
                    "created_at": user.created_at,
                }
            )

        return {"users": result, "total_count": len(result)}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting users: {str(e)}",
        )


@router.post("/test-bot")
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error testing bot: {str(e)}",
        )


@router.post("/broadcast-system-message")
async def broadcast_system_message(
    message: str,
    message_type: str = "info",  # info, warning, error, success
    current_user: User = Depends(require_roles(["SuperAdmin"])),
    db: Session = Depends(get_db),
):
    """Системное сообщение для всех пользователей (только для SuperAdmin)"""
    try:
        bot = get_enhanced_telegram_bot()

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
        all_user_ids = [
            user.id
            for user in _repo(db).query(User)
            .filter(User.telegram_chat_id.isnot(None), User.is_active == True)
            .all()
        ]

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error broadcasting system message: {str(e)}",
        )


@router.get("/bot-commands")
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting bot commands: {str(e)}",
        )
