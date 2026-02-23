"""Repository helpers for messages endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.crud.message import message as message_crud
from app.models.file_system import File as FileModel
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

    def create_message(self, *, sender_id: int, obj_in):
        return message_crud.create(self.db, sender_id=sender_id, obj_in=obj_in)

    def get_conversations_list(self, *, user_id: int):
        return message_crud.get_conversations_list(self.db, user_id=user_id)

    def get_unread_count(self, *, user_id: int) -> int:
        return message_crud.get_unread_count(self.db, user_id=user_id)

    def get_conversation(self, *, user1_id: int, user2_id: int, skip: int, limit: int):
        return message_crud.get_conversation(
            self.db,
            user1_id=user1_id,
            user2_id=user2_id,
            skip=skip,
            limit=limit,
        )

    def mark_conversation_as_read(self, *, user_id: int, other_user_id: int) -> None:
        message_crud.mark_conversation_as_read(self.db, user_id=user_id, other_user_id=other_user_id)

    def mark_message_as_read(self, *, message_id: int, user_id: int):
        return message_crud.mark_as_read(self.db, message_id=message_id, user_id=user_id)

    def delete_message_for_user(self, *, message_id: int, user_id: int) -> bool:
        return message_crud.delete_for_user(self.db, message_id=message_id, user_id=user_id)

    def get_message_by_id(self, *, message_id: int):
        return message_crud.get(self.db, id=message_id)

    def toggle_reaction(self, *, user_id: int, message_id: int, reaction: str) -> bool:
        return message_crud.toggle_reaction(
            self.db,
            user_id=user_id,
            message_id=message_id,
            reaction=reaction,
        )

    def get_unread_message_ids(self, *, sender_id: int, recipient_id: int) -> list[int]:
        query = self.query_message_ids().filter(
            Message.sender_id == sender_id,
            Message.recipient_id == recipient_id,
            Message.is_read.is_(False),
        )
        return [item[0] for item in query.all()]

    def get_file_by_id(self, file_id: int):
        return self.db.query(FileModel).filter(FileModel.id == file_id).first()

    def add(self, obj) -> None:
        self.db.add(obj)

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)

    def flush(self) -> None:
        self.db.flush()
