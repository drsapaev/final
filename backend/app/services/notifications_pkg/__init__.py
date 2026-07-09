"""notifications_pkg — split from notifications.py (2395 LOC).

Re-exports NotificationSenderService and notification_sender_service
for backward compatibility.
"""
from __future__ import annotations

from app.services.notifications_pkg._appointments import AppointmentsMixin
from app.services.notifications_pkg._base import (
    NotificationSenderMixinBase,
        logger,  # noqa: F401,
        settings,  # noqa: F401,
)
from app.services.notifications_pkg._canonical import CanonicalMixin
from app.services.notifications_pkg._channels import ChannelsMixin
from app.services.notifications_pkg._core import CoreMixin
from app.services.notifications_pkg._formatting import FormattingMixin
from app.services.notifications_pkg._helpers import (
        _fresh_db,  # noqa: F401,
        _normalize_notification_event_type,  # noqa: F401,
        _normalize_patient_telegram_language,  # noqa: F401,
        _patient_telegram_event_message,  # noqa: F401,
        _safe_patient_telegram_value,  # noqa: F401,
)
from app.services.notifications_pkg._medical import MedicalMixin
from app.services.notifications_pkg._reminders import RemindersMixin
from app.services.notifications_pkg._system import SystemMixin
from app.services.notifications_pkg._templated import TemplatedMixin

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

    def __init__(self, db=None):
        self._db = db
        self._email_settings = None
        self._sms_settings = None


notification_sender_service = NotificationSenderService()
