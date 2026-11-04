"""P1 issue 3859 (CSH-FE-008 remainder) — server-side payment idempotency.

``POST /api/v1/cashier/payments`` and ``POST /api/v1/cashier/payments/grouped``
had no server-side idempotency: a network-loss retry of the same client
intent inserted a second PAID payment row (the ``with_for_update()`` visit
lock serializes concurrent attempts but cannot distinguish a retry of a
partial payment from a legitimate second partial — the overpayment check
only rejects when the visit is fully paid).

Schema anchors introduced here:

* ``payments.client_request_id`` — nullable traceability column. NOT
  unique: a grouped allocation creates N payment rows under ONE client
  key, which a unique column cannot express (the issue's example design
  assumed single-row payments; the grouped endpoint made it untenable).
* ``payment_client_requests`` — the dedup anchor. ONE row per client
  ``client_request_id`` (unique index ``uq_payment_client_requests_key``)
  holding a JSON snapshot of the original operation's response. A
  repeated key replays the stored snapshot with 200 — no second payment
  row, no re-derived response (allocations are not reconstructible once
  the visit debt changes). The anchor row and the payment rows commit in
  the SAME transaction, and the concurrent-duplicate race resolves
  through the unique index: the loser rolls back, re-reads the winner's
  snapshot and replays it.

RLS is enabled per the public-schema guardrail
(2026-09-02 Supabase incident; enforced by ops/scripts/check_public_rls.py
in CI). Follows the 0087/0088 idempotency-guard precedent.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# alembic_version.version_num is VARCHAR(32) on PostgreSQL.
revision = "0090_payment_client_request"
down_revision = "0089_merge_booking_refund_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Traceability column on every payment row created under a client key
    # (single: 1 row per key; grouped: N rows per key — hence non-unique).
    op.add_column(
        "payments",
        sa.Column(
            "client_request_id",
            sa.String(length=64),
            nullable=True,
            comment=(
                "Ключ идемпотентности клиента (UUID): все строки одной "
                "групповой аллокации несут один и тот же ключ"
            ),
        ),
    )
    op.create_index(
        "ix_payments_client_request_id",
        "payments",
        ["client_request_id"],
    )

    op.create_table(
        "payment_client_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "client_request_id",
            sa.String(length=64),
            nullable=False,
            comment="Клиентский ключ идемпотентности — UNIQUE: один якорь на intent",
        ),
        sa.Column(
            "endpoint",
            sa.String(length=16),
            nullable=False,
            comment="single | grouped — эндпоинт, создавший якорь",
        ),
        sa.Column(
            "response_payload",
            sa.JSON(),
            nullable=False,
            comment="Снимок ответа исходной операции для реплея (JSON)",
        ),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="Кассир, создавший платёж (ID пользователя)",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_client_requests")),
    )
    # THE dedup guard: one anchor per client_request_id.
    op.create_index(
        "uq_payment_client_requests_key",
        "payment_client_requests",
        ["client_request_id"],
        unique=True,
    )

    # RLS guardrail: every public table must have RLS enabled
    # (2026-09-02 Supabase incident; enforced by check_public_rls.py in CI).
    op.execute(
        sa.text("ALTER TABLE public.payment_client_requests ENABLE ROW LEVEL SECURITY")
    )


def downgrade() -> None:
    op.drop_index(
        "uq_payment_client_requests_key",
        table_name="payment_client_requests",
    )
    op.drop_table("payment_client_requests")
    op.drop_index("ix_payments_client_request_id", table_name="payments")
    op.drop_column("payments", "client_request_id")
