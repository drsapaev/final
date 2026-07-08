"""Service audit log model for tracking changes to services."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    pass


class ServiceAuditLog(Base):
    """Audit log for service changes.

    Tracks all modifications to services including:
    - Price changes
    - Code changes
    - Category changes
    - Status changes (active/inactive)
    - Any other field modifications
    """

    __tablename__ = "service_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Service reference
    service_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # User who made the change
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Action type
    action: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True
    )  # 'create', 'update', 'delete', 'activate', 'deactivate'

    # Changed fields (JSON)
    changes: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )  # {"field": {"old": value, "new": value}}

    # Old and new values as JSON for full snapshot
    old_values: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )

    new_values: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True
    )

    # Optional comment/reason
    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    # IP address and user agent for security
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True
    )  # IPv6 max length

    user_agent: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True
    )

    # Relationships
    service = relationship("Service", backref="audit_logs")
    user = relationship("User", backref="service_audit_logs")

    def __repr__(self) -> str:
        return f"<ServiceAuditLog(id={self.id}, service_id={self.service_id}, action={self.action})>"
