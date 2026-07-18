"""Core mixin for NotificationSenderService.

Split from notifications.py.
"""
from __future__ import annotations

from app.services.notifications_pkg._base import (
    Any,
    NotificationSenderMixinBase,
    Session,
    _jinja_env,
    get_fcm_service,
    get_notification_platform_service,
    logger,
    settings,
    telegram_bot,
)


class CoreMixin(NotificationSenderMixinBase):
    """Core methods for NotificationSenderService."""

    def __init__(self):
        self.smtp_server = getattr(settings, "SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = getattr(settings, "SMTP_PORT", 587)
        self.smtp_username = getattr(settings, "SMTP_USERNAME", None)
        self.smtp_password = getattr(settings, "SMTP_PASSWORD", None)

        self.telegram_bot_token = settings.TELEGRAM_BOT_TOKEN
        self.telegram_chat_id = settings.TELEGRAM_CHAT_ID

        self.sms_api_key = getattr(settings, "SMS_API_KEY", None)
        self.sms_api_url = getattr(settings, "SMS_API_URL", None)

        # Интеграция с Telegram ботом
        self.telegram_bot = telegram_bot

        # Интеграция с FCM
        self.fcm_service = get_fcm_service()


    def _platform_service(self, db: Session):
        return get_notification_platform_service(db)


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


