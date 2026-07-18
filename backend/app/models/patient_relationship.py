"""
Patient Relationship Model — M4-P1-3 (Epic M4 — Backend Security & Compliance).

Defines authorization relationships between patients for PHI access:
- guardian: parent/legal guardian can access child/ward's PHI
- heir: authorized heir can access deceased relative's PHI
- caregiver: authorized caregiver can access patient's PHI

Separate from FamilyRelation (which is for family tree / contact info).
This model is specifically for ABAC authorization decisions.

Design:
- subject_patient_id: whose PHI can be accessed
- actor_patient_id: who can access it (the guardian/heir/caregiver)
- relationship_type: guardian | heir | caregiver
- permissions: JSON dict of allowed resource_type:action pairs
  (null = all permissions, empty dict = no permissions)
- valid_from / valid_to: time-bounded access
- active: can be deactivated without deleting the record
- created_by: admin who created the relationship (audit trail)
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class RelationshipType:
    """Types of PHI access relationships."""

    GUARDIAN = "guardian"      # Parent/legal guardian → child/ward
    HEIR = "heir"              # Authorized heir → deceased relative
    CAREGIVER = "caregiver"    # Authorized caregiver → patient


class PatientRelationship(Base):
    """PHI access relationship between patients (M4-P1-3).

    Allows one patient (actor) to access another patient's (subject) PHI
    based on a relationship: guardian, heir, or caregiver.

    Used by AuthorizationService to determine non-self access.
    """

    __tablename__ = "patient_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ─── Subject: whose PHI can be accessed ────────────────────────────────
    subject_patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Patient whose PHI can be accessed (the child/ward/deceased)",
    )

    # ─── Actor: who can access the PHI ─────────────────────────────────────
    actor_patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Patient who can access the subject's PHI (the guardian/heir/caregiver)",
    )

    # ─── Relationship type ─────────────────────────────────────────────────
    relationship_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
        comment="guardian | heir | caregiver",
    )

    # ─── Permissions ───────────────────────────────────────────────────────
    # JSON dict of allowed resource_type:action pairs.
    # null = all permissions (full access to subject's PHI)
    # {} = no permissions (relationship exists but no PHI access)
    # Example: {"lab_report": ["view", "download"], "cabinet_summary": ["view"]}
    permissions: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Allowed resource:actions. null = all, {} = none.",
    )

    # ─── Validity period ───────────────────────────────────────────────────
    valid_from: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When access becomes valid. null = immediately.",
    )
    valid_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When access expires. null = indefinite.",
    )

    # ─── Status ────────────────────────────────────────────────────────────
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Can be deactivated without deleting the record.",
    )

    # ─── Audit ─────────────────────────────────────────────────────────────
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    created_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who created this relationship.",
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the relationship was deactivated.",
    )
    deactivated_by: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who deactivated this relationship.",
    )

    # ─── Notes ─────────────────────────────────────────────────────────────
    notes: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="Optional notes (e.g. court order reference, guardianship document).",
    )

    # ─── Relationships ─────────────────────────────────────────────────────
    subject_patient = relationship(
        "Patient",
        foreign_keys=[subject_patient_id],
    )
    actor_patient = relationship(
        "Patient",
        foreign_keys=[actor_patient_id],
    )

    # ─── Constraints ───────────────────────────────────────────────────────
    __table_args__ = (
        # Actor and subject cannot be the same patient
        CheckConstraint(
            "subject_patient_id != actor_patient_id",
            name="ck_patient_relationships_subject_not_actor",
        ),
        # Prevent duplicate active relationships for same (subject, actor, type)
        Index(
            "ix_patient_relationships_unique_active",
            "subject_patient_id",
            "actor_patient_id",
            "relationship_type",
            unique=True,
            postgresql_where="active = true",
        ),
        Index("ix_patient_relationships_subject_type", "subject_patient_id", "relationship_type"),
        Index("ix_patient_relationships_actor_type", "actor_patient_id", "relationship_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<PatientRelationship("
            f"subject={self.subject_patient_id}, "
            f"actor={self.actor_patient_id}, "
            f"type={self.relationship_type}, "
            f"active={self.active})>"
        )

    def is_valid_now(self, now: datetime | None = None) -> bool:
        """Check if relationship is currently valid (active + within time bounds)."""
        from datetime import UTC, datetime as dt

        if not self.active:
            return False

        checked_at = now or dt.now(UTC)
        if checked_at.tzinfo is None:
            checked_at = checked_at.replace(tzinfo=UTC)

        if self.valid_from and checked_at < self.valid_from:
            return False
        if self.valid_to and checked_at > self.valid_to:
            return False

        return True

    def has_permission(self, resource_type: str, action: str) -> bool:
        """Check if this relationship allows a specific resource:action.

        Returns True if:
        - permissions is null (full access), OR
        - permissions dict contains resource_type with action in the list
        """
        if self.permissions is None:
            return True  # Full access

        allowed_actions = self.permissions.get(resource_type)
        if not allowed_actions:
            return False

        if isinstance(allowed_actions, list):
            return action in allowed_actions
        if isinstance(allowed_actions, str):
            return action == allowed_actions

        return False
