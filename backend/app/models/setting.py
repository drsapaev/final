from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, UniqueConstraint

from .base import Base  # ваш общий Base (как в проекте)

class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    # колонка называется "key" в БД; SQLAlchemy сам её экранирует как "key"
    key: Mapped[str] = mapped_column("key", String(100), nullable=False)
    value: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # ВАЖНО: python-дефолты, чтобы не было NULL
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        UniqueConstraint("category", "key", name="uq_settings_category_key"),
    )
