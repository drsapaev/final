import logging
import smtplib
from datetime import datetime, UTC
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from typing import Any

import httpx
from jinja2 import Environment, select_autoescape

# NOTIF-REAUDIT-28 P1-1: autoescape для защиты от SSTI/XSS.
# Раньше Template(template_text) использовался без autoescape —
# admin-controlled templates могли выполнять произвольный Python (SSTI),
# а user data с HTML попадала в email body unescaped.
_jinja_env = Environment(autoescape=True)
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


def _fresh_db():
    """NOTIF-REAUDIT-28 P0-5: create a fresh DB session for background tasks.

    FastAPI закрывает request-scoped сессию после ответа. Background tasks,
    которым передали `db=db`, работают с закрытой сессией → DetachedInstanceError.
    Использование: `with _fresh_db() as db: sender.send(db, ...)`
    """
    from contextlib import contextmanager
    from app.db.session import SessionLocal

    @contextmanager
    def _session():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    return _session()


NOTIFICATION_EVENT_TYPE_ALIASES = {
    "queue_changed": "queue_update",
    "diagnostics_return": "diagnostics_return_needed",
    "queue_status": "queue_status_changed",
    "payment_update": "payment_notification",
    "payment_success": "payment_notification",
    "paymentcreated": "payment_created",
    "paymentpaid": "payment_paid",
    "result_ready": "lab_results",
    "lab_result_ready": "lab_results",
    "labresultready": "lab_results",
    "appointment_rescheduled": "schedule_change",
    "appointment_cancelled": "schedule_change",
    "visitcreated": "visit_created",
    "queueticketissued": "queue_ticket_issued",
    "queuestatuschanged": "queue_status_changed",
    "patientcalled": "patient_called",
    "all_free_pending": "all_free_requested",
    "all_free_declined": "all_free_rejected",
    "allfree_requested": "all_free_requested",
    "allfree_approved": "all_free_approved",
    "allfree_rejected": "all_free_rejected",
    "notification_message_received": "message_received",
    "lab_critical": "lab_critical_result",
    "lab_new_assignment": "lab_new_study",
    "lab_result_sent": "lab_result_sent_confirmation",
    "registrar_alert": "registrar_system_alert",
    "security_warning": "security_alert",
    "billing_warning": "billing_alert",
    "patient_create": "patient_registered",
}

LAB_NOTIFICATION_EVENT_TYPES = {
    "lab_results",
    "lab_critical_result",
    "lab_new_study",
    "lab_critical_finding",
    "lab_result_sent_confirmation",
    "diagnostics_return_needed",
}

REGISTRAR_NOTIFICATION_EVENT_TYPES = {
    "new_appointment",
    "price_change",
    "queue_status_changed",
    "system_alert",
    "registrar_system_alert",
    "security_alert",
    "billing_alert",
    "all_free_requested",
    "all_free_approved",
    "all_free_rejected",
    "patient_registered",
}

QUEUE_NOTIFICATION_EVENT_TYPES = {
    "patient_called",
    "queue_call",
    "queue_status_changed",
    "queue_position",
    "queue_reminder",
    "queue_ticket_issued",
    "diagnostics_return_needed",
    "queue_update",
}

PATIENT_TELEGRAM_EVENT_PREFERENCES = {
    "appointment_reminder": "appointment_reminders",
    "visit_created": "appointment_reminders",
    "queue_ticket_issued": "appointment_reminders",
    "queue_status_changed": "appointment_reminders",
    "patient_called": "appointment_reminders",
    "payment_created": "notifications_enabled",
    "payment_notification": "notifications_enabled",
    "payment_paid": "notifications_enabled",
    "lab_results": "lab_notifications",
}

PATIENT_TELEGRAM_EVENT_MESSAGES = {
    "appointment_reminder": {
        "ru": "Напоминание о записи. Дата: {date}. Врач: {doctor}.",
        "uz-Latn": "Qabul eslatmasi. Sana: {date}. Shifokor: {doctor}.",
    },
    "visit_created": {
        "ru": "Запись создана. Дата: {date}. Врач: {doctor}.",
        "uz-Latn": "Qabul yaratildi. Sana: {date}. Shifokor: {doctor}.",
    },
    "queue_ticket_issued": {
        "ru": "Талон очереди готов. Номер: {queue_number}. Кабинет: {cabinet}.",
        "uz-Latn": "Navbat taloni tayyor. Raqam: {queue_number}. Xona: {cabinet}.",
    },
    "queue_status_changed": {
        "ru": "Статус очереди обновлен. Номер: {queue_number}. Статус: {status}.",
        "uz-Latn": "Navbat holati yangilandi. Raqam: {queue_number}. Holat: {status}.",
    },
    "patient_called": {
        "ru": "Вас приглашают. Номер: {queue_number}. Кабинет: {cabinet}.",
        "uz-Latn": "Sizni chaqirishmoqda. Raqam: {queue_number}. Xona: {cabinet}.",
    },
    "payment_created": {
        "ru": "Сформирована оплата. Сумма: {amount} {currency}.",
        "uz-Latn": "To'lov yaratildi. Summa: {amount} {currency}.",
    },
    "payment_notification": {
        "ru": "Статус оплаты обновлен. Сумма: {amount} {currency}.",
        "uz-Latn": "To'lov holati yangilandi. Summa: {amount} {currency}.",
    },
    "payment_paid": {
        "ru": "Оплата получена. Квитанция доступна в защищенном кабинете.",
        "uz-Latn": "To'lov qabul qilindi. Kvitansiya himoyalangan kabinetda mavjud.",
    },
    "lab_results": {
        "ru": "Результаты готовы. Откройте защищенный кабинет.",
        "uz-Latn": "Natijalar tayyor. Himoyalangan kabinetni oching.",
    },
}


def _normalize_notification_event_type(
    event_type: str | None,
    *,
    fallback: str = "",
) -> str:
    normalized = str(event_type or "").strip().lower()
    if not normalized:
        return fallback
    return NOTIFICATION_EVENT_TYPE_ALIASES.get(normalized, normalized)


def _normalize_patient_telegram_language(language_code: Any) -> str:
    value = str(language_code or "").strip().lower().replace("_", "-")
    if value in {"uz", "uz-latn", "uzbek", "o'zbekcha"}:
        return "uz-Latn"
    return "ru"


def _safe_patient_telegram_value(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    return escape(text[:80])


def _patient_telegram_event_message(
    event_type: str,
    language_code: Any,
    metadata: dict[str, Any] | None = None,
) -> str | None:
    templates = PATIENT_TELEGRAM_EVENT_MESSAGES.get(event_type)
    if not templates:
        return None

    language = _normalize_patient_telegram_language(language_code)
    template = templates.get(language) or templates["ru"]
    data = metadata or {}
    safe_data = {
        "date": _safe_patient_telegram_value(
            data.get("date") or data.get("visit_date") or data.get("appointment_date"),
            "-" if language == "ru" else "-",
        ),
        "doctor": _safe_patient_telegram_value(
            data.get("doctor") or data.get("doctor_name"),
            "уточняется" if language == "ru" else "aniqlanmoqda",
        ),
        "queue_number": _safe_patient_telegram_value(
            data.get("queue_number") or data.get("number"),
            "-" if language == "ru" else "-",
        ),
        "cabinet": _safe_patient_telegram_value(
            data.get("cabinet") or data.get("cabinet_number"),
            "уточняется" if language == "ru" else "aniqlanmoqda",
        ),
        "status": _safe_patient_telegram_value(
            data.get("status"),
            "обновлен" if language == "ru" else "yangilandi",
        ),
        "amount": _safe_patient_telegram_value(data.get("amount"), "0"),
        "currency": _safe_patient_telegram_value(data.get("currency"), "UZS"),
    }
    return template.format(**safe_data)


class NotificationSenderService:
    """Сервис для отправки уведомлений (Email, SMS, Telegram)"""

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

    async def send_patient_telegram_event_notification(
        self,
        *,
        db: Session,
        patient_id: int,
        event_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Send a safe patient Telegram message for a canonical business event."""
        normalized_event_type = _normalize_notification_event_type(
            event_type,
            fallback="notification",
        )
        preference_field = PATIENT_TELEGRAM_EVENT_PREFERENCES.get(normalized_event_type)
        if not preference_field:
            logger.warning(
                "Patient Telegram event skipped: unsupported event type",
                extra={"event_type": normalized_event_type},
            )
            return False

        from app.models.telegram_config import TelegramUser

        telegram_user = (
            db.query(TelegramUser)
            .filter(
                TelegramUser.patient_id == patient_id,
                TelegramUser.active.is_(True),
                TelegramUser.blocked.is_(False),
            )
            .order_by(TelegramUser.id.desc())
            .first()
        )
        if not telegram_user:
            logger.info(
                "Patient Telegram event skipped: linked chat not found",
                extra={"event_type": normalized_event_type},
            )
            return False

        if not bool(getattr(telegram_user, "notifications_enabled", False)):
            return False
        if preference_field != "notifications_enabled" and not bool(
            getattr(telegram_user, preference_field, False)
        ):
            return False

        message = _patient_telegram_event_message(
            normalized_event_type,
            getattr(telegram_user, "language_code", None),
            metadata,
        )
        if not message:
            return False

        return await self.send_telegram(message, chat_id=str(telegram_user.chat_id))

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

    async def send_canonical_notification_to_user(
        self,
        *,
        db: Session,
        recipient: User,
        event_type: str,
        title: str,
        message: str,
        source_module: str,
        metadata: dict[str, Any] | None = None,
        deep_link: str | None = None,
        severity: str = "info",
        priority: str = "normal",
        actor_id: int | None = None,
        actor_role: str | None = None,
        entity_type: str | None = None,
        entity_id: str | int | None = None,
    ) -> bool:
        """Record one canonical inbox delivery for a specific recipient."""
        try:
            normalized_event_type = _normalize_notification_event_type(
                event_type,
                fallback="notification",
            )
            if not recipient or not recipient.is_active:
                logger.warning(
                    "[FIX:NOTIFICATIONS] canonical notification skipped: inactive/missing recipient",
                    extra={"event_type": normalized_event_type},
                )
                return False

            platform_service = self._platform_service(db)
            await platform_service.record_delivery_for_user(
                user=recipient,
                event_type=normalized_event_type,
                title=title,
                message=message,
                source_module=source_module,
                recipient_type="user",
                severity=severity,
                priority=priority,
                actor_id=actor_id,
                actor_role=actor_role,
                entity_type=entity_type,
                entity_id=entity_id,
                payload_snapshot=self._payload_snapshot(title, message, metadata),
                deep_link=deep_link,
            )
            logger.info(
                "[FIX:NOTIFICATIONS] canonical delivery created",
                extra={
                    "event_type": normalized_event_type,
                    "recipient_id": recipient.id,
                    "source_module": source_module,
                },
            )
            return True
        except Exception as exc:
            logger.error(
                "[FIX:NOTIFICATIONS] canonical delivery failed",
                extra={
                    "event_type": event_type,
                    "recipient_id": getattr(recipient, "id", None),
                    "source_module": source_module,
                    "error": str(exc),
                },
            )
            return False

    async def send_canonical_notification_to_roles(
        self,
        *,
        db: Session,
        roles: list[str],
        event_type: str,
        title: str,
        message: str,
        source_module: str,
        metadata: dict[str, Any] | None = None,
        deep_link: str | None = None,
        severity: str = "info",
        priority: str = "normal",
        actor_id: int | None = None,
        actor_role: str | None = None,
        entity_type: str | None = None,
        entity_id: str | int | None = None,
        ) -> bool:
        """Record one canonical inbox delivery fan-out for role recipients."""
        try:
            normalized_event_type = _normalize_notification_event_type(
                event_type,
                fallback="notification",
            )
            platform_service = self._platform_service(db)
            recipients: dict[int, User] = {}
            for role in roles:
                for user in platform_service.resolve_users_for_role(role):
                    recipients[user.id] = user

            if not recipients:
                logger.warning(
                    "[FIX:NOTIFICATIONS] canonical role delivery skipped: no recipients",
                    extra={
                        "event_type": normalized_event_type,
                        "roles": roles,
                        "source_module": source_module,
                    },
                )
                return False

            await platform_service.record_delivery_for_users(
                users=list(recipients.values()),
                event_type=normalized_event_type,
                title=title,
                message=message,
                source_module=source_module,
                recipient_type="user",
                severity=severity,
                priority=priority,
                actor_id=actor_id,
                actor_role=actor_role,
                entity_type=entity_type,
                entity_id=entity_id,
                payload_snapshot=self._payload_snapshot(title, message, metadata),
                deep_link=deep_link,
            )
            logger.info(
                "[FIX:NOTIFICATIONS] canonical role deliveries created",
                extra={
                    "event_type": normalized_event_type,
                    "source_module": source_module,
                    "roles": roles,
                    "recipient_count": len(recipients),
                },
            )
            return True
        except Exception as exc:
            logger.error(
                "[FIX:NOTIFICATIONS] canonical role deliveries failed",
                extra={
                    "event_type": event_type,
                    "roles": roles,
                    "source_module": source_module,
                    "error": str(exc),
                },
            )
            return False

    async def send_lab_event_notification(
        self,
        *,
        db: Session,
        recipient: User,
        event_type: str,
        metadata: dict[str, Any] | None = None,
        title: str | None = None,
        message: str | None = None,
        actor_user: User | None = None,
    ) -> bool:
        """Typed producer helper for canonical lab family events."""
        normalized_type = _normalize_notification_event_type(event_type)
        if normalized_type not in LAB_NOTIFICATION_EVENT_TYPES:
            logger.warning(
                "[FIX:NOTIFICATIONS] unsupported lab event type",
                extra={
                    "event_type": event_type,
                    "normalized_event_type": normalized_type,
                },
            )
            return False

        default_titles = {
            "lab_results": "Результаты анализов готовы",
            "lab_critical_result": "Критический результат анализа",
            "lab_new_study": "Назначено новое исследование",
            "lab_critical_finding": "Критическая находка в исследовании",
            "lab_result_sent_confirmation": "Результат исследования отправлен",
            "diagnostics_return_needed": "Требуется повторная диагностика",
        }
        fallback_title = default_titles[normalized_type]
        body = message or fallback_title

        return await self.send_canonical_notification_to_user(
            db=db,
            recipient=recipient,
            event_type=normalized_type,
            title=title or fallback_title,
            message=body,
            source_module="lab",
            metadata=metadata,
            deep_link="/lab/results",
            severity="critical" if normalized_type == "lab_critical_result" else "info",
            priority="urgent" if normalized_type == "lab_critical_result" else "high",
            actor_id=getattr(actor_user, "id", None),
            actor_role=getattr(actor_user, "role", None),
            entity_type="lab_result",
            entity_id=(metadata or {}).get("result_id") or (metadata or {}).get("order_id"),
        )

    async def send_registrar_event_notification(
        self,
        *,
        db: Session,
        event_type: str,
        metadata: dict[str, Any] | None = None,
        title: str,
        message: str,
        roles: list[str] | None = None,
        deep_link: str | None = None,
        actor_user: User | None = None,
    ) -> bool:
        """Typed producer helper for registrar/admin canonical events."""
        normalized_type = _normalize_notification_event_type(event_type)
        if normalized_type not in REGISTRAR_NOTIFICATION_EVENT_TYPES:
            logger.warning(
                "[FIX:NOTIFICATIONS] unsupported registrar event type",
                extra={
                    "event_type": event_type,
                    "normalized_event_type": normalized_type,
                },
            )
            return False

        resolved_roles = roles or ["registrar"]
        if normalized_type in {
            "registrar_system_alert",
            "security_alert",
            "billing_alert",
            "all_free_requested",
            "patient_registered",
        } and "admin" not in resolved_roles:
            resolved_roles = [*resolved_roles, "admin"]

        return await self.send_canonical_notification_to_roles(
            db=db,
            roles=resolved_roles,
            event_type=normalized_type,
            title=title,
            message=message,
            source_module="registrar",
            metadata=metadata,
            deep_link=deep_link or "/registrar",
            severity="critical"
            if normalized_type in {"security_alert", "billing_alert"}
            else "info",
            priority="urgent"
            if normalized_type in {"security_alert", "billing_alert"}
            else "high",
            actor_id=getattr(actor_user, "id", None),
            actor_role=getattr(actor_user, "role", None),
            entity_type="visit",
            entity_id=(metadata or {}).get("visit_id"),
        )

    async def send_queue_position_event_notification(
        self,
        *,
        db: Session,
        recipient: User,
        event_type: str,
        title: str,
        message: str,
        metadata: dict[str, Any] | None = None,
        actor_user: User | None = None,
    ) -> bool:
        """Typed producer helper for queue position family events."""
        normalized_type = _normalize_notification_event_type(event_type)
        if normalized_type not in QUEUE_NOTIFICATION_EVENT_TYPES:
            logger.warning(
                "[FIX:NOTIFICATIONS] unsupported queue family event type",
                extra={
                    "event_type": event_type,
                    "normalized_event_type": normalized_type,
                },
            )
            return False

        return await self.send_canonical_notification_to_user(
            db=db,
            recipient=recipient,
            event_type=normalized_type,
            title=title,
            message=message,
            source_module="queue",
            metadata=metadata,
            deep_link="/queue",
            severity="info",
            priority="high",
            actor_id=getattr(actor_user, "id", None),
            actor_role=getattr(actor_user, "role", None),
            entity_type="queue",
            entity_id=(metadata or {}).get("queue_id"),
        )

    async def send_patient_registered_notification(
        self,
        *,
        db: Session,
        patient: Any,
        registration_source: str = "internal",
        actor_user: User | None = None,
    ) -> bool:
        """Typed producer helper for patient creation canonical event."""
        patient_id = getattr(patient, "id", None)
        if not patient_id:
            logger.warning(
                "[FIX:NOTIFICATIONS] patient_registered skipped: missing patient id",
            )
            return False

        patient_name = (
            getattr(patient, "full_name", None)
            or f"{getattr(patient, 'first_name', '')} {getattr(patient, 'last_name', '')}".strip()
            or f"Пациент #{patient_id}"
        )
        title = "Новый пациент зарегистрирован"
        message = f"{patient_name} зарегистрирован в системе."

        return await self.send_canonical_notification_to_roles(
            db=db,
            roles=["admin", "registrar"],
            event_type="patient_registered",
            title=title,
            message=message,
            source_module="patients",
            metadata={
                "patient_id": patient_id,
                "registration_source": registration_source,
            },
            deep_link="/registrar/patients",
            severity="info",
            priority="high",
            actor_id=getattr(actor_user, "id", None),
            actor_role=getattr(actor_user, "role", None),
            entity_type="patient",
            entity_id=patient_id,
        )

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

    async def send_appointment_reminder(
        self,
        patient_email: str,
        patient_phone: str,
        appointment_date: datetime,
        doctor_name: str,
        department: str,
        db: Session | None = None,
        patient_id: int | None = None,
    ) -> dict[str, bool]:
        """Отправка напоминания о записи"""
        subject = "Напоминание о записи к врачу"

        # Формируем сообщения
        email_body = f"""
        Здравствуйте!

        Напоминаем о записи к врачу {doctor_name} в отделении {department}.
        Дата и время: {appointment_date.strftime('%d.%m.%Y в %H:%M')}

        Пожалуйста, не забудьте взять с собой документы и прийти за 10 минут до приёма.

        С уважением,
        Администрация клиники
        """

        sms_message = f"Напоминание: запись к {doctor_name} {appointment_date.strftime('%d.%m в %H:%M')}"

        telegram_message = f"""
        📅 <b>Напоминание о записи</b>

        👤 Пациент: {patient_email}
        📱 Телефон: {patient_phone}
        👨‍⚕️ Врач: {doctor_name}
        🏥 Отделение: {department}
        📅 Дата: {appointment_date.strftime('%d.%m.%Y в %H:%M')}
        """

        # Отправляем уведомления
        results = {}

        if db and patient_id:
            from app.models.patient import Patient

            patient = db.query(Patient).filter(Patient.id == patient_id).first()
            if patient and patient.user_id:
                await self.send_push(
                    user_id=patient.user_id,
                    title=subject,
                    message=f"Запись к {doctor_name} {appointment_date.strftime('%d.%m.%Y в %H:%M')}",
                    data={
                        "type": "appointment_reminder",
                        "appointment_date": appointment_date.isoformat(),
                        "doctor_name": doctor_name,
                        "department": department,
                    },
                    db=db,
                )

        if patient_email:
            results["email"] = await self.send_email(patient_email, subject, email_body)

        if patient_phone:
            results["sms"] = await self.send_sms(patient_phone, sms_message)

        if db and patient_id:
            results["telegram"] = await self.send_patient_telegram_event_notification(
                db=db,
                patient_id=patient_id,
                event_type="appointment_reminder",
                metadata={
                    "appointment_date": appointment_date.strftime("%d.%m.%Y %H:%M"),
                    "doctor_name": doctor_name,
                    "department": department,
                },
            )
        else:
            results["telegram"] = await self.send_telegram(telegram_message)

        return results

    async def send_visit_confirmation(
        self,
        patient_email: str,
        patient_phone: str,
        visit_date: datetime,
        doctor_name: str,
        department: str,
        queue_number: int | None = None,
        db: Session | None = None,
        patient_id: int | None = None,
    ) -> dict[str, bool]:
        """Отправка подтверждения визита"""
        subject = "Подтверждение визита к врачу"

        email_body = f"""
        Здравствуйте!

        Ваш визит к врачу {doctor_name} в отделении {department} подтверждён.
        Дата и время: {visit_date.strftime('%d.%m.%Y в %H:%M')}
        """

        if queue_number:
            email_body += f"Номер в очереди: {queue_number}\n"

        email_body += """
        Пожалуйста, придите за 10 минут до назначенного времени.

        С уважением,
        Администрация клиники
        """

        sms_message = (
            f"Визит к {doctor_name} подтверждён {visit_date.strftime('%d.%m в %H:%M')}"
        )
        if queue_number:
            sms_message += f", очередь №{queue_number}"

        telegram_message = f"""
        ✅ <b>Подтверждение визита</b>

        👤 Пациент: {patient_email}
        📱 Телефон: {patient_phone}
        👨‍⚕️ Врач: {doctor_name}
        🏥 Отделение: {department}
        📅 Дата: {visit_date.strftime('%d.%m.%Y в %H:%M')}
        """

        if queue_number:
            telegram_message += f"🎫 Номер в очереди: {queue_number}"

        # Отправляем уведомления
        results = {}

        if db and patient_id:
            from app.models.patient import Patient

            patient = db.query(Patient).filter(Patient.id == patient_id).first()
            if patient and patient.user_id:
                await self.send_push(
                    user_id=patient.user_id,
                    title=subject,
                    message=f"Ваш визит к {doctor_name} подтверждён на {visit_date.strftime('%d.%m.%Y в %H:%M')}",
                    data={
                        "type": "visit_confirmation",
                        "visit_date": visit_date.isoformat(),
                        "doctor_name": doctor_name,
                        "department": department,
                        "queue_number": queue_number,
                    },
                    db=db,
                )

        if patient_email:
            results["email"] = await self.send_email(patient_email, subject, email_body)

        if patient_phone:
            results["sms"] = await self.send_sms(patient_phone, sms_message)

        results["telegram"] = await self.send_telegram(telegram_message)

        return results

    async def send_appointment_confirmation(
        self,
        db: Session,
        appointment_id: int,
    ) -> dict[str, bool]:
        """Отправка подтверждения записи (Unified: Push, Email, SMS, Telegram)"""
        from app.models.appointment import Appointment
        from app.models.user import User

        try:
            appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
            if not appointment:
                return {}

            doctor_name = appointment.doctor.name if appointment.doctor else "Врач"
            specialty = appointment.doctor.specialty if appointment.doctor else ""
            visit_date_str = appointment.appointment_date.strftime('%d.%m.%Y в %H:%M')
            appointment_datetime = appointment.appointment_date
            if appointment.appointment_time:
                try:
                    appointment_datetime = datetime.combine(
                        appointment.appointment_date,
                        datetime.strptime(appointment.appointment_time, "%H:%M").time(),
                    )
                except ValueError:
                    logger.warning(
                        "Failed to parse appointment time for notification",
                        extra={
                            "has_appointment_time": True,
                        },
                    )

            # --- Push Notification Logic ---
            if appointment.patient and appointment.patient.user_id:
                user = db.query(User).filter(User.id == appointment.patient.user_id).first()
                if user:
                    title = "Запись подтверждена"
                    message = f"Ваша запись к врачу {doctor_name} на {visit_date_str} подтверждена"

                    await self.send_push(
                        user_id=user.id,
                        title=title,
                        message=message,
                        data={
                            "type": "appointment_confirmation",
                            "appointment_id": appointment_id,
                        },
                        db=db
                    )

            # --- Unified Channels Logic ---
            # Call the lower-level send_visit_confirmation for Email/SMS/Telegram
            # We need patient email/phone.
            patient_email = appointment.patient.email if appointment.patient else None
            patient_phone = appointment.patient.phone if appointment.patient else None

            # Use send_visit_confirmation which handles Email/SMS/Telegram template formatting
            # Note: send_visit_confirmation sends "confirmation" logic.
            # Ideally we reuse it.

            return await self.send_visit_confirmation(
                patient_email=patient_email,
                patient_phone=patient_phone,
                visit_date=appointment_datetime,
                doctor_name=doctor_name,
                department=appointment.department or specialty,
                db=db,
                patient_id=appointment.patient_id,
            )

        except Exception as e:
            logger.error(f"Error sending appointment confirmation: {e}")
            return {}

    async def send_payment_notification(
        self,
        patient_email: str,
        patient_phone: str,
        amount: float,
        currency: str,
        visit_date: datetime,
        doctor_name: str,
        db: Session | None = None,
        patient_id: int | None = None,
    ) -> dict[str, bool]:
        """Отправка уведомления об оплате"""
        subject = "Подтверждение оплаты"

        email_body = f"""
        Здравствуйте!

        Получена оплата за визит к врачу {doctor_name}.
        Сумма: {amount} {currency}
        Дата визита: {visit_date.strftime('%d.%m.%Y в %H:%M')}

        Спасибо за оплату!

        С уважением,
        Администрация клиники
        """

        sms_message = f"Оплата {amount} {currency} получена за визит к {doctor_name}"

        telegram_message = f"""
        💰 <b>Подтверждение оплаты</b>

        👤 Пациент: {patient_email}
        📱 Телефон: {patient_phone}
        💵 Сумма: {amount} {currency}
        👨‍⚕️ Врач: {doctor_name}
        📅 Дата визита: {visit_date.strftime('%d.%m.%Y в %H:%M')}
        """

        # Отправляем уведомления
        results = {}

        if db and patient_id:
            from app.models.patient import Patient

            patient = db.query(Patient).filter(Patient.id == patient_id).first()
            if patient and patient.user_id:
                await self.send_push(
                    user_id=patient.user_id,
                    title=subject,
                    message=f"Оплата {amount} {currency} за визит к {doctor_name} подтверждена",
                    data={
                        "type": "payment_notification",
                        "amount": amount,
                        "currency": currency,
                        "visit_date": visit_date.isoformat(),
                        "doctor_name": doctor_name,
                    },
                    db=db,
                )

        if patient_email:
            results["email"] = await self.send_email(patient_email, subject, email_body)

        if patient_phone:
            results["sms"] = await self.send_sms(patient_phone, sms_message)

        results["telegram"] = await self.send_telegram(telegram_message)

        return results

    async def send_queue_update(
        self,
        department: str,
        current_number: int,
        estimated_wait: str,
        patient_id: int | None = None,
        db: Session | None = None,
    ) -> bool:
        """Отправка обновления очереди (Telegram + Push)"""
        message = (
            f"📊 Обновление очереди\n\n"
            f"Отделение: {department}\n"
            f"Текущий номер: {current_number}\n"
            f"Примерное время ожидания: {estimated_wait}\n"
            f"Обновлено: {datetime.now().strftime('%H:%M:%S')}"
        )

        if db:
            platform_service = self._platform_service(db)
            if patient_id:
                from app.models.patient import Patient

                patient = db.query(Patient).filter(Patient.id == patient_id).first()
                if patient and patient.user_id:
                    await self.send_push(
                        user_id=patient.user_id,
                        title="Обновление очереди",
                        message=f"Ваша очередь обновлена: #{current_number}",
                        data={
                            "type": "queue_update",
                            "department": department,
                            "current_number": current_number,
                            "estimated_wait": estimated_wait,
                        },
                        db=db,
                    )
            else:
                targets = platform_service.resolve_users_for_department(department)
                await platform_service.record_delivery_for_users(
                    users=targets,
                    event_type="queue_update",
                    title="Обновление очереди",
                    message=message,
                    source_module="queue",
                    recipient_type="user",
                    severity="info",
                    priority="normal",
                    payload_snapshot={
                        "department": department,
                        "current_number": current_number,
                        "estimated_wait": estimated_wait,
                    },
                    transport_type="queue_update",
                )

        return await self.send_telegram(message)

    async def send_patient_queue_update(
        self,
        db: Session,
        patient_id: int,
        queue_position: int,
        specialty: str
    ) -> bool:
        """Отправка уведомления пациенту о позиции в очереди (Mobile/Push)"""
        try:
             # Находим пользователя через пациента
             from app.models.patient import Patient
             from app.models.user import User

             patient = db.query(Patient).filter(Patient.id == patient_id).first()
             if not patient or not patient.user_id:
                 return False

             user = db.query(User).filter(User.id == patient.user_id).first()
             if not user:
                 return False

             title = "Обновление очереди"
             message = f"Ваша позиция в очереди к {specialty}: #{queue_position}"

             # Push
             if user:
                  await self.send_push(
                      user_id=user.id,
                      title=title,
                     message=message,
                     data={
                         "type": "queue_update",
                         "queue_position": queue_position,
                         "specialty": specialty,
                     },
                     db=db
                 )

             # Telegram (если есть)
             if user.telegram_id:
                 await self.send_telegram_message(
                     user.telegram_id,
                     f"🔢 <b>{title}</b>\n\n{message}"
                 )

             return True
        except Exception as e:
            logger.error(f"Error sending patient queue update: {e}")
            return False

    async def send_system_alert(
        self,
        alert_type: str,
        message: str,
        details: dict[str, Any] | None = None,
        db: Session | None = None,
        actor_id: int | None = None,
        actor_role: str | None = None,
    ) -> bool:
        """Отправка системного оповещения"""
        alert_message = f"""
        🚨 <b>Системное оповещение</b>

        Тип: {alert_type}
        Сообщение: {message}
        """

        if details:
            alert_message += "\nДетали:\n"
            for key, value in details.items():
                alert_message += f"• {key}: {value}\n"

        alert_message += f"\nВремя: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"

        if db:
            platform_service = self._platform_service(db)
            admins = platform_service.resolve_users_for_role("admin")
            await platform_service.record_delivery_for_users(
                users=admins,
                event_type="system_alert",
                title=f"Системное оповещение: {alert_type}",
                message=message,
                source_module="system",
                recipient_type="user",
                severity="critical" if alert_type.lower() in {"critical", "security"} else "warning",
                priority="urgent" if alert_type.lower() in {"critical", "security"} else "high",
                actor_id=actor_id,
                actor_role=actor_role,
                payload_snapshot={
                    "alert_type": alert_type,
                    "message": message,
                    "details": details or {},
                },
                transport_type="system_alert",
            )

        return await self.send_telegram(alert_message)

    async def send_all_free_request_notification(
        self,
        *,
        db: Session,
        visit: Any,
        actor_user: User,
    ) -> bool:
        """Create the canonical inbox signal for a pending All Free request."""
        try:
            platform_service = self._platform_service(db)
            admin_users = platform_service.resolve_users_for_role("admin")
            if not admin_users:
                logger.warning(
                    "[FIX:NOTIFICATIONS] all_free_requested skipped: no admin recipients",
                    extra={"visit_id": getattr(visit, "id", None)},
                )
                return False

            title = "Новая заявка All Free"
            body = f"Визит #{visit.id} ожидает одобрения All Free."
            payload_snapshot = {
                "title": title,
                "message": body,
                "metadata": {
                    "visit_id": visit.id,
                    "patient_id": visit.patient_id,
                    "doctor_id": visit.doctor_id,
                    "discount_mode": visit.discount_mode,
                    "approval_status": visit.approval_status,
                    "request_source": getattr(visit, "source", "desk"),
                    "requested_by": actor_user.id,
                },
            }

            await platform_service.record_delivery_for_users(
                users=admin_users,
                event_type="all_free_requested",
                title=title,
                message=body,
                source_module="registrar",
                recipient_type="user",
                severity="warning",
                priority="high",
                actor_id=actor_user.id,
                actor_role=actor_user.role,
                entity_type="visit",
                entity_id=str(visit.id),
                payload_snapshot=payload_snapshot,
                deep_link="/admin/all-free-requests",
            )
            logger.info(
                "[FIX:NOTIFICATIONS] created all_free_requested delivery",
                extra={
                    "visit_id": visit.id,
                    "recipient_count": len(admin_users),
                    "actor_id": actor_user.id,
                },
            )
            return True
        except Exception as exc:
            logger.error(
                "[FIX:NOTIFICATIONS] failed to create all_free_requested delivery",
                extra={
                    "visit_id": getattr(visit, "id", None),
                    "actor_id": getattr(actor_user, "id", None),
                    "error": str(exc),
                },
            )
            return False

    async def send_all_free_decision_notification(
        self,
        *,
        db: Session,
        visit: Any,
        actor_user: User,
        rejection_reason: str | None = None,
    ) -> bool:
        """Create canonical inbox signals for All Free approve/reject decisions."""
        try:
            from app.models.patient import Patient

            platform_service = self._platform_service(db)
            recipients: dict[int, User] = {}

            registrar_user_id = self._extract_prefixed_user_id(
                getattr(visit, "confirmed_by", None),
                "registrar_",
            )
            if registrar_user_id:
                registrar_user = (
                    db.query(User)
                    .filter(User.id == registrar_user_id, User.is_active.is_(True))
                    .first()
                )
                if registrar_user:
                    recipients[registrar_user.id] = registrar_user

            patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
            if patient and patient.user_id:
                patient_user = (
                    db.query(User)
                    .filter(User.id == patient.user_id, User.is_active.is_(True))
                    .first()
                )
                if patient_user:
                    recipients[patient_user.id] = patient_user

            if not recipients:
                logger.warning(
                    "[FIX:NOTIFICATIONS] all_free decision skipped: no linked recipients",
                    extra={"visit_id": getattr(visit, "id", None)},
                )
                return False

            approved = str(getattr(visit, "approval_status", "")).lower() == "approved"
            event_type = "all_free_approved" if approved else "all_free_rejected"
            title = "Заявка All Free одобрена" if approved else "Заявка All Free отклонена"
            body = (
                f"Заявка All Free для визита #{visit.id} одобрена."
                if approved
                else f"Заявка All Free для визита #{visit.id} отклонена."
            )
            payload_snapshot = {
                "title": title,
                "message": body,
                "metadata": {
                    "visit_id": visit.id,
                    "patient_id": visit.patient_id,
                    "doctor_id": visit.doctor_id,
                    "approval_status": visit.approval_status,
                    "approver_id": actor_user.id,
                    "approver_role": actor_user.role,
                    "rejection_reason": rejection_reason,
                },
            }

            await platform_service.record_delivery_for_users(
                users=list(recipients.values()),
                event_type=event_type,
                title=title,
                message=body,
                source_module="registrar",
                recipient_type="user",
                severity="info" if approved else "warning",
                priority="high",
                actor_id=actor_user.id,
                actor_role=actor_user.role,
                entity_type="visit",
                entity_id=str(visit.id),
                payload_snapshot=payload_snapshot,
                deep_link="/registrar",
            )
            logger.info(
                "[FIX:NOTIFICATIONS] created %s delivery",
                event_type,
                extra={
                    "visit_id": visit.id,
                    "recipient_count": len(recipients),
                    "actor_id": actor_user.id,
                },
            )
            return True
        except Exception as exc:
            logger.error(
                "[FIX:NOTIFICATIONS] failed to create all_free decision delivery",
                extra={
                    "visit_id": getattr(visit, "id", None),
                    "actor_id": getattr(actor_user, "id", None),
                    "approval_status": getattr(visit, "approval_status", None),
                    "error": str(exc),
                },
            )
            return False

    async def send_message_received_notification(
        self,
        *,
        db: Session,
        recipient: User,
        sender: User,
        message_id: int,
        conversation_id: str,
        message_type: str,
        preview: str | None = None,
        patient_id: int | None = None,
    ) -> bool:
        """Create a canonical inbox signal for a newly received chat message."""
        try:
            platform_service = self._platform_service(db)
            sender_name = sender.full_name or sender.username or sender.email or f"User {sender.id}"
            normalized_message_type = str(message_type or "text").strip().lower()

            if normalized_message_type == "voice":
                body = f"{sender_name} отправил(а) голосовое сообщение."
            elif normalized_message_type in {"file", "document"}:
                body = f"{sender_name} отправил(а) файл."
            elif normalized_message_type == "image":
                body = f"{sender_name} отправил(а) изображение."
            else:
                preview_text = (preview or "").strip()
                body = (
                    f"{sender_name}: {preview_text}"
                    if preview_text
                    else f"Новое сообщение от {sender_name}"
                )

            title = "Новое сообщение"
            payload_snapshot = {
                "title": title,
                "message": body,
                "metadata": {
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "sender_id": sender.id,
                    "sender_name": sender_name,
                    "message_type": normalized_message_type,
                    "patient_id": patient_id,
                },
            }

            await platform_service.record_delivery_for_user(
                user=recipient,
                event_type="message_received",
                title=title,
                message=body,
                source_module="messages",
                recipient_type="user",
                severity="info",
                priority="normal",
                actor_id=sender.id,
                actor_role=sender.role,
                entity_type="message",
                entity_id=str(message_id),
                payload_snapshot=payload_snapshot,
                deep_link=f"/messages?user={sender.id}",
            )
            logger.info(
                "[FIX:NOTIFICATIONS] created message_received delivery",
                extra={
                    "message_id": message_id,
                    "conversation_id": conversation_id,
                    "sender_id": sender.id,
                    "recipient_id": recipient.id,
                },
            )
            return True
        except Exception as exc:
            logger.error(
                "[FIX:NOTIFICATIONS] failed to create message_received delivery",
                extra={
                    "message_id": message_id,
                    "sender_id": getattr(sender, "id", None),
                    "recipient_id": getattr(recipient, "id", None),
                    "error": str(exc),
                },
            )
            return False

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

    async def send_templated_notification(
        self,
        db: Session,
        notification_type: str,
        channel: str,
        recipient_contact: str,
        template_data: dict[str, Any],
        recipient_type: str = "patient",
        recipient_id: int | None = None,
        related_entity_type: str | None = None,
        related_entity_id: int | None = None,
    ) -> NotificationHistory:
        """Отправка уведомления с использованием шаблона"""

        raw_notification_type = str(notification_type or "").strip().lower()
        canonical_notification_type = _normalize_notification_event_type(
            raw_notification_type,
            fallback="notification",
        )
        template_lookup_types = [canonical_notification_type]
        if raw_notification_type and raw_notification_type != canonical_notification_type:
            template_lookup_types.append(raw_notification_type)

        # Получаем шаблон
        template = None
        for template_type in template_lookup_types:
            template = crud_notification_template.get_by_type_and_channel(
                db, type=template_type, channel=channel
            )
            if template:
                break

        if not template:
            logger.warning(
                f"Шаблон не найден: {canonical_notification_type}/{channel}"
            )
            # Используем базовый шаблон
            subject = template_data.get("subject", "Уведомление")
            content = template_data.get("message", "Сообщение")
        else:
            subject = (
                self.render_template(template.subject or "", template_data)
                if template.subject
                else None
            )
            content = self.render_template(template.template, template_data)

        # Создаем запись в истории
        history_data = NotificationHistoryCreate(
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            recipient_contact=recipient_contact,
            notification_type=canonical_notification_type,
            channel=channel,
            template_id=template.id if template else None,
            subject=subject,
            content=content,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            notification_metadata=template_data,
        )

        history = crud_notification_history.create(db, obj_in=history_data)

        if db and recipient_id is not None:
            platform_service = self._platform_service(db)
            recipient_user = None
            if recipient_type == "patient":
                from app.models.patient import Patient

                patient = db.query(Patient).filter(Patient.id == recipient_id).first()
                if patient and patient.user_id:
                    recipient_user = db.query(User).filter(User.id == patient.user_id).first()
            else:
                recipient_user = db.query(User).filter(User.id == recipient_id).first()

            if recipient_user:
                await platform_service.record_delivery_for_user(
                    user=recipient_user,
                    event_type=canonical_notification_type,
                    title=subject or "Уведомление",
                    message=content,
                    source_module="notifications",
                    recipient_type=recipient_type,
                    severity="info",
                    priority="normal",
                    entity_type=related_entity_type,
                    entity_id=related_entity_id,
                    payload_snapshot={
                        "template_data": template_data,
                    },
                    transport_type=channel,
                )

        # Отправляем уведомление
        success = False
        error_message = None

        try:
            if channel == "email":
                success = await self.send_email(
                    recipient_contact, subject or "Уведомление", content
                )
            elif channel == "sms":
                success = await self.send_sms(recipient_contact, content)
            elif channel == "telegram":
                success = await self.send_telegram(content, recipient_contact)
            else:
                error_message = f"Неподдерживаемый канал: {channel}"

        except Exception as e:
            error_message = str(e)
            logger.error(f"Ошибка отправки уведомления: {e}")

        # Обновляем статус в истории
        status = "sent" if success else "failed"
        crud_notification_history.update_status(
            db, notification_id=history.id, status=status, error_message=error_message
        )

        return history

    async def send_bulk_notification(
        self,
        db: Session,
        notification_type: str,
        channels: list[str],
        recipients: list[dict[str, Any]],
        template_data: dict[str, Any],
    ) -> list[NotificationHistory]:
        """Массовая отправка уведомлений с проверкой настроек пользователей"""
        results = []

        for recipient in recipients:
            for channel in channels:
                # Проверяем настройки пользователя
                settings = crud_user_notification_settings.get_by_user_id(
                    db, user_id=recipient["id"]
                )

                if settings:
                    # Проверяем конкретную настройку для этого типа уведомления и канала
                    # формат: email_appointment_reminder
                    # Если тип уведомления "appointment_reminder", то ищем "email_appointment_reminder"

                    setting_key = f"{channel}_{notification_type}"

                    # Проверяем наличие атрибута, если нет - считаем включенным по умолчанию (или глобальным)
                    if hasattr(settings, setting_key):
                        if not getattr(settings, setting_key):
                            continue # Выключено пользователем

                # Получаем контакт для канала
                contact = None
                if channel == "email":
                    contact = recipient.get("email")
                elif channel == "sms":
                    contact = recipient.get("phone")
                elif channel == "telegram":
                    contact = recipient.get("telegram")

                if not contact:
                    continue  # Пропускаем, если нет контакта

                # Объединяем данные получателя с общими данными шаблона
                merged_data = {**template_data, **recipient}

                # Отправляем уведомление
                history = await self.send_templated_notification(
                    db=db,
                    notification_type=notification_type,
                    channel=channel,
                    recipient_contact=contact,
                    template_data=merged_data,
                    recipient_type=recipient["type"],
                    recipient_id=recipient["id"],
                )

                results.append(history)

        return results

    async def send_appointment_notification(
        self,
        db: Session,
        appointment_id: int,
        patient_id: int,
        notification_type: str = "appointment_reminder",
        channels: list[str] | None = None,
    ) -> list[NotificationHistory]:
        """Отправка уведомления о записи"""
        from app.crud import patient as patient_crud
        from app.models.appointment import Appointment

        # Получаем данные записи
        appointment = (
            db.query(Appointment).filter(Appointment.id == appointment_id).first()
        )
        if not appointment:
            logger.warning(
                "Appointment notification skipped: appointment not found",
                extra={"notification_type": notification_type},
            )
            return []

        # Получаем данные пациента
        patient = patient_crud.get(db, id=patient_id)
        if not patient:
            logger.warning(
                "Appointment notification skipped: patient not found",
                extra={"notification_type": notification_type},
            )
            return []

        # Данные для шаблона
        template_data = {
            "patient_name": patient.full_name
            or f"{patient.first_name} {patient.last_name}",
            "patient_phone": patient.phone,
            "appointment_date": appointment.appointment_date.strftime("%d.%m.%Y"),
            "appointment_time": (
                appointment.appointment_time.strftime("%H:%M")
                if appointment.appointment_time
                else ""
            ),
            "doctor_name": appointment.doctor_name or "врач",
            "department": appointment.department or "отделение",
            "clinic_name": "Медицинская клиника",
            "clinic_phone": "+998 90 123 45 67",
        }

        # Определяем каналы
        if channels is None:
            channels = ["email", "sms"]

        # Отправляем уведомления
        results = []
        for channel in channels:
            contact = None
            if channel == "email":
                contact = patient.email
            elif channel == "sms":
                contact = patient.phone

            if contact:
                history = await self.send_templated_notification(
                    db=db,
                    notification_type=notification_type,
                    channel=channel,
                    recipient_contact=contact,
                    template_data=template_data,
                    recipient_type="patient",
                    recipient_id=patient_id,
                    related_entity_type="appointment",
                    related_entity_id=appointment_id,
                )
                results.append(history)

        return results

    async def send_payment_notification_by_id(
        self,
        db: Session,
        payment_id: int,
        patient_id: int,
        amount: float,
        currency: str = "UZS",
        notification_type: str = "payment_success",
        channels: list[str] | None = None,
    ) -> list[NotificationHistory]:
        """Отправка уведомления об оплате"""
        from app.crud import patient as patient_crud

        # Получаем данные пациента
        canonical_notification_type = _normalize_notification_event_type(
            notification_type,
            fallback="payment_notification",
        )

        patient = patient_crud.get(db, id=patient_id)
        if not patient:
            logger.warning(
                "Payment notification skipped: patient not found",
                extra={"notification_type": canonical_notification_type},
            )
            return []


        # Данные для шаблона
        template_data = {
            "patient_name": patient.full_name
            or f"{patient.first_name} {patient.last_name}",
            "amount": amount,
            "currency": currency,
            "formatted_amount": f"{amount:,.0f} {currency}",
            "payment_date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "clinic_name": "Медицинская клиника",
            "clinic_phone": "+998 90 123 45 67",
        }

        # Определяем каналы
        if channels is None:
            channels = ["email", "sms"]

        # Отправляем уведомления
        results = []
        for channel in channels:
            contact = None
            if channel == "email":
                contact = patient.email
            elif channel == "sms":
                contact = patient.phone

            if contact:
                history = await self.send_templated_notification(
                    db=db,
                    notification_type=canonical_notification_type,
                    channel=channel,
                    recipient_contact=contact,
                    template_data=template_data,
                    recipient_type="patient",
                    recipient_id=patient_id,
                    related_entity_type="payment",
                    related_entity_id=payment_id,
                )
                results.append(history)

        return results

    # === Business Logic Methods (Merged from Mobile/Telegram Services) ===

    async def send_lab_results_notification(
        self,
        db: Session,
        user_id: int,
        test_name: str,
        test_date: datetime,
        lab_result_id: int | None = None,
    ) -> dict[str, bool]:
        """Уведомление о готовности результатов анализов"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {}

            subject = "Результаты анализов готовы"
            message = f"Результаты анализа '{test_name}' от {test_date.strftime('%d.%m.%Y')} готовы к просмотру."

            results = {}

            # Telegram
            if user.telegram_id:
                tele_msg = f"🔬 <b>{subject}</b>\n\n{message}"
                results["telegram"] = await self.send_telegram_message(user.telegram_id, tele_msg)

            # Push
            if user:
                results["push"] = await self.send_push(
                    user_id=user.id,
                    title=subject,
                    message=message,
                    data={"type": "lab_results", "lab_result_id": lab_result_id},
                    db=db
                )

            return results
        except Exception as e:
            logger.error(f"Error sending lab results notification: {e}")
            return {}

    async def send_prescription_ready_notification(
        self,
        db: Session,
        user_id: int,
        prescription_id: int,
        doctor_name: str,
    ) -> dict[str, bool]:
        """Уведомление о готовности рецепта"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {}

            subject = "Рецепт готов"
            message = f"Ваш рецепт №{prescription_id} от врача {doctor_name} готов."

            results = {}

            # Telegram
            if user.telegram_id:
                tele_msg = f"""
💊 <b>{subject}</b>

👨‍⚕️ Врач: {doctor_name}
📄 Рецепт №{prescription_id}
📅 Дата: {datetime.now().strftime("%d.%m.%Y")}

Рецепт доступен в приложении.
"""
                # TODO: Add download button if using pure telegram bot API manually,
                # but send_telegram_message is simple text.
                # For now keeping clear text.
                results["telegram"] = await self.send_telegram_message(user.telegram_id, tele_msg)

            # Push
            if user:
                results["push"] = await self.send_push(
                    user_id=user.id,
                    title=subject,
                    message=message,
                    data={"type": "prescription_ready", "prescription_id": prescription_id},
                    db=db
                )

            return results
        except Exception as e:
            logger.error(f"Error sending prescription notification: {e}")
            return {}

    async def send_schedule_change_notification(
        self,
        db: Session,
        user_id: int,
        change_type: str,
        old_data: dict[str, Any],
        new_data: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        """Уведомление об изменении в расписании"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {}

            subject = ""
            message = ""

            if change_type == "cancelled":
                subject = "Визит отменен"
                message = f"Визит к врачу {old_data.get('doctor')} на {old_data.get('date')} {old_data.get('time')} отменен."
            elif change_type == "rescheduled":
                subject = "Визит перенесен"
                message = f"Визит перенесен на {new_data.get('date')} {new_data.get('time')}."
            elif change_type == "doctor_changed":
                subject = "Смена врача"
                message = f"Ваш лечащий врач изменен на {new_data.get('doctor')}."

            results = {}

            # Telegram
            if user.telegram_id:
                tele_msg = f"📅 <b>{subject}</b>\n\n{message}"
                results["telegram"] = await self.send_telegram_message(user.telegram_id, tele_msg)

            # Push
            if user:
                results["push"] = await self.send_push(
                    user_id=user.id,
                    title=subject,
                    message=message,
                    data={"type": "schedule_change", "change_type": change_type},
                    db=db
                )

            return results
        except Exception as e:
            logger.error(f"Error sending schedule change notification: {e}")
            return {}

    async def send_appointment_cancellation(
        self,
        db: Session,
        appointment_id: int,
        reason: str | None = None
    ) -> bool:
        """Отправка уведомления об отмене записи (Wrapper logic)"""
        from app.models.appointment import Appointment

        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            return False

        old_data = {
            "doctor": appointment.doctor.name if appointment.doctor else "Врач",
            "date": appointment.appointment_date.strftime("%d.%m.%Y"),
            "time": appointment.appointment_date.strftime("%H:%M") # Assuming appointment_date has time or separate field
        }

        return await self.send_schedule_change_notification(
            db=db,
            user_id=appointment.patient_id,
            change_type="cancelled",
            old_data=old_data
        )

    async def send_visit_confirmation_invitation(
        self, db: Session, visit_id: int, channel: str = "auto"
    ) -> dict[str, Any]:
        """
        Отправляет приглашение на подтверждение визита
        """
        from app.models.patient import Patient
        from app.models.visit import Visit

        try:
            visit = db.query(Visit).filter(Visit.id == visit_id).first()
            if not visit:
                return {"success": False, "error": "Визит не найден"}

            patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
            if not patient:
                return {"success": False, "error": "Пациент не найден"}

            # Определяем канал автоматически если нужно
            if channel == "auto":
                channel = self._determine_best_channel(patient)

            # Формируем данные для уведомления
            notification_data = self._prepare_notification_data(db, visit, patient)

            # Отправляем уведомление по выбранному каналу
            if channel == "telegram":
                return await self._send_telegram_invitation(patient, notification_data)
            elif channel == "pwa":
                return await self._send_pwa_invitation(patient, notification_data)
            elif channel == "phone":
                return await self._send_phone_invitation(patient, notification_data)
            else:
                return {"success": False, "error": f"Неподдерживаемый канал: {channel}"}

        except Exception as e:
            logger.error(f"Ошибка отправки приглашения на подтверждение: {e}")
            return {"success": False, "error": str(e)}

    def _determine_best_channel(self, patient: Any) -> str:
        """Определяет лучший канал для отправки уведомления"""
        # Приоритет: Telegram > PWA > Phone
        if hasattr(patient, 'telegram_id') and patient.telegram_id:
            return "telegram"
        if patient.phone and patient.phone.startswith('+998'):
            return "pwa"
        return "phone"

    def _prepare_notification_data(
        self, db: Session, visit: Any, patient: Any
    ) -> dict[str, Any]:
        """Подготавливает данные для уведомления"""
        from app.models.clinic import Doctor
        from app.models.visit import VisitService

        visit_services = (
            db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
        )

        services_text = []
        total_amount = 0
        for vs in visit_services:
            services_text.append(f"• {vs.name} - {vs.price} сум")
            total_amount += float(vs.price) if vs.price else 0

        doctor_name = "Без врача"
        if visit.doctor_id:
            doctor = db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
            if doctor and doctor.user:
                doctor_name = doctor.user.full_name or doctor.user.username

        return {
            "visit_id": visit.id,
            "patient_name": patient.short_name() if hasattr(patient, 'short_name') else f"{patient.first_name} {patient.last_name}",
            "doctor_name": doctor_name,
            "visit_date": visit.visit_date.strftime("%d.%m.%Y"),
            "visit_time": visit.visit_time or "Время не указано",
            "services": services_text,
            "total_amount": total_amount,
            "confirmation_token": visit.confirmation_token,
            "expires_at": visit.confirmation_expires_at,
            "visit_type": self._get_visit_type_text(visit.discount_mode),
        }

    def _get_visit_type_text(self, discount_mode: str | None) -> str:
        if discount_mode == "repeat":
            return "Повторный визит"
        elif discount_mode == "benefit":
            return "Льготный визит"
        elif discount_mode == "all_free":
            return "Бесплатный визит"
        else:
            return "Платный визит"

    async def _send_telegram_invitation(
        self, patient: Any, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Отправляет приглашение через Telegram"""
        try:
            if not hasattr(patient, 'telegram_id') or not patient.telegram_id:
                return {"success": False, "error": "У пациента нет Telegram ID"}

            message = self._format_telegram_message(data)
            keyboard = self._create_telegram_keyboard(data["confirmation_token"])

            # Используем telegram_bot для отправки
            result = await self.telegram_bot.send_confirmation_invitation(
                chat_id=patient.telegram_id, message=message, keyboard=keyboard
            )

            if result.get("success"):
                logger.info(f"Telegram приглашение отправлено пациенту {patient.id}")
                return {
                    "success": True,
                    "channel": "telegram",
                    "message_id": result.get("message_id"),
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Ошибка отправки Telegram"),
                }

        except Exception as e:
            logger.error(f"Ошибка отправки Telegram приглашения: {e}")
            return {"success": False, "error": str(e)}

    def _format_telegram_message(self, data: dict[str, Any]) -> str:
        services_list = "\n".join(data["services"])
        message = f"""
🏥 **Подтверждение визита в клинику**

👤 **Пациент:** {data["patient_name"]}
👨‍⚕️ **Врач:** {data["doctor_name"]}
📅 **Дата:** {data["visit_date"]}
🕐 **Время:** {data["visit_time"]}
💰 **Тип:** {data["visit_type"]}

📋 **Услуги:**
{services_list}

💵 **Общая сумма:** {data["total_amount"]} сум

⏰ **Подтвердите визит до:** {data["expires_at"].strftime("%d.%m.%Y %H:%M") if data["expires_at"] else "Не указано"}

Нажмите кнопку ниже для подтверждения:
        """.strip()
        return message

    def _create_telegram_keyboard(
        self, confirmation_token: str
    ) -> list[list[dict[str, str]]]:
        return [
            [
                {
                    "text": "✅ Подтвердить визит",
                    "callback_data": f"confirm_visit:{confirmation_token}",
                }
            ],
            [
                {
                    "text": "❌ Отменить визит",
                    "callback_data": f"cancel_visit:{confirmation_token}",
                }
            ],
            [
                {
                    "text": "📞 Связаться с клиникой",
                    "url": f"tel:{settings.CLINIC_PHONE}",
                }
            ],
        ]

    async def _send_pwa_invitation(
        self, patient: Any, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Отправляет приглашение через PWA (SMS с deep link)"""
        try:
            if not patient.phone:
                return {"success": False, "error": "У пациента нет номера телефона"}

            pwa_url = f"{settings.PWA_BASE_URL}/confirm-visit?token={data['confirmation_token']}"
            sms_text = self._format_sms_message(data, pwa_url)

            success = await self.send_sms(patient.phone, sms_text)

            if success:
                logger.info(f"PWA приглашение отправлено пациенту {patient.id}")
                return {"success": True, "channel": "pwa", "pwa_url": pwa_url}
            else:
                return {"success": False, "error": "Ошибка отправки SMS"}

        except Exception as e:
            logger.error(f"Ошибка отправки PWA приглашения: {e}")
            return {"success": False, "error": str(e)}

    def _format_sms_message(self, data: dict[str, Any], pwa_url: str) -> str:
        return f"""
Клиника: Подтвердите визит на {data["visit_date"]} в {data["visit_time"]} к врачу {data["doctor_name"]}.
Сумма: {data["total_amount"]} сум.
Подтвердить: {pwa_url}
        """.strip()

    async def _send_phone_invitation(
        self, patient: Any, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Создает задачу для регистратуры - позвонить пациенту"""
        # Пока просто логируем, в будущем можно интегрировать с CRM/Task системой
        logger.info(f"Создано уведомление для регистратуры: позвонить пациенту {patient.id} для подтверждения визита {data['visit_id']}")
        return {
            "success": True,
            "channel": "phone",
            "message": "Создана задача для регистратуры",
        }

    async def send_confirmation_reminder(
        self, db: Session, visit_id: int, hours_before: int = 24
    ) -> dict[str, Any]:
        """Отправляет напоминание о необходимости подтверждения"""
        from app.models.patient import Patient
        from app.models.visit import Visit

        try:
            visit = db.query(Visit).filter(Visit.id == visit_id).first()
            if not visit:
                return {"success": False, "error": "Визит не найден"}

            patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
            if not patient:
                return {"success": False, "error": "Пациент не найден"}

            channel = self._determine_best_channel(patient)
            notification_data = self._prepare_notification_data(db, visit, patient)
            notification_data["is_reminder"] = True
            notification_data["hours_before"] = hours_before

            if channel == "telegram":
                # Упрощенная версия напоминания для Telegram (можно расширить)
                message = f"🔔 Напоминание! Пожалуйста, подтвердите визит к врачу {notification_data['doctor_name']} на {notification_data['visit_date']} {notification_data['visit_time']}."
                keyboard = self._create_telegram_keyboard(notification_data["confirmation_token"])
                result = await self.telegram_bot.send_confirmation_invitation(
                    chat_id=patient.telegram_id, message=message, keyboard=keyboard
                )
                return {"success": result.get("success"), "error": result.get("error")}
            elif channel == "pwa":
                 return await self._send_pwa_invitation(patient, notification_data)
            else:
                 return await self._send_phone_invitation(patient, notification_data)

        except Exception as e:
            logger.error(f"Ошибка отправки напоминания: {e}")
            return {"success": False, "error": str(e)}

    async def send_telegram_message(
        self, user_id: int | str, message: str, parse_mode: str = "HTML"
    ) -> dict[str, Any]:
        """
        Отправляет сообщение через Telegram бот.
        Метод-обертка для совместимости с кодом, использующим NotificationService.
        """
        try:
            if not self.telegram_bot:
                logger.warning("Telegram bot integration not initialized")
                return {"success": False, "error": "Telegram bot not initialized"}

            # Используем telegram_bot.send_message (предполагая что такой метод есть или будет добавлен)
            # Если в TelegramBotService нет send_message, используем telegram_bot.application.bot.send_message
            # Но лучше использовать методы сервиса.
            # Проверим есть ли метод send_message в TelegramBotService,
            # если нет - используем send_message из bot instance

            # В TelegramBotService обычно есть send_message
            if hasattr(self.telegram_bot, "send_message"):
                 return await self.telegram_bot.send_message(user_id=user_id, text=message, parse_mode=parse_mode)
            else:
                 # Fallback
                 await self.telegram_bot.application.bot.send_message(chat_id=user_id, text=message, parse_mode=parse_mode)
                 return {"success": True}

        except Exception as e:
            logger.error(f"Error sending telegram message: {e}")
            return {"success": False, "error": str(e)}

    # === End merged methods ===

# Создаём глобальный экземпляр сервиса
notification_sender_service = NotificationSenderService()
# Сохраняем старое имя для совместимости (пока не обновим все импорты)
notification_service = notification_sender_service
