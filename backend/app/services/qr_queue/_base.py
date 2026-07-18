"""
Сервис для управления QR очередями
"""

from __future__ import annotations

import base64  # noqa: F401
import io  # noqa: F401
import logging  # noqa: F401
import re  # noqa: F401
import secrets  # noqa: F401
import socket  # noqa: F401
from datetime import UTC, date, datetime, timedelta  # noqa: F401
from typing import TYPE_CHECKING, Any  # noqa: F401

import qrcode  # noqa: F401
from sqlalchemy import func  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

from app.core.config import settings  # noqa: F401
from app.models.clinic import Doctor  # noqa: F401
from app.models.online_queue import (  # noqa: F401
    DailyQueue,
    OnlineQueueEntry,
    QueueJoinSession,
    QueueStatistics,
    QueueToken,
)
from app.models.patient import Patient  # noqa: F401
from app.models.user import User  # noqa: F401
from app.services.queue_domain_service import QueueDomainService  # noqa: F401
from app.services.queue_service import (  # noqa: F401
    QueueConflictError,
    QueueNotFoundError,
    QueueValidationError,
    queue_service,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

JOIN_SESSION_PROCESSING_STATUS = "joining"


def _now(tz=None) -> datetime:
    """Return the current datetime, honoring test monkeypatches.

    Tests freeze time by patching ``app.services.qr_queue_service.datetime``
    (and ``app.services.queue_service.datetime``) with a ``FixedDateTime``
    subclass. The split modules under ``qr_queue`` import ``datetime``
    directly from the stdlib, so a plain ``datetime.now()`` would bypass the
    patch. Look the class up via the public shim module at call time so the
    patched class (if any) is used.
    """
    from app.services import qr_queue_service

    return qr_queue_service.datetime.now(tz)




class QRQueueServiceMixinBase:
    """Type-hint anchor for QRQueueService mixins."""
