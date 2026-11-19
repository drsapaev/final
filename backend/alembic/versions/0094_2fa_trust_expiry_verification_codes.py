"""Bound trusted-device lifetimes and persist one-time SMS/email codes."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0094_2fa_trust_expiry"
down_revision = "0093_display_board_devices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "two_factor_devices",
        sa.Column("trusted_until", sa.DateTime(timezone=True), nullable=True),
    )
    # Preserve existing trust only for a short migration window. No historical
    # device receives an indefinite grant after this revision.
    op.execute(
        sa.text(
            "UPDATE public.two_factor_devices "
            "SET trusted_until = CURRENT_TIMESTAMP + INTERVAL '30 days' "
            "WHERE trusted = TRUE AND trusted_until IS NULL"
        )
    )

    op.create_table(
        "two_factor_verification_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("contact_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "attempts_remaining",
            sa.Integer(),
            server_default="5",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "method IN ('sms', 'email')",
            name=op.f("ck_two_factor_verification_codes_method"),
        ),
        sa.CheckConstraint(
            "attempts_remaining BETWEEN 0 AND 5",
            name=op.f("ck_two_factor_verification_codes_attempts_remaining"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_two_factor_verification_codes")),
        sa.UniqueConstraint(
            "user_id",
            "method",
            name="uq_two_factor_verification_codes_user_method",
        ),
    )
    op.create_index(
        op.f("ix_two_factor_verification_codes_id"),
        "two_factor_verification_codes",
        ["id"],
        unique=False,
    )
    op.execute(
        sa.text(
            "ALTER TABLE public.two_factor_verification_codes "
            "ENABLE ROW LEVEL SECURITY"
        )
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_two_factor_verification_codes_id"),
        table_name="two_factor_verification_codes",
    )
    op.drop_table("two_factor_verification_codes")
    op.drop_column("two_factor_devices", "trusted_until")
