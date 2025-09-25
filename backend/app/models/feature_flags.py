"""
Модели для управления фича-флагами
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.db.base_class import Base


class FeatureFlag(Base):
    """
    Модель фича-флага для управления функциональностью системы
    """
    __tablename__ = "feature_flags"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Основная информация
    key = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    
    # Состояние флага
    enabled = Column(Boolean, default=False, nullable=False)
    
    # Конфигурация
    config = Column(JSON, default=dict)  # Дополнительные настройки флага
    
    # Метаданные
    category = Column(String(50), default="general")  # Категория флага
    environment = Column(String(20), default="all")  # production, staging, development, all
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Аудит
    created_by = Column(String(100))
    updated_by = Column(String(100))
    
    def __repr__(self):
        return f"<FeatureFlag(key='{self.key}', enabled={self.enabled})>"


class FeatureFlagHistory(Base):
    """
    История изменений фича-флагов для аудита
    """
    __tablename__ = "feature_flag_history"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Связь с флагом
    flag_key = Column(String(100), nullable=False, index=True)
    
    # Изменения
    action = Column(String(20), nullable=False)  # created, enabled, disabled, updated, deleted
    old_value = Column(JSON)
    new_value = Column(JSON)
    
    # Метаданные изменения
    changed_by = Column(String(100))
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(45))  # IPv4/IPv6
    user_agent = Column(String(500))
    reason = Column(Text)  # Причина изменения
    
    def __repr__(self):
        return f"<FeatureFlagHistory(flag_key='{self.flag_key}', action='{self.action}')>"
