from __future__ import annotations

import pytest

from app.models.notification import NotificationDelivery, NotificationEvent
from app.services.notifications import notification_sender_service


@pytest.mark.asyncio
async def test_send_queue_position_event_creates_canonical_delivery(
    db_session,
    admin_user,
):
    created = await notification_sender_service.send_queue_position_event_notification(
        db=db_session,
        recipient=admin_user,
        event_type="queue_position",
        title="Ваша очередь обновлена",
        message="Номер очереди изменился",
        metadata={"queue_id": 44, "position": 3},
    )

    assert created is True
    delivery = (
        db_session.query(NotificationDelivery)
        .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
        .filter(
            NotificationEvent.event_type == "queue_position",
            NotificationDelivery.recipient_id == admin_user.id,
        )
        .one()
    )
    event = (
        db_session.query(NotificationEvent)
        .filter(NotificationEvent.id == delivery.event_id)
        .one()
    )

    assert event.source_module == "queue"
    assert event.entity_type == "queue"
    assert event.entity_id == "44"
    assert event.deep_link == "/queue"
    assert event.priority == "high"
    assert delivery.role == "admin"
    assert delivery.payload_snapshot["metadata"]["position"] == 3


@pytest.mark.asyncio
async def test_send_diagnostics_return_needed_event_uses_same_queue_family_contract(
    db_session,
    admin_user,
    registrar_user,
):
    created = await notification_sender_service.send_queue_position_event_notification(
        db=db_session,
        recipient=admin_user,
        event_type="diagnostics_return_needed",
        title="Нужно вернуться на диагностику",
        message="Пожалуйста, вернитесь в кабинет",
        metadata={"queue_id": 77, "entry_id": 888},
        actor_user=registrar_user,
    )

    assert created is True
    delivery = (
        db_session.query(NotificationDelivery)
        .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
        .filter(
            NotificationEvent.event_type == "diagnostics_return_needed",
            NotificationDelivery.recipient_id == admin_user.id,
        )
        .one()
    )
    event = (
        db_session.query(NotificationEvent)
        .filter(NotificationEvent.id == delivery.event_id)
        .one()
    )

    assert event.severity == "info"
    assert event.priority == "high"
    assert event.actor_id == registrar_user.id
    assert event.actor_role == registrar_user.role
    assert event.entity_type == "queue"
    assert event.entity_id == "77"
    assert delivery.payload_snapshot["metadata"]["entry_id"] == 888


@pytest.mark.asyncio
async def test_send_queue_position_event_rejects_unknown_type(
    db_session,
    admin_user,
):
    created = await notification_sender_service.send_queue_position_event_notification(
        db=db_session,
        recipient=admin_user,
        event_type="queue_position_legacy_runtime_type",
        title="Legacy event",
        message="Legacy event payload",
        metadata={"queue_id": 999},
    )

    assert created is False
    count = (
        db_session.query(NotificationEvent)
        .filter(NotificationEvent.event_type == "queue_position_legacy_runtime_type")
        .count()
    )
    assert count == 0
