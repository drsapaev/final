from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.notification import NotificationDelivery, NotificationEvent
from app.schemas.message import MessageCreate
from app.services.messages_api_service import MessagesApiService


@pytest.mark.asyncio
async def test_send_message_creates_canonical_message_received_delivery(
    db_session,
    admin_user,
    registrar_user,
    monkeypatch,
):
    fake_chat_manager = SimpleNamespace(
        notify_new_message=AsyncMock(return_value=None),
        notify_messages_read=AsyncMock(return_value=None),
        notify_message_read=AsyncMock(return_value=None),
        broadcast_event=AsyncMock(return_value=None),
    )
    monkeypatch.setattr("app.ws.chat_ws.chat_manager", fake_chat_manager)

    service = MessagesApiService(db_session)
    payload = MessageCreate(recipient_id=registrar_user.id, content="Проверка inbox")

    result = await service.send_message(
        request=None,
        message_data=payload,
        current_user=admin_user,
    )

    persisted_delivery = (
        db_session.query(NotificationDelivery)
        .join(NotificationEvent, NotificationEvent.id == NotificationDelivery.event_id)
        .filter(
            NotificationEvent.event_type == "message_received",
            NotificationDelivery.recipient_id == registrar_user.id,
        )
        .one()
    )
    persisted_event = (
        db_session.query(NotificationEvent)
        .filter(NotificationEvent.id == persisted_delivery.event_id)
        .one()
    )

    assert result.id is not None
    assert persisted_event.entity_type == "message"
    assert persisted_event.entity_id == str(result.id)
    assert persisted_event.actor_id == admin_user.id
    assert persisted_delivery.role == "registrar"
    assert persisted_delivery.payload_snapshot["metadata"]["sender_id"] == admin_user.id
    assert persisted_delivery.payload_snapshot["metadata"]["conversation_id"] == f"{admin_user.id}:{registrar_user.id}"
    assert fake_chat_manager.notify_new_message.call_count == 2
