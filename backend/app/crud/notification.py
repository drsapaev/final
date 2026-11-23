import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, desc, func, text
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.notification import (
    NotificationHistory,
    NotificationSettings,
    NotificationTemplate,
)
from app.schemas.notification import (
    NotificationHistoryCreate,
    NotificationSettingsCreate,
    NotificationSettingsUpdate,
    NotificationTemplateCreate,
    NotificationTemplateUpdate,
)


class TemplateConcurrentUpdate(RuntimeError):
    """A template changed pair repeatedly while acquiring locks."""


class CRUDNotificationTemplate(
    CRUDBase[
        NotificationTemplate, NotificationTemplateCreate, NotificationTemplateUpdate
    ]
):
    @staticmethod
    def _lock_pairs(db: Session, pairs: set[tuple[str, str]]) -> None:
        """Serialize a template key before taking any row locks on PostgreSQL."""
        if db.get_bind().dialect.name != "postgresql":
            return
        for pair in sorted(pairs):
            raw = json.dumps(["notification-template", *pair], ensure_ascii=True).encode()
            key = int.from_bytes(hashlib.sha256(raw).digest()[:8], "big", signed=True)
            db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})

    @staticmethod
    def _deactivate_siblings(db: Session, pair: tuple[str, str], exclude_id: int | None = None) -> None:
        query = db.query(NotificationTemplate).filter(
            NotificationTemplate.type == pair[0],
            NotificationTemplate.channel == pair[1],
            NotificationTemplate.is_active.is_(True),
        )
        if exclude_id is not None:
            query = query.filter(NotificationTemplate.id != exclude_id)
        query.update(
            {NotificationTemplate.is_active: False, NotificationTemplate.updated_at: datetime.now(UTC)},
            synchronize_session=False,
        )
        # The partial index is immediate, so deactivate before inserting or
        # changing the target. Both flushes remain inside the same transaction.
        db.flush()

    def create_atomic(self, db: Session, *, obj_in: NotificationTemplateCreate) -> NotificationTemplate:
        data = obj_in.model_dump()
        pair = (data["type"], data["channel"])
        try:
            self._lock_pairs(db, {pair})
            if data["is_active"]:
                self._deactivate_siblings(db, pair)
            result = NotificationTemplate(**data)
            db.add(result)
            db.flush()
            db.commit()
            db.refresh(result)
            return result
        except Exception:
            db.rollback()
            raise

    def update_atomic(
        self, db: Session, *, template_id: int, obj_in: NotificationTemplateUpdate
    ) -> NotificationTemplate | None:
        data = obj_in.model_dump(exclude_unset=True)
        if any(data.get(field, object()) is None for field in ("name", "type", "channel", "template", "is_active")):
            raise ValueError("Required template fields cannot be null")
        # An old pair can change before its lock is acquired. Roll back and
        # retry with a fresh snapshot instead of taking a row-first lock.
        for _ in range(4):
            try:
                old = db.query(NotificationTemplate.type, NotificationTemplate.channel).filter(
                    NotificationTemplate.id == template_id
                ).first()
                if old is None:
                    db.rollback()
                    return None
                old_pair = (old[0], old[1])
                new_pair = (data.get("type", old_pair[0]), data.get("channel", old_pair[1]))
                self._lock_pairs(db, {old_pair, new_pair})
                target = db.query(NotificationTemplate).filter(
                    NotificationTemplate.id == template_id
                ).with_for_update().populate_existing().first()
                if target is None:
                    db.rollback()
                    return None
                if (target.type, target.channel) != old_pair:
                    db.rollback()
                    continue
                active = data.get("is_active", target.is_active)
                if active:
                    self._deactivate_siblings(db, new_pair, exclude_id=template_id)
                for key, value in data.items():
                    setattr(target, key, value)
                db.flush()
                db.commit()
                db.refresh(target)
                return target
            except Exception:
                db.rollback()
                raise
        raise TemplateConcurrentUpdate("Concurrent template update; retry")

    def get_by_type_and_channel(
        self, db: Session, *, type: str, channel: str
    ) -> NotificationTemplate | None:
        return (
            db.query(NotificationTemplate)
            .filter(
                and_(
                    NotificationTemplate.type == type,
                    NotificationTemplate.channel == channel,
                    NotificationTemplate.is_active,
                )
            )
            .order_by(NotificationTemplate.updated_at.desc(), NotificationTemplate.id.desc())
            .first()
        )

    def get_active_templates(self, db: Session) -> list[NotificationTemplate]:
        return (
            db.query(NotificationTemplate)
            .filter(NotificationTemplate.is_active)
            .order_by(NotificationTemplate.type, NotificationTemplate.channel)
            .all()
        )


class CRUDNotificationHistory(
    CRUDBase[NotificationHistory, NotificationHistoryCreate, None]
):
    def get_by_recipient(
        self, db: Session, *, recipient_id: int, recipient_type: str, limit: int = 100
    ) -> list[NotificationHistory]:
        return (
            db.query(NotificationHistory)
            .filter(
                and_(
                    NotificationHistory.recipient_id == recipient_id,
                    NotificationHistory.recipient_type == recipient_type,
                )
            )
            .order_by(desc(NotificationHistory.created_at))
            .limit(limit)
            .all()
        )

    def get_by_status(
        self, db: Session, *, status: str, limit: int = 100
    ) -> list[NotificationHistory]:
        return (
            db.query(NotificationHistory)
            .filter(NotificationHistory.status == status)
            .order_by(desc(NotificationHistory.created_at))
            .limit(limit)
            .all()
        )

    def get_recent(
        self, db: Session, *, hours: int = 24, limit: int = 100
    ) -> list[NotificationHistory]:
        since = datetime.now(UTC) - timedelta(hours=hours)
        return (
            db.query(NotificationHistory)
            .filter(NotificationHistory.created_at >= since)
            .order_by(desc(NotificationHistory.created_at))
            .limit(limit)
            .all()
        )

    def get_stats(self, db: Session, *, days: int = 7) -> dict[str, Any]:
        since = datetime.now(UTC) - timedelta(days=days)

        # Общая статистика
        total_query = db.query(NotificationHistory).filter(
            NotificationHistory.created_at >= since
        )

        total_sent = total_query.count()
        successful = total_query.filter(NotificationHistory.status == "sent").count()
        failed = total_query.filter(NotificationHistory.status == "failed").count()
        pending = total_query.filter(NotificationHistory.status == "pending").count()

        # Статистика по каналам
        by_channel = {}
        channel_stats = (
            db.query(
                NotificationHistory.channel,
                func.count(NotificationHistory.id).label("count"),
            )
            .filter(NotificationHistory.created_at >= since)
            .group_by(NotificationHistory.channel)
            .all()
        )

        for channel, count in channel_stats:
            by_channel[channel] = count

        # Статистика по типам
        by_type = {}
        type_stats = (
            db.query(
                NotificationHistory.notification_type,
                func.count(NotificationHistory.id).label("count"),
            )
            .filter(NotificationHistory.created_at >= since)
            .group_by(NotificationHistory.notification_type)
            .all()
        )

        for notif_type, count in type_stats:
            by_type[notif_type] = count

        return {
            "period_days": days,
            "total_sent": total_sent,
            "successful": successful,
            "failed": failed,
            "pending": pending,
            "success_rate": (successful / total_sent * 100) if total_sent > 0 else 0,
            "by_channel": by_channel,
            "by_type": by_type,
        }

    def update_status(
        self,
        db: Session,
        *,
        notification_id: int,
        status: str,
        error_message: str | None = None,
    ) -> NotificationHistory | None:
        notification = (
            db.query(NotificationHistory)
            .filter(NotificationHistory.id == notification_id)
            .first()
        )

        if notification:
            notification.status = status
            if error_message:
                notification.error_message = error_message

            if status == "sent":
                notification.sent_at = datetime.now(UTC)
            elif status == "delivered":
                notification.delivered_at = datetime.now(UTC)
                if not notification.sent_at:
                    notification.sent_at = datetime.now(UTC)

            db.commit()
            db.refresh(notification)

        return notification


class CRUDNotificationSettings(
    CRUDBase[
        NotificationSettings, NotificationSettingsCreate, NotificationSettingsUpdate
    ]
):
    def get_by_user(
        self, db: Session, *, user_id: int, user_type: str
    ) -> NotificationSettings | None:
        return (
            db.query(NotificationSettings)
            .filter(
                and_(
                    NotificationSettings.user_id == user_id,
                    NotificationSettings.user_type == user_type,
                )
            )
            .first()
        )

    def get_or_create(
        self, db: Session, *, user_id: int, user_type: str
    ) -> NotificationSettings:
        settings = self.get_by_user(db, user_id=user_id, user_type=user_type)

        if not settings:
            settings_data = NotificationSettingsCreate(
                user_id=user_id, user_type=user_type
            )
            settings = self.create(db, obj_in=settings_data)

        return settings

    def get_users_for_notification(
        self, db: Session, *, notification_type: str, channel: str
    ) -> list[NotificationSettings]:
        """Получить пользователей, которые должны получить уведомление определенного типа"""
        filters = [getattr(NotificationSettings, f"{channel}_enabled")]

        # Добавляем фильтр по типу уведомления
        if notification_type == "appointment_reminder":
            filters.append(NotificationSettings.appointment_reminders)
        elif notification_type == "payment_notification":
            filters.append(NotificationSettings.payment_notifications)
        elif notification_type == "queue_update":
            filters.append(NotificationSettings.queue_updates)
        elif notification_type == "system_alert":
            filters.append(NotificationSettings.system_alerts)

        return db.query(NotificationSettings).filter(and_(*filters)).all()


# Создаем экземпляры CRUD
crud_notification_template = CRUDNotificationTemplate(NotificationTemplate)
crud_notification_history = CRUDNotificationHistory(NotificationHistory)
crud_notification_settings = CRUDNotificationSettings(NotificationSettings)


# === ФУНКЦИИ ДЛЯ МОБИЛЬНОГО API ===


def create_notification(db: Session, notification_data: dict) -> NotificationHistory:
    """Создать новое уведомление"""
    notification = NotificationHistory(**notification_data)
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def get_user_notifications(
    db: Session, user_id: int, limit: int = 50
) -> list[NotificationHistory]:
    """Получить уведомления пользователя"""
    return (
        db.query(NotificationHistory)
        .filter(NotificationHistory.user_id == user_id)
        .order_by(NotificationHistory.created_at.desc())
        .limit(limit)
        .all()
    )


def get_notification(
    db: Session, notification_id: int
) -> NotificationHistory | None:
    """Получить уведомление по ID"""
    return (
        db.query(NotificationHistory)
        .filter(NotificationHistory.id == notification_id)
        .first()
    )


def count_unread_notifications_by_user(db: Session, user_id: int) -> int:
    """Подсчитать количество непрочитанных уведомлений пользователя"""
    return (
        db.query(NotificationHistory)
        .filter(
            and_(
                NotificationHistory.user_id == user_id,
                NotificationHistory.is_read == False,
            )
        )
        .count()
    )
