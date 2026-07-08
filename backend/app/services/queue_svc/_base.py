"""
Сервис для бизнес-логики очереди
"""

from __future__ import annotations

import copy
import logging
import secrets
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.crud.clinic import get_queue_settings
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueToken
from app.models.user import User
from app.models.visit import Visit
from app.services.queue_session import (
    get_or_create_session_id,
)

logger = logging.getLogger(__name__)


class QueueError(Exception):
    """Базовое исключение для сервиса очереди."""


class QueueValidationError(QueueError):
    """Ошибки валидации входных данных."""


class QueueConflictError(QueueError):
    """Конфликты (дубликаты, лимиты, блокировки)."""


class QueueNotFoundError(QueueError):
    """Запрашиваемая очередь или запись не найдены."""



class QueueBusinessServiceMixinBase:
    """Type-hint anchor with class-level constants."""


    SPECIALTY_START_NUMBERS = {
        "cardio": 1,  # Кардиолог - с №1
        "derma": 15,  # Дерматолог - с №15
        "dental": 3,  # Стоматолог - с №3
        "general": 1,  # Общий врач - с №1
        "default": 1,  # По умолчанию - с №1
    }

    ONLINE_QUEUE_START_TIME = time(7, 0)  # 07:00

    DEFAULT_MAX_SLOTS = 15
    QUEUE_QR_TOKEN_MIN_TTL_MINUTES = 5
    QUEUE_QR_TOKEN_MAX_TTL_MINUTES = 15
    QR_HIDDEN_PROFILE_KEYS = {"ecg", "general"}
    QR_SPECIALTY_ALIASES = {
        "cardio": "cardiology",
        "derma": "dermatology",
        "dentist": "stomatology",
        "dentistry": "stomatology",
        "laboratory": "lab",
    }









































































































































