"""Schema-only provider attempt snapshots and active visit reservations.

No URL or provider secret is stored here. This schema alone does not perform
provider calls, authorize actors, enforce append-only history, validate
callbacks or release reservations. Callers must never use snapshot IDs to
reconstruct deleted live authority. Future release and reconciliation must be
verified and transactional before any public workflow relies on this schema.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


def _minor_constraints(prefix: str, *, positive: bool):
    return (
        CheckConstraint(
            "length(amount_minor) BETWEEN 1 AND 128 AND "
            "(length(amount_minor) = 1 OR substr(amount_minor, 1, 1) <> '0')"
            + (" AND amount_minor <> '0'" if positive else ""),
            name=f"ck_{prefix}_minor_format",
        ),
        CheckConstraint("amount_minor NOT GLOB '*[^0-9]*'", name=f"ck_{prefix}_minor_digits_sqlite").ddl_if(dialect="sqlite"),
        CheckConstraint("amount_minor ~ '^[0-9]+$'", name=f"ck_{prefix}_minor_digits_pg").ddl_if(dialect="postgresql"),
    )


class ProviderAttempt(Base):
    """One prepared provider intent; no secret or URL material is stored."""

    __tablename__ = "provider_attempts"
    __table_args__ = (
        Index("uq_click_attempt_snapshot", "id", "order_ref", "merchant_hash", "fingerprint", "amount_minor",
              "currency", "currency_exponent", "provider", "target_kind", "actor_user_id_snapshot", unique=True),
        UniqueConstraint("public_id", name="uq_provider_attempt_public_id"),
        UniqueConstraint("provider", "merchant_hash", "order_ref", name="uq_provider_attempt_order"),
        UniqueConstraint("actor_user_id_snapshot", "client_key_hash", name="uq_provider_attempt_actor_key"),
        CheckConstraint("length(public_id) = 36", name="ck_provider_attempt_public_id"),
        CheckConstraint("length(provider) BETWEEN 1 AND 32 AND provider = lower(provider)", name="ck_provider_attempt_provider"),
        CheckConstraint("length(order_ref) BETWEEN 1 AND 128 AND length(trim(order_ref)) > 0", name="ck_provider_attempt_order"),
        CheckConstraint("length(merchant_hash) = 64 AND length(fingerprint) = 64", name="ck_provider_attempt_hash_lengths"),
        CheckConstraint("client_key_hash IS NULL OR length(client_key_hash) = 64", name="ck_provider_attempt_client_key_length"),
        CheckConstraint("client_key_hash IS NULL OR client_key_hash NOT GLOB '*[^0-9a-f]*'", name="ck_provider_attempt_client_key_sqlite").ddl_if(dialect="sqlite"),
        CheckConstraint("client_key_hash IS NULL OR client_key_hash ~ '^[0-9a-f]{64}$'", name="ck_provider_attempt_client_key_pg").ddl_if(dialect="postgresql"),
        CheckConstraint("merchant_hash NOT GLOB '*[^0-9a-f]*' AND fingerprint NOT GLOB '*[^0-9a-f]*'", name="ck_provider_attempt_hash_sqlite").ddl_if(dialect="sqlite"),
        CheckConstraint("merchant_hash ~ '^[0-9a-f]{64}$' AND fingerprint ~ '^[0-9a-f]{64}$'", name="ck_provider_attempt_hash_pg").ddl_if(dialect="postgresql"),
        CheckConstraint("length(currency) = 3 AND currency = upper(currency) AND currency_exponent BETWEEN 0 AND 9", name="ck_provider_attempt_currency"),
        CheckConstraint("status IN ('prepared', 'dispatching', 'unknown')", name="ck_provider_attempt_status"),
        CheckConstraint(
            "(target_kind = 'payment' AND payment_id_snapshot IS NOT NULL AND payment_id_snapshot > 0 "
            "AND invoice_id_snapshot IS NULL AND invoice_id IS NULL) OR "
            "(target_kind = 'payment_invoice' AND invoice_id_snapshot IS NOT NULL AND invoice_id_snapshot > 0 "
            "AND payment_id_snapshot IS NULL AND payment_id IS NULL)", name="ck_provider_attempt_target"),
        CheckConstraint("payment_id IS NULL OR payment_id = payment_id_snapshot", name="ck_provider_attempt_payment_snapshot"),
        CheckConstraint("invoice_id IS NULL OR invoice_id = invoice_id_snapshot", name="ck_provider_attempt_invoice_snapshot"),
        CheckConstraint("actor_user_id_snapshot > 0 AND (actor_user_id IS NULL OR actor_user_id = actor_user_id_snapshot)", name="ck_provider_attempt_actor_snapshot"),
        *_minor_constraints("provider_attempt", positive=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    payment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("payments.id", ondelete="SET NULL"))
    payment_id_snapshot: Mapped[int | None] = mapped_column(Integer)
    invoice_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("payment_invoices.id", ondelete="SET NULL"))
    invoice_id_snapshot: Mapped[int | None] = mapped_column(Integer)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    actor_user_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    merchant_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    order_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    client_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount_minor: Mapped[str] = mapped_column(String(128), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    currency_exponent: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProviderAttemptVisit(Base):
    """Historical association; service must preserve it when releasing."""

    __tablename__ = "provider_attempt_visits"
    __table_args__ = (
        UniqueConstraint("attempt_id", "visit_id_snapshot", name="uq_provider_attempt_visit_snapshot"),
        UniqueConstraint("id", "attempt_id", "visit_id", name="uq_provider_attempt_visit_live"),
        CheckConstraint("visit_id IS NULL OR visit_id = visit_id_snapshot", name="ck_provider_attempt_visit_live_snapshot"),
        CheckConstraint("visit_id_snapshot > 0 AND patient_id_snapshot > 0 AND context_epoch > 0", name="ck_provider_attempt_visit_snapshot"),
        *_minor_constraints("provider_attempt_visit", positive=False),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(Integer, ForeignKey("provider_attempts.id", ondelete="RESTRICT"), nullable=False, index=True)
    visit_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("visits.id", ondelete="SET NULL"), index=True)
    visit_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    patient_id_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    context_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount_minor: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ProviderActiveVisitReservation(Base):
    """One outstanding reservation per live visit, across all providers."""

    __tablename__ = "provider_active_visit_reservations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["attempt_visit_id", "attempt_id", "visit_id"],
            ["provider_attempt_visits.id", "provider_attempt_visits.attempt_id", "provider_attempt_visits.visit_id"],
            name="fk_provider_active_reservation_history", ondelete="RESTRICT",
        ),
        UniqueConstraint("attempt_visit_id", name="uq_provider_active_history"),
        CheckConstraint("visit_id > 0", name="ck_provider_active_visit_id"),
    )

    visit_id: Mapped[int] = mapped_column(Integer, ForeignKey("visits.id", ondelete="RESTRICT"), primary_key=True)
    attempt_id: Mapped[int] = mapped_column(Integer, ForeignKey("provider_attempts.id", ondelete="RESTRICT"), nullable=False, index=True)
    attempt_visit_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
