"""PR-3 (round 24): telegram_configs.bot_identity — the persisted,
STABLE per-bot dedup identity.

The dedup ledger key is (bot_identity, update_id). The identity must be
ONE value shared by every process that claims updates: the backend runs
multiple uvicorn workers plus the polling worker, and a credential-scoped
fallback resolved independently by each of them can diverge (one worker
caches a fallback while another resolves the real getMe id — retries
routed across them then claim the same update under different unique
keys and execute it twice, codex round 24).

telegram_configs is the SSOT row for the bot credential, so the identity
resolved from getMe is persisted next to it:

- every resolver first reads the persisted value (token-conditioned: it
  is only used while the stored credential is the one it was resolved
  for);
- the first successful getMe writes it (best-effort, idempotent —
  concurrent writers store the same value);
- the token store clears it on any credential change (the identity is
  bound to the current credential, mirroring the bot_username contract
  from PR-2 round 17); during a Telegram outage the resolvers degrade to
  the deterministic credential-scoped hash and converge on the persisted
  id as soon as getMe answers.

Additive column only: no backfill needed (resolvers lazily persist on
the first successful getMe).

Revision ID: 0063_telegram_config_identity
Revises: 0062_telegram_webhook_dedup
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0063_telegram_config_identity"
down_revision = "0062_telegram_webhook_dedup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "telegram_configs",
        sa.Column("bot_identity", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("telegram_configs", "bot_identity")
