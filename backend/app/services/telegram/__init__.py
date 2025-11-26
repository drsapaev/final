"""
Telegram сервисы для системы клиники
"""
from .bot import telegram_bot, ClinicTelegramBot
from .notifications import notification_service, TelegramNotificationService

__all__ = [
    "telegram_bot",
    "ClinicTelegramBot",
    "notification_service",
    "TelegramNotificationService"
]
