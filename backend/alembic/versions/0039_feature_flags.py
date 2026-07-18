"""PR-4: Create feature_flags + feature_flag_history tables.

Revision ID: 0039_feature_flags
Revises: 0038_user_fcm_fields
Create Date: 2026-07-10

The FeatureFlag / FeatureFlagHistory models existed in
app/models/feature_flags.py but were never registered in
app/models/__init__.py, so they were absent from Base.metadata
and Alembic never created the corresponding tables.

This blocked the CI "AI safety contract regression" job, which runs
``python -m app.scripts.seed_ai_feature_flags`` and aborts with
"Table 'feature_flags' does not exist. Run alembic upgrade head first."

This PR-4 commit also adds the missing imports to app/models/__init__.py
so the metadata stays in sync going forward.
"""
from alembic import op
import sqlalchemy as sa


revision = "0039_feature_flags"
down_revision = "0038_user_fcm_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(length=100), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=True, server_default="general"),
        sa.Column("environment", sa.String(length=20), nullable=True, server_default="all"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("updated_by", sa.String(length=100), nullable=True),
    )
    op.create_table(
        "feature_flag_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("flag_key", sa.String(length=100), nullable=False, index=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("changed_by", sa.String(length=100), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("feature_flag_history")
    op.drop_table("feature_flags")
