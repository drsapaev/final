"""Repository helpers for ai chat API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class AiChatApiRepository:
    """Shared DB session adapter for ai chat service."""

    def __init__(self, db: Session):
        self.db = db
