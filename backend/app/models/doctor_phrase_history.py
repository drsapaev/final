"""
DoctorPhraseHistory - История фраз врача для автоподсказок

Хранит извлечённые фразы из предыдущих записей врача
для использования в autocomplete (история, не генерация).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class DoctorPhraseHistory(Base):
    """
    История фраз врача - основа для autocomplete из истории.
    
    Принцип: НЕ генерация, а поиск и ранжирование ранее введённых фраз.
    """
    
    __tablename__ = "doctor_phrase_history"
    __table_args__ = (
        # Составной индекс для быстрого поиска
        Index('ix_doctor_phrase_lookup', 'doctor_id', 'field', 'specialty'),
        # Индекс для prefix search
        Index('ix_doctor_phrase_prefix', 'doctor_id', 'field', 'prefix_index'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Врач (FK → users)
    doctor_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False,
        index=True
    )
    
    # Поле EMR: 'complaints', 'anamnesis_morbi', 'anamnesis_vitae', 
    # 'examination', 'diagnosis', 'treatment', 'recommendations'
    field: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # Сама фраза (например: "давящего характера, усиливается к вечеру")
    phrase: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Первые N символов для prefix search (lowercase, stripped)
    prefix_index: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # Статистика использования
    usage_count: Mapped[int] = mapped_column(Integer, default=1)
    last_used: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        onupdate=func.now()
    )
    first_used: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    
    # Специальность врача (кардиология, терапия и т.д.)
    specialty: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Контекст (опционально - предыдущие слова для лучшего matching)
    context_prefix: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Telemetry для расчёта acceptance_rate
    suggestions_shown: Mapped[int] = mapped_column(Integer, default=0)
    suggestions_accepted: Mapped[int] = mapped_column(Integer, default=0)
    
    # Связь с врачом
    doctor: Mapped["User"] = relationship("User", foreign_keys=[doctor_id])

    def __repr__(self) -> str:
        return f"<DoctorPhraseHistory(id={self.id}, doctor={self.doctor_id}, field={self.field}, phrase='{self.phrase[:30]}...')>"
    
    @staticmethod
    def create_prefix_index(phrase: str, length: int = 50) -> str:
        """Создать индекс для prefix search"""
        return phrase.lower().strip()[:length]
