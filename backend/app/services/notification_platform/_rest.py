"""Rest mixin for NotificationPlatformService.

Split from notification_platform_service.py.
"""
from __future__ import annotations

from app.services.notification_platform._base import *  # noqa: F401, F403
from app.services.notification_platform._base import (
    NotificationPlatformServiceMixinBase,
)


class RestMixin(NotificationPlatformServiceMixinBase):
    """Rest methods."""

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
        transport_type: str = NotificationPlatformServiceMixinBase.TRANSPORT_NOTIFICATION,
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
        transport_type: str = NotificationPlatformServiceMixinBase.TRANSPORT_NOTIFICATION,
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
    return _resolve_platform_service_class()(db)


def _resolve_platform_service_class():
    # Local helper kept for backward-compat with code that monkeypatches
    # ``app.services.notification_platform_service.get_notification_ws_manager``
    # and similar shims. Resolved lazily to avoid the circular import that
    # occurs because ``app.services.notification_platform`` imports this
    # mixin module before ``NotificationPlatformService`` is defined.
    from app.services.notification_platform import NotificationPlatformService

    return NotificationPlatformService



