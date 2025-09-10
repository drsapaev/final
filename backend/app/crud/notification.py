from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func
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


class CRUDNotificationTemplate(
    CRUDBase[
        NotificationTemplate, NotificationTemplateCreate, NotificationTemplateUpdate
    ]
):
    def get_by_type_and_channel(
        self, db: Session, *, type: str, channel: str
    ) -> Optional[NotificationTemplate]:
        return (
            db.query(NotificationTemplate)
            .filter(
                and_(
                    NotificationTemplate.type == type,
                    NotificationTemplate.channel == channel,
                    NotificationTemplate.is_active,
                )
            )
            .first()
        )

    def get_active_templates(self, db: Session) -> List[NotificationTemplate]:
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
    ) -> List[NotificationHistory]:
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
    ) -> List[NotificationHistory]:
        return (
            db.query(NotificationHistory)
            .filter(NotificationHistory.status == status)
            .order_by(desc(NotificationHistory.created_at))
            .limit(limit)
            .all()
        )

    def get_recent(
        self, db: Session, *, hours: int = 24, limit: int = 100
    ) -> List[NotificationHistory]:
        since = datetime.utcnow() - timedelta(hours=hours)
        return (
            db.query(NotificationHistory)
            .filter(NotificationHistory.created_at >= since)
            .order_by(desc(NotificationHistory.created_at))
            .limit(limit)
            .all()
        )

    def get_stats(self, db: Session, *, days: int = 7) -> Dict[str, Any]:
        since = datetime.utcnow() - timedelta(days=days)

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
        error_message: Optional[str] = None,
    ) -> Optional[NotificationHistory]:
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
                notification.sent_at = datetime.utcnow()
            elif status == "delivered":
                notification.delivered_at = datetime.utcnow()
                if not notification.sent_at:
                    notification.sent_at = datetime.utcnow()

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
    ) -> Optional[NotificationSettings]:
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
    ) -> List[NotificationSettings]:
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


def get_user_notifications(db: Session, user_id: int, limit: int = 50) -> List[NotificationHistory]:
    """Получить уведомления пользователя"""
    return (
        db.query(NotificationHistory)
        .filter(NotificationHistory.user_id == user_id)
        .order_by(NotificationHistory.created_at.desc())
        .limit(limit)
        .all()
    )


def get_notification(db: Session, notification_id: int) -> Optional[NotificationHistory]:
    """Получить уведомление по ID"""
    return db.query(NotificationHistory).filter(NotificationHistory.id == notification_id).first()


def count_unread_notifications_by_user(db: Session, user_id: int) -> int:
    """Подсчитать количество непрочитанных уведомлений пользователя"""
    return (
        db.query(NotificationHistory)
        .filter(
            and_(
                NotificationHistory.user_id == user_id,
                NotificationHistory.is_read == False
            )
        )
        .count()
    )