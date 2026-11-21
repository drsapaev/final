"""Clinical AI WebSocket safety envelope: real route and fail-closed output."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.v1.endpoints import ai_chat
from app.core.messaging_contract import CONTRACT_VERSION

_MISSING = object()


@pytest.fixture
def client(monkeypatch):
    """Exercise FastAPI's actual websocket route, with synthetic auth/provider."""
    application = FastAPI()
    application.include_router(ai_chat.router, prefix="/api/v1/ai/chat")
    application.dependency_overrides[get_db] = lambda: None
    monkeypatch.setattr(ai_chat, "extract_ws_token", lambda _ws: "SYNTHETIC-ws-token")
    monkeypatch.setattr(
        ai_chat,
        "authenticate_websocket",
        AsyncMock(return_value=SimpleNamespace(id=17, role="Doctor")),
    )
    monkeypatch.setattr(ai_chat, "has_permission", lambda *_args: True)
    monkeypatch.setattr(ai_chat, "_ai_ws_session_is_current", lambda *_args: True)
    with TestClient(application) as test_client:
        yield test_client


def _assert_safety(frame: dict) -> None:
    assert type(frame["ai_safety_meta"]) is dict
    assert frame["ai_safety_meta"]["requires_doctor_confirmation"] is True


def test_real_websocket_marks_every_medical_chunk_done_and_error(client, monkeypatch):
    text = "SYNTHETIC medical suggestion; clinician review required. " * 2
    response = SimpleNamespace(
        content=text,
        id=52,
        provider="SYNTHETIC-provider",
        model="SYNTHETIC-model",
        tokens_used=7,
        latency_ms=10,
        was_cached=False,
    )
    service = SimpleNamespace(send_message=AsyncMock(return_value=response))
    monkeypatch.setattr(ai_chat, "get_chat_service", lambda _db: service)

    with client.websocket_connect("/api/v1/ai/chat/ws") as socket:
        socket.send_json({"type": "message", "session_id": 42, "content": "SYNTHETIC"})
        chunks = []
        while True:
            frame = socket.receive_json()
            assert frame["contract_version"] == CONTRACT_VERSION
            assert frame["session_id"] == 42
            _assert_safety(frame)
            if frame["type"] == "done":
                assert frame["message_id"] == 52
                break
            assert frame["type"] == "chunk"
            chunks.append(frame["content"])
        assert len(chunks) > 1
        assert "".join(chunks) == text

        # Even an error rendered to the clinician retains the safety marker;
        # no provider call is made for an empty input.
        socket.send_json({"type": "message", "session_id": 42, "content": ""})
        error = socket.receive_json()
        assert error["type"] == "error"
        _assert_safety(error)
        assert service.send_message.await_count == 1


@pytest.mark.parametrize("event_type", ["chunk", "done", "error"])
def test_builder_never_accepts_a_forged_safety_override(event_type):
    frame = ai_chat._build_ai_ws_payload(
        event_type,
        42,
        ai_safety_meta={"requires_doctor_confirmation": False},
    )
    _assert_safety(frame)


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", ["chunk", "done", "error"])
@pytest.mark.parametrize(
    "metadata",
    [_MISSING, None, {}, {"requires_doctor_confirmation": False},
     {"requires_doctor_confirmation": 1},
     {"requires_doctor_confirmation": "true"}, [], "true"],
    ids=["missing", "null", "empty", "false", "integer", "string-boolean", "array", "string"],
)
async def test_invalid_safety_never_sends_a_medical_frame(event_type, metadata):
    class Socket:
        def __init__(self):
            self.sent = []
            self.closed = []

        async def send_json(self, payload):
            self.sent.append(payload)

        async def close(self, **kwargs):
            self.closed.append(kwargs)

    websocket = Socket()
    revoked, lock = asyncio.Event(), asyncio.Lock()
    frame = {"type": event_type, "content": "SYNTHETIC"}
    if metadata is not _MISSING:
        frame["ai_safety_meta"] = metadata

    with pytest.raises(ai_chat._AIWebSocketRevoked):
        await ai_chat._ai_ws_send(websocket, frame, revoked, lock)

    assert websocket.sent == []
    assert revoked.is_set()
    assert websocket.closed == [{"code": 1011, "reason": "Safety metadata required"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["content", "message"])
async def test_unrecognized_content_event_without_safety_is_not_sent(field):
    """Unknown event names must not bypass the medical-content boundary."""
    websocket = SimpleNamespace(send_json=AsyncMock(), close=AsyncMock())
    revoked, lock = asyncio.Event(), asyncio.Lock()
    with pytest.raises(ai_chat._AIWebSocketRevoked):
        await ai_chat._ai_ws_send(
            websocket, {"type": "future-event", field: "SYNTHETIC"}, revoked, lock
        )
    websocket.send_json.assert_not_awaited()
    websocket.close.assert_awaited_once_with(
        code=1011, reason="Safety metadata required"
    )


@pytest.mark.asyncio
async def test_safety_close_serializes_with_existing_revocation_close():
    """An invalid frame cannot produce a second close during revocation."""
    entered, release = asyncio.Event(), asyncio.Event()

    class Socket:
        def __init__(self):
            self.sent = []
            self.closed = []

        async def send_json(self, payload):
            self.sent.append(payload)

        async def close(self, **kwargs):
            self.closed.append(kwargs)
            entered.set()
            await release.wait()

    websocket = Socket()
    revoked, lock = asyncio.Event(), asyncio.Lock()
    closer = asyncio.create_task(
        ai_chat.close_revoked_websocket(websocket, revoked, lock)
    )
    await asyncio.wait_for(entered.wait(), timeout=2)
    sender = asyncio.create_task(
        ai_chat._ai_ws_send(websocket, {"type": "chunk", "content": "SYNTHETIC"}, revoked, lock)
    )
    await asyncio.sleep(0)
    assert websocket.sent == []
    release.set()
    await asyncio.wait_for(closer, timeout=2)
    with pytest.raises(ai_chat._AIWebSocketRevoked):
        await asyncio.wait_for(sender, timeout=2)
    assert websocket.closed == [{"code": 4001, "reason": "Authorization expired"}]
