"""Base infrastructure for notifications package.

Split from notifications.py (2395 LOC → modular).
"""
from __future__ import annotations

import logging  # noqa: F401
import smtplib  # noqa: F401
from datetime import UTC, datetime  # noqa: F401
from email.mime.multipart import MIMEMultipart  # noqa: F401
from email.mime.text import MIMEText  # noqa: F401
from html import escape  # noqa: F401
from typing import Any  # noqa: F401

import httpx  # noqa: F401
from jinja2 import Environment, select_autoescape  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

from app.core.config import settings  # noqa: F401
from app.crud.notification import (  # noqa: F401
    crud_notification_history,
    crud_notification_template,
)
from app.crud.user_management import (  # noqa: F401
    user_notification_settings as crud_user_notification_settings,
)
from app.models.notification import NotificationHistory  # noqa: F401
from app.models.user import User  # noqa: F401
from app.schemas.notification import NotificationHistoryCreate  # noqa: F401
from app.services.fcm_service import get_fcm_service  # noqa: F401
from app.services.notification_platform_service import (
    get_notification_platform_service,  # noqa: F401
)
from app.services.notification_websocket import (
    get_notification_ws_manager,  # noqa: F401
)
from app.services.telegram.bot import telegram_bot  # noqa: F401

logger = logging.getLogger(__name__)

_jinja_env = Environment(autoescape=True)


class NotificationSenderMixinBase:
    """Type-hint anchor for NotificationSenderService mixins."""

    if False:
        _email_settings: Any
        _sms_settings: Any
