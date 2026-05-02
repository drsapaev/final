"""Service layer for ai_chat endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.ai_chat_api_repository import AIChatApiRepository
from app.services.ai.chat_service import AIChatService, get_chat_service


@dataclass
class AIChatApiDomainError(Exception):
    status_code: int
    detail: str


class AIChatApiService:
    """Builds payloads for AI chat REST/WebSocket endpoint handlers."""

    def __init__(
        self,
        db: Session,
        repository: AIChatApiRepository | None = None,
        chat_service_factory: Callable[[Session], AIChatService] | None = None,
    ):
        self.db = db
        self.repository = repository or AIChatApiRepository(db)
        self._chat_service_factory = chat_service_factory or get_chat_service

    def _chat_service(self) -> AIChatService:
        return self._chat_service_factory(self.db)

    @staticmethod
    def _session_payload(session) -> dict:
        return {
            "id": session.id,
            "title": session.title,
            "context_type": session.context_type,
            "specialty": session.specialty,
            "is_active": session.is_active,
            "message_count": len(session.messages),
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        }

    @staticmethod
    def _message_payload(message) -> dict:
        return {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "provider": message.provider,
            "model": message.model,
            "tokens_used": message.tokens_used,
            "latency_ms": message.latency_ms,
            "is_error": message.is_error,
            "was_cached": message.was_cached,
            "created_at": message.created_at.isoformat(),
        }

    def get_session_payload(self, *, session_id: int, user_id: int) -> dict:
        session = self.repository.get_session_for_user(
            session_id=session_id,
            user_id=user_id,
        )
        if not session:
            raise AIChatApiDomainError(status_code=404, detail="Session not found")
        return self._session_payload(session)

    async def get_messages_payload(
        self,
        *,
        session_id: int,
        user_id: int,
        limit: int,
        before_id: int | None,
    ) -> list[dict]:
        session = self.repository.get_session_for_user(
            session_id=session_id,
            user_id=user_id,
        )
        if not session:
            raise AIChatApiDomainError(status_code=404, detail="Session not found")

        messages = await self._chat_service().get_history(
            session_id,
            limit=limit,
            before_id=before_id,
        )
        return [self._message_payload(message) for message in messages]

    async def add_feedback_payload(
        self,
        *,
        message_id: int,
        user_id: int,
        feedback_type: str,
        comment: str | None,
        correction: str | None,
    ) -> dict[str, Any]:
        message = self.repository.get_message_for_user(
            message_id=message_id,
            user_id=user_id,
        )
        if not message:
            raise AIChatApiDomainError(status_code=404, detail="Message not found")

        try:
            feedback = await self._chat_service().add_feedback(
                message_id=message_id,
                user_id=user_id,
                feedback_type=feedback_type,
                comment=comment,
                correction=correction,
            )
        except ValueError as exc:
            raise AIChatApiDomainError(status_code=400, detail=str(exc)) from exc

        return {
            "message": "Feedback recorded",
            "feedback_id": feedback.id,
            "feedback_type": feedback.feedback_type,
        }

    def authenticate_websocket_user(
        self,
        *,
        token: str,
        secret_key: str,
        algorithm: str,
    ) -> User | None:
        try:
            payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        except JWTError:
            return None

        user_id = payload.get("sub")
        if user_id is None:
            return None

        try:
            parsed_user_id = int(user_id)
        except (TypeError, ValueError):
            return None

        return self.repository.get_user(parsed_user_id)
