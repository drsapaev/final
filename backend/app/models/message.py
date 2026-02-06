"""
Модель для сообщений между пользователями
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db.base_class import Base


class Message(Base):
    """Модель сообщения между пользователями"""
    
    __tablename__ = "messages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Отправитель и получатель
    sender_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    recipient_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Тип сообщения: "text" или "voice"
    message_type: Mapped[str] = mapped_column(
        String(20), 
        nullable=False, 
        default="text"
    )
    
    # Содержимое текстового сообщения
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    
    # Для голосовых сообщений
    file_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True
    )
    voice_duration: Mapped[Optional[int]] = mapped_column(
        Integer, 
        nullable=True,
        comment="Длительность голосового сообщения в секундах"
    )
    
    # EMR Integration: link message to patient record
    patient_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Link to patient record for medical consultations"
    )
    
    # Статус прочтения
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Мягкое удаление для отправителя и получателя
    is_deleted_by_sender: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted_by_recipient: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        nullable=False
    )
    
    # Relationships
    sender = relationship(
        "User", 
        foreign_keys=[sender_id],
        backref="sent_messages"
    )
    recipient = relationship(
        "User", 
        foreign_keys=[recipient_id],
        backref="received_messages"
    )
    file = relationship(
        "File",
        foreign_keys=[file_id],
        backref="voice_messages"
    )
    
    def __repr__(self):
        return f"<Message {self.id} from {self.sender_id} to {self.recipient_id}>"


class MessageReaction(Base):
    """Реакция на сообщение"""
    __tablename__ = "message_reactions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    message_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("messages.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    reaction: Mapped[str] = mapped_column(String(10), nullable=False) # Emoji char
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        nullable=False
    )
    
    # Relationships
    message = relationship("Message", backref="reactions")
    user = relationship("User")

