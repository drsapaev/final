"""Durable evidence of provider debit reconciliation, not an authorization flow.

Only verified, normalized and non-secret provider evidence belongs here.
The schema does not verify provider signatures or implement callback handling.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


def _amount_checks(prefix: str):
    return (
        CheckConstraint(
            "length(amount_minor) BETWEEN 1 AND 128 AND (length(amount_minor) = 1 OR substr(amount_minor, 1, 1) <> '0')",
            name=f"ck_{prefix}_amount_length",
        ),
        CheckConstraint(
            "amount_minor NOT GLOB '*[^0-9]*'", name=f"ck_{prefix}_amount_digits_sqlite"
        ).ddl_if(dialect="sqlite"),
        CheckConstraint(
            "amount_minor ~ '^[0-9]+$'", name=f"ck_{prefix}_amount_digits_pg"
        ).ddl_if(dialect="postgresql"),
    )


class ProviderReconciliationEvent(Base):
    __tablename__ = "provider_reconciliation_events"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "event_key",
            "phase",
            name="uq_provider_reconciliation_event_phase",
        ),
        CheckConstraint(
            "target_kind IN ('payment', 'payment_invoice', 'unmatched')",
            name="ck_provider_recon_target_kind",
        ),
        CheckConstraint(
            "(target_kind = 'payment' AND payment_id_snapshot IS NOT NULL AND payment_id_snapshot > 0 AND invoice_id_snapshot IS NULL AND invoice_id IS NULL) OR (target_kind = 'payment_invoice' AND invoice_id_snapshot IS NOT NULL AND invoice_id_snapshot > 0 AND payment_id_snapshot IS NULL AND payment_id IS NULL) OR (target_kind = 'unmatched' AND payment_id_snapshot IS NULL AND invoice_id_snapshot IS NULL AND payment_id IS NULL AND invoice_id IS NULL)",
            name="ck_provider_recon_target",
        ),
        CheckConstraint(
            "payment_id IS NULL OR (payment_id_snapshot IS NOT NULL AND payment_id = payment_id_snapshot)",
            name="ck_provider_recon_payment_snapshot",
        ),
        CheckConstraint(
            "invoice_id IS NULL OR (invoice_id_snapshot IS NOT NULL AND invoice_id = invoice_id_snapshot)",
            name="ck_provider_recon_invoice_snapshot",
        ),
        CheckConstraint(
            "(webhook_id_snapshot IS NULL AND webhook_id IS NULL) OR (webhook_id_snapshot IS NOT NULL AND webhook_id_snapshot > 0 AND (webhook_id IS NULL OR webhook_id = webhook_id_snapshot))",
            name="ck_provider_recon_receipt_snapshot",
        ),
        CheckConstraint(
            "source IN ('webhook', 'poll')", name="ck_provider_recon_source"
        ),
        CheckConstraint(
            "source <> 'webhook' OR webhook_id_snapshot IS NOT NULL",
            name="ck_provider_recon_webhook_receipt",
        ),
        CheckConstraint(
            "length(provider) BETWEEN 1 AND 32 AND length(phase) BETWEEN 1 AND 32 AND length(observed_status) BETWEEN 1 AND 32",
            name="ck_provider_recon_labels",
        ),
        CheckConstraint(
            "length(event_key) = 64 AND length(provider_reference_digest) = 64 AND length(evidence_sha256) = 64",
            name="ck_provider_recon_digests",
        ),
        CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency) AND currency_exponent BETWEEN 0 AND 9",
            name="ck_provider_recon_currency",
        ),
        CheckConstraint("status = 'needs_review'", name="ck_provider_recon_status"),
        *_amount_checks("provider_recon"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(12), nullable=False)
    phase: Mapped[str] = mapped_column(String(32), nullable=False)
    event_key: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_transaction_id: Mapped[str | None] = mapped_column(String(128))
    provider_reference_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    target_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("payments.id", ondelete="SET NULL")
    )
    payment_id_snapshot: Mapped[int | None] = mapped_column(Integer)
    invoice_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_invoices.id", ondelete="SET NULL")
    )
    invoice_id_snapshot: Mapped[int | None] = mapped_column(Integer)
    webhook_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_webhooks.id", ondelete="SET NULL")
    )
    webhook_id_snapshot: Mapped[int | None] = mapped_column(Integer)
    amount_minor: Mapped[str] = mapped_column(String(128), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    currency_exponent: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    observed_status: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="needs_review"
    )
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProviderReconciliationConflict(Base):
    """A same-key observation whose material facts disagree with the event."""

    __tablename__ = "provider_reconciliation_conflicts"
    __table_args__ = (
        CheckConstraint(
            "target_kind IN ('payment', 'payment_invoice', 'unmatched')",
            name="ck_provider_recon_conflict_target_kind",
        ),
        CheckConstraint(
            "(target_kind = 'payment' AND target_id_snapshot IS NOT NULL AND target_id_snapshot > 0) OR (target_kind = 'payment_invoice' AND target_id_snapshot IS NOT NULL AND target_id_snapshot > 0) OR (target_kind = 'unmatched' AND target_id_snapshot IS NULL)",
            name="ck_provider_recon_conflict_target",
        ),
        CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency) AND currency_exponent BETWEEN 0 AND 9",
            name="ck_provider_recon_conflict_currency",
        ),
        CheckConstraint(
            "source IN ('webhook', 'poll')", name="ck_provider_recon_conflict_source"
        ),
        CheckConstraint(
            "(webhook_id_snapshot IS NULL AND webhook_id IS NULL) OR (webhook_id_snapshot IS NOT NULL AND webhook_id_snapshot > 0 AND (webhook_id IS NULL OR webhook_id = webhook_id_snapshot))",
            name="ck_provider_recon_conflict_receipt",
        ),
        CheckConstraint(
            "source <> 'webhook' OR webhook_id_snapshot IS NOT NULL",
            name="ck_provider_recon_conflict_webhook",
        ),
        CheckConstraint(
            "length(observed_status) BETWEEN 1 AND 32 AND length(evidence_sha256) = 64 AND length(provider_reference_digest) = 64",
            name="ck_provider_recon_conflict_evidence",
        ),
        *_amount_checks("provider_recon_conflict"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("provider_reconciliation_events.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(12), nullable=False)
    provider_transaction_id: Mapped[str | None] = mapped_column(String(128))
    provider_reference_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    webhook_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_webhooks.id", ondelete="SET NULL")
    )
    webhook_id_snapshot: Mapped[int | None] = mapped_column(Integer)
    target_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    target_id_snapshot: Mapped[int | None] = mapped_column(Integer)
    amount_minor: Mapped[str] = mapped_column(String(128), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    currency_exponent: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    observed_status: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
