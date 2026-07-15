"""
Passkey Credential Model — M4-P1-4 (Epic M4 — Backend Security & Compliance).

Stores WebAuthn passkey credentials for patients who want alternative
authentication (instead of Telegram Mini App only).

Each patient can register multiple passkeys (phone, laptop, hardware key).
Passkeys are phishing-resistant by design (WebAuthn standard).

Fields:
- patient_id: linked patient
- credential_id: WebAuthn credential ID (base64url, unique)
- public_key: COSE-encoded public key
- sign_count: replay protection counter
- transports: list of supported transports (usb, nfc, ble, internal)
- device_type: platform (TouchID/FaceID) or cross-platform (YubiKey)
- name: user-assigned name ("iPhone 15", "Work laptop")
- active: can be deactivated without deleting
- created_at / last_used_at: audit timestamps
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class PasskeyCredential(Base):
    """WebAuthn passkey credential for patient authentication (M4-P1-4)."""

    __tablename__ = "passkey_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ─── Patient ───────────────────────────────────────────────────────────
    patient_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Patient who owns this passkey",
    )

    # ─── WebAuthn credential ───────────────────────────────────────────────
    credential_id: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        unique=True,
        index=True,
        comment="WebAuthn credential ID (base64url encoded)",
    )
    public_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="COSE-encoded public key (base64url)",
    )
    sign_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Replay protection counter (incremented on each use)",
    )

    # ─── Metadata ──────────────────────────────────────────────────────────
    transports: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        comment="Comma-separated: usb,nfc,ble,internal",
    )
    device_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="platform (TouchID/FaceID) or cross-platform (YubiKey)",
    )
    name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="User-assigned name (e.g. 'iPhone 15', 'Work laptop')",
    )

    # ─── Status ────────────────────────────────────────────────────────────
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    # ─── Timestamps ────────────────────────────────────────────────────────
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful authentication with this passkey",
    )

    # ─── Relationship ──────────────────────────────────────────────────────
    patient = relationship("Patient", foreign_keys=[patient_id])

    __table_args__ = (
        Index("ix_passkey_credentials_patient_active", "patient_id", "active"),
    )

    def __repr__(self) -> str:
        return (
            f"<PasskeyCredential("
            f"id={self.id}, "
            f"patient_id={self.patient_id}, "
            f"name={self.name}, "
            f"active={self.active})>"
        )
