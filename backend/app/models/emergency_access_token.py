"""
Emergency Access Token Model — M4-P2-1 (Epic M4).

One-time emergency tokens for patients who lost both Telegram and passkey.
Issued by admin after manual identity verification (passport, video call).

Fields:
- patient_id: patient who needs emergency access
- token_hash: SHA-256 hash of the emergency token (never store plaintext)
- resource_type: what the token grants access to (lab_report, cabinet_summary, all)
- resource_id: optional specific resource ID
- expires_at: short-lived (15 minutes)
- used: one-time use flag
- used_at: when the token was consumed
- issued_by: admin who issued the token
- issued_at: when the token was issued
- verification_method: how identity was verified (passport, video_call, in_person)
- verification_notes: admin's notes
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class EmergencyAccessToken(Base):
    """One-time emergency access token for patient PHI (M4-P2-1)."""

    __tablename__ = "emergency_access_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ─── Patient ───────────────────────────────────────────────────────────
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ─── Token ─────────────────────────────────────────────────────────────
    token_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
        comment="SHA-256 hash of the emergency token",
    )

    # ─── Scope ─────────────────────────────────────────────────────────────
    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="all",
        comment="all | lab_report | cabinet_summary | specific resource",
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Specific resource ID if resource_type is specific",
    )

    # ─── Validity ──────────────────────────────────────────────────────────
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Short-lived: 15 minutes",
    )

    # ─── One-time use ──────────────────────────────────────────────────────
    used: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ─── Audit ─────────────────────────────────────────────────────────────
    issued_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who issued the token",
    )
    issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    verification_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="passport | video_call | in_person",
    )
    verification_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Admin's verification notes",
    )

    # ─── Relationships ─────────────────────────────────────────────────────
    patient = relationship("Patient", foreign_keys=[patient_id])
    issuer = relationship("User", foreign_keys=[issued_by])

    __table_args__ = (
        Index("ix_emergency_tokens_patient_unused", "patient_id", "used"),
    )

    def __repr__(self) -> str:
        return (
            f"<EmergencyAccessToken("
            f"patient_id={self.patient_id}, "
            f"used={self.used}, "
            f"expires_at={self.expires_at})>"
        )
