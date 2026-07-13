"""Canonical mixin for NotificationSenderService.

Split from notifications.py.
"""
from __future__ import annotations

from app.services.notifications_pkg._base import (
    Any,
    NotificationSenderMixinBase,
    Session,
    User,
    logger,
)
from app.services.notifications_pkg._helpers import (  # noqa: F401
    LAB_NOTIFICATION_EVENT_TYPES,
    PATIENT_TELEGRAM_EVENT_PREFERENCES,
    QUEUE_NOTIFICATION_EVENT_TYPES,
    REGISTRAR_NOTIFICATION_EVENT_TYPES,
    _normalize_notification_event_type,
    _patient_telegram_event_message,
)


class CanonicalMixin(NotificationSenderMixinBase):
    """Canonical methods for NotificationSenderService."""

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


