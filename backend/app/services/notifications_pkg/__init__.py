"""notifications_pkg — split from notifications.py (2395 LOC).

Re-exports NotificationSenderService and notification_sender_service
for backward compatibility.
"""
from __future__ import annotations

from app.services.notifications_pkg._base import (
    NotificationSenderMixinBase,
    logger,
    settings,
)
from app.services.notifications_pkg._helpers import (
    _fresh_db,
    _normalize_notification_event_type,
    _normalize_patient_telegram_language,
    _safe_patient_telegram_value,
    _patient_telegram_event_message,
)
from app.services.notifications_pkg._core import CoreMixin
from app.services.notifications_pkg._canonical import CanonicalMixin
from app.services.notifications_pkg._channels import ChannelsMixin
from app.services.notifications_pkg._appointments import AppointmentsMixin
from app.services.notifications_pkg._system import SystemMixin
from app.services.notifications_pkg._templated import TemplatedMixin
from app.services.notifications_pkg._medical import MedicalMixin
from app.services.notifications_pkg._formatting import FormattingMixin
from app.services.notifications_pkg._reminders import RemindersMixin

__all__ = ["NotificationSenderService", "notification_sender_service"]


class NotificationSenderService(
    CoreMixin,
    CanonicalMixin,
    ChannelsMixin,
    AppointmentsMixin,
    SystemMixin,
    TemplatedMixin,
    MedicalMixin,
    FormattingMixin,
    RemindersMixin,
    NotificationSenderMixinBase,
):
    """Main notification sender service.

    Composed of focused mixin modules under notifications_pkg/.
    """

    def __init__(self):
        self._email_settings = None
        self._sms_settings = None


notification_sender_service = NotificationSenderService()
