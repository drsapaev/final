"""
CRUD операции для сообщений
"""

from typing import List, Optional, Tuple
from datetime import datetime
from sqlalchemy import or_, and_, func, desc, case
from sqlalchemy.orm import Session

from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageCreate


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
            content=obj_in.content,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get(self, db: Session, *, id: int) -> Optional[Message]:
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
    ) -> Tuple[List[Message], int]:
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
        user_id: int
    ) -> List[dict]:
        """Получить список всех бесед пользователя"""
        
        # Получаем все сообщения пользователя
        all_messages = db.query(Message).filter(
            or_(Message.sender_id == user_id, Message.recipient_id == user_id)
        ).order_by(desc(Message.created_at)).all()
        
        # Группируем по собеседникам
        conversations = {}
        for msg in all_messages:
            other_user_id = msg.recipient_id if msg.sender_id == user_id else msg.sender_id
            
            if other_user_id not in conversations:
                # Получаем информацию о пользователе
                other_user = db.query(User).filter(User.id == other_user_id).first()
                if not other_user:
                    continue
                
                # Resolve display name: full_name -> username -> email -> ID
                display_name = other_user.full_name
                if not display_name:
                    # Если username похож на email, пробуем найти что-то получше или оставляем как есть
                    display_name = other_user.username
                if not display_name:
                    display_name = other_user.email
                if not display_name:
                    display_name = f"User {other_user_id}"
                
                # Считаем непрочитанные
                unread = db.query(Message).filter(
                    Message.sender_id == other_user_id,
                    Message.recipient_id == user_id,
                    Message.is_read == False
                ).count()
                
                conversations[other_user_id] = {
                    'user_id': other_user.id,
                    'user_name': display_name,
                    'user_role': other_user.role or "User",
                    'last_message': msg.content[:100] if len(msg.content) > 100 else msg.content,
                    'last_message_time': msg.created_at,
                    'unread_count': unread,
                    'is_online': False
                }
        
        # Сортируем по времени последнего сообщения
        result = list(conversations.values())
        result.sort(key=lambda x: x['last_message_time'], reverse=True)
        
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
    ) -> Optional[Message]:
        """Пометить сообщение как прочитанное"""
        message = db.query(Message).filter(
            Message.id == message_id,
            Message.recipient_id == user_id
        ).first()
        
        if message and not message.is_read:
            message.is_read = True
            message.read_at = datetime.utcnow()
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
        now = datetime.utcnow()
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
