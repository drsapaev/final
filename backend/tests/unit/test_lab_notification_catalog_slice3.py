from __future__ import annotations

import pytest

from app.models.notification import NotificationDelivery, NotificationEvent
from app.services.notifications import notification_sender_service


@pytest.mark.asyncio
async def test_send_lab_results_creates_canonical_delivery(
    db_session,
    admin_user,
):
    created = await notification_sender_service.send_lab_event_notification(
        db=db_session,
        recipient=admin_user,
        event_type="lab_results",
        metadata={
            "order_id": 101,
            "patient_id": 202,
        },
    )

    assert created is True
    delivery = (
        db_session.query(NotificationDelivery)
        .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
        .filter(
            NotificationEvent.event_type == "lab_results",
            NotificationDelivery.recipient_id == admin_user.id,
        )
        .one()
    )
    event = (
        db_session.query(NotificationEvent)
        .filter(NotificationEvent.id == delivery.event_id)
        .one()
    )

    assert event.source_module == "lab"
    assert event.severity == "info"
    assert event.priority == "high"
    assert event.entity_type == "lab_result"
    assert event.entity_id == "101"
    assert event.deep_link == "/lab/results"
    assert delivery.role == "admin"
    assert delivery.payload_snapshot["metadata"]["order_id"] == 101


@pytest.mark.asyncio
async def test_send_lab_critical_result_sets_critical_priority_and_actor(
    db_session,
    admin_user,
    registrar_user,
):
    created = await notification_sender_service.send_lab_event_notification(
        db=db_session,
        recipient=admin_user,
        event_type="lab_critical_result",
        metadata={
            "result_id": 501,
            "order_id": 301,
            "patient_id": 401,
        },
        actor_user=registrar_user,
    )

    assert created is True
    delivery = (
        db_session.query(NotificationDelivery)
        .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
        .filter(
            NotificationEvent.event_type == "lab_critical_result",
            NotificationDelivery.recipient_id == admin_user.id,
        )
        .one()
    )
    event = (
        db_session.query(NotificationEvent)
        .filter(NotificationEvent.id == delivery.event_id)
        .one()
    )

    assert event.severity == "critical"
    assert event.priority == "urgent"
    assert event.actor_id == registrar_user.id
    assert event.actor_role == registrar_user.role
    assert event.entity_type == "lab_result"
    assert event.entity_id == "501"
    assert delivery.payload_snapshot["metadata"]["result_id"] == 501


@pytest.mark.asyncio
async def test_send_lab_event_rejects_unsupported_type(
    db_session,
    admin_user,
):
    created = await notification_sender_service.send_lab_event_notification(
        db=db_session,
        recipient=admin_user,
        event_type="lab_result_ready_legacy",
        metadata={"order_id": 999},
    )

    assert created is False
    count = (
        db_session.query(NotificationEvent)
        .filter(NotificationEvent.event_type == "lab_result_ready_legacy")
        .count()
    )
    assert count == 0
