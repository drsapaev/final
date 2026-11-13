"""Core mixin for NotificationSenderService.

Split from notifications.py.
"""
from __future__ import annotations

from app.services.notifications_pkg._base import (
    Any,
    NotificationSenderMixinBase,
    Session,
    crud_user_notification_settings,
    _jinja_env,
    get_fcm_service,
    get_notification_platform_service,
    logger,
    settings,
    telegram_bot,
)
from app.services.notifications_pkg._helpers import _normalize_notification_event_type


class CoreMixin(NotificationSenderMixinBase):
    """Core methods for NotificationSenderService."""

    def __init__(self):
        self.smtp_server = getattr(settings, "SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = getattr(settings, "SMTP_PORT", 587)
        self.smtp_username = getattr(settings, "SMTP_USERNAME", None)
        self.smtp_password = getattr(settings, "SMTP_PASSWORD", None)
        self.smtp_from = getattr(settings, "SMTP_FROM", None)

        self.telegram_bot_token = settings.TELEGRAM_BOT_TOKEN

        self.sms_api_key = getattr(settings, "SMS_API_KEY", None)
        self.sms_api_url = getattr(settings, "SMS_API_URL", None)

        # Интеграция с Telegram ботом
        self.telegram_bot = telegram_bot

        # Интеграция с FCM
        self.fcm_service = get_fcm_service()


    def _platform_service(self, db: Session):
        return get_notification_platform_service(db)

    @staticmethod
    def _notification_preference_suffix(event_type: str) -> str | None:
        normalized = _normalize_notification_event_type(
            event_type, fallback="notification"
        )
        return {
            "appointment_reminder": "appointment_reminder",
            "appointment_confirmation": "appointment_confirmation",
            "visit_confirmation": "appointment_confirmation",
            "schedule_change": "appointment_cancellation",
            "payment_notification": "payment_receipt",
            "payment_created": "payment_receipt",
            "payment_paid": "payment_receipt",
            "security_alert": "security_alerts",
            "system_alert": "system_updates",
            "registrar_system_alert": "system_updates",
            "queue_update": "system_updates",
            "queue_status_changed": "system_updates",
            "patient_registered": "system_updates",
        }.get(normalized)

    def _channel_opted_in(
        self,
        *,
        db: Session | None,
        user_id: int | None,
        channel: str,
        event_type: str,
    ) -> bool:
        """Honor global and event-specific channel preferences when present."""
        if db is None or user_id is None:
            return True

        from app.models.user_profile import UserPreferences

        preferences = (
            db.query(UserPreferences)
            .filter(UserPreferences.user_id == user_id)
            .first()
        )
        global_field = {
            "email": "email_notifications",
            "sms": "sms_notifications",
            "push": "push_notifications",
        }.get(channel)
        if (
            preferences is not None
            and global_field
            and getattr(preferences, global_field, True) is False
        ):
            return False

        normalized_event_type = _normalize_notification_event_type(
            event_type, fallback="notification"
        )
        suffix = self._notification_preference_suffix(normalized_event_type) or normalized_event_type
        settings = crud_user_notification_settings.get_by_user_id(
            db, user_id=user_id
        )
        preference_field = f"{channel}_{suffix}"
        return not (
            settings is not None
            and hasattr(settings, preference_field)
            and getattr(settings, preference_field) is False
        )

    def _patient_channel_opted_in(
        self,
        *,
        db: Session | None,
        patient_id: int | None,
        channel: str,
        event_type: str,
    ) -> bool:
        if db is None or patient_id is None:
            return True

        from app.models.patient import Patient

        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        return self._channel_opted_in(
            db=db,
            user_id=patient.user_id if patient is not None else None,
            channel=channel,
            event_type=event_type,
        )


    @staticmethod
    def _extract_prefixed_user_id(actor_ref: str | None, prefix: str) -> int | None:
        normalized = str(actor_ref or "").strip().lower()
        expected_prefix = prefix.lower()
        if not normalized.startswith(expected_prefix):
            return None

        raw_value = normalized[len(expected_prefix):].strip()
        if not raw_value.isdigit():
            return None

        return int(raw_value)

    @staticmethod


    def _payload_snapshot(
        title: str,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "title": title,
            "message": message,
            "metadata": metadata or {},
        }


    def render_template(self, template_text: str, data: dict[str, Any]) -> str:
        """Рендеринг шаблона с данными.

        NOTIF-REAUDIT-28 P1-1: использует Environment с autoescape=True
        для защиты от SSTI/XSS.
        """
        try:
            template = _jinja_env.from_string(template_text)
            return template.render(**data)
        except Exception as e:
            logger.error(f"Ошибка рендеринга шаблона: {e}")
            return template_text


