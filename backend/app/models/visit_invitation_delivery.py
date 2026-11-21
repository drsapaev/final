"""Durable subject-bound attempt to deliver a visit confirmation invitation."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class VisitInvitationDelivery(Base):
    __tablename__ = "visit_invitation_deliveries"
    __table_args__ = (
        Index("ix_invitation_state_id", "state", "id"),
        UniqueConstraint("visit_id_snapshot", "context_epoch", "token_digest", name="uq_visit_invitation_context"),
        UniqueConstraint("issuer_actor_id", "issuer_key_digest", name="uq_invitation_issuer_key"),
        CheckConstraint("visit_id IS NULL OR visit_id=visit_id_snapshot", name="ck_invitation_visit"),
        CheckConstraint("patient_id IS NULL OR patient_id=patient_id_snapshot", name="ck_invitation_patient"),
        CheckConstraint("visit_id_snapshot>0 AND patient_id_snapshot>0 AND owner_generation>0 AND context_epoch>0", name="ck_invitation_subject"),
        CheckConstraint("length(token_digest)=64", name="ck_invitation_digest"),
        CheckConstraint("channel IN ('telegram','pwa','phone')", name="ck_invitation_channel"),
        CheckConstraint("state IN ('pending','unknown','sent','cancelled')", name="ck_invitation_state"),
        CheckConstraint("(dispatch_nonce_digest IS NULL OR length(dispatch_nonce_digest)=64) AND (state='unknown' OR dispatch_nonce_digest IS NULL)", name="ck_invitation_nonce"),
        CheckConstraint("(issuer_actor_id IS NULL AND issuer_key_digest IS NULL AND issuer_fingerprint IS NULL) OR (issuer_actor_id IS NOT NULL AND issuer_key_digest IS NOT NULL AND issuer_fingerprint IS NOT NULL AND issuer_actor_id>0 AND length(issuer_key_digest)=64 AND length(issuer_fingerprint)=64)", name="ck_invitation_issuer"),
        CheckConstraint("(channel='telegram' AND telegram_link_id IS NOT NULL AND telegram_link_epoch IS NOT NULL) OR (channel<>'telegram' AND telegram_link_id IS NULL AND telegram_link_epoch IS NULL)", name="ck_invitation_telegram"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int | None] = mapped_column(ForeignKey("visits.id", ondelete="SET NULL"))
    visit_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id", ondelete="SET NULL"))
    patient_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    context_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    dispatch_nonce_digest: Mapped[str | None] = mapped_column(String(64))
    issuer_actor_id: Mapped[int | None] = mapped_column(Integer)
    issuer_key_digest: Mapped[str | None] = mapped_column(String(64))
    issuer_fingerprint: Mapped[str | None] = mapped_column(String(64))
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    telegram_link_id: Mapped[int | None] = mapped_column(Integer)
    telegram_link_epoch: Mapped[int | None] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class VisitInvitationIssuerAuth(Base):
    """Immutable authorization context; ciphertext contains no bearer JWT."""

    __tablename__ = "visit_invitation_issuer_auth"
    __table_args__ = (
        CheckConstraint("actor_user_id_snapshot>0 AND actor_auth_epoch>=0 AND expires_at>0", name="ck_invitation_issuer_identity"),
        CheckConstraint("actor_user_id IS NULL OR actor_user_id=actor_user_id_snapshot", name="ck_invitation_issuer_actor"),
        CheckConstraint("requester_type IN ('admin','doctor')", name="ck_invitation_issuer_type"),
        CheckConstraint("(doctor_id_snapshot IS NULL AND doctor_id IS NULL AND doctor_generation IS NULL) OR (doctor_id_snapshot IS NOT NULL AND doctor_id_snapshot>0 AND doctor_generation IS NOT NULL AND doctor_generation>0 AND (doctor_id IS NULL OR doctor_id=doctor_id_snapshot))", name="ck_invitation_issuer_doctor"),
        CheckConstraint("requester_type<>'doctor' OR doctor_id_snapshot IS NOT NULL", name="ck_invitation_issuer_doctor_required"),
        CheckConstraint("cipher_version=1 AND length(jti_ciphertext) BETWEEN 100 AND 2048", name="ck_invitation_issuer_cipher"),
    )

    delivery_id: Mapped[int] = mapped_column(ForeignKey("visit_invitation_deliveries.id", ondelete="RESTRICT"), primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_user_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_auth_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    requester_type: Mapped[str] = mapped_column(String(12), nullable=False)
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id", ondelete="SET NULL"))
    doctor_id_snapshot: Mapped[int | None] = mapped_column(Integer)
    doctor_generation: Mapped[int | None] = mapped_column(BigInteger)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cipher_version: Mapped[int] = mapped_column(Integer, nullable=False)
    jti_ciphertext: Mapped[str] = mapped_column(String(2048), nullable=False)


class VisitInvitationPriceApprovalAuth(Base):
    """A single approved override, approver session and resulting line snapshot."""

    __tablename__ = "visit_invitation_price_approval_auth"
    __table_args__ = (
        CheckConstraint("actor_user_id_snapshot>0 AND actor_auth_epoch>=0 AND expires_at>0", name="ck_invite_price_actor"),
        CheckConstraint("actor_user_id IS NULL OR actor_user_id=actor_user_id_snapshot", name="ck_invite_price_actor_live"),
        CheckConstraint("override_id_snapshot>0 AND (override_id IS NULL OR override_id=override_id_snapshot)", name="ck_invite_price_override"),
        CheckConstraint("line_id_snapshot>0 AND line_generation>0 AND (line_id IS NULL OR line_id=line_id_snapshot)", name="ck_invite_price_line"),
        CheckConstraint("quantity>0 AND unit_price>=0 AND cipher_version=1 AND length(jti_ciphertext) BETWEEN 100 AND 2048", name="ck_invite_price_snapshot"),
    )

    delivery_id: Mapped[int] = mapped_column(ForeignKey("visit_invitation_deliveries.id", ondelete="RESTRICT"), primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_user_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_auth_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    override_id: Mapped[int | None] = mapped_column(ForeignKey("doctor_price_overrides.id", ondelete="SET NULL"))
    override_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    line_id: Mapped[int | None] = mapped_column(ForeignKey("visit_services.id", ondelete="SET NULL"))
    line_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    line_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cipher_version: Mapped[int] = mapped_column(Integer, nullable=False)
    jti_ciphertext: Mapped[str] = mapped_column(String(2048), nullable=False)


class VisitInvitationApprovalRecovery(Base):
    """A durable admin task when an approved pending visit needs reissue."""

    __tablename__ = "visit_invitation_approval_recoveries"
    __table_args__ = (
        UniqueConstraint("override_id_snapshot", name="uq_invite_recovery_override"),
        Index("ix_invite_recovery_state_id", "state", "id"),
        CheckConstraint("state IN ('pending','dispatched','resolved')", name="ck_invite_recovery_state"),
        CheckConstraint("previous_token_digest IS NULL OR length(previous_token_digest)=64", name="ck_invite_recovery_token"),
        CheckConstraint("visit_id_snapshot>0 AND patient_id_snapshot>0 AND override_id_snapshot>0 AND owner_generation>0 AND context_epoch>0 AND actor_user_id_snapshot>0", name="ck_invite_recovery_identity"),
        CheckConstraint("(visit_id IS NULL OR visit_id=visit_id_snapshot) AND (patient_id IS NULL OR patient_id=patient_id_snapshot) AND (override_id IS NULL OR override_id=override_id_snapshot)", name="ck_invite_recovery_live"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    visit_id: Mapped[int | None] = mapped_column(ForeignKey("visits.id", ondelete="SET NULL"))
    visit_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id", ondelete="SET NULL"))
    patient_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    override_id: Mapped[int | None] = mapped_column(ForeignKey("doctor_price_overrides.id", ondelete="SET NULL"))
    override_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_user_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    context_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    previous_token_digest: Mapped[str | None] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
