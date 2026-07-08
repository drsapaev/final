"""Base infrastructure for notifications package.

Split from notifications.py (2395 LOC → modular).
"""
from __future__ import annotations

import logging
import smtplib
from datetime import datetime, UTC
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from typing import Any

import httpx
from jinja2 import Environment, select_autoescape
from sqlalchemy.orm import Session

from app.core.config import settings
from app.crud.notification import (
    crud_notification_history,
    crud_notification_template,
)
from app.crud.user_management import (
    user_notification_settings as crud_user_notification_settings,
)
from app.models.notification import NotificationHistory
from app.models.user import User
from app.schemas.notification import NotificationHistoryCreate
from app.services.fcm_service import get_fcm_service
from app.services.notification_platform_service import get_notification_platform_service
from app.services.notification_websocket import get_notification_ws_manager
from app.services.telegram.bot import telegram_bot

logger = logging.getLogger(__name__)

_jinja_env = Environment(autoescape=True)


class NotificationSenderMixinBase:
    """Type-hint anchor for NotificationSenderService mixins."""

    if False:
        _email_settings: Any
        _sms_settings: Any
