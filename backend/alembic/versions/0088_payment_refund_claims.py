"""3808 review round 4 — unified per-payment refund claim (cross-channel).

PR #3809 round 3 left two INDEPENDENT idempotency guards: a partial unique
index on automatic refund requests (0087) and one on deposit credits
(0087). Neither sees the other channel, so a paid visit referenced from
entries in DIFFERENT queues could be refunded twice — once to the deposit,
once as an automatic bank request (review round 4, P1).

``payment_refund_claims`` is the unified guard: ONE row per payment_id,
regardless of the refund channel. ``ON CONFLICT (payment_id) DO NOTHING``
backfill preserves the guarantee for rows that predate the guard. RLS is
enabled per the public-schema guardrail (ops/scripts/check_public_rls.py).

3808 review round 5 (P1 claim lifecycle): the backfill is STATUS-AWARE —
only requests whose refund is live (pending/approved/processing/completed)
occupy a claim. A preexisting REJECTED or CANCELLED automatic request
paid nothing and must NOT reserve the payment: on rollout such a payment
stays claimable, so the patient can be refunded again (corrected bank
request or deposit). COMPLETED requests — money actually returned — keep
their claims strictly. Both 0087 and 0088 live only in this unmerged Draft
PR (main's alembic head is 0086), so the lifecycle fix amends them in
place instead of growing a 0089 cleanup for never-deployed schema.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# alembic_version.version_num is VARCHAR(32) on PostgreSQL.
revision = "0088_fm_refund_claim"
down_revision = "0087_fm_refund_idem"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_refund_claims",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "payment_id",
            sa.Integer(),
            sa.ForeignKey("payments.id", ondelete="RESTRICT"),
            nullable=False,
            comment="Платёж, возврат которого занят этим claim-ом (UNIQUE)",
        ),
        sa.Column(
            "channel",
            sa.String(length=20),
            nullable=False,
            comment="deposit | refund_request — канал состоявшегося возврата",
        ),
        sa.Column(
            "deposit_transaction_id",
            sa.Integer(),
            sa.ForeignKey("deposit_transactions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "refund_request_id",
            sa.Integer(),
            sa.ForeignKey("refund_requests.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_refund_claims")),
    )
    op.create_index(
        op.f("ix_payment_refund_claims_id"),
        "payment_refund_claims",
        ["id"],
        unique=False,
    )
    # THE unified guard: one claim per payment, independent of the channel.
    op.create_index(
        "uq_payment_refund_claims_payment",
        "payment_refund_claims",
        ["payment_id"],
        unique=True,
    )

    # Backfill — claim payments that were already refunded before the guard:
    # LIVE automatic (force majeure) refund requests first, then deposit
    # credits; DO NOTHING keeps the first channel when a payment somehow
    # has both. 3808 round 5 (P1 lifecycle): rejected/cancelled requests
    # paid nothing and are EXCLUDED — such payments stay claimable so a
    # corrected retry (any channel) can proceed after rollout.
    op.execute(
        sa.text(
            """
            INSERT INTO payment_refund_claims
                (payment_id, channel, refund_request_id, reason)
            SELECT payment_id, 'refund_request', id,
                   '0088 backfill: automatic refund request predates the unified guard'
            FROM refund_requests
            WHERE is_automatic AND payment_id IS NOT NULL
              AND status IN ('pending', 'approved', 'processing', 'completed')
            ON CONFLICT (payment_id) DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO payment_refund_claims
                (payment_id, channel, deposit_transaction_id, reason)
            SELECT payment_id, 'deposit', id,
                   '0088 backfill: deposit credit predates the unified guard'
            FROM deposit_transactions
            WHERE transaction_type = 'credit' AND payment_id IS NOT NULL
            ON CONFLICT (payment_id) DO NOTHING
            """
        )
    )

    # RLS guardrail: every public table must have RLS enabled
    # (2026-09-02 Supabase incident; enforced by check_public_rls.py in CI).
    op.execute(
        sa.text("ALTER TABLE public.payment_refund_claims ENABLE ROW LEVEL SECURITY")
    )


def downgrade() -> None:
    op.drop_index(
        "uq_payment_refund_claims_payment", table_name="payment_refund_claims"
    )
    op.drop_index(
        op.f("ix_payment_refund_claims_id"), table_name="payment_refund_claims"
    )
    op.drop_table("payment_refund_claims")
