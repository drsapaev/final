"""Repository helpers for the backend-owned notification platform."""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.notification import NotificationDelivery, NotificationEvent


class NotificationPlatformRepository:
    """Persistence boundary for notification events and deliveries."""

    def __init__(self, db: Session):
        self.db = db

    # ---------------------------------------------------------------------
    # Events
    # ---------------------------------------------------------------------
    def get_event_by_dedup_key(self, *, dedup_key: str) -> NotificationEvent | None:
        return (
            self.db.query(NotificationEvent)
            .filter(NotificationEvent.dedup_key == dedup_key)
            .first()
        )

    def create_event(self, event: NotificationEvent) -> NotificationEvent:
        self.db.add(event)
        self.db.flush()
        self.db.refresh(event)
        return event

    # ---------------------------------------------------------------------
    # Deliveries
    # ---------------------------------------------------------------------
    def get_delivery_by_external_id(
        self, *, delivery_id: str
    ) -> NotificationDelivery | None:
        return (
            self.db.query(NotificationDelivery)
            .options(joinedload(NotificationDelivery.event))
            .filter(NotificationDelivery.delivery_id == delivery_id)
            .first()
        )

    def get_delivery_by_dedup_key(
        self,
        *,
        recipient_id: int,
        channel: str,
        dedup_key: str,
    ) -> NotificationDelivery | None:
        return (
            self.db.query(NotificationDelivery)
            .options(joinedload(NotificationDelivery.event))
            .filter(
                and_(
                    NotificationDelivery.recipient_id == recipient_id,
                    NotificationDelivery.channel == channel,
                    NotificationDelivery.dedup_key == dedup_key,
                )
            )
            .first()
        )

    def create_delivery(self, delivery: NotificationDelivery) -> NotificationDelivery:
        self.db.add(delivery)
        self.db.flush()
        self.db.refresh(delivery)
        return delivery

    def get_next_sequence_id(self, *, recipient_id: int) -> int:
        current_max = (
            self.db.query(func.max(NotificationDelivery.sequence_id))
            .filter(NotificationDelivery.recipient_id == recipient_id)
            .scalar()
        )
        return int(current_max or 0) + 1

    def list_deliveries(
        self,
        *,
        recipient_id: int,
        role: str | None = None,
        status: str = "all",
        event_type: str | None = None,
        severity: str | None = None,
        department_key: str | None = None,
        search: str | None = None,
        cursor: int | None = None,
        limit: int = 50,
    ) -> list[NotificationDelivery]:
        query = (
            self.db.query(NotificationDelivery)
            .options(joinedload(NotificationDelivery.event))
            .filter(NotificationDelivery.recipient_id == recipient_id)
        )

        if role:
            query = query.filter(func.lower(NotificationDelivery.role) == role.lower())

        if department_key:
            query = query.filter(
                func.lower(NotificationDelivery.department_key) == department_key.lower()
            )

        if status == "unread":
            query = query.filter(
                NotificationDelivery.read_at.is_(None),
                NotificationDelivery.archived_at.is_(None),
            )
        elif status == "archived":
            query = query.filter(NotificationDelivery.archived_at.is_not(None))
        else:
            query = query.filter(NotificationDelivery.archived_at.is_(None))

        if event_type or severity or search:
            query = query.join(NotificationDelivery.event)

        if event_type:
            query = query.filter(
                func.lower(NotificationEvent.event_type) == event_type.lower()
            )

        if severity:
            query = query.filter(func.lower(NotificationEvent.severity) == severity.lower())

        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    NotificationEvent.title.ilike(term),
                    NotificationEvent.message.ilike(term),
                    NotificationEvent.event_type.ilike(term),
                    NotificationDelivery.channel.ilike(term),
                    NotificationDelivery.role.ilike(term),
                    NotificationDelivery.department_key.ilike(term),
                )
            )

        if cursor is not None:
            query = query.filter(NotificationDelivery.sequence_id < cursor)

        return (
            query.order_by(
                desc(NotificationDelivery.sequence_id),
                desc(NotificationDelivery.id),
            )
            .limit(limit)
            .all()
        )

    def count_deliveries(
        self,
        *,
        recipient_id: int,
        role: str | None = None,
        status: str = "all",
        department_key: str | None = None,
        event_type: str | None = None,
        severity: str | None = None,
        search: str | None = None,
    ) -> int:
        query = (
            self.db.query(func.count(NotificationDelivery.id))
            .select_from(NotificationDelivery)
            .join(NotificationDelivery.event)
            .filter(NotificationDelivery.recipient_id == recipient_id)
        )

        if role:
            query = query.filter(func.lower(NotificationDelivery.role) == role.lower())

        if department_key:
            query = query.filter(
                func.lower(NotificationDelivery.department_key) == department_key.lower()
            )

        if status == "unread":
            query = query.filter(
                NotificationDelivery.read_at.is_(None),
                NotificationDelivery.archived_at.is_(None),
            )
        elif status == "archived":
            query = query.filter(NotificationDelivery.archived_at.is_not(None))
        else:
            query = query.filter(NotificationDelivery.archived_at.is_(None))

        if event_type:
            query = query.filter(
                func.lower(NotificationEvent.event_type) == event_type.lower()
            )

        if severity:
            query = query.filter(func.lower(NotificationEvent.severity) == severity.lower())

        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    NotificationEvent.title.ilike(term),
                    NotificationEvent.message.ilike(term),
                    NotificationEvent.event_type.ilike(term),
                    NotificationDelivery.channel.ilike(term),
                    NotificationDelivery.role.ilike(term),
                    NotificationDelivery.department_key.ilike(term),
                )
            )

        return int(query.scalar() or 0)

    def count_unread_deliveries(
        self,
        *,
        recipient_id: int,
        role: str | None = None,
        department_key: str | None = None,
    ) -> int:
        query = (
            self.db.query(func.count(NotificationDelivery.id))
            .select_from(NotificationDelivery)
            .filter(
                NotificationDelivery.recipient_id == recipient_id,
                NotificationDelivery.read_at.is_(None),
                NotificationDelivery.archived_at.is_(None),
            )
        )

        if role:
            query = query.filter(func.lower(NotificationDelivery.role) == role.lower())

        if department_key:
            query = query.filter(
                func.lower(NotificationDelivery.department_key) == department_key.lower()
            )

        return int(query.scalar() or 0)

    def count_unread_by_role(self, *, recipient_id: int) -> dict[str, int]:
        rows = (
            self.db.query(
                NotificationDelivery.role,
                func.count(NotificationDelivery.id).label("count"),
            )
            .filter(
                NotificationDelivery.recipient_id == recipient_id,
                NotificationDelivery.read_at.is_(None),
                NotificationDelivery.archived_at.is_(None),
            )
            .group_by(NotificationDelivery.role)
            .all()
        )

        return {role or "unknown": int(count) for role, count in rows}

    def count_unread_by_channel(self, *, recipient_id: int) -> dict[str, int]:
        rows = (
            self.db.query(
                NotificationDelivery.channel,
                func.count(NotificationDelivery.id).label("count"),
            )
            .filter(
                NotificationDelivery.recipient_id == recipient_id,
                NotificationDelivery.read_at.is_(None),
                NotificationDelivery.archived_at.is_(None),
            )
            .group_by(NotificationDelivery.channel)
            .all()
        )

        return {channel or "unknown": int(count) for channel, count in rows}

    def count_unread_by_severity(self, *, recipient_id: int) -> dict[str, int]:
        rows = (
            self.db.query(
                NotificationEvent.severity,
                func.count(NotificationDelivery.id).label("count"),
            )
            .join(NotificationDelivery.event)
            .filter(
                NotificationDelivery.recipient_id == recipient_id,
                NotificationDelivery.read_at.is_(None),
                NotificationDelivery.archived_at.is_(None),
            )
            .group_by(NotificationEvent.severity)
            .all()
        )

        return {severity or "unknown": int(count) for severity, count in rows}

    def list_recent_deliveries(
        self,
        *,
        limit: int = 10,
        since: datetime | None = None,
    ) -> list[NotificationDelivery]:
        query = self.db.query(NotificationDelivery).options(
            joinedload(NotificationDelivery.event)
        )
        if since is not None:
            query = query.filter(NotificationDelivery.created_at >= since)
        return query.order_by(desc(NotificationDelivery.created_at)).limit(limit).all()

    def mark_delivery_seen(
        self, *, delivery: NotificationDelivery, seen_at: datetime | None = None
    ) -> NotificationDelivery:
        delivery.seen_at = seen_at or datetime.now(UTC)
        if delivery.delivery_status not in {"seen", "read", "archived"}:
            delivery.delivery_status = "seen"
        self.db.flush()
        self.db.refresh(delivery)
        return delivery

    def mark_delivery_read(
        self, *, delivery: NotificationDelivery, read_at: datetime | None = None
    ) -> NotificationDelivery:
        now = read_at or datetime.now(UTC)
        if delivery.seen_at is None:
            delivery.seen_at = now
        delivery.read_at = now
        if delivery.delivery_status != "archived":
            delivery.delivery_status = "read"
        self.db.flush()
        self.db.refresh(delivery)
        return delivery

    def archive_delivery(
        self, *, delivery: NotificationDelivery, archived_at: datetime | None = None
    ) -> NotificationDelivery:
        now = archived_at or datetime.now(UTC)
        if delivery.seen_at is None:
            delivery.seen_at = now
        if delivery.read_at is None:
            delivery.read_at = now
        delivery.archived_at = now
        delivery.delivery_status = "archived"
        self.db.flush()
        self.db.refresh(delivery)
        return delivery

    def mark_all_read(
        self,
        *,
        recipient_id: int,
        role: str | None = None,
        department_key: str | None = None,
    ) -> int:
        query = self.db.query(NotificationDelivery).filter(
            NotificationDelivery.recipient_id == recipient_id,
            NotificationDelivery.read_at.is_(None),
            NotificationDelivery.archived_at.is_(None),
        )

        if role:
            query = query.filter(func.lower(NotificationDelivery.role) == role.lower())

        if department_key:
            query = query.filter(
                func.lower(NotificationDelivery.department_key) == department_key.lower()
            )

        deliveries = query.all()
        now = datetime.now(UTC)
        for delivery in deliveries:
            delivery.seen_at = delivery.seen_at or now
            delivery.read_at = now
            delivery.delivery_status = "read"

        self.db.flush()
        return len(deliveries)

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, obj: Any) -> Any:
        self.db.refresh(obj)
        return obj

    def rollback(self) -> None:
        self.db.rollback()
