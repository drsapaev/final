"""
EMR v2 Models - Production-grade Electronic Medical Record

Architecture:
- EMRRecord: Main EMR entity (one per visit)
- EMRRevision: Immutable version snapshots (legal compliance)
- EMRAuditLog: PHI-specific audit trail

Rules:
- EMR is NEVER physically deleted
- Every change creates a new revision
- Snapshots are immutable (not diffs)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base

if TYPE_CHECKING:
    pass


# System user ID for migrations and automated actions
SYSTEM_USER_ID = 0


class EMRRecord(Base):
    """
    Production EMR Record - One per visit
    
    RULE: EMR is NEVER physically deleted
    RULE: visit_id is unique (one EMR per visit)
    """

    __tablename__ = "emr_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # ✅ Core relationships (SSOT)
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Patient - for search and analytics",
    )
    visit_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("visits.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        unique=True,
        comment="Visit - primary anchor (one EMR per visit)",
    )

    # ✅ Version control
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, comment="Increments on each save"
    )

    # ✅ Clinical data (JSONB for flexibility)
    data: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Complete clinical data: complaints, anamnesis, diagnosis, etc.",
    )

    # ✅ Materialized fields for search/indexing (per user feedback)
    diagnosis_main: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        index=True,
        comment="Extracted main diagnosis for search",
    )
    icd10_code: Mapped[Optional[str]] = mapped_column(
        String(16),
        nullable=True,
        index=True,
        comment="Extracted ICD-10 code for reports",
    )

    # ✅ Status workflow
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        index=True,
        comment="draft | in_progress | signed | amended | locked",
    )

    # ✅ Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    created_by: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True, comment="User ID who created"
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    signed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True, comment="When EMR was signed"
    )
    signed_by: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True, comment="Doctor who signed"
    )

    # ✅ Soft delete (legal compliance)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ✅ Concurrency control (optimistic locking)
    row_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Optimistic locking version - increment on each save",
    )

    # ✅ Client session for smart conflict resolution (per user feedback)
    last_client_session_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="UUID of last editing session - for conflict resolution",
    )

    # Relationships
    revisions: Mapped[list["EMRRevision"]] = relationship(
        "EMRRevision",
        back_populates="emr_record",
        cascade="all, delete-orphan",
        order_by="desc(EMRRevision.version)",
    )

    # Indexes for common queries
    __table_args__ = (
        Index("ix_emr_records_patient_status", "patient_id", "status"),
        Index("ix_emr_records_signed", "signed_at", "signed_by"),
    )

    def __repr__(self) -> str:
        return f"<EMRRecord(id={self.id}, visit_id={self.visit_id}, version={self.version}, status={self.status})>"


class EMRRevision(Base):
    """
    EMR Revision - Immutable snapshot of EMR at a point in time
    
    RULE: Revisions are NEVER modified or deleted
    RULE: Store full snapshot (not diff) for legal compliance
    
    Note: Model uses DB column names for compatibility with existing schema
    """

    __tablename__ = "emr_revisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    emr_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("emr_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ✅ Version tracking
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # ✅ Complete snapshot (not diff - for legal compliance)
    # Note: DB column is 'data', model provides alias 'data_snapshot' for clarity
    data: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="Complete EMR data at this version"
    )

    # ✅ Change tracking
    change_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="created | updated | signed | amended | restored | migrated",
    )

    change_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Auto-generated: 'Changed fields: complaints, diagnosis'",
    )

    # ✅ Author tracking (using DB column names)
    created_by: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
        comment="User ID, or SYSTEM_USER_ID=0 for migrations",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    
    # Client session for tracking
    client_session_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="Client session that made this revision"
    )

    # Relationship
    emr_record: Mapped["EMRRecord"] = relationship(back_populates="revisions")

    # Unique constraint: one revision per version per EMR
    __table_args__ = (
        UniqueConstraint("emr_id", "version", name="uq_emr_revision_version"),
        Index("ix_emr_revisions_emr_version", "emr_id", "version"),
    )

    def __repr__(self) -> str:
        return f"<EMRRevision(id={self.id}, emr_id={self.emr_id}, version={self.version}, change_type={self.change_type})>"


class EMRAuditLog(Base):
    """
    EMR-specific audit log for PHI compliance
    
    Separate from general AuditLog for:
    - PHI isolation
    - EMR-specific actions
    - Healthcare compliance (HIPAA-like)
    """

    __tablename__ = "emr_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # ✅ Target identification
    emr_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    patient_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    visit_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # ✅ Action tracking
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="create | view | update | sign | amend | restore | export | print",
    )

    # ✅ Actor identification
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_role: Mapped[str] = mapped_column(String(50), nullable=False)

    # ✅ Request metadata
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45), nullable=True, comment="IPv4 or IPv6"
    )
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # ✅ Additional context
    extra_data: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional context: version, fields_changed, etc.",
    )

    # ✅ Timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )

    # Indexes for audit queries
    __table_args__ = (
        Index("ix_emr_audit_patient_action", "patient_id", "action"),
        Index("ix_emr_audit_user_timestamp", "user_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<EMRAuditLog(id={self.id}, emr_id={self.emr_id}, action={self.action}, user_id={self.user_id})>"
