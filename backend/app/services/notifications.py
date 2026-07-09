"""Backward-compatible shim for the notifications package.

Originally a 2406-LOC god file — now split into focused mixin modules
under :mod:`app.services.notifications_pkg`.
"""
from __future__ import annotations

from datetime import datetime  # noqa: F401

from app.services.notifications_pkg import (  # noqa: F401
    NotificationSenderService,
    notification_sender_service,
)
from app.services.notifications_pkg._helpers import (  # noqa: F401
    _fresh_db,
    _normalize_notification_event_type,
    _normalize_patient_telegram_language,
    _patient_telegram_event_message,
    _safe_patient_telegram_value,
)

# Backward-compat alias: some modules import notification_service
# (the old name) instead of notification_sender_service.
notification_service = notification_sender_service

__all__ = [
    "NotificationSenderService",
    "notification_sender_service",
    "notification_service",
    "_fresh_db",
    "_normalize_notification_event_type",
    "_normalize_patient_telegram_language",
    "_safe_patient_telegram_value",
    "_patient_telegram_event_message",
]
