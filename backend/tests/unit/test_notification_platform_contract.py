from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import HTTPException
import pytest

from app.api.v1.endpoints.notifications import _validate_recipient_scope
from app.models.notification import NotificationDelivery, NotificationEvent
from app.services.notification_platform_service import NotificationPlatformService


@pytest.mark.asyncio
async def test_notification_platform_service_creates_persistent_delivery_and_deduplicates(
    db_session,
    admin_user,
):
    service = NotificationPlatformService(db_session)
    service.ws_manager = SimpleNamespace(send_json=AsyncMock(return_value=None))

    payload = {
        "title": "Очередь обновлена",
        "message": "Пациент вызван к врачу",
        "metadata": {"source": "queue"},
    }

    delivery = await service.record_delivery_for_user(
        user=admin_user,
        event_type="queue_update",
        title=payload["title"],
        message=payload["message"],
        source_module="queue",
        actor_id=admin_user.id,
        actor_role=admin_user.role,
        entity_type="visit",
        entity_id="visit-123",
        payload_snapshot=payload,
        deep_link="/queue",
    )

    persisted_delivery = (
        db_session.query(NotificationDelivery)
        .filter(NotificationDelivery.delivery_id == delivery.delivery_id)
        .one()
    )
    persisted_event = (
        db_session.query(NotificationEvent)
        .filter(NotificationEvent.id == persisted_delivery.event_id)
        .one()
    )

    assert persisted_event.event_type == "queue_changed"
    assert persisted_delivery.delivery_status == "delivered"
    assert persisted_delivery.role == "admin"
    assert persisted_delivery.sequence_id == 1
    assert persisted_delivery.payload_snapshot["metadata"]["source"] == "queue"
    assert service.ws_manager.send_json.await_count == 1

    duplicate_delivery = await service.record_delivery_for_user(
        user=admin_user,
        event_type="queue_update",
        title=payload["title"],
        message=payload["message"],
        source_module="queue",
        actor_id=admin_user.id,
        actor_role=admin_user.role,
        entity_type="visit",
        entity_id="visit-123",
        payload_snapshot=payload,
        deep_link="/queue",
    )

    assert duplicate_delivery.delivery_id == delivery.delivery_id
    assert db_session.query(NotificationDelivery).count() == 1
    assert db_session.query(NotificationEvent).count() == 1
    assert service.ws_manager.send_json.await_count == 2

    inbox = service.get_inbox(current_user=admin_user, status="all", limit=10)
    assert inbox["total"] == 1
    assert inbox["unread_count"] == 1
    assert inbox["items"][0]["id"] == delivery.delivery_id
    assert inbox["items"][0]["event_type"] == "queue_changed"

    seen_delivery = await service.mark_seen(current_user=admin_user, delivery_id=delivery.delivery_id)
    assert seen_delivery.seen_at is not None
    assert seen_delivery.delivery_status == "seen"

    read_delivery = await service.mark_read(current_user=admin_user, delivery_id=delivery.delivery_id)
    assert read_delivery.read_at is not None
    assert read_delivery.delivery_status == "read"

    archived_delivery = await service.archive(
        current_user=admin_user,
        delivery_id=delivery.delivery_id,
    )
    assert archived_delivery.archived_at is not None
    assert archived_delivery.delivery_status == "archived"

    unread_counts = service.get_unread_counts(current_user=admin_user)
    assert unread_counts["total"] == 0

    archived_inbox = service.get_inbox(
        current_user=admin_user,
        status="archived",
        limit=10,
    )
    assert archived_inbox["total"] == 1
    assert archived_inbox["items"][0]["delivery_status"] == "archived"


def test_notification_history_scope_rejects_cross_recipient_requests(
    db_session,
    admin_user,
):
    service = NotificationPlatformService(db_session)

    with pytest.raises(HTTPException) as exc_info:
        _validate_recipient_scope(
            platform_service=service,
            current_user=admin_user,
            recipient_id=admin_user.id + 1,
            recipient_type='admin',
        )

    assert exc_info.value.status_code == 403

    with pytest.raises(HTTPException) as exc_info:
        _validate_recipient_scope(
            platform_service=service,
            current_user=admin_user,
            recipient_id=admin_user.id,
            recipient_type='doctor',
        )

    assert exc_info.value.status_code == 403
