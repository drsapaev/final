"""Medical AI chat HTTP responses enforce the nested safety contract."""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.deps import get_current_user, get_db
from app.api.v1.endpoints import ai_chat
from app.services import ai_feature_gating


def _message(**changes):
    """A persisted historical row, deliberately without stored safety metadata."""
    value = {
        "id": 47,
        "role": "assistant",
        "content": "SYNTHETIC suggestion; clinician review required.",
        "provider": "SYNTHETIC-provider",
        "model": "SYNTHETIC-model",
        "tokens_used": 9,
        "latency_ms": 7,
        "is_error": False,
        "was_cached": False,
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    value.update(changes)
    return value


def _assert_strict_safety(message):
    assert type(message["ai_safety_meta"]) is dict
    assert message["ai_safety_meta"]["requires_doctor_confirmation"] is True


@pytest.fixture
def app(monkeypatch):
    application = FastAPI()
    application.include_router(ai_chat.router, prefix="/api/v1/ai/chat")
    application.dependency_overrides[get_db] = lambda: None
    application.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=19, role="Doctor"
    )
    monkeypatch.setattr(ai_feature_gating, "is_ai_feature_enabled", lambda *_args: True)
    return application


def test_send_real_http_has_required_nested_safety_and_keeps_response(app, monkeypatch):
    raw = _message()
    raw["created_at"] = datetime(2026, 1, 1, tzinfo=UTC)
    service = SimpleNamespace(send_message=AsyncMock(return_value=SimpleNamespace(**raw)))
    monkeypatch.setattr(ai_chat, "get_chat_service", lambda _db: service)

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/chat/sessions/31/messages",
            json={"content": "SYNTHETIC prompt", "include_history": True},
        )
    assert response.status_code == 200
    result = response.json()
    _assert_strict_safety(result)
    assert (result["id"], result["role"], result["content"]) == (
        47, "assistant", raw["content"]
    )
    service.send_message.assert_awaited_once_with(
        session_id=31, user_id=19, content="SYNTHETIC prompt", include_history=True
    )


def test_history_real_http_marks_legacy_assistant_rows_without_claiming_review(app, monkeypatch):
    historic = [_message(), _message(id=48, role="user", content="SYNTHETIC question")]
    service = SimpleNamespace(get_messages_payload=AsyncMock(return_value=historic))
    monkeypatch.setattr(ai_chat, "AIChatApiService", lambda _db: service)

    with TestClient(app) as client:
        response = client.get("/api/v1/ai/chat/sessions/31/messages?limit=5")
    assert response.status_code == 200
    result = response.json()
    assert [item["role"] for item in result] == ["assistant", "user"]
    _assert_strict_safety(result[0])
    assert result[0]["content"] == historic[0]["content"]
    service.get_messages_payload.assert_awaited_once_with(
        session_id=31, user_id=19, limit=5, before_id=None
    )


@pytest.mark.parametrize("bad", [False, 1, "true", None, [], {}])
def test_history_rejects_explicitly_invalid_safety_before_exposing_content(app, monkeypatch, bad):
    metadata = bad if isinstance(bad, (dict, list)) or bad is None else {
        "requires_doctor_confirmation": bad
    }
    service = SimpleNamespace(
        get_messages_payload=AsyncMock(return_value=[_message(ai_safety_meta=metadata)])
    )
    monkeypatch.setattr(ai_chat, "AIChatApiService", lambda _db: service)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/ai/chat/sessions/31/messages")
    assert response.status_code == 500
    assert "SYNTHETIC suggestion" not in response.text


@pytest.mark.parametrize("bad", [False, 1, "true", None, [], {}])
def test_schema_requires_boolean_true_without_coercion(bad):
    metadata = bad if isinstance(bad, (dict, list)) or bad is None else {
        "requires_doctor_confirmation": bad
    }
    with pytest.raises(ValidationError):
        ai_chat.ChatMessageResponse.model_validate(_message(ai_safety_meta=metadata))


def test_schema_rejects_missing_nested_safety():
    with pytest.raises(ValidationError):
        ai_chat.ChatMessageResponse.model_validate(_message())


def test_actual_openapi_declares_required_safety_for_chat_messages(app):
    openapi = app.openapi()
    schema = openapi["components"]["schemas"]["ChatMessageResponse"]
    assert "ai_safety_meta" in schema["required"]
    assert schema["properties"]["ai_safety_meta"]["$ref"] == "#/components/schemas/AIChatSafetyMeta"
    safety = openapi["components"]["schemas"]["AIChatSafetyMeta"]
    assert "requires_doctor_confirmation" in safety["required"]
    assert safety["properties"]["requires_doctor_confirmation"]["const"] is True
    path = openapi["paths"]["/api/v1/ai/chat/sessions/{session_id}/messages"]
    history = path["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    reply = path["post"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert history["items"]["$ref"] == "#/components/schemas/ChatMessageResponse"
    assert reply["$ref"] == "#/components/schemas/ChatMessageResponse"


def test_denied_user_cannot_read_history_and_provider_is_not_called(app, monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=20, role="Cashier"
    )
    service = SimpleNamespace(get_messages_payload=AsyncMock())
    monkeypatch.setattr(ai_chat, "AIChatApiService", lambda _db: service)
    with TestClient(app) as client:
        response = client.get("/api/v1/ai/chat/sessions/31/messages")
    assert response.status_code == 403
    service.get_messages_payload.assert_not_awaited()


def test_send_service_error_does_not_expose_provider_content(app, monkeypatch):
    service = SimpleNamespace(
        send_message=AsyncMock(side_effect=ValueError("SYNTHETIC private provider response"))
    )
    monkeypatch.setattr(ai_chat, "get_chat_service", lambda _db: service)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/chat/sessions/31/messages", json={"content": "SYNTHETIC"}
        )
    assert response.status_code == 404
    assert "private provider response" not in response.text
