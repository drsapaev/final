"""Persist normalized provider reconciliation evidence.

This schema alone neither verifies callbacks nor implements conflict handling.
"""

import sqlalchemy as sa

from alembic import op

revision = "0109_provider_reconciliation"
down_revision = "0108_benefit_quota_anchor"
branch_labels = None
depends_on = None


def _amount_constraints(prefix: str, dialect: str):
    constraints = [
        sa.CheckConstraint(
            "length(amount_minor) BETWEEN 1 AND 128 AND (length(amount_minor) = 1 OR substr(amount_minor, 1, 1) <> '0')",
            name=f"ck_{prefix}_amount_length",
        )
    ]
    if dialect == "postgresql":
        constraints.append(
            sa.CheckConstraint(
                "amount_minor ~ '^[0-9]+$'", name=f"ck_{prefix}_amount_digits_pg"
            )
        )
    elif dialect == "sqlite":
        constraints.append(
            sa.CheckConstraint(
                "amount_minor NOT GLOB '*[^0-9]*'",
                name=f"ck_{prefix}_amount_digits_sqlite",
            )
        )
    else:
        raise RuntimeError(f"Unsupported provider reconciliation dialect: {dialect}")
    return constraints


def upgrade() -> None:
    dialect = op.get_context().dialect.name
    op.create_table(
        "provider_reconciliation_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("source", sa.String(12), nullable=False),
        sa.Column("phase", sa.String(32), nullable=False),
        sa.Column("event_key", sa.String(64), nullable=False),
        sa.Column("provider_transaction_id", sa.String(128)),
        sa.Column("provider_reference_digest", sa.String(64), nullable=False),
        sa.Column("target_kind", sa.String(16), nullable=False),
        sa.Column(
            "payment_id",
            sa.Integer(),
            sa.ForeignKey("payments.id", ondelete="SET NULL"),
        ),
        sa.Column("payment_id_snapshot", sa.Integer()),
        sa.Column(
            "invoice_id",
            sa.Integer(),
            sa.ForeignKey("payment_invoices.id", ondelete="SET NULL"),
        ),
        sa.Column("invoice_id_snapshot", sa.Integer()),
        sa.Column(
            "webhook_id",
            sa.Integer(),
            sa.ForeignKey("payment_webhooks.id", ondelete="SET NULL"),
        ),
        sa.Column("webhook_id_snapshot", sa.Integer()),
        sa.Column("amount_minor", sa.String(128), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("currency_exponent", sa.SmallInteger(), nullable=False),
        sa.Column("observed_status", sa.String(32), nullable=False),
        sa.Column("evidence_sha256", sa.String(64), nullable=False),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="needs_review"
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "provider",
            "event_key",
            "phase",
            name="uq_provider_reconciliation_event_phase",
        ),
        sa.CheckConstraint(
            "target_kind IN ('payment', 'payment_invoice', 'unmatched')",
            name="ck_provider_recon_target_kind",
        ),
        sa.CheckConstraint(
            "(target_kind = 'payment' AND payment_id_snapshot IS NOT NULL AND payment_id_snapshot > 0 AND invoice_id_snapshot IS NULL AND invoice_id IS NULL) OR (target_kind = 'payment_invoice' AND invoice_id_snapshot IS NOT NULL AND invoice_id_snapshot > 0 AND payment_id_snapshot IS NULL AND payment_id IS NULL) OR (target_kind = 'unmatched' AND payment_id_snapshot IS NULL AND invoice_id_snapshot IS NULL AND payment_id IS NULL AND invoice_id IS NULL)",
            name="ck_provider_recon_target",
        ),
        sa.CheckConstraint(
            "payment_id IS NULL OR (payment_id_snapshot IS NOT NULL AND payment_id = payment_id_snapshot)",
            name="ck_provider_recon_payment_snapshot",
        ),
        sa.CheckConstraint(
            "invoice_id IS NULL OR (invoice_id_snapshot IS NOT NULL AND invoice_id = invoice_id_snapshot)",
            name="ck_provider_recon_invoice_snapshot",
        ),
        sa.CheckConstraint(
            "(webhook_id_snapshot IS NULL AND webhook_id IS NULL) OR (webhook_id_snapshot IS NOT NULL AND webhook_id_snapshot > 0 AND (webhook_id IS NULL OR webhook_id = webhook_id_snapshot))",
            name="ck_provider_recon_receipt_snapshot",
        ),
        sa.CheckConstraint(
            "source IN ('webhook', 'poll')", name="ck_provider_recon_source"
        ),
        sa.CheckConstraint(
            "source <> 'webhook' OR webhook_id_snapshot IS NOT NULL",
            name="ck_provider_recon_webhook_receipt",
        ),
        sa.CheckConstraint(
            "length(provider) BETWEEN 1 AND 32 AND length(phase) BETWEEN 1 AND 32 AND length(observed_status) BETWEEN 1 AND 32",
            name="ck_provider_recon_labels",
        ),
        sa.CheckConstraint(
            "length(event_key) = 64 AND length(provider_reference_digest) = 64 AND length(evidence_sha256) = 64",
            name="ck_provider_recon_digests",
        ),
        sa.CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency) AND currency_exponent BETWEEN 0 AND 9",
            name="ck_provider_recon_currency",
        ),
        sa.CheckConstraint("status = 'needs_review'", name="ck_provider_recon_status"),
        *_amount_constraints("provider_recon", dialect),
    )
    op.create_table(
        "provider_reconciliation_conflicts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "event_id",
            sa.Integer(),
            sa.ForeignKey("provider_reconciliation_events.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source", sa.String(12), nullable=False),
        sa.Column("provider_transaction_id", sa.String(128)),
        sa.Column("provider_reference_digest", sa.String(64), nullable=False),
        sa.Column(
            "webhook_id",
            sa.Integer(),
            sa.ForeignKey("payment_webhooks.id", ondelete="SET NULL"),
        ),
        sa.Column("webhook_id_snapshot", sa.Integer()),
        sa.Column("target_kind", sa.String(16), nullable=False),
        sa.Column("target_id_snapshot", sa.Integer()),
        sa.Column("amount_minor", sa.String(128), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("currency_exponent", sa.SmallInteger(), nullable=False),
        sa.Column("observed_status", sa.String(32), nullable=False),
        sa.Column("evidence_sha256", sa.String(64), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "target_kind IN ('payment', 'payment_invoice', 'unmatched')",
            name="ck_provider_recon_conflict_target_kind",
        ),
        sa.CheckConstraint(
            "(target_kind = 'payment' AND target_id_snapshot IS NOT NULL AND target_id_snapshot > 0) OR (target_kind = 'payment_invoice' AND target_id_snapshot IS NOT NULL AND target_id_snapshot > 0) OR (target_kind = 'unmatched' AND target_id_snapshot IS NULL)",
            name="ck_provider_recon_conflict_target",
        ),
        sa.CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency) AND currency_exponent BETWEEN 0 AND 9",
            name="ck_provider_recon_conflict_currency",
        ),
        sa.CheckConstraint(
            "source IN ('webhook', 'poll')", name="ck_provider_recon_conflict_source"
        ),
        sa.CheckConstraint(
            "(webhook_id_snapshot IS NULL AND webhook_id IS NULL) OR (webhook_id_snapshot IS NOT NULL AND webhook_id_snapshot > 0 AND (webhook_id IS NULL OR webhook_id = webhook_id_snapshot))",
            name="ck_provider_recon_conflict_receipt",
        ),
        sa.CheckConstraint(
            "source <> 'webhook' OR webhook_id_snapshot IS NOT NULL",
            name="ck_provider_recon_conflict_webhook",
        ),
        sa.CheckConstraint(
            "length(observed_status) BETWEEN 1 AND 32 AND length(evidence_sha256) = 64 AND length(provider_reference_digest) = 64",
            name="ck_provider_recon_conflict_evidence",
        ),
        *_amount_constraints("provider_recon_conflict", dialect),
    )
    op.create_index(
        "ix_provider_reconciliation_conflicts_event_id",
        "provider_reconciliation_conflicts",
        ["event_id"],
    )
    if dialect == "postgresql":
        op.execute(
            "ALTER TABLE provider_reconciliation_events ENABLE ROW LEVEL SECURITY"
        )
        op.execute(
            "ALTER TABLE provider_reconciliation_conflicts ENABLE ROW LEVEL SECURITY"
        )


def downgrade() -> None:
    dialect = op.get_context().dialect.name
    unsafe = "EXISTS (SELECT 1 FROM provider_reconciliation_events) OR EXISTS (SELECT 1 FROM provider_reconciliation_conflicts)"
    if dialect == "postgresql":
        op.execute("SET LOCAL row_security = off")
        op.execute(
            "LOCK TABLE provider_reconciliation_events, provider_reconciliation_conflicts IN ACCESS EXCLUSIVE MODE"
        )
        op.execute(
            f"DO $$ BEGIN IF {unsafe} THEN RAISE EXCEPTION 'provider reconciliation downgrade would discard evidence'; END IF; END $$"
        )
    elif dialect == "sqlite":
        op.execute("UPDATE provider_reconciliation_events SET id=id WHERE 0")
        op.execute("UPDATE provider_reconciliation_conflicts SET id=id WHERE 0")
        op.execute(
            "CREATE TEMP TABLE provider_recon_downgrade_guard_0109 (value INTEGER NOT NULL CHECK (value=0))"
        )
        op.execute(
            f"INSERT INTO provider_recon_downgrade_guard_0109 SELECT CASE WHEN {unsafe} THEN 1 ELSE 0 END"
        )
        op.execute("DROP TABLE provider_recon_downgrade_guard_0109")
    else:
        raise RuntimeError(f"Unsupported provider reconciliation dialect: {dialect}")
    op.drop_index(
        "ix_provider_reconciliation_conflicts_event_id",
        table_name="provider_reconciliation_conflicts",
    )
    op.drop_table("provider_reconciliation_conflicts")
    op.drop_table("provider_reconciliation_events")
