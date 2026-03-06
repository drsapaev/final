from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from app.api.deps import get_current_user
from app.main import app
from app.schemas.message import MessageOut
from app.services.messages_api_service import MessagesApiService


def _override_current_user() -> SimpleNamespace:
    return SimpleNamespace(
        id=101,
        role="Admin",
        full_name="Router Test User",
        username="router_test",
        email="router@test.local",
    )


def test_unread_endpoint_delegates_to_service(client, monkeypatch) -> None:
    captured = {}

    def fake_get_unread_count(self, *, user_id: int) -> int:
        captured["user_id"] = user_id
        return 7

    monkeypatch.setattr(MessagesApiService, "get_unread_count", fake_get_unread_count)
    app.dependency_overrides[get_current_user] = _override_current_user
    try:
        response = client.get("/api/v1/messages/unread")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.json() == {"unread_count": 7}
    assert captured["user_id"] == 101


def test_send_endpoint_delegates_to_service(client, monkeypatch) -> None:
    captured = {}

    async def fake_send_message(self, *, request, message_data, current_user):
        captured["recipient_id"] = message_data.recipient_id
        captured["sender_id"] = current_user.id
        return MessageOut(
            id=9001,
            sender_id=current_user.id,
            recipient_id=message_data.recipient_id,
            message_type="text",
            content=message_data.content,
            is_read=False,
            created_at=datetime.utcnow(),
            read_at=None,
            file_id=None,
            voice_duration=None,
            file_url=None,
            sender_name="Router Test User",
            sender_role="Admin",
            recipient_name="Receiver",
            recipient_role="Doctor",
            patient_id=None,
            reactions=[],
        )

    monkeypatch.setattr(MessagesApiService, "send_message", fake_send_message)
    app.dependency_overrides[get_current_user] = _override_current_user
    try:
        response = client.post(
            "/api/v1/messages/send",
            json={"recipient_id": 202, "content": "hello service wiring"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 9001
    assert payload["sender_id"] == 101
    assert payload["recipient_id"] == 202
    assert payload["content"] == "hello service wiring"
    assert captured == {"recipient_id": 202, "sender_id": 101}

