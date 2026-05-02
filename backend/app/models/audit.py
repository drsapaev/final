from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    entity_type: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    actor_user_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )

    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
