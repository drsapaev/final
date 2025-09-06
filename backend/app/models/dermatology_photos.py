"""
Модели для фото дерматологии
Основа: passport.md стр. 1789-2063
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

class DermatologyPhoto(Base):
    """Фото для дерматологических пациентов"""
    __tablename__ = "dermatology_photos"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    
    # Категория фото
    category = Column(String(20), nullable=False)  # before, after, progress
    
    # Информация о файле
    filename = Column(String(255), nullable=False)  # Уникальное имя файла
    original_filename = Column(String(255), nullable=False)  # Оригинальное имя
    file_path = Column(String(500), nullable=False)  # Путь к файлу
    thumbnail_path = Column(String(500), nullable=True)  # Путь к миниатюре
    file_size = Column(BigInteger, nullable=False)  # Размер в байтах
    mime_type = Column(String(100), nullable=False)  # MIME тип
    
    # Метаданные
    notes = Column(Text, nullable=True)  # Заметки врача
    tags = Column(String(500), nullable=True)  # Теги (через запятую)
    
    # Системные поля
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    patient = relationship("Patient", back_populates="dermatology_photos")
    uploader = relationship("User", foreign_keys=[uploaded_by])
