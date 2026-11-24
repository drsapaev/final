"""Clinical confirmation of released critical reports."""

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class LabCriticalCommunication(Base):
    __tablename__ = "lab_critical_communications"
    __table_args__ = (
        Index("ix_lab_critical_dispatch", "state", "next_attempt_at"),
        Index("ix_lab_critical_recipient", "recipient_user_id", "state"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    report_instance_id: Mapped[int] = mapped_column(
        ForeignKey("lab_report_instances.id", ondelete="RESTRICT"), unique=True
    )
    supersedes_communication_id: Mapped[int | None] = mapped_column(
        ForeignKey("lab_critical_communications.id", ondelete="RESTRICT")
    )
    field_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    recipient_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    released_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    acknowledged_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    inbox_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LabCriticalCommunicationEvent(Base):
    __tablename__ = "lab_critical_communication_events"
    __table_args__ = (
        Index("ix_lab_critical_events_communication", "communication_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    communication_id: Mapped[int] = mapped_column(
        ForeignKey("lab_critical_communications.id", ondelete="RESTRICT"),
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    event_type: Mapped[str] = mapped_column(String(24))
    channel: Mapped[str | None] = mapped_column(String(24))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
