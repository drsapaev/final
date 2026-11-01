"""3808 review round 3 — force-majeure refund idempotency guards.

DB-level backstop for the concurrent cancel-with-refund race
(PR #3809 review round 2, P1): partial UNIQUE indexes so a payment can
be refunded at most once —

* ``uq_refund_requests_auto_payment``: one LIVE automatic (force
  majeure) refund request per payment; manual cashier requests
  (is_automatic=False, partial refunds) stay unconstrained.
  3808 review round 5 (P1 claim lifecycle): the predicate is
  STATUS-AWARE — only pending/approved/processing/completed requests
  hold the uniqueness. A REJECTED or CANCELLED request paid nothing,
  leaves the partial index and a corrected retry (same channel, e.g.
  after fixing the bank details) becomes insertable; COMPLETED (money
  actually returned) keeps blocking strictly.
* ``uq_deposit_transactions_credit_payment``: one deposit CREDIT per
  payment; only the force-majeure flow writes credit rows with
  payment_id set, so the predicate pins exactly that refund leg.

The predicates mirror the daily_queues active-uniqueness precedent
(postgresql_where AND sqlite_where) so both dialects enforce the same
partial contract. Both 0087 and 0088 live only in this unmerged Draft
PR (main's alembic head is 0086), so the round-5 lifecycle fix amends
them in place instead of growing a 0089 cleanup for never-deployed
schema.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# alembic_version.version_num is VARCHAR(32) on PostgreSQL.
revision = "0087_fm_refund_idem"
down_revision = "0086_public_booking_confirm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_refund_requests_auto_payment",
        "refund_requests",
        ["payment_id"],
        unique=True,
        postgresql_where=sa.text(
            "is_automatic AND status IN "
            "('pending', 'approved', 'processing', 'completed')"
        ),
        sqlite_where=sa.text(
            "is_automatic AND status IN "
            "('pending', 'approved', 'processing', 'completed')"
        ),
    )
    op.create_index(
        "uq_deposit_transactions_credit_payment",
        "deposit_transactions",
        ["payment_id"],
        unique=True,
        postgresql_where=sa.text(
            "transaction_type = 'credit' AND payment_id IS NOT NULL"
        ),
        sqlite_where=sa.text(
            "transaction_type = 'credit' AND payment_id IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_deposit_transactions_credit_payment",
        table_name="deposit_transactions",
    )
    op.drop_index(
        "uq_refund_requests_auto_payment",
        table_name="refund_requests",
    )
