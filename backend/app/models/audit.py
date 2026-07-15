"""
AuditLog model — unified audit log for all system events (M5.1 + M5.5).

Extended from original audit.py to support:
- event_type (PATIENT_LOGIN, DOCTOR_OPEN_EMR, ADMIN_EXPORT, etc.)
- actor_patient_id (for patient-initiated actions)
- subject_patient_id (whose PHI was accessed)
- outcome (success | denied | error)
- reason_code (M5.4: why the action was performed)
- ip_address, user_agent, session_id (request metadata)

M5.5: Immutable — DB trigger prevents UPDATE/DELETE (migration 0044).

Backward compatible: existing fields (action, entity_type, entity_id,
actor_user_id, payload, created_at) are preserved.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class AuditLog(Base):
    """Unified audit log for all system events (M5.1 + M5.5).

    Immutable: append-only. DB trigger prevents UPDATE/DELETE.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        # M5.1: New indexes for unified audit queries
        Index("ix_audit_event_created", "event_type", "created_at"),
        Index("ix_audit_actor_created", "actor_user_id", "created_at"),
        Index("ix_audit_subject_created", "subject_patient_id", "created_at"),
        Index("ix_audit_outcome_created", "outcome", "created_at"),
        {"extend_existing": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # ─── Original fields (backward compatible) ─────────────────────────────
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
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    # ─── M5.1: New fields for unified audit ────────────────────────────────
    event_type: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        index=True,
        comment="PATIENT_LOGIN | DOCTOR_OPEN_EMR | ADMIN_EXPORT | etc. (M5.1)",
    )
    actor_patient_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Patient ID (null for staff actions) — M5.1",
    )
    actor_role: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Role at time of action — M5.1",
    )
    actor_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="staff",
        comment="staff | patient | system — M5.1",
    )
    subject_patient_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Patient whose PHI was accessed — M5.1",
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="lab_report | emr | appointment | user | payment — M5.1",
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="ID of specific resource — M5.1",
    )
    outcome: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="success",
        comment="success | denied | error — M5.1",
    )
    reason_code: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Why the action was performed (M5.4)",
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, event_type={self.event_type}, "
            f"action={self.action}, outcome={self.outcome})>"
        )
