"""Base infrastructure for telegram_bot_enhanced_pkg package.

Split from telegram_bot_enhanced.py.
"""
from __future__ import annotations

"""
Расширенный Telegram Bot с дополнительными командами и интеграцией с админ-панелью
"""

import asyncio  # noqa: F401
import json  # noqa: F401
import logging  # noqa: F401
from datetime import date, datetime  # noqa: F401

import httpx  # noqa: F401
from sqlalchemy import and_, func  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

from app.crud import (  # noqa: F401
    clinic as crud_doctor,
)
from app.crud import (  # noqa: F401
    service as crud_service,
)
from app.crud import (  # noqa: F401
    user as crud_user,
)
from app.models.appointment import Appointment  # noqa: F401
from app.models.clinic import Doctor  # noqa: F401
from app.models.online_queue import DailyQueue  # noqa: F401
from app.models.patient import Patient  # noqa: F401
from app.models.service import Service  # noqa: F401
from app.models.user import User  # noqa: F401
from app.services.telegram_bot import TelegramBotService  # noqa: F401

logger = logging.getLogger(__name__)



class EnhancedTelegramBotServiceMixinBase:
    """Type-hint anchor for EnhancedTelegramBotService mixins."""
