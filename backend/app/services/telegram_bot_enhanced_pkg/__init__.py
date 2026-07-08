"""telegram_bot_enhanced_pkg — split from telegram_bot_enhanced.py.

Re-exports EnhancedTelegramBotService for backward compatibility.
"""
from __future__ import annotations

from app.services.telegram_bot_enhanced_pkg._admin import AdminMixin
from app.services.telegram_bot_enhanced_pkg._appointments import AppointmentsMixin
from app.services.telegram_bot_enhanced_pkg._base import (
    EnhancedTelegramBotServiceMixinBase,
)
from app.services.telegram_bot_enhanced_pkg._core import CoreMixin
from app.services.telegram_bot_enhanced_pkg._info import InfoMixin
from app.services.telegram_bot_enhanced_pkg._patient import PatientMixin

__all__ = ["EnhancedTelegramBotService"]


class EnhancedTelegramBotService(
    CoreMixin,
    AdminMixin,
    PatientMixin,
    AppointmentsMixin,
    InfoMixin,
    EnhancedTelegramBotServiceMixinBase,
):
    """Composed of focused mixin modules under telegram_bot_enhanced_pkg/."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

# Global instance for backward compatibility
enhanced_telegram_bot = EnhancedTelegramBotService()
