"""
Unified Audit Log Model — M5.1 (Epic M5 — Enterprise Security).

Single audit table for ALL events across the system:
- Patient access (M4-P0-1 PatientAccessAuditLog → migrated)
- EMR access (EMRAuditLog → migrated)
- Sensitive actions (diagnosis change, prescription, export, etc.)
- Session events (login, logout, revoke)
- Admin operations (user create, role change)

Replaces fragmented EMRAuditLog + PatientAccessAuditLog with one table.

M5.5: Immutable — DB trigger prevents UPDATE/DELETE.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class AuditLog(Base):
    """Unified audit log for all system events (M5.1 + M5.5).

    Immutable: append-only. DB trigger prevents UPDATE/DELETE.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ─── Event type ────────────────────────────────────────────────────────
    event_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        index=True,
        comment="PATIENT_LOGIN | DOCTOR_OPEN_EMR | ADMIN_EXPORT | etc.",
    )

    # ─── Actor: who performed the action ──────────────────────────────────
    actor_user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Staff user ID (null for patient actions)",
    )
    actor_patient_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Patient ID (null for staff actions)",
    )
    actor_role: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Role at time of action (admin/doctor/patient/etc.)",
    )
    actor_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="staff",
        comment="staff | patient | system",
    )

    # ─── Subject: whose data was accessed ─────────────────────────────────
    subject_patient_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Patient whose PHI was accessed (null for non-PHI events)",
    )

    # ─── Resource ──────────────────────────────────────────────────────────
    resource_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="lab_report | emr | appointment | user | payment | etc.",
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="ID of specific resource",
    )

    # ─── Action + outcome ──────────────────────────────────────────────────
    action: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="view | download | create | edit | delete | export | login | logout",
    )
    outcome: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="success",
        comment="success | denied | error",
    )

    # ─── Reason code (M5.4) ───────────────────────────────────────────────
    reason_code: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Why the action was performed, e.g. {context: consultation, id: 5832}",
    )

    # ─── Request metadata ─────────────────────────────────────────────────
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    # ─── Additional context ───────────────────────────────────────────────
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # ─── Timestamp ─────────────────────────────────────────────────────────
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(__import__("datetime").UTC),
        index=True,
    )

    # ─── Indexes ───────────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_audit_event_timestamp", "event_type", "timestamp"),
        Index("ix_audit_actor_timestamp", "actor_user_id", "timestamp"),
        Index("ix_audit_subject_timestamp", "subject_patient_id", "timestamp"),
        Index("ix_audit_resource_action", "resource_type", "action"),
        Index("ix_audit_outcome_timestamp", "outcome", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, event_type={self.event_type}, "
            f"action={self.action}, outcome={self.outcome})>"
        )
