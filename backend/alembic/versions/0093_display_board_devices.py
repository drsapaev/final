"""Add revocable board-scoped credentials for public display devices."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0093_display_board_devices"
down_revision = "0092_price_override_visit_price"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "display_board_devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("board_id", sa.Integer(), nullable=False),
        sa.Column("device_name", sa.String(length=120), nullable=False),
        sa.Column("secret_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "credential_version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column("last_connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'revoked')",
            name=op.f("ck_display_board_devices_status"),
        ),
        sa.ForeignKeyConstraint(
            ["board_id"], ["display_boards.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_display_board_devices")),
    )
    op.create_index(
        op.f("ix_display_board_devices_board_id"),
        "display_board_devices",
        ["board_id"],
        unique=False,
    )
    op.execute(
        sa.text(
            "ALTER TABLE public.display_board_devices ENABLE ROW LEVEL SECURITY"
        )
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_display_board_devices_board_id"),
        table_name="display_board_devices",
    )
    op.drop_table("display_board_devices")
