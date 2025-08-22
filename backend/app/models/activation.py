from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Enum as SAEnum, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base  # декларативная база


class ActivationStatus(str):
    ISSUED = "issued"    # ключ выдан, ещё не привязан
    TRIAL = "trial"      # тестовый режим (может быть сразу активен)
    ACTIVE = "active"    # привязан к устройству, срок не истёк
    EXPIRED = "expired"  # срок истёк
    REVOKED = "revoked"  # отозван админом


class Activation(Base):
    """
    Таблица активаций/ключей. Один ключ = одно устройство (machine_hash).
    """
    __tablename__ = "activations"
    __table_args__ = (
        UniqueConstraint("key", name="uq_activation_key"),
    )

    # UUID как строка (36)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Ключ активации (человекочитаемый)
    key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Хэш устройства (заполняется при привязке). Пустой => ещё не активирован.
    machine_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    # Дата и время окончания действия (UTC)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True, index=True)

    # Статус
    status: Mapped[str] = mapped_column(
        SAEnum(
            ActivationStatus.ISSUED,
            ActivationStatus.TRIAL,
            ActivationStatus.ACTIVE,
            ActivationStatus.EXPIRED,
            ActivationStatus.REVOKED,
            name="activation_status",
        ),
        nullable=False,
        default=ActivationStatus.ISSUED,
    )

    # Опциональные метаданные (кто выдал, заметки, версия)
    meta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)