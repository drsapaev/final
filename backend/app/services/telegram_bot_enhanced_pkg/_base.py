"""Base infrastructure for telegram_bot_enhanced_pkg package.

Split from telegram_bot_enhanced.py.
"""
from __future__ import annotations

"""
Расширенный Telegram Bot с дополнительными командами и интеграцией с админ-панелью
"""

import asyncio
import json
import logging
from datetime import date, datetime

import httpx
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.crud import (
    clinic as crud_doctor,
)
from app.crud import (
    service as crud_service,
)
from app.crud import (
    user as crud_user,
)
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.services.telegram_bot import TelegramBotService

logger = logging.getLogger(__name__)



class EnhancedTelegramBotServiceMixinBase:
    """Type-hint anchor for EnhancedTelegramBotService mixins."""
