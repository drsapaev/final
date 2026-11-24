"""Authenticated laboratory report workflow history."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class LabReportWorkflowEvent(Base):
    __tablename__ = "lab_report_workflow_events"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('entered', 'submitted', 'reviewed', 'returned', "
            "'qc_recorded', 'finalized', 'revision_created')",
            name="ck_lab_workflow_event_kind",
        ),
        Index("ix_lab_workflow_event_report_kind", "instance_id", "kind", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instance_id: Mapped[int] = mapped_column(
        ForeignKey("lab_report_instances.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    actor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    report_version: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expected_version: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(1000))
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON)
