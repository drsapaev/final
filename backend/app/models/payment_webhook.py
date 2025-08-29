# app/models/payment_webhook.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class PaymentWebhook(Base):
    __tablename__ = "payment_webhooks"

    id = Column(Integer, primary_key=True, index=True)
    
    # Основная информация
    provider = Column(String(50), nullable=False, index=True)  # payme, click, etc.
    webhook_id = Column(String(100), nullable=False, unique=True, index=True)
    transaction_id = Column(String(100), nullable=False, index=True)
    
    # Статус
    status = Column(String(20), default="pending", nullable=False)  # pending, processed, failed
    amount = Column(Integer, nullable=False)  # в тийинах (1 сум = 100 тийин)
    currency = Column(String(3), default="UZS", nullable=False)
    
    # Данные вебхука
    raw_data = Column(JSON, nullable=False)  # сырые данные от провайдера
    signature = Column(String(500), nullable=True)  # подпись для верификации
    
    # Связи (пока без внешних ключей для SQLite)
    visit_id = Column(Integer, nullable=True)
    patient_id = Column(Integer, nullable=True)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id = Column(Integer, primary_key=True, index=True)
    
    # Основная информация
    transaction_id = Column(String(100), nullable=False, unique=True, index=True)
    provider = Column(String(50), nullable=False, index=True)
    
    # Финансовая информация
    amount = Column(Integer, nullable=False)
    currency = Column(String(3), default="UZS", nullable=False)
    commission = Column(Integer, default=0)  # комиссия провайдера
    
    # Статус
    status = Column(String(20), default="pending", nullable=False)  # pending, success, failed, cancelled
    
    # Связи (пока без внешних ключей для SQLite)
    webhook_id = Column(Integer, nullable=True)
    visit_id = Column(Integer, nullable=True)
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class PaymentProvider(Base):
    __tablename__ = "payment_providers"

    id = Column(Integer, primary_key=True, index=True)
    
    # Основная информация
    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(50), nullable=False, unique=True, index=True)
    
    # Конфигурация
    is_active = Column(Boolean, default=True, nullable=False)
    webhook_url = Column(String(500), nullable=True)
    api_key = Column(String(500), nullable=True)
    secret_key = Column(String(500), nullable=True)
    
    # Настройки
    commission_percent = Column(Integer, default=0)  # комиссия в процентах
    min_amount = Column(Integer, default=0)  # минимальная сумма
    max_amount = Column(Integer, default=100000000)  # максимальная сумма
    
    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
