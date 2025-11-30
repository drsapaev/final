"""
CRUD операции для webhook'ов
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from app.models.webhook import (
    Webhook,
    WebhookCall,
    WebhookCallStatus,
    WebhookEvent,
    WebhookEventType,
    WebhookStatus,
)
from app.schemas.webhook import WebhookCallCreate, WebhookCreate, WebhookUpdate


class CRUDWebhook:
    """CRUD операции для webhook'ов"""

    def create(
        self, db: Session, *, obj_in: WebhookCreate, created_by: int = None
    ) -> Webhook:
        """Создает новый webhook"""
        db_obj = Webhook(
            name=obj_in.name,
            description=obj_in.description,
            url=obj_in.url,
            events=obj_in.events,
            headers=obj_in.headers or {},
            secret=obj_in.secret,
            max_retries=obj_in.max_retries,
            retry_delay=obj_in.retry_delay,
            timeout=obj_in.timeout,
            filters=obj_in.filters or {},
            created_by=created_by,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, id: int) -> Optional[Webhook]:
        """Получает webhook по ID"""
        return db.query(Webhook).filter(Webhook.id == id).first()

    def get_by_uuid(self, db: Session, uuid: str) -> Optional[Webhook]:
        """Получает webhook по UUID"""
        return db.query(Webhook).filter(Webhook.uuid == uuid).first()

    def get_multi(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 100,
        status: WebhookStatus = None,
        event_type: str = None,
        created_by: int = None,
    ) -> List[Webhook]:
        """Получает список webhook'ов с фильтрацией"""
        query = db.query(Webhook)

        if status:
            query = query.filter(Webhook.status == status)

        if event_type:
            query = query.filter(Webhook.events.contains([event_type]))

        if created_by:
            query = query.filter(Webhook.created_by == created_by)

        return query.order_by(desc(Webhook.created_at)).offset(skip).limit(limit).all()

    def get_active_for_event(
        self, db: Session, event_type: WebhookEventType
    ) -> List[Webhook]:
        """Получает активные webhook'и для определенного типа события"""
        return (
            db.query(Webhook)
            .filter(
                and_(
                    Webhook.is_active == True,
                    Webhook.status == WebhookStatus.ACTIVE,
                    Webhook.events.contains([event_type.value]),
                )
            )
            .all()
        )

    def update(self, db: Session, *, db_obj: Webhook, obj_in: WebhookUpdate) -> Webhook:
        """Обновляет webhook"""
        update_data = obj_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def remove(self, db: Session, *, id: int) -> Optional[Webhook]:
        """Удаляет webhook"""
        obj = db.query(Webhook).get(id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj

    def activate(self, db: Session, *, id: int) -> Optional[Webhook]:
        """Активирует webhook"""
        obj = db.query(Webhook).get(id)
        if obj:
            obj.is_active = True
            obj.status = WebhookStatus.ACTIVE
            db.commit()
            db.refresh(obj)
        return obj

    def deactivate(self, db: Session, *, id: int) -> Optional[Webhook]:
        """Деактивирует webhook"""
        obj = db.query(Webhook).get(id)
        if obj:
            obj.is_active = False
            obj.status = WebhookStatus.INACTIVE
            db.commit()
            db.refresh(obj)
        return obj

    def get_stats(self, db: Session, *, id: int) -> Dict[str, Any]:
        """Получает статистику webhook'а"""
        webhook = self.get(db, id)
        if not webhook:
            return {}

        # Статистика за последние 24 часа
        last_24h = datetime.utcnow() - timedelta(hours=24)
        recent_calls = (
            db.query(WebhookCall)
            .filter(
                and_(WebhookCall.webhook_id == id, WebhookCall.created_at >= last_24h)
            )
            .all()
        )

        recent_success = len(
            [c for c in recent_calls if c.status == WebhookCallStatus.SUCCESS]
        )
        recent_failed = len(
            [c for c in recent_calls if c.status == WebhookCallStatus.FAILED]
        )

        # Средняя скорость ответа
        successful_calls = [
            c
            for c in recent_calls
            if c.status == WebhookCallStatus.SUCCESS and c.duration_ms
        ]
        avg_response_time = (
            sum(c.duration_ms for c in successful_calls) / len(successful_calls)
            if successful_calls
            else 0
        )

        return {
            "webhook_id": webhook.id,
            "name": webhook.name,
            "status": webhook.status.value,
            "total_calls": webhook.total_calls,
            "successful_calls": webhook.successful_calls,
            "failed_calls": webhook.failed_calls,
            "success_rate": (
                (webhook.successful_calls / webhook.total_calls * 100)
                if webhook.total_calls > 0
                else 0
            ),
            "last_call_at": (
                webhook.last_call_at.isoformat() if webhook.last_call_at else None
            ),
            "last_success_at": (
                webhook.last_success_at.isoformat() if webhook.last_success_at else None
            ),
            "last_failure_at": (
                webhook.last_failure_at.isoformat() if webhook.last_failure_at else None
            ),
            "recent_24h": {
                "total_calls": len(recent_calls),
                "successful_calls": recent_success,
                "failed_calls": recent_failed,
                "success_rate": (
                    (recent_success / len(recent_calls) * 100) if recent_calls else 0
                ),
                "avg_response_time_ms": round(avg_response_time, 2),
            },
        }


class CRUDWebhookCall:
    """CRUD операции для вызовов webhook'ов"""

    def create(self, db: Session, *, obj_in: WebhookCallCreate) -> WebhookCall:
        """Создает новый вызов webhook'а"""
        db_obj = WebhookCall(**obj_in.dict())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, id: int) -> Optional[WebhookCall]:
        """Получает вызов webhook'а по ID"""
        return db.query(WebhookCall).filter(WebhookCall.id == id).first()

    def get_multi_by_webhook(
        self,
        db: Session,
        *,
        webhook_id: int,
        skip: int = 0,
        limit: int = 100,
        status: WebhookCallStatus = None,
    ) -> List[WebhookCall]:
        """Получает вызовы webhook'а"""
        query = db.query(WebhookCall).filter(WebhookCall.webhook_id == webhook_id)

        if status:
            query = query.filter(WebhookCall.status == status)

        return (
            query.order_by(desc(WebhookCall.created_at)).offset(skip).limit(limit).all()
        )

    def get_pending_retries(self, db: Session, limit: int = 50) -> List[WebhookCall]:
        """Получает вызовы, готовые к повтору"""
        return (
            db.query(WebhookCall)
            .filter(
                and_(
                    WebhookCall.status == WebhookCallStatus.RETRYING,
                    WebhookCall.next_retry_at <= datetime.utcnow(),
                )
            )
            .limit(limit)
            .all()
        )

    def update_status(
        self,
        db: Session,
        *,
        db_obj: WebhookCall,
        status: WebhookCallStatus,
        response_status_code: int = None,
        response_body: str = None,
        error_message: str = None,
        duration_ms: int = None,
    ) -> WebhookCall:
        """Обновляет статус вызова webhook'а"""
        db_obj.status = status

        if response_status_code is not None:
            db_obj.response_status_code = response_status_code

        if response_body is not None:
            db_obj.response_body = response_body[:10000]  # Ограничиваем размер

        if error_message is not None:
            db_obj.error_message = error_message[:1000]

        if duration_ms is not None:
            db_obj.duration_ms = duration_ms

        if status in [WebhookCallStatus.SUCCESS, WebhookCallStatus.FAILED]:
            db_obj.completed_at = datetime.utcnow()

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def cleanup_old(self, db: Session, days: int = 30) -> int:
        """Удаляет старые вызовы webhook'ов"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        deleted_count = (
            db.query(WebhookCall).filter(WebhookCall.created_at < cutoff_date).delete()
        )

        db.commit()
        return deleted_count


class CRUDWebhookEvent:
    """CRUD операции для событий webhook'ов"""

    def create(
        self,
        db: Session,
        *,
        event_type: WebhookEventType,
        event_data: Dict[str, Any],
        source: str = "api",
        source_id: str = None,
        correlation_id: str = None,
    ) -> WebhookEvent:
        """Создает новое событие"""
        db_obj = WebhookEvent(
            event_type=event_type,
            event_data=event_data,
            source=source,
            source_id=source_id,
            correlation_id=correlation_id,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, id: int) -> Optional[WebhookEvent]:
        """Получает событие по ID"""
        return db.query(WebhookEvent).filter(WebhookEvent.id == id).first()

    def get_unprocessed(self, db: Session, limit: int = 100) -> List[WebhookEvent]:
        """Получает необработанные события"""
        return (
            db.query(WebhookEvent)
            .filter(WebhookEvent.processed == False)
            .order_by(WebhookEvent.created_at)
            .limit(limit)
            .all()
        )

    def mark_processed(self, db: Session, *, db_obj: WebhookEvent) -> WebhookEvent:
        """Отмечает событие как обработанное"""
        db_obj.processed = True
        db_obj.processed_at = datetime.utcnow()
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def cleanup_old(self, db: Session, days: int = 7) -> int:
        """Удаляет старые обработанные события"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        deleted_count = (
            db.query(WebhookEvent)
            .filter(
                and_(
                    WebhookEvent.created_at < cutoff_date,
                    WebhookEvent.processed == True,
                )
            )
            .delete()
        )

        db.commit()
        return deleted_count


# Создаем экземпляры CRUD классов
crud_webhook = CRUDWebhook()
crud_webhook_call = CRUDWebhookCall()
crud_webhook_event = CRUDWebhookEvent()
