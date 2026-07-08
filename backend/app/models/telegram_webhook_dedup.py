
"""P1-9: Telegram webhook update_id dedup table."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class TelegramWebhookDedup(Base):
    """Prevents duplicate processing of the same Telegram update_id."""
    __tablename__ = "telegram_webhook_dedup"
    __table_args__ = (
        Index("ix_tg_webhook_dedup_update_id", "update_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    update_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    status: Mapped[str] = mapped_column(String(20), default="processed")
