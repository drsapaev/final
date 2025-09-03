"""initial schema

Revision ID: 20250814_0001
Revises:
Create Date: 2025-08-14
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20250814_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="User"),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ux_users_username", "users", ["username"], unique=True)
    op.create_index("ux_users_email", "users", ["email"], unique=True)

    # patients
    op.create_table(
        "patients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("first_name", sa.String(length=120), nullable=True),
        sa.Column("last_name", sa.String(length=120), nullable=True),
        sa.Column("middle_name", sa.String(length=120), nullable=True),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(length=8), nullable=True),  # M/F/other
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("doc_type", sa.String(length=32), nullable=True),
        sa.Column("doc_number", sa.String(length=64), nullable=True),
        sa.Column("address", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_patients_phone", "patients", ["phone"], unique=False)
    op.create_index(
        "ix_patients_doc", "patients", ["doc_type", "doc_number"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_patients_doc", table_name="patients")
    op.drop_index("ix_patients_phone", table_name="patients")
    op.drop_table("patients")

    op.drop_index("ux_users_email", table_name="users")
    op.drop_index("ux_users_username", table_name="users")
    op.drop_table("users")
