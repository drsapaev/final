"""Backward-compatible shim for the telegram_bot_enhanced package.

Originally a 1668-LOC god file — now split into focused mixin modules
under :mod:`app.services.telegram_bot_enhanced_pkg`.
"""
from __future__ import annotations

from app.services.telegram_bot_enhanced_pkg import (
    EnhancedTelegramBotService,
    enhanced_telegram_bot,
)
from app.services.telegram_bot_enhanced_pkg._core import get_enhanced_telegram_bot

__all__ = [
    "EnhancedTelegramBotService",
    "enhanced_telegram_bot",
    "get_enhanced_telegram_bot",
]
