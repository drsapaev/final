"""PR-3: telegram_webhook_dedup — the schema behind update_id dedup.

The Telegram contour has two ingress paths for bot updates: the
POST /telegram/webhook endpoint and the long-polling worker. Telegram
re-delivers updates whenever a delivery is not ACKed in time (timeout,
crash, slow handler), so both paths can receive the same update_id twice.
Deduplication is enforced at the database level: a UNIQUE index on
(bot_identity, update_id) makes the claim INSERT atomic, so two
concurrent deliveries of the same bot cannot both win.

The ORM model (app/models/telegram_webhook_dedup.py) previously existed
without this migration, so on PostgreSQL the table did not exist at all
and the fail-open dedup silently degraded to "no dedup". This revision
creates the real table.

Column notes:
- owner_token fences mark/release to the CURRENT owner: regenerated on
  insert and on stale-reclaim, so a handler whose claim was handed to a
  later delivery can never mark or delete the new owner's row (codex
  round 29).
- bot_identity is a stable, NON-SECRET per-credential identity (SHA-256
  prefix of the resolved bot token; never the token itself), "unknown"
  when no credential resolves. Telegram update_id sequences are PER BOT,
  so the ledger key must include the bot identity — a row retained from
  a previous bot must never suppress the replacement bot's claims (codex
  round 20). NOT NULL: NULLs never collide in a unique index, which
  would silently disable dedup for those claims.
- update_id is BigInteger: Telegram update_ids are per-bot sequences that
  keep growing; PostgreSQL INT4 max (2147483647) is a real overflow risk.
- processed_at is TIMESTAMPTZ with a server-side default; the ORM layer
  always writes timezone-aware UTC values.
- status starts at 'processing' (the claim) and is flipped to
  'processed' after the handler succeeds; failed claims are deleted so a
  redelivery is reprocessed.

Revision ID: 0062_telegram_webhook_dedup
Revises: 0061_telegram_config_singleton
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0062_telegram_webhook_dedup"
down_revision = "0061_telegram_config_singleton"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_webhook_dedup",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_identity", sa.String(length=64), nullable=False),
        sa.Column("owner_token", sa.String(length=64), nullable=False),
        sa.Column("update_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=20), server_default="processing",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_telegram_webhook_dedup_bot_update_id",
        "telegram_webhook_dedup",
        ["bot_identity", "update_id"],
        unique=True,
    )
    # RLS parity with the 0046/0050 sweeps — ops/scripts/check_public_rls.py
    # (CI backend-tests job, right after `alembic upgrade head`) fails the
    # build on any public table with relrowsecurity = false. The table holds
    # no PII (only Telegram update_ids), but the guardrail is table-wide.
    op.execute("ALTER TABLE public.telegram_webhook_dedup ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index(
        "uq_telegram_webhook_dedup_bot_update_id", table_name="telegram_webhook_dedup"
    )
    op.drop_table("telegram_webhook_dedup")
