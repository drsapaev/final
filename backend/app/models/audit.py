from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    entity_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)