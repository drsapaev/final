"""PR-2 round 4: telegram_configs singleton guard.

Two concurrent first-token writes could both observe "no config" and INSERT,
after which get_telegram_config().first() picks an arbitrary credential and
later rotations update only one row. A NOT NULL DEFAULT 1 column with a
UNIQUE constraint makes the singleton invariant explicit at the database
level: the second INSERT fails with an integrity error and the store falls
back to updating the winner.

Any pre-existing duplicate rows (pathological - the app has always treated
the table as a singleton) are collapsed to the lowest id before the unique
constraint is created.

Revision ID: 0061_telegram_config_singleton
Revises: 0060_visit_reminder_sent_at
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0061_telegram_config_singleton"
down_revision = "0060_visit_reminder_sent_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    row_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM telegram_configs")
    ).scalar_one()
    if row_count > 1:
        # Codex round 5: there is no authoritative ordering or merge rule for
        # conflicting duplicates, so the upgrade must not destructively keep
        # MIN(id) — the valid credential may live on a later row. Abort and
        # require manual reconciliation instead.
        raise RuntimeError(
            "telegram_configs contains "
            f"{row_count} rows; the singleton guard requires exactly one. "
            "Reconcile the conflicting configurations manually (keep the row "
            "holding the valid credential) before upgrading."
        )
    op.add_column(
        "telegram_configs",
        sa.Column("singleton_guard", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_unique_constraint(
        "uq_telegram_configs_singleton_guard",
        "telegram_configs",
        ["singleton_guard"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_telegram_configs_singleton_guard", "telegram_configs", type_="unique"
    )
    op.drop_column("telegram_configs", "singleton_guard")
