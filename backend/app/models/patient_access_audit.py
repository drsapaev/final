"""
Patient Access Audit Log — PHI compliance for patient-facing endpoints.

M4-P0-1 (Epic M4 — Backend Security & Compliance):
Previously, patient-access endpoints (cabinet summary, forms preview,
form submission, report download, appointment booking) did NOT log
PHI access. EMRAuditLog exists but is doctor/staff-facing only.

This model provides:
- subject_patient_id: whose PHI is being accessed
- actor_patient_id: who is accessing (differs from subject for guardian/heir)
- actor_type: self | guardian | heir | staff (future-proofing for M4-P1-3)
- resource_type: lab_report | cabinet_summary | form_submission | appointment | manifest
- resource_id: optional ID of specific resource
- action: view | download | submit | create | preview
- outcome: success | denied | error
- ip_address + user_agent: request metadata
- session_id: correlation with UserSession (future M4-P0-2 JWT)
- correlation_id: request tracing
- timestamp: timezone-aware

Design decisions:
- Separate table from EMRAuditLog (patient-access has different fields,
  different retention policies, different query patterns)
- Immutable: append-only, no UPDATE/DELETE (enforced via DB GRANT + app guard)
- Indexed for common queries: patient_id+timestamp, actor_patient_id+timestamp
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class PatientAccessAuditLog(Base):
    """PHI access audit log for patient-facing endpoints (M4-P0-1)."""

    __tablename__ = "patient_access_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ─── Subject: whose PHI is being accessed ──────────────────────────────
    subject_patient_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="Patient whose PHI is being accessed",
    )

    # ─── Actor: who is accessing (differs from subject for guardian/heir) ──
    actor_patient_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Patient actor (self-access). NULL if actor is staff.",
    )
    actor_staff_user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Staff user actor. NULL if actor is patient.",
    )
    actor_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="self | guardian | heir | staff (future-proofing for M4-P1-3)",
    )
    actor_telegram_user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Telegram user ID if access via Mini App",
    )

    # ─── Resource: what is being accessed ──────────────────────────────────
    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="lab_report | cabinet_summary | form_submission | appointment | manifest | forms_preview",
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="ID of specific resource (e.g. report_id, form_id, appointment_id)",
    )

    # ─── Action + outcome ──────────────────────────────────────────────────
    action: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
        comment="view | download | submit | create | preview",
    )
    outcome: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="success",
        comment="success | denied | error",
    )

    # ─── Request metadata ──────────────────────────────────────────────────
    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
        comment="IPv4 or IPv6",
    )
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    session_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
        comment="UserSession ID (future M4-P0-2 JWT jti)",
    )
    correlation_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
        comment="Request tracing ID",
    )

    # ─── Additional context ────────────────────────────────────────────────
    extra_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional context: form_status, appointment_date, etc.",
    )

    # ─── Timestamp ─────────────────────────────────────────────────────────
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )

    # ─── Indexes for common audit queries ──────────────────────────────────
    __table_args__ = (
        Index("ix_patient_audit_subject_timestamp", "subject_patient_id", "timestamp"),
        Index("ix_patient_audit_actor_timestamp", "actor_patient_id", "timestamp"),
        Index("ix_patient_audit_resource_action", "resource_type", "action"),
        Index("ix_patient_audit_outcome_timestamp", "outcome", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<PatientAccessAuditLog("
            f"id={self.id}, "
            f"subject_patient_id={self.subject_patient_id}, "
            f"actor_type={self.actor_type}, "
            f"resource_type={self.resource_type}, "
            f"action={self.action}, "
            f"outcome={self.outcome})"
        )
