"""
Telegram сервисы для системы клиники
"""

from .bot import ClinicTelegramBot, telegram_bot

__all__ = [
    "telegram_bot",
    "ClinicTelegramBot",
]
