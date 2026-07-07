"""Backend-owned notification platform orchestration."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, UTC
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.models.notification import NotificationDelivery, NotificationEvent
from app.models.patient import Patient
from app.models.user import User
from app.models.user_profile import UserProfile
from app.repositories.notification_platform_repository import (
    NotificationPlatformRepository,
)
from app.services.notification_websocket import get_notification_ws_manager

logger = logging.getLogger(__name__)


class NotificationPlatformService:
    """Owns canonical notification events, inbox deliveries, and sync helpers."""

    INBOX_CHANNEL = "in_app_inbox"
    TRANSPORT_NOTIFICATION = "notification"
    TRANSPORT_QUEUE_UPDATE = "queue_update"
    TRANSPORT_SYSTEM_ALERT = "system_alert"
    DEFAULT_TIMEZONE = "Asia/Tashkent"

    CRITICAL_EVENT_TYPES = {
        "security_alert",
        "billing_alert",
        "lab_critical_result",
    }

    QUIET_HOURS_QUEUE_EVENT_TYPES = {
        "queue_update",
        "queue_changed",
        "queue_call",
        "queue_position",
        "queue_reminder",
        "diagnostics_return_needed",
        "diagnostics_return",
        "queue_status_changed",
    }

    # Anti-noise runtime guardrail:
    # suppress repeated realtime queue-family signals in a short burst window,
    # while keeping canonical inbox persistence untouched.
    QUEUE_BURST_SUPPRESSION_EVENT_TYPES = {
        "queue_update",
        "queue_changed",
        "queue_position",
        "queue_reminder",
        "diagnostics_return_needed",
        "diagnostics_return",
        "queue_status_changed",
    }
    QUEUE_BURST_SUPPRESSION_WINDOW_SECONDS = 45

    REALTIME_PUSH_SETTING_BY_EVENT_TYPE = {
        "appointment_reminder": "push_appointment_reminder",
        "appointment_confirmation": "push_appointment_confirmation",
        "visit_confirmation": "push_appointment_confirmation",
        "new_appointment": "push_appointment_confirmation",
        "schedule_change": "push_appointment_cancellation",
        "payment_notification": "push_payment_receipt",
        "security_alert": "push_security_alerts",
        "system_alert": "push_system_updates",
        "registrar_system_alert": "push_system_updates",
        "price_change": "push_system_updates",
        "all_free_requested": "push_system_updates",
        "all_free_approved": "push_system_updates",
        "all_free_rejected": "push_system_updates",
        "queue_update": "push_system_updates",
        "queue_call": "push_system_updates",
        "queue_position": "push_system_updates",
        "queue_reminder": "push_system_updates",
        "diagnostics_return_needed": "push_system_updates",
        "queue_status_changed": "push_system_updates",
        "patient_registered": "push_system_updates",
    }

    ROLE_ALIASES = {
        "admin": "admin",
        "cashier": "cashier",
        "doctor": "doctor",
        "lab": "lab",
        "labtechnician": "lab",
        "lab_technician": "lab",
        "patient": "patient",
        "registrar": "registrar",
        "receptionist": "registrar",
        "cardiologist": "cardiologist",
        "dermatologist": "dermatologist",
        "dentist": "dentist",
    }

    DEPARTMENT_ROLE_ALIASES = {
        "cardiology": "cardiologist",
        "cardiologist": "cardiologist",
        "dentistry": "dentist",
        "dental": "dentist",
        "dentist": "dentist",
        "dermatology": "dermatologist",
        "dermatologist": "dermatologist",
        "lab": "lab",
        "laboratory": "lab",
        "registrar": "registrar",
        "reception": "registrar",
        "receptionist": "registrar",
        "cashier": "cashier",
        "clinic": "doctor",
        "doctor": "doctor",
        "general": "doctor",
    }

    LEGACY_EVENT_TYPE_ALIASES = {
        "queue_changed": "queue_update",
        "diagnostics_return": "diagnostics_return_needed",
        "queue_status": "queue_status_changed",
        "payment_update": "payment_notification",
        "payment_success": "payment_notification",
        "result_ready": "lab_results",
        "lab_result_ready": "lab_results",
        "appointment_rescheduled": "schedule_change",
        "appointment_cancelled": "schedule_change",
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

    EVENT_FAMILY_BY_TYPE = {
        "appointment_reminder": "appointment",
        "appointment_confirmation": "appointment",
        "visit_confirmation": "appointment",
        "schedule_change": "appointment",
        "new_appointment": "appointment",
        "payment_notification": "payment",
        "queue_update": "queue",
        "queue_call": "queue",
        "queue_position": "queue",
        "queue_reminder": "queue",
        "queue_status_changed": "queue",
        "diagnostics_return_needed": "queue",
        "lab_results": "lab",
        "lab_critical_result": "lab",
        "lab_new_study": "lab",
        "lab_critical_finding": "lab",
        "lab_result_sent_confirmation": "lab",
        "prescription_ready": "lab",
        "all_free_requested": "all_free",
        "all_free_approved": "all_free",
        "all_free_rejected": "all_free",
        "message_received": "message",
        "patient_registered": "patient",
        "system_alert": "system",
        "registrar_system_alert": "system",
        "price_change": "system",
        "security_alert": "security",
        "billing_alert": "billing",
    }

    def __init__(self, db: Session):
        self.db = db
        self.repository = NotificationPlatformRepository(db)
        self.ws_manager = get_notification_ws_manager()

    # ------------------------------------------------------------------
    # Normalization helpers
    # ------------------------------------------------------------------
    def normalize_event_type(self, event_type: str | None) -> str:
        value = self.normalize_slug(event_type) or "notification"
        return self.LEGACY_EVENT_TYPE_ALIASES.get(value, value)

    def normalize_role(self, role: str | None) -> str | None:
        normalized = self.normalize_slug(role)
        if not normalized:
            return None
        return self.ROLE_ALIASES.get(normalized, normalized)

    def normalize_department_key(self, department_key: str | None) -> str | None:
        normalized = self.normalize_slug(department_key)
        if not normalized:
            return None
        return self.DEPARTMENT_ROLE_ALIASES.get(normalized, normalized)

    @staticmethod
    def normalize_slug(value: str | None) -> str | None:
        if value is None:
            return None
        text = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower())
        text = re.sub(r"_+", "_", text).strip("_")
        return text or None

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _parse_hhmm(value: str | None, fallback: tuple[int, int]) -> tuple[int, int]:
        if not value:
            return fallback
        try:
            hour, minute = str(value).split(":", maxsplit=1)
            parsed_hour = max(0, min(23, int(hour)))
            parsed_minute = max(0, min(59, int(minute)))
            return parsed_hour, parsed_minute
        except (TypeError, ValueError):
            return fallback

    def _resolve_timezone_name_for_user(self, user: User) -> str:
        user_preferences = getattr(user, "preferences", None)
        user_profile = getattr(user, "profile", None)
        candidate = (
            getattr(user_preferences, "timezone", None)
            or getattr(user_profile, "timezone", None)
            or self.DEFAULT_TIMEZONE
        )
        try:
            ZoneInfo(candidate)
            return candidate
        except Exception:
            return self.DEFAULT_TIMEZONE

    def _is_within_quiet_hours(self, *, now_local: datetime, start: str | None, end: str | None) -> bool:
        start_h, start_m = self._parse_hhmm(start, (22, 0))
        end_h, end_m = self._parse_hhmm(end, (8, 0))
        now_minutes = now_local.hour * 60 + now_local.minute
        start_minutes = start_h * 60 + start_m
        end_minutes = end_h * 60 + end_m
        if start_minutes == end_minutes:
            return False
        if start_minutes < end_minutes:
            return start_minutes <= now_minutes < end_minutes
        return now_minutes >= start_minutes or now_minutes < end_minutes

    def _parse_policy_datetime(
        self,
        *,
        value: Any,
        timezone_name: str,
    ) -> datetime | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            normalized = f"{normalized[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        target_tz = ZoneInfo(timezone_name)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=target_tz)
        return parsed.astimezone(target_tz)

    def _resolve_event_family(self, *, event_type: str) -> str:
        normalized_type = self.normalize_event_type(event_type)
        return self.EVENT_FAMILY_BY_TYPE.get(normalized_type, "other")

    @staticmethod
    def _extract_realtime_control_state(control: Any) -> bool | None:
        if isinstance(control, bool):
            return control
        if not isinstance(control, dict):
            return None

        for key in ("desktop", "realtime_enabled", "enabled"):
            value = control.get(key)
            if isinstance(value, bool):
                return value

        channels = control.get("channels")
        if isinstance(channels, dict):
            desktop_channel = channels.get("desktop")
            if isinstance(desktop_channel, bool):
                return desktop_channel
        return None

    def _load_notification_policy_overrides(self, *, user: User) -> dict[str, Any]:
        user_preferences = getattr(user, "preferences", None)
        if user_preferences is None:
            return {}

        security_settings = getattr(user_preferences, "security_settings", None)
        if not isinstance(security_settings, dict):
            return {}

        policy = security_settings.get("notification_policy")
        if not isinstance(policy, dict):
            return {}
        return policy

    def _evaluate_realtime_policy_overrides(
        self,
        *,
        user: User,
        event_type: str,
        now_local: datetime,
    ) -> tuple[bool | None, str]:
        policy = self._load_notification_policy_overrides(user=user)
        if not policy:
            return None, "no_policy_overrides"

        timezone_name = self._resolve_timezone_name_for_user(user)

        muted_until = self._parse_policy_datetime(
            value=policy.get("muted_until"),
            timezone_name=timezone_name,
        )
        if muted_until and now_local <= muted_until:
            return False, "policy_muted_until"

        snooze_until = self._parse_policy_datetime(
            value=policy.get("snooze_until"),
            timezone_name=timezone_name,
        )
        if snooze_until and now_local <= snooze_until:
            return False, "policy_snoozed_until"

        dnd = policy.get("dnd")
        if isinstance(dnd, dict) and bool(dnd.get("enabled", False)):
            if bool(dnd.get("always_on", False)):
                return False, "policy_dnd_always_on"
            dnd_start = dnd.get("start")
            dnd_end = dnd.get("end")
            if dnd_start or dnd_end:
                if self._is_within_quiet_hours(
                    now_local=now_local,
                    start=dnd_start,
                    end=dnd_end,
                ):
                    return False, "policy_dnd_window"

        global_controls = policy.get("channel_controls")
        if isinstance(global_controls, dict):
            global_realtime_state = self._extract_realtime_control_state(global_controls)
            if global_realtime_state is False:
                return False, "policy_channel_controls_disabled"

        normalized_type = self.normalize_event_type(event_type)
        event_controls = policy.get("event_controls")
        if isinstance(event_controls, dict):
            event_state = self._extract_realtime_control_state(
                event_controls.get(normalized_type)
            )
            if event_state is False:
                return False, f"policy_event_disabled:{normalized_type}"

        event_family = self._resolve_event_family(event_type=normalized_type)
        family_controls = policy.get("family_controls")
        if isinstance(family_controls, dict):
            family_state = self._extract_realtime_control_state(
                family_controls.get(event_family)
            )
            if family_state is False:
                return False, f"policy_family_disabled:{event_family}"

        return None, "policy_no_suppression"

    def _is_critical_breakthrough_event(
        self,
        *,
        event_type: str,
        severity: str | None,
        priority: str | None,
    ) -> bool:
        normalized_type = self.normalize_event_type(event_type)
        normalized_severity = self.normalize_slug(severity)
        normalized_priority = self.normalize_slug(priority)
        if normalized_type in self.CRITICAL_EVENT_TYPES:
            return True
        if normalized_severity in {"critical"}:
            return True
        if normalized_priority in {"urgent"}:
            return True
        return False

    def _resolve_realtime_push_setting_key(self, *, event_type: str) -> str | None:
        normalized_type = self.normalize_event_type(event_type)
        return self.REALTIME_PUSH_SETTING_BY_EVENT_TYPE.get(normalized_type)

    def _is_realtime_event_enabled_in_settings(
        self,
        *,
        notification_settings: Any,
        event_type: str,
    ) -> tuple[bool, str]:
        setting_key = self._resolve_realtime_push_setting_key(event_type=event_type)
        if not setting_key:
            return True, "event_not_mapped_to_push_setting"
        if bool(getattr(notification_settings, setting_key, True)) is False:
            return False, f"setting_disabled:{setting_key}"
        return True, f"setting_enabled:{setting_key}"

    def _should_broadcast_realtime(
        self,
        *,
        user: User,
        event_type: str,
        severity: str | None,
        priority: str | None,
    ) -> tuple[bool, str]:
        normalized_type = self.normalize_event_type(event_type)
        if self._is_critical_breakthrough_event(
            event_type=normalized_type,
            severity=severity,
            priority=priority,
        ):
            return True, "critical_breakthrough"

        timezone_name = self._resolve_timezone_name_for_user(user)
        now_local = datetime.now(ZoneInfo(timezone_name))
        policy_decision, policy_reason = self._evaluate_realtime_policy_overrides(
            user=user,
            event_type=normalized_type,
            now_local=now_local,
        )
        if policy_decision is False:
            return False, policy_reason

        user_preferences = getattr(user, "preferences", None)
        if user_preferences is not None and getattr(user_preferences, "desktop_notifications", True) is False:
            return False, "desktop_notifications_disabled"

        notification_settings = getattr(user, "notification_settings", None)
        if notification_settings is None:
            return True, "no_notification_settings"

        enabled_in_settings, settings_reason = self._is_realtime_event_enabled_in_settings(
            notification_settings=notification_settings,
            event_type=normalized_type,
        )
        if not enabled_in_settings:
            return False, settings_reason

        if (
            getattr(notification_settings, "weekend_notifications", True) is False
            and now_local.weekday() >= 5
            and normalized_type in self.QUIET_HOURS_QUEUE_EVENT_TYPES
        ):
            return False, "weekend_suppression"

        if normalized_type in self.QUIET_HOURS_QUEUE_EVENT_TYPES and self._is_within_quiet_hours(
            now_local=now_local,
            start=getattr(notification_settings, "quiet_hours_start", None),
            end=getattr(notification_settings, "quiet_hours_end", None),
        ):
            return False, "quiet_hours_queue_suppression"

        return True, "default_allow"

    def _should_suppress_queue_burst_realtime(
        self,
        *,
        delivery: NotificationDelivery,
        event_type: str,
    ) -> tuple[bool, str]:
        normalized_type = self.normalize_event_type(event_type)
        if normalized_type not in self.QUEUE_BURST_SUPPRESSION_EVENT_TYPES:
            return False, "not_queue_burst_candidate"

        event = delivery.event
        if event is None:
            return False, "missing_event_for_delivery"

        window_start = self._now() - timedelta(
            seconds=self.QUEUE_BURST_SUPPRESSION_WINDOW_SECONDS
        )
        recent_delivery = (
            self.db.query(NotificationDelivery)
            .join(NotificationDelivery.event)
            .filter(
                NotificationDelivery.recipient_id == delivery.recipient_id,
                NotificationDelivery.channel == self.INBOX_CHANNEL,
                NotificationDelivery.delivery_id != delivery.delivery_id,
                NotificationDelivery.created_at >= window_start,
                NotificationEvent.event_type.in_(
                    tuple(self.QUEUE_BURST_SUPPRESSION_EVENT_TYPES)
                ),
            )
            .order_by(
                NotificationDelivery.created_at.desc(),
                NotificationDelivery.id.desc(),
            )
            .first()
        )
        if recent_delivery is None:
            return False, "no_recent_queue_delivery"

        recent_event = recent_delivery.event
        if recent_event is None:
            return False, "missing_recent_event"

        same_entity = bool(
            event.entity_type
            and event.entity_id
            and recent_event.entity_type == event.entity_type
            and recent_event.entity_id == event.entity_id
        )
        recent_type = self.normalize_event_type(recent_event.event_type)
        same_type_same_message = (
            recent_type == normalized_type
            and (recent_event.message or "").strip() == (event.message or "").strip()
        )
        if same_entity or same_type_same_message:
            return True, f"queue_burst_suppression:{recent_delivery.delivery_id}"

        return False, "recent_queue_delivery_not_similar"

    async def _broadcast_delivery_with_policy(
        self,
        *,
        user: User,
        delivery: NotificationDelivery,
        event_type: str,
        severity: str | None,
        priority: str | None,
    ) -> bool:
        should_broadcast, reason = self._should_broadcast_realtime(
            user=user,
            event_type=event_type,
            severity=severity,
            priority=priority,
        )
        if not should_broadcast:
            logger.info(
                "[Notifications] websocket broadcast suppressed by policy",
                extra={
                    "recipient_id": user.id,
                    "delivery_id": delivery.delivery_id,
                    "event_type": event_type,
                    "reason": reason,
                },
            )
            return False
        suppress_burst, suppress_reason = self._should_suppress_queue_burst_realtime(
            delivery=delivery,
            event_type=event_type,
        )
        if suppress_burst:
            logger.info(
                "[Notifications] websocket broadcast suppressed by anti-noise",
                extra={
                    "recipient_id": user.id,
                    "delivery_id": delivery.delivery_id,
                    "event_type": event_type,
                    "reason": suppress_reason,
                },
            )
            return False
        await self._broadcast_delivery(user.id, delivery)
        return True

    def _hash_seed(self, seed: dict[str, Any]) -> str:
        packed = json.dumps(seed, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha1(packed.encode("utf-8"), usedforsecurity=False).hexdigest()

    # ------------------------------------------------------------------
    # Scope resolution
    # ------------------------------------------------------------------
    def resolve_panel_role_for_user(self, user: User | None) -> str | None:
        if not user:
            return None

        if user.is_superuser:
            return "admin"

        role = self.normalize_role(user.role)
        department = self.normalize_department_key(getattr(user.profile, "department", None))

        if department in self.DEPARTMENT_ROLE_ALIASES.values():
            return department

        return role

    def resolve_patient_user(self, patient_id: int) -> User | None:
        patient = (
            self.db.query(Patient)
            .options(selectinload(Patient.user))
            .filter(Patient.id == patient_id)
            .first()
        )
        if not patient or not patient.user_id:
            return None
        return patient.user

    def resolve_users_for_role(self, role: str) -> list[User]:
        normalized_role = self.normalize_role(role)
        if not normalized_role:
            return []

        query = (
            self.db.query(User)
            .options(selectinload(User.profile))
            .filter(User.is_active.is_(True))
        )

        if normalized_role == "admin":
            query = query.filter(func.lower(User.role) == "admin")
        elif normalized_role == "registrar":
            query = query.filter(func.lower(User.role).in_(["receptionist", "registrar"]))
        elif normalized_role == "cashier":
            query = query.filter(func.lower(User.role) == "cashier")
        elif normalized_role == "lab":
            query = query.filter(
                or_(
                    func.lower(User.role).in_(["lab", "labtechnician", "lab_technician"]),
                    User.profile.has(func.lower(UserProfile.department).like("%lab%")),
                )
            )
        elif normalized_role in {"cardiologist", "dermatologist", "dentist"}:
            query = query.filter(
                or_(
                    func.lower(User.role) == "doctor",
                    func.lower(User.role) == normalized_role,
                    User.profile.has(
                        or_(
                            func.lower(UserProfile.department).like(
                                f"%{normalized_role[:4]}%"
                            ),
                            func.lower(UserProfile.department).like(
                                f"%{normalized_role}%"
                            ),
                        )
                    ),
                )
            )
        elif normalized_role == "doctor":
            query = query.filter(func.lower(User.role) == "doctor")
        elif normalized_role == "patient":
            query = query.filter(func.lower(User.role) == "patient")
        else:
            query = query.filter(func.lower(User.role) == normalized_role)

        users = query.order_by(User.id.asc()).all()
        logger.info(
            "[Notifications] resolve_users_for_role",
            extra={
                "role": normalized_role,
                "count": len(users),
            },
        )
        return users

    def resolve_users_for_department(self, department: str) -> list[User]:
        panel_role = self.normalize_department_key(department) or "doctor"
        users = self.resolve_users_for_role(panel_role)
        registrar_users = self.resolve_users_for_role("registrar")
        admin_users = self.resolve_users_for_role("admin")

        deduped: dict[int, User] = {}
        for user in [*users, *registrar_users, *admin_users]:
            deduped[user.id] = user
        return list(deduped.values())

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _build_event_dedup_key(
        self,
        *,
        event_type: str,
        source_module: str,
        scope_key: str,
        title: str,
        message: str,
        severity: str,
        priority: str,
        correlation_id: str | None,
        entity_type: str | None,
        entity_id: str | int | None,
        payload_snapshot: dict[str, Any] | None,
    ) -> str:
        seed = {
            "event_type": event_type,
            "source_module": source_module,
            "scope_key": scope_key,
            "title": title,
            "message": message,
            "severity": severity,
            "priority": priority,
            "correlation_id": correlation_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "payload_snapshot": payload_snapshot,
        }
        return self._hash_seed(seed)

    def _build_delivery_dedup_key(
        self,
        *,
        event_dedup_key: str,
        recipient_id: int,
        channel: str,
    ) -> str:
        return self._hash_seed(
            {
                "event_dedup_key": event_dedup_key,
                "recipient_id": recipient_id,
                "channel": channel,
            }
        )

    def _build_payload_snapshot(
        self,
        *,
        title: str,
        message: str,
        deep_link: str | None,
        metadata: dict[str, Any] | None,
    ) -> dict[str, Any]:
        snapshot: dict[str, Any] = {
            "title": title,
            "message": message,
        }
        if deep_link:
            snapshot["deep_link"] = deep_link
        if metadata:
            snapshot["metadata"] = metadata
        return snapshot

    def _create_or_get_event(
        self,
        *,
        event_type: str,
        source_module: str,
        scope_key: str,
        title: str,
        message: str,
        severity: str,
        priority: str,
        correlation_id: str | None,
        actor_id: int | None,
        actor_role: str | None,
        entity_type: str | None,
        entity_id: str | int | None,
        payload_snapshot: dict[str, Any] | None,
        deep_link: str | None,
        expires_at: datetime | None,
    ) -> NotificationEvent:
        dedup_key = self._build_event_dedup_key(
            event_type=event_type,
            source_module=source_module,
            scope_key=scope_key,
            title=title,
            message=message,
            severity=severity,
            priority=priority,
            correlation_id=correlation_id,
            entity_type=entity_type,
            entity_id=entity_id,
            payload_snapshot=payload_snapshot,
        )

        existing = self.repository.get_event_by_dedup_key(dedup_key=dedup_key)
        if existing:
            logger.info(
                "[Notifications] reusing event",
                extra={
                    "event_id": existing.event_id,
                    "event_type": event_type,
                    "scope_key": scope_key,
                },
            )
            return existing

        event = NotificationEvent(
            event_type=event_type,
            correlation_id=correlation_id,
            dedup_key=dedup_key,
            source_module=source_module,
            actor_id=actor_id,
            actor_role=actor_role,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            severity=severity,
            priority=priority,
            title=title,
            message=message,
            payload_snapshot=payload_snapshot,
            deep_link=deep_link,
            expires_at=expires_at,
        )
        self.repository.create_event(event)
        logger.info(
            "[Notifications] created event",
            extra={
                "event_id": event.event_id,
                "event_type": event_type,
                "scope_key": scope_key,
            },
        )
        return event

    def _create_or_get_delivery(
        self,
        *,
        event: NotificationEvent,
        recipient_type: str,
        recipient_id: int,
        role: str | None,
        department_key: str | None,
        channel: str,
        payload_snapshot: dict[str, Any] | None,
    ) -> NotificationDelivery:
        delivery_dedup_key = self._build_delivery_dedup_key(
            event_dedup_key=event.dedup_key,
            recipient_id=recipient_id,
            channel=channel,
        )

        existing = self.repository.get_delivery_by_dedup_key(
            recipient_id=recipient_id,
            channel=channel,
            dedup_key=delivery_dedup_key,
        )
        if existing:
            logger.info(
                "[Notifications] reusing delivery",
                extra={
                    "delivery_id": existing.delivery_id,
                    "recipient_id": recipient_id,
                    "channel": channel,
                },
            )
            return existing

        delivery = NotificationDelivery(
            event=event,
            recipient_type=recipient_type,
            recipient_id=recipient_id,
            role=role,
            department_key=department_key,
            channel=channel,
            dedup_key=delivery_dedup_key,
            sequence_id=self.repository.get_next_sequence_id(recipient_id=recipient_id),
            delivery_status="delivered",
            dispatched_at=self._now(),
            first_delivered_at=self._now(),
            payload_snapshot=payload_snapshot,
        )
        self.repository.create_delivery(delivery)
        logger.info(
            "[Notifications] created delivery",
            extra={
                "delivery_id": delivery.delivery_id,
                "recipient_id": recipient_id,
                "channel": channel,
            },
        )
        return delivery

    async def _broadcast_delivery(self, user_id: int, delivery: NotificationDelivery) -> None:
        event = delivery.event
        transport_type = self.TRANSPORT_NOTIFICATION
        if event.event_type in {"queue_update", "queue_changed"}:
            transport_type = self.TRANSPORT_QUEUE_UPDATE
        elif event.event_type == "system_alert":
            transport_type = self.TRANSPORT_SYSTEM_ALERT

        envelope = self.serialize_delivery(delivery)
        payload = {
            "type": transport_type,
            "event_type": event.event_type,
            "notification_type": event.event_type,
            "delivery_id": delivery.delivery_id,
            "event_id": event.event_id,
            "sequence_id": delivery.sequence_id,
            "recipient_id": delivery.recipient_id,
            "recipient_type": delivery.recipient_type,
            "role": delivery.role,
            "department_key": delivery.department_key,
            "channel": delivery.channel,
            "title": event.title,
            "message": event.message,
            "status": delivery.delivery_status,
            "delivery_status": delivery.delivery_status,
            "is_read": delivery.read_at is not None,
            "is_seen": delivery.seen_at is not None,
            "is_archived": delivery.archived_at is not None,
            "created_at": envelope["created_at"],
            "notification": envelope,
        }

        logger.info(
            "[Notifications] broadcasting websocket delivery",
            extra={
                "user_id": user_id,
                "delivery_id": delivery.delivery_id,
                "event_type": event.event_type,
            },
        )
        await self.ws_manager.send_json(payload, user_id)

    def serialize_delivery(self, delivery: NotificationDelivery) -> dict[str, Any]:
        event = delivery.event
        return {
            "id": delivery.delivery_id,
            "delivery_id": delivery.delivery_id,
            "event_id": event.event_id,
            "sequence_id": delivery.sequence_id,
            "notification_type": event.event_type,
            "event_type": event.event_type,
            "title": event.title,
            "message": event.message,
            "severity": event.severity,
            "priority": event.priority,
            "recipient_type": delivery.recipient_type,
            "recipient_id": delivery.recipient_id,
            "role": delivery.role,
            "department_key": delivery.department_key,
            "channel": delivery.channel,
            "status": delivery.delivery_status,
            "delivery_status": delivery.delivery_status,
            "is_read": delivery.read_at is not None,
            "is_seen": delivery.seen_at is not None,
            "is_archived": delivery.archived_at is not None,
            "correlation_id": event.correlation_id,
            "dedup_key": delivery.dedup_key,
            "deep_link": event.deep_link,
            "payload_snapshot": delivery.payload_snapshot or event.payload_snapshot,
            "created_at": delivery.created_at.isoformat(),
            "dispatched_at": delivery.dispatched_at.isoformat()
            if delivery.dispatched_at
            else None,
            "first_delivered_at": delivery.first_delivered_at.isoformat()
            if delivery.first_delivered_at
            else None,
            "seen_at": delivery.seen_at.isoformat() if delivery.seen_at else None,
            "read_at": delivery.read_at.isoformat() if delivery.read_at else None,
            "archived_at": delivery.archived_at.isoformat()
            if delivery.archived_at
            else None,
        }

    def serialize_stats_item(self, delivery: NotificationDelivery) -> dict[str, Any]:
        event = delivery.event
        return {
            "id": delivery.delivery_id,
            "notification_type": event.event_type,
            "status": delivery.delivery_status,
            "message": event.message,
            "created_at": delivery.created_at,
            "role": delivery.role,
            "channel": delivery.channel,
            "severity": event.severity,
        }

    # ------------------------------------------------------------------
    # Inbox queries
    # ------------------------------------------------------------------
    def get_inbox(
        self,
        *,
        current_user: User,
        role: str | None = None,
        status: str = "all",
        event_type: str | None = None,
        severity: str | None = None,
        department_key: str | None = None,
        search: str | None = None,
        cursor: int | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        panel_role = self.normalize_role(role) or self.resolve_panel_role_for_user(current_user)
        normalized_department = self.normalize_department_key(department_key)

        deliveries = self.repository.list_deliveries(
            recipient_id=current_user.id,
            role=panel_role,
            status=status,
            event_type=event_type,
            severity=severity,
            department_key=normalized_department,
            search=search,
            cursor=cursor,
            limit=limit,
        )
        total = self.repository.count_deliveries(
            recipient_id=current_user.id,
            role=panel_role,
            status=status,
            event_type=event_type,
            severity=severity,
            department_key=normalized_department,
            search=search,
        )
        unread_count = self.repository.count_unread_deliveries(
            recipient_id=current_user.id,
            role=panel_role,
            department_key=normalized_department,
        )

        items = [self.serialize_delivery(delivery) for delivery in deliveries]
        next_cursor = None
        has_more = False
        if len(items) == limit and items:
            has_more = total > len(items)
            next_cursor = str(items[-1]["sequence_id"]) if has_more else None

        logger.info(
            "[Notifications] inbox fetched",
            extra={
                "user_id": current_user.id,
                "role": panel_role,
                "status": status,
                "count": len(items),
                "unread_count": unread_count,
            },
        )

        return {
            "items": items,
            "total": total,
            "unread_count": unread_count,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "cursor": str(cursor) if cursor is not None else None,
            "role": panel_role,
            "status": status,
        }

    def get_unread_counts(
        self,
        *,
        current_user: User,
        role: str | None = None,
        department_key: str | None = None,
    ) -> dict[str, Any]:
        panel_role = self.normalize_role(role) or self.resolve_panel_role_for_user(current_user)
        normalized_department = self.normalize_department_key(department_key)

        total = self.repository.count_unread_deliveries(
            recipient_id=current_user.id,
            role=panel_role,
            department_key=normalized_department,
        )
        return {
            "total": total,
            "by_role": self.repository.count_unread_by_role(recipient_id=current_user.id),
            "by_channel": self.repository.count_unread_by_channel(recipient_id=current_user.id),
            "by_severity": self.repository.count_unread_by_severity(
                recipient_id=current_user.id
            ),
        }

    def get_stats(self, *, days: int = 7) -> dict[str, Any]:
        since = self._now() - timedelta(days=days)

        total_query = self.db.query(NotificationDelivery).filter(
            NotificationDelivery.created_at >= since
        )
        total_sent = total_query.count()

        successful = (
            self.db.query(func.count(NotificationDelivery.id))
            .filter(
                NotificationDelivery.created_at >= since,
                NotificationDelivery.delivery_status.in_(
                    ["delivered", "seen", "read", "archived"]
                ),
            )
            .scalar()
            or 0
        )
        failed = (
            self.db.query(func.count(NotificationDelivery.id))
            .filter(
                NotificationDelivery.created_at >= since,
                NotificationDelivery.delivery_status == "failed",
            )
            .scalar()
            or 0
        )
        pending = (
            self.db.query(func.count(NotificationDelivery.id))
            .filter(
                NotificationDelivery.created_at >= since,
                NotificationDelivery.delivery_status.in_(["pending", "dispatched"]),
            )
            .scalar()
            or 0
        )

        by_channel_rows = (
            self.db.query(
                NotificationDelivery.channel,
                func.count(NotificationDelivery.id).label("count"),
            )
            .filter(NotificationDelivery.created_at >= since)
            .group_by(NotificationDelivery.channel)
            .all()
        )
        by_channel = {channel or "unknown": int(count) for channel, count in by_channel_rows}

        by_type_rows = (
            self.db.query(
                NotificationEvent.event_type,
                func.count(NotificationDelivery.id).label("count"),
            )
            .join(NotificationDelivery.event)
            .filter(NotificationDelivery.created_at >= since)
            .group_by(NotificationEvent.event_type)
            .all()
        )
        by_type = {event_type or "unknown": int(count) for event_type, count in by_type_rows}

        recent_activity = [
            self.serialize_stats_item(delivery)
            for delivery in self.repository.list_recent_deliveries(limit=10, since=since)
        ]

        return {
            "period_days": days,
            "total_sent": int(total_sent),
            "successful": int(successful),
            "failed": int(failed),
            "pending": int(pending),
            "success_rate": (successful / total_sent * 100) if total_sent else 0,
            "by_channel": by_channel,
            "by_type": by_type,
            "recent_activity": recent_activity,
        }

    # ------------------------------------------------------------------
    # State mutation
    # ------------------------------------------------------------------
    async def record_delivery_for_user(
        self,
        *,
        user: User,
        event_type: str,
        title: str,
        message: str,
        source_module: str = "notifications",
        recipient_type: str = "user",
        severity: str = "info",
        priority: str = "normal",
        correlation_id: str | None = None,
        actor_id: int | None = None,
        actor_role: str | None = None,
        entity_type: str | None = None,
        entity_id: str | int | None = None,
        payload_snapshot: dict[str, Any] | None = None,
        deep_link: str | None = None,
        expires_at: datetime | None = None,
        transport_type: str = TRANSPORT_NOTIFICATION,
    ) -> NotificationDelivery:
        panel_role = self.resolve_panel_role_for_user(user)
        normalized_event_type = self.normalize_event_type(event_type)
        snapshot = payload_snapshot or self._build_payload_snapshot(
            title=title,
            message=message,
            deep_link=deep_link,
            metadata=None,
        )
        event = self._create_or_get_event(
            event_type=normalized_event_type,
            source_module=source_module,
            scope_key=f"user:{user.id}",
            title=title,
            message=message,
            severity=severity,
            priority=priority,
            correlation_id=correlation_id,
            actor_id=actor_id,
            actor_role=actor_role,
            entity_type=entity_type,
            entity_id=entity_id,
            payload_snapshot=snapshot,
            deep_link=deep_link,
            expires_at=expires_at,
        )
        delivery = self._create_or_get_delivery(
            event=event,
            recipient_type=recipient_type,
            recipient_id=user.id,
            role=panel_role,
            department_key=self.normalize_department_key(
                getattr(user.profile, "department", None)
            ),
            channel=self.INBOX_CHANNEL,
            payload_snapshot=snapshot,
        )
        self.repository.commit()
        await self._broadcast_delivery_with_policy(
            user=user,
            delivery=delivery,
            event_type=normalized_event_type,
            severity=severity,
            priority=priority,
        )
        return delivery

    async def record_delivery_for_users(
        self,
        *,
        users: list[User],
        event_type: str,
        title: str,
        message: str,
        source_module: str = "notifications",
        recipient_type: str = "user",
        severity: str = "info",
        priority: str = "normal",
        correlation_id: str | None = None,
        actor_id: int | None = None,
        actor_role: str | None = None,
        entity_type: str | None = None,
        entity_id: str | int | None = None,
        payload_snapshot: dict[str, Any] | None = None,
        deep_link: str | None = None,
        expires_at: datetime | None = None,
        transport_type: str = TRANSPORT_NOTIFICATION,
    ) -> list[NotificationDelivery]:
        if not users:
            return []

        normalized_event_type = self.normalize_event_type(event_type)
        snapshot = payload_snapshot or self._build_payload_snapshot(
            title=title,
            message=message,
            deep_link=deep_link,
            metadata=None,
        )
        event = self._create_or_get_event(
            event_type=normalized_event_type,
            source_module=source_module,
            scope_key=f"scope:{normalized_event_type}:{source_module}",
            title=title,
            message=message,
            severity=severity,
            priority=priority,
            correlation_id=correlation_id,
            actor_id=actor_id,
            actor_role=actor_role,
            entity_type=entity_type,
            entity_id=entity_id,
            payload_snapshot=snapshot,
            deep_link=deep_link,
            expires_at=expires_at,
        )

        deliveries: list[NotificationDelivery] = []
        for user in users:
            panel_role = self.resolve_panel_role_for_user(user)
            delivery = self._create_or_get_delivery(
                event=event,
                recipient_type=recipient_type,
                recipient_id=user.id,
                role=panel_role,
                department_key=self.normalize_department_key(
                    getattr(user.profile, "department", None)
                ),
                channel=self.INBOX_CHANNEL,
                payload_snapshot=snapshot,
            )
            deliveries.append(delivery)

        self.repository.commit()

        for user, delivery in zip(users, deliveries, strict=False):
            await self._broadcast_delivery_with_policy(
                user=user,
                delivery=delivery,
                event_type=normalized_event_type,
                severity=severity,
                priority=priority,
            )

        return deliveries

    async def mark_seen(
        self, *, current_user: User, delivery_id: str
    ) -> NotificationDelivery:
        delivery = self.repository.get_delivery_by_external_id(delivery_id=delivery_id)
        if not delivery or delivery.recipient_id != current_user.id:
            raise PermissionError("Delivery not found")
        updated = self.repository.mark_delivery_seen(delivery=delivery)
        self.repository.commit()
        await self._broadcast_delivery(current_user.id, updated)
        return updated

    async def mark_read(
        self, *, current_user: User, delivery_id: str
    ) -> NotificationDelivery:
        delivery = self.repository.get_delivery_by_external_id(delivery_id=delivery_id)
        if not delivery or delivery.recipient_id != current_user.id:
            raise PermissionError("Delivery not found")
        updated = self.repository.mark_delivery_read(delivery=delivery)
        self.repository.commit()
        await self._broadcast_delivery(current_user.id, updated)
        return updated

    async def archive(
        self, *, current_user: User, delivery_id: str
    ) -> NotificationDelivery:
        delivery = self.repository.get_delivery_by_external_id(delivery_id=delivery_id)
        if not delivery or delivery.recipient_id != current_user.id:
            raise PermissionError("Delivery not found")
        updated = self.repository.archive_delivery(delivery=delivery)
        self.repository.commit()
        await self._broadcast_delivery(current_user.id, updated)
        return updated

    async def mark_all_read(
        self,
        *,
        current_user: User,
        role: str | None = None,
        department_key: str | None = None,
    ) -> int:
        normalized_role = self.normalize_role(role) or self.resolve_panel_role_for_user(current_user)
        normalized_department = self.normalize_department_key(department_key)
        count = self.repository.mark_all_read(
            recipient_id=current_user.id,
            role=normalized_role,
            department_key=normalized_department,
        )
        self.repository.commit()
        logger.info(
            "[Notifications] mark_all_read",
            extra={
                "user_id": current_user.id,
                "role": normalized_role,
                "department_key": normalized_department,
                "count": count,
            },
        )
        return count


def get_notification_platform_service(db: Session) -> NotificationPlatformService:
    return NotificationPlatformService(db)
