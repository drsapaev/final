from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from jose import jwt

from app.services.ai_chat_api_service import AIChatApiDomainError, AIChatApiService


@pytest.mark.unit
class TestAIChatApiService:
    def test_get_session_payload_raises_when_session_missing(self):
        repository = SimpleNamespace(
            get_session_for_user=lambda session_id, user_id: None,
            get_message_for_user=lambda message_id, user_id: None,
            get_user=lambda user_id: None,
        )
        service = AIChatApiService(db=None, repository=repository)

        with pytest.raises(AIChatApiDomainError) as exc_info:
            service.get_session_payload(session_id=1, user_id=10)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_messages_payload_returns_serialized_messages(self):
        message = SimpleNamespace(
            id=7,
            role="assistant",
            content="ok",
            provider="p",
            model="m",
            tokens_used=10,
            latency_ms=50,
            is_error=False,
            was_cached=False,
            created_at=datetime(2026, 2, 14, 12, 0, 0),
        )
        repository = SimpleNamespace(
            get_session_for_user=lambda session_id, user_id: SimpleNamespace(id=session_id),
            get_message_for_user=lambda message_id, user_id: None,
            get_user=lambda user_id: None,
        )
        chat_service = SimpleNamespace(
            get_history=lambda session_id, limit, before_id: None,
            add_feedback=lambda **kwargs: None,
        )

        async def get_history(session_id, limit, before_id):
            return [message]

        chat_service.get_history = get_history
        service = AIChatApiService(
            db=None,
            repository=repository,
            chat_service_factory=lambda db: chat_service,
        )

        payload = await service.get_messages_payload(
            session_id=1,
            user_id=10,
            limit=50,
            before_id=None,
        )

        assert payload[0]["id"] == 7
        assert payload[0]["content"] == "ok"

    @pytest.mark.asyncio
    async def test_add_feedback_payload_raises_when_message_missing(self):
        repository = SimpleNamespace(
            get_session_for_user=lambda session_id, user_id: None,
            get_message_for_user=lambda message_id, user_id: None,
            get_user=lambda user_id: None,
        )
        service = AIChatApiService(db=None, repository=repository)

        with pytest.raises(AIChatApiDomainError) as exc_info:
            await service.add_feedback_payload(
                message_id=15,
                user_id=2,
                feedback_type="helpful",
                comment=None,
                correction=None,
            )

        assert exc_info.value.status_code == 404

    def test_authenticate_websocket_user_decodes_token_and_loads_user(self):
        user = SimpleNamespace(id=12, username="u12")
        repository = SimpleNamespace(
            get_session_for_user=lambda session_id, user_id: None,
            get_message_for_user=lambda message_id, user_id: None,
            get_user=lambda user_id: user if user_id == 12 else None,
        )
        service = AIChatApiService(db=None, repository=repository)
        token = jwt.encode({"sub": "12"}, "secret", algorithm="HS256")

        authenticated = service.authenticate_websocket_user(
            token=token,
            secret_key="secret",
            algorithm="HS256",
        )

        assert authenticated.username == "u12"
