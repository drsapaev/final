"""
Модель для связей между пациентами (семья, опекунство)

Позволяет связывать пациентов для:
- Регистрации детей без телефона (контакт - родитель)
- Отображения истории семьи
- Уведомлений опекунам
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.user import User


class RelationType(str):
    """Типы семейных связей"""
    PARENT = "parent"           # Родитель
    CHILD = "child"             # Ребёнок
    GUARDIAN = "guardian"       # Опекун
    SPOUSE = "spouse"           # Супруг(а)
    SIBLING = "sibling"         # Брат/сестра
    OTHER = "other"             # Другое


class FamilyRelation(Base):
    """
    Связь между двумя пациентами.
    
    Например:
    - patient_id=5 (ребёнок) -> related_patient_id=3 (мама), relation_type="parent"
    - Это значит: у пациента 5 родитель - пациент 3
    """
    __tablename__ = "family_relations"
    __table_args__ = (
        Index('idx_family_relations_patient', 'patient_id'),
        Index('idx_family_relations_related', 'related_patient_id'),
        {'extend_existing': True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Пациент, для которого указана связь
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Связанный пациент (родственник/опекун)
    related_patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Тип связи (с точки зрения related_patient по отношению к patient)
    # Например: "parent" означает, что related_patient - родитель patient
    relation_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RelationType.OTHER
    )
    
    # Описание связи (опционально)
    description: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    
    # Является ли основным контактом (для уведомлений)
    is_primary_contact: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )

    # Relationships
    patient: Mapped["Patient"] = relationship(
        "Patient",
        foreign_keys=[patient_id],
        backref="family_relations"
    )
    related_patient: Mapped["Patient"] = relationship(
        "Patient",
        foreign_keys=[related_patient_id]
    )
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])

    def __repr__(self) -> str:
        return f"<FamilyRelation {self.patient_id} -> {self.related_patient_id} ({self.relation_type})>"
