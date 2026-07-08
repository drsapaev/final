"""Channels mixin for NotificationSenderService.

Split from notifications.py.
"""
from __future__ import annotations

from app.services.notifications_pkg._base import (
    NotificationSenderMixinBase,
    logger,
    settings,
    Any,
    Session,
    datetime,
    UTC,
    httpx,
    smtplib,
    MIMEMultipart,
    MIMEText,
    escape,
    _jinja_env,
    crud_notification_history,
    crud_notification_template,
    crud_user_notification_settings,
    NotificationHistory,
    User,
    NotificationHistoryCreate,
    get_fcm_service,
    get_notification_platform_service,
    get_notification_ws_manager,
    telegram_bot,
)


class ChannelsMixin(NotificationSenderMixinBase):
    """Channels methods for NotificationSenderService."""

    async def send_email(
        self, to_email: str, subject: str, body: str, html_body: str | None = None
    ) -> bool:
        """Отправка email уведомления"""
        if not all([self.smtp_username, self.smtp_password]):
            logger.warning("SMTP credentials не настроены")
            return False

        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._send_email_sync, to_email, subject, body, html_body
        )


    def _send_email_sync(
        self, to_email: str, subject: str, body: str, html_body: str | None = None
    ) -> bool:
        """Синхронная отправка email (для запуска в executor)"""
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = self.smtp_username
            msg["To"] = to_email
            msg["Subject"] = subject

            # Добавляем текстовую версию
            text_part = MIMEText(body, "plain", "utf-8")
            msg.attach(text_part)

            # Добавляем HTML версию, если есть
            if html_body:
                html_part = MIMEText(html_body, "html", "utf-8")
                msg.attach(html_part)

            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)

            # Отправляем письмо
            server.send_message(msg)
            server.quit()

            # NOTIF-REAUDIT-28 P1: PII-safe logging
            logger.info("Email sent", extra={"has_recipient": bool(to_email)})
            return True

        except Exception as e:
            logger.error(f"Ошибка отправки email: {e}")
            return False


    async def send_telegram(self, message: str, chat_id: str | None = None) -> bool:
        """Отправка уведомления в Telegram"""
        if not self.telegram_bot_token:
            logger.warning("Telegram bot token не настроен")
            return False

        chat_id = chat_id or self.telegram_chat_id
        if not chat_id:
            logger.warning("Telegram chat ID не настроен")
            return False

        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            data = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}

            async with httpx.AsyncClient() as client:
                response = await client.post(url, data=data, timeout=10)
                response.raise_for_status()

            # NOTIF-REAUDIT-28 P1: PII-safe logging
            logger.info("Telegram notification sent", extra={"has_chat_id": bool(chat_id)})
            return True

        except Exception as e:
            logger.error(f"Ошибка отправки Telegram: {e}")
            return False


    async def send_sms(self, phone: str, message: str) -> bool:
        """Отправка SMS уведомления"""
        try:
            from app.services.sms_providers import get_sms_manager

            sms_manager = get_sms_manager()
            response = await sms_manager.send_sms(phone, message)

            if response.success:
                # NOTIF-REAUDIT-28 P1: PII-safe logging
                logger.info("SMS sent", extra={"provider": getattr(response, "provider", "unknown")})
                return True
            else:
                logger.error(f"Ошибка отправки SMS ({response.provider}): {response.error}")
                return False

        except Exception as e:
            logger.error(f"Ошибка отправки SMS: {e}")
            return False


    async def send_push(
        self,
        user_id: int,
        title: str,
        message: str,
        data: dict[str, Any] | None = None,
        db: Session | None = None,
    ) -> bool:
        """Отправка Push-уведомления (Mobile + WebSocket)"""
        try:
            notification_type = _normalize_notification_event_type(
                data.get("type") if data else None,
                fallback="notification",
            )
            platform_payload = {
                "type": notification_type,
                "title": title,
                "message": message,
                "data": data or {},
                "timestamp": datetime.now(UTC).isoformat(),
            }

            if db:
                user = db.query(User).filter(User.id == user_id).first()
                if not user:
                    logger.warning("Push target user not found")
                    return False

                platform_service = self._platform_service(db)
                await platform_service.record_delivery_for_user(
                    user=user,
                    event_type=notification_type,
                    title=title,
                    message=message,
                    source_module="notifications",
                    recipient_type="patient" if (user.role or "").lower() == "patient" else "user",
                    payload_snapshot={
                        "title": title,
                        "message": message,
                        "metadata": data or {},
                    },
                    transport_type=notification_type,
                )

                # Legacy audit trail remains for external/mobile channels.
                try:
                    notification_data = {
                        "recipient_type": "patient",
                        "recipient_id": user_id,
                        "recipient_contact": "mobile_app",
                        "notification_type": notification_type,
                        "channel": "mobile",
                        "subject": title,
                        "content": message,
                        "status": "sent",
                    }
                    crud_notification_history.create(
                        db, obj_in=NotificationHistoryCreate(**notification_data)
                    )
                except Exception as hist_e:
                    logger.error(
                        "Failed to save notification history",
                        extra={
                            "error_type": type(hist_e).__name__,
                        },
                    )

                # Отправляем FCM только если есть токен
                if user.device_token:
                    await self.fcm_service.send_notification(
                        device_token=user.device_token,
                        title=title,
                        body=message,
                        data=data or {},
                    )
            else:
                try:
                    ws_manager = get_notification_ws_manager()
                    await ws_manager.send_json(platform_payload, user_id)
                except Exception as ws_e:
                    logger.warning(
                        "Failed to send WebSocket notification without DB",
                        extra={
                            "error_type": type(ws_e).__name__,
                        },
                    )

            return True
        except Exception as e:
            logger.error(
                "Push notification delivery failed",
                extra={
                    "error_type": type(e).__name__,
                },
            )
            return False


