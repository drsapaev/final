"""Repository helpers for messages endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.message import Message
from app.models.user import User


class MessagesApiRepository:
    """Encapsulates ORM operations for messaging API."""

    def __init__(self, db: Session):
        self.db = db

    def get_user(self, user_id: int):
        return self.db.query(User).filter(User.id == user_id).first()

    def query_users(self):
        return self.db.query(User)

    def get_message(self, message_id: int):
        return self.db.query(Message).filter(Message.id == message_id).first()

    def query_message_ids(self):
        return self.db.query(Message.id)

    def add(self, obj) -> None:
        self.db.add(obj)

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)

    def flush(self) -> None:
        self.db.flush()
