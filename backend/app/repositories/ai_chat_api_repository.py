"""Repository helpers for ai_chat endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.ai_chat import AIChatMessage, AIChatSession
from app.models.user import User


class AIChatApiRepository:
    """Encapsulates ORM lookups used by AI chat API endpoints."""

    def __init__(self, db: Session):
        self.db = db

    def get_session_for_user(
        self,
        *,
        session_id: int,
        user_id: int,
    ) -> AIChatSession | None:
        return (
            self.db.query(AIChatSession)
            .filter(
                AIChatSession.id == session_id,
                AIChatSession.user_id == user_id,
            )
            .first()
        )

    def get_message_for_user(
        self,
        *,
        message_id: int,
        user_id: int,
    ) -> AIChatMessage | None:
        return (
            self.db.query(AIChatMessage)
            .join(AIChatSession)
            .filter(
                AIChatMessage.id == message_id,
                AIChatSession.user_id == user_id,
            )
            .first()
        )

    def get_user(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()
