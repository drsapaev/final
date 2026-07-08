"""
Сервис для управления QR очередями
"""

from __future__ import annotations

import base64
import io
import logging
import re
import secrets
import socket
from datetime import date, datetime, timedelta, UTC
from typing import TYPE_CHECKING, Any

import qrcode
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.clinic import Doctor
from app.models.online_queue import (
    DailyQueue,
    OnlineQueueEntry,
    QueueJoinSession,
    QueueStatistics,
    QueueToken,
)
from app.models.patient import Patient
from app.models.user import User
from app.services.queue_domain_service import QueueDomainService
from app.services.queue_service import (
    QueueConflictError,
    QueueNotFoundError,
    QueueValidationError,
    queue_service,
)

if TYPE_CHECKING:
    from app.models.visit import Visit

logger = logging.getLogger(__name__)

JOIN_SESSION_PROCESSING_STATUS = "joining"




class QRQueueServiceMixinBase:
    """Type-hint anchor for QRQueueService mixins."""
