"""Policy mixin for NotificationPlatformService.

Split from notification_platform_service.py.
"""
from __future__ import annotations

from app.services.notification_platform._base import *  # noqa: F401, F403
from app.services.notification_platform._base import NotificationPlatformServiceMixinBase


class PolicyMixin(NotificationPlatformServiceMixinBase):
    """Policy methods."""

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


