"""
CRUD операции для сообщений
"""

from datetime import UTC, datetime

from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageCreate



def _make_preview(msg) -> str:
    """F-008: neutral preview without PHI — no message content in conversation list."""
    if msg.message_type == "voice":
        return "🎙 Голосовое сообщение"
    if msg.message_type == "file":
        return "📎 Файл"
    if msg.message_type == "image":
        return "🖼 Изображение"
    # Для текста — только индикатор длины, без контента
    return f"Сообщение ({len(msg.content)} символов)"


class CRUDMessage:
    """CRUD операции для сообщений"""

    def create(
        self,
        db: Session,
        *,
        sender_id: int,
        obj_in: MessageCreate
    ) -> Message:
        """Создать новое сообщение"""
        db_obj = Message(
            sender_id=sender_id,
            recipient_id=obj_in.recipient_id,
            patient_id=getattr(obj_in, "patient_id", None),
        )
        db_obj.set_content(obj_in.content)  # F-009: encrypt on write
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, *, id: int) -> Message | None:
        """Получить сообщение по ID"""
        return db.query(Message).filter(Message.id == id).first()

    def get_conversation(
        self,
        db: Session,
        *,
        user1_id: int,
        user2_id: int,
        skip: int = 0,
        limit: int = 50
    ) -> tuple[list[Message], int]:
        """Получить переписку между двумя пользователями"""
        query = db.query(Message).filter(
            or_(
                and_(Message.sender_id == user1_id, Message.recipient_id == user2_id),
                and_(Message.sender_id == user2_id, Message.recipient_id == user1_id)
            ),
            # Не показывать удалённые для текущего пользователя
            or_(
                and_(Message.sender_id == user1_id, Message.is_deleted_by_sender == False),
                and_(Message.recipient_id == user1_id, Message.is_deleted_by_recipient == False)
            )
        ).order_by(desc(Message.created_at))

        total = query.count()
        messages = query.offset(skip).limit(limit).all()

        return messages, total

    def get_conversations_list(
        self,
        db: Session,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 50
    ) -> list[dict]:
        """F-013: SQL-based conversations list — no N+1, with pagination."""
        from sqlalchemy import func, case, desc as sa_desc

        partner_expr = case(
            (Message.sender_id == user_id, Message.recipient_id),
            else_=Message.sender_id,
        ).label("partner_id")

        subq = (
            db.query(
                Message.id,
                Message.sender_id,
                Message.recipient_id,
                Message.content,
                Message.message_type,
                Message.created_at,
                partner_expr,
                func.row_number().over(
                    partition_by=partner_expr,
                    order_by=sa_desc(Message.created_at),
                ).label("rn"),
            )
            .filter(
                or_(Message.sender_id == user_id, Message.recipient_id == user_id),
            )
            .subquery()
        )

        rows = (
            db.query(subq, User)
            .join(User, User.id == subq.c.partner_id)
            .filter(subq.c.rn == 1)
            .order_by(sa_desc(subq.c.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

        if not rows:
            return []

        partner_ids = [row[0].partner_id for row in rows]
        unread_map = dict(
            db.query(Message.sender_id, func.count(Message.id))
            .filter(
                Message.recipient_id == user_id,
                Message.is_read == False,
                Message.sender_id.in_(partner_ids),
            )
            .group_by(Message.sender_id)
            .all()
        )

        result = []
        for row_data, partner in rows:
            display_name = partner.full_name or partner.username or partner.email or f"User {partner.id}"
            msg_type = row_data.message_type or "text"
            if msg_type == "voice":
                preview = "🎙 Голосовое сообщение"
            elif msg_type == "file":
                preview = "📎 Файл"
            elif msg_type == "image":
                preview = "🖼 Изображение"
            else:
                preview = f"Сообщение ({len(row_data.content or '')} символов)"

            result.append({
                'user_id': partner.id,
                'user_name': display_name,
                'user_role': partner.role or "User",
                'last_message': preview,
                'last_message_time': row_data.created_at,
                'unread_count': unread_map.get(partner.id, 0),
                'is_online': False,
            })

        return result

    def get_unread_count(self, db: Session, *, user_id: int) -> int:
        """Получить количество непрочитанных сообщений"""
        return db.query(Message).filter(
            Message.recipient_id == user_id,
            Message.is_read == False,
            Message.is_deleted_by_recipient == False
        ).count()

    def mark_as_read(
        self,
        db: Session,
        *,
        message_id: int,
        user_id: int
    ) -> Message | None:
        """Пометить сообщение как прочитанное"""
        message = db.query(Message).filter(
            Message.id == message_id,
            Message.recipient_id == user_id
        ).first()

        if message and not message.is_read:
            message.is_read = True
            message.read_at = datetime.now(UTC)
            db.commit()
            db.refresh(message)

        return message

    def mark_conversation_as_read(
        self,
        db: Session,
        *,
        user_id: int,
        other_user_id: int
    ) -> int:
        """Пометить все сообщения в беседе как прочитанные"""
        now = datetime.now(UTC)
        count = db.query(Message).filter(
            Message.sender_id == other_user_id,
            Message.recipient_id == user_id,
            Message.is_read == False
        ).update({
            Message.is_read: True,
            Message.read_at: now
        }, synchronize_session=False)
        db.commit()
        return count

    def delete_for_user(
        self,
        db: Session,
        *,
        message_id: int,
        user_id: int
    ) -> bool:
        """Мягкое удаление сообщения для пользователя"""
        message = db.query(Message).filter(Message.id == message_id).first()

    def toggle_reaction(
        self, db: Session, *, user_id: int, message_id: int, reaction: str
    ) -> bool:
        """CHAT-AUDIT-28 P0-1: implement toggle_reaction (was missing → 500).

        Toggles a reaction: if the same user+message+reaction exists, removes it;
        otherwise creates it.
        """
        from app.models.message import MessageReaction

        existing = (
            db.query(MessageReaction)
            .filter(
                MessageReaction.message_id == message_id,
                MessageReaction.user_id == user_id,
                MessageReaction.reaction == reaction,
            )
            .first()
        )
        if existing:
            db.delete(existing)
            db.commit()
            return False  # removed
        else:
            new_reaction = MessageReaction(
                message_id=message_id,
                user_id=user_id,
                reaction=reaction,
            )
            db.add(new_reaction)
            db.commit()
            return True  # added


        if not message:
            return False

        if message.sender_id == user_id:
            message.is_deleted_by_sender = True
        elif message.recipient_id == user_id:
            message.is_deleted_by_recipient = True
        else:
            return False

        db.commit()
        return True


message = CRUDMessage()
